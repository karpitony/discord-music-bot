import os
import time
import asyncio
import discord
import yt_dlp as youtube_dl
from discord.ext import commands
from discord import app_commands

# YouTube 다운로드 및 재생 설정
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
    'retries': 5,
}
ffmpeg_options = {'options': '-vn'}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

# 유틸리티 함수
def is_file_in_use(filepath):
    """파일이 점유 중인지 확인"""
    try:
        with open(filepath, 'r+'):
            return False  # 파일이 점유되지 않음
    except IOError:
        return True  # 파일이 점유 중

# YTDLSource 클래스
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5, filename=None):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.filename = filename

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        """YouTube URL에서 파일을 다운로드"""
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        except Exception as e:
            print(f"Error extracting URL info: {e}")
            raise

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        source = discord.FFmpegPCMAudio(filename, **ffmpeg_options)
        return cls(source, data=data, filename=filename)

    def cleanup(self):
        """파일 삭제"""
        if self.filename:
            # FFmpeg 프로세스가 존재하면 종료 시도
            try:
                if hasattr(self, '_process'):
                    ffmpeg_process = self._process
                    if ffmpeg_process and ffmpeg_process.poll() is None:
                        print("Terminating FFmpeg process...")
                        ffmpeg_process.terminate()
                        ffmpeg_process.wait(timeout=5)  # 최대 5초 대기
                        print("FFmpeg process terminated successfully.")
            except Exception as e:
                print(f"Error terminating FFmpeg process: {e}")

            # 파일 삭제 시도
            for attempt in range(5):
                if not is_file_in_use(self.filename):
                    try:
                        os.remove(self.filename)
                        print(f"Deleted file: {self.filename}")
                        break
                    except Exception as e:
                        print(f"Failed to delete file {self.filename}: {e}")
                else:
                    print(f"File {self.filename} is in use. Retrying ({attempt + 1}/5)...")
                    time.sleep(2)
            else:
                print(f"Failed to delete file after retries: {self.filename}")

# Music Cog
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.song_queue = []  # [(title, url)]
        self.current_player = None

    async def play_next(self, voice_client):
        """대기열에서 다음 곡 재생"""
        if self.current_player:
            voice_client.stop()
            self.cleanup_player()

        if self.song_queue:
            next_song = self.song_queue.pop(0)
            await self.play_song(voice_client, next_song[1])
        else:
            self.current_player = None

    async def play_song(self, voice_client, url):
        """곡 다운로드 및 재생"""
        try:
            player = await YTDLSource.from_url(url, loop=self.bot.loop)
            voice_client.play(
                player,  # YTDLSource 객체 직접 전달
                after=lambda _: asyncio.run_coroutine_threadsafe(self.play_next(voice_client), self.bot.loop),
            )
            self.current_player = player
            print(f"Now playing: {player.title}")
            return player
        except Exception as e:
            print(f"Error playing song: {e}")
            raise

    def cleanup_player(self):
        """현재 플레이어 정리"""
        if self.current_player:
            try:
                self.current_player.cleanup()
            except Exception as e:
                print(f"Error during cleanup: {e}")
            finally:
                self.current_player = None

# MusicCommands Cog
class MusicCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, music_cog: Music):
        self.bot = bot
        self.music_cog = music_cog

    @app_commands.command(name="join", description="봇을 음성 채널에 연결합니다.")
    async def join(self, interaction: discord.Interaction):
        """봇 음성 채널 연결"""
        if not interaction.user.voice:
            await interaction.response.send_message("먼저 음성 채널에 들어가세요.")
            return

        channel = interaction.user.voice.channel
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.move_to(channel)
        else:
            await channel.connect()

        await interaction.response.send_message(f"{channel.name} 채널에 연결되었습니다.")

    @app_commands.command(name="yt", description="YouTube URL에서 음악을 재생합니다.")
    async def yt(self, interaction: discord.Interaction, url: str):
        """YouTube 음악 재생"""
        voice_client = interaction.guild.voice_client
        if not voice_client:
            channel = interaction.user.voice.channel
            await channel.connect()
            voice_client = interaction.guild.voice_client

        await interaction.response.defer()

        try:
            player = await YTDLSource.from_url(url, loop=self.bot.loop)
        except Exception as e:
            await interaction.followup.send(f"노래를 다운로드하는 중 오류가 발생했습니다: {e}")
            return

        if voice_client.is_playing():
            self.music_cog.song_queue.append((player.title, url))
            await interaction.followup.send(f"대기열에 추가되었습니다: {player.title}")
        else:
            await self.music_cog.play_song(voice_client, url)
            await interaction.followup.send(f"Now playing: {player.title}")

    @app_commands.command(name="skip", description="현재 곡 건너뛰기")
    async def skip(self, interaction: discord.Interaction):
        """현재 곡 건너뛰기"""
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_playing():
            await interaction.response.send_message("현재 재생 중인 곡이 없습니다.")
            return
        
        voice_client.stop()
        self.music_cog.cleanup_player()
        await interaction.response.send_message("현재 곡을 건너뛰었습니다.")

    @app_commands.command(name="playlist", description="대기열 표시")
    async def playlist(self, interaction: discord.Interaction):
        """대기열 표시"""
        if not self.music_cog.song_queue:
            await interaction.response.send_message("대기열에 곡이 없습니다.")
        else:
            playlist = "\n".join(f"{idx + 1}. {song[0]}" for idx, song in enumerate(self.music_cog.song_queue))
            await interaction.response.send_message(f"대기열:\n{playlist}")

    @app_commands.command(name="quit", description="봇이 음성 채널에서 나갑니다.")
    async def quit(self, interaction: discord.Interaction):
        """봇 음성 채널 나가기"""
        voice_client = interaction.guild.voice_client
        if not voice_client:
            await interaction.response.send_message("봇이 음성 채널에 연결되어 있지 않습니다.")
            return

        self.music_cog.cleanup_player()
        await voice_client.disconnect()
        self.music_cog.song_queue.clear()
        await interaction.response.send_message("봇이 음성 채널에서 나갔습니다.")

# Cog 등록
async def setup(bot: commands.Bot):
    music_cog = Music(bot)
    await bot.add_cog(music_cog)
    await bot.add_cog(MusicCommands(bot, music_cog))
