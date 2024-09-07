import os
import asyncio
import discord
import yt_dlp as youtube_dl
from discord import app_commands
from discord.ext import commands

# Suppress noise about console usage from errors
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
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
    'retries': 5,
}

ffmpeg_options = {
    'options': '-vn',
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5, filename=None):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.filename = filename  # 파일 경로 저장

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, filename=None if stream else filename)

    # 파일 삭제 메서드
    def cleanup(self):
        if self.filename:  # 파일이 다운로드된 경우에만
            try:
                os.remove(self.filename)
                print(f"Deleted file: {self.filename}")
            except Exception as e:
                print(f"Error deleting file {self.filename}: {e}")


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.song_queue = []  # 대기열을 저장하는 리스트
        self.current_player = None  # 현재 재생 중인 플레이어 객체

    @app_commands.command(name="join", description="봇을 사용자가 있는 음성 채널에 연결합니다.")
    async def join(self, interaction: discord.Interaction):
        """사용자가 있는 음성 채널에 봇이 연결하는 슬래시 명령어"""
        if interaction.user.voice is None:
            await interaction.response.send_message("먼저 음성 채널에 들어가 주세요.")
            return

        channel = interaction.user.voice.channel

        if interaction.guild.voice_client is not None:
            await interaction.guild.voice_client.move_to(channel)
        else:
            await channel.connect()

        await interaction.response.send_message(f"봇이 {channel.name}에 연결되었습니다.")

    @app_commands.command(name="yt", description="YouTube URL에서 음악을 재생합니다.")
    async def yt(self, interaction: discord.Interaction, url: str):
        """YouTube URL에서 음악을 재생하는 슬래시 명령어"""
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            channel = interaction.user.voice.channel
            await channel.connect()
            voice_client = interaction.guild.voice_client

        await interaction.response.defer()

        async with interaction.channel.typing():
            try:
                player = await YTDLSource.from_url(url, loop=self.bot.loop)
                self.current_player = player  # 현재 재생 중인 플레이어 설정
                voice_client.play(player, after=lambda e: self._after_playback_cleanup(e))
                await interaction.followup.send(f"Now playing: {player.title}")
            except Exception as e:
                await interaction.followup.send(f"Error: {str(e)}")

    @app_commands.command(name="stream", description="YouTube URL에서 스트리밍을 재생합니다.")
    async def stream(self, interaction: discord.Interaction, url: str):
        """YouTube에서 스트리밍으로 음악을 재생하는 슬래시 명령어"""
        # 사용자가 음성 채널에 있는지 확인
        if interaction.user.voice is None:
            await interaction.response.send_message("먼저 음성 채널에 들어가 주세요.")
            return

        # 봇이 음성 채널에 연결되어 있지 않으면 사용자가 있는 채널로 연결
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            channel = interaction.user.voice.channel
            await channel.connect()
            voice_client = interaction.guild.voice_client

        # 응답을 미리 예약
        await interaction.response.defer()

        async with interaction.channel.typing():
            try:
                player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
                self.current_player = player  # 현재 재생 중인 플레이어 설정
                voice_client.play(player, after=lambda e: self._after_playback_cleanup(e))
                await interaction.followup.send(f"Now playing: {player.title}")
            except Exception as e:
                await interaction.followup.send(f"Error: {str(e)}")

    # 대기열 및 플레이어 종료 후 파일 삭제 처리
    def _after_playback_cleanup(self, error):
        if error:
            print(f"Player error: {error}")
        if self.current_player:
            self.current_player.cleanup()  # 파일 삭제
        self.current_player = None

    @app_commands.command(name="playlist", description="현재 대기열을 보여줍니다.")
    async def playlist(self, interaction: discord.Interaction):
        """대기열에 있는 노래 목록을 보여주는 명령어"""
        if not self.song_queue:
            await interaction.response.send_message("대기열에 노래가 없습니다.")
        else:
            playlist_str = "\n".join(f"{idx + 1}. {song}" for idx, song in enumerate(self.song_queue))
            await interaction.response.send_message(f"현재 대기열:\n{playlist_str}")

    @app_commands.command(name="stop", description="현재 재생 중인 노래를 멈춥니다.")
    async def stop(self, interaction: discord.Interaction):
        """현재 재생 중인 노래를 멈추는 슬래시 명령어"""
        voice_client = interaction.guild.voice_client
        if voice_client is None or not voice_client.is_playing():
            await interaction.response.send_message("현재 재생 중인 노래가 없습니다.")
            return

        if self.current_player:
            self.current_player.cleanup()  # 파일 삭제
        voice_client.stop()
        self.current_player = None
        await interaction.response.send_message("현재 재생 중인 노래를 멈췄습니다.")

    @app_commands.command(name="skip", description="현재 재생 중인 노래를 건너뜁니다.")
    async def skip(self, interaction: discord.Interaction):
        """현재 재생 중인 노래를 건너뛰는 슬래시 명령어"""
        voice_client = interaction.guild.voice_client
        if voice_client is None or not voice_client.is_playing():
            await interaction.response.send_message("현재 재생 중인 노래가 없습니다.")
            return

        # 현재 노래를 건너뛰고, 대기열의 다음 노래를 재생
        if self.current_player:
            self.current_player.cleanup()  # 파일 삭제
        voice_client.stop()  # 현재 노래 중단
        self.current_player = None

        if self.song_queue:
            next_song_title = self.song_queue.pop(0)
            await interaction.response.send_message(f"다음 노래: {next_song_title} 재생 중입니다.")
            # 다음 노래 재생 로직 추가 가능
        else:
            await interaction.response.send_message("대기열에 더 이상 노래가 없습니다.")

    @app_commands.command(name="quit", description="봇이 음성 채널에서 나가고 대기열을 비웁니다.")
    async def quit(self, interaction: discord.Interaction):
        """봇이 음성 채널에서 나가게 하는 슬래시 명령어"""
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            await interaction.response.send_message("봇이 음성 채널에 연결되지 않았습니다.")
            return

        if self.current_player:
            self.current_player.cleanup()  # 파일 삭제
        await voice_client.disconnect()
        self.song_queue.clear()  # 대기열을 정리
        await interaction.response.send_message("봇이 음성 채널에서 나갔고 대기열이 비워졌습니다.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
