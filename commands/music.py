import os
import asyncio
import discord
import yt_dlp as youtube_dl
from discord import app_commands
from discord.ext import commands

# YouTube 다운로드 및 재생을 위한 설정
youtube_dl.utils.bug_reports_message = lambda: ''
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'retries': 5,  # 자동 재시도 설정
}

# 스트리밍 옵션 (스트리밍 시 필요한 옵션)
ffmpeg_stream_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

# 파일 재생 옵션 (로컬 파일 재생 시)
ffmpeg_file_options = {
    'options': '-vn',
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

# YTDLSource 클래스: 음악 재생 및 파일 관리
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5, filename=None):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.filename = filename  # 파일 경로 저장

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False, ffmpeg_options=None):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        except Exception as e:
            print(f"Error extracting URL info: {e}")
            raise

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)

        # ffmpeg_options를 사용하여 FFmpegPCMAudio 호출
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, filename=None if stream else filename)
    
    # 파일 삭제 메서드
    def cleanup(self):
        if self.filename:
            try:
                os.remove(self.filename)
                print(f"Deleted file: {self.filename}")
            except Exception as e:
                print(f"Error deleting file {self.filename}: {e}")

# 핵심 기능 함수
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.song_queue = []  # 대기열 저장
        self.current_player = None  # 현재 재생 중인 플레이어

    async def play_next(self, voice_client):
        """대기열에서 다음 곡을 재생하는 함수"""
        if self.song_queue:
            next_song = self.song_queue.pop(0)
            voice_client.play(next_song, after=lambda e: self.play_next(voice_client))

    async def play_with_retries(self, interaction, url, stream=False, max_retries=3):
        """오류 발생 시 자동 재시도를 수행하는 재생 함수"""
        retries = 0
        voice_client = interaction.guild.voice_client

        if voice_client.is_playing():
            await interaction.followup.send("현재 오디오가 재생 중입니다. 재생이 끝난 후 다시 시도하세요.")
            return

        while retries < max_retries:
            try:
                # stream 여부에 따라 ffmpeg 옵션을 선택
                ffmpeg_options = ffmpeg_stream_options if stream else ffmpeg_file_options
                
                # 선택한 ffmpeg_options를 from_url에 전달
                player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=stream, ffmpeg_options=ffmpeg_options)

                if not stream and player.filename:
                    print(f"Playing from downloaded file: {player.filename}")
                    voice_client.play(discord.FFmpegPCMAudio(player.filename, **ffmpeg_options), 
                                    after=lambda e: self._after_playback_cleanup(e))
                else:
                    voice_client.play(discord.FFmpegPCMAudio(player.filename, **ffmpeg_options), 
                                    after=lambda e: self._after_playback_cleanup(e))
                
                self.current_player = player
                await interaction.followup.send(f"Now playing: {player.title}")
                return
            except Exception as e:
                retries += 1
                print(f"Error playing {url}: {e}. Retrying ({retries}/{max_retries})...")
                await asyncio.sleep(3)

        await interaction.followup.send("스트리밍 중 오류가 발생했고, 최대 재시도 횟수를 초과했습니다.")

    def _after_playback_cleanup(self, error):
        """재생 후 파일을 정리하는 함수"""
        if error:
            print(f"Player error: {error}")
        if self.current_player:
            self.current_player.cleanup()
        self.current_player = None

# 명령어 (Command) 부분
class MusicCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, music_cog: Music):
        self.bot = bot
        self.music_cog = music_cog

    @app_commands.command(name="join", description="봇을 음성 채널에 연결합니다.")
    async def join(self, interaction: discord.Interaction):
        """봇이 음성 채널에 연결하는 명령어"""
        if interaction.user.voice is None:
            await interaction.response.send_message("먼저 음성 채널에 들어가 주세요.")
            return

        channel = interaction.user.voice.channel
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.move_to(channel)
        else:
            await channel.connect()

        await interaction.response.send_message(f"봇이 {channel.name}에 연결되었습니다.")

    @app_commands.command(name="yt", description="YouTube URL에서 음악을 재생합니다.")
    async def yt(self, interaction: discord.Interaction, url: str):
        """YouTube URL에서 음악을 재생하는 명령어"""
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            channel = interaction.user.voice.channel
            await channel.connect()
            voice_client = interaction.guild.voice_client

        await interaction.response.defer()
        await self.music_cog.play_with_retries(interaction, url)

    @app_commands.command(name="stream", description="YouTube URL에서 스트리밍을 재생합니다.")
    async def stream(self, interaction: discord.Interaction, url: str):
        """YouTube 스트리밍 명령어"""
        if interaction.user.voice is None:
            await interaction.response.send_message("먼저 음성 채널에 들어가 주세요.")
            return

        voice_client = interaction.guild.voice_client
        if voice_client is None:
            channel = interaction.user.voice.channel
            await channel.connect()
            voice_client = interaction.guild.voice_client

        await interaction.response.defer()
        await self.music_cog.play_with_retries(interaction, url, stream=True)

    @app_commands.command(name="skip", description="현재 재생 중인 곡을 건너뜁니다.")
    async def skip(self, interaction: discord.Interaction):
        """현재 재생 중인 곡을 건너뛰는 명령어"""
        voice_client = interaction.guild.voice_client
        if voice_client is None or not voice_client.is_playing():
            await interaction.response.send_message("현재 재생 중인 곡이 없습니다.")
            return

        voice_client.stop()
        await interaction.response.send_message("노래를 건너뛰었습니다.")

    @app_commands.command(name="playlist", description="현재 대기열을 보여줍니다.")
    async def playlist(self, interaction: discord.Interaction):
        """대기열에 있는 노래 목록을 보여주는 명령어"""
        if not self.music_cog.song_queue:
            await interaction.response.send_message("대기열에 노래가 없습니다.")
        else:
            playlist_str = "\n".join(f"{idx + 1}. {song.title}" for idx, song in enumerate(self.music_cog.song_queue))
            await interaction.response.send_message(f"현재 대기열:\n{playlist_str}")

    @app_commands.command(name="stop", description="현재 재생 중인 노래를 멈춥니다.")
    async def stop(self, interaction: discord.Interaction):
        """현재 재생 중인 노래를 멈추는 명령어"""
        voice_client = interaction.guild.voice_client
        if voice_client is None or not voice_client.is_playing():
            await interaction.response.send_message("현재 재생 중인 곡이 없습니다.")
            return

        self.music_cog.current_player.cleanup()
        voice_client.stop()
        await interaction.response.send_message("노래를 멈췄습니다.")

    @app_commands.command(name="quit", description="봇이 음성 채널에서 나가고 대기열을 정리합니다.")
    async def quit(self, interaction: discord.Interaction):
        """봇이 음성 채널에서 나가고 대기열을 정리하는 명령어"""
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            await interaction.response.send_message("봇이 음성 채널에 연결되지 않았습니다.")
            return

        if self.music_cog.current_player:
            self.music_cog.current_player.cleanup()

        await voice_client.disconnect()
        self.music_cog.song_queue.clear()
        await interaction.response.send_message("봇이 음성 채널에서 나갔고 대기열이 정리되었습니다.")

# Cog 설정
async def setup(bot: commands.Bot):
    music_cog = Music(bot)
    await bot.add_cog(music_cog)
    await bot.add_cog(MusicCommands(bot, music_cog))
