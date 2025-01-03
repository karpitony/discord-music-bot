import discord
import asyncio
from discord.ext import commands
from discord import app_commands
from services import MusicPlayer

# MusicCommands Cog
class MusicCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, music_cog: MusicPlayer):
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
            title = await self.music_cog.queue_song(url)  # 대기열에 추가
        except Exception as e:
            await interaction.followup.send(f"노래를 추가하는 중 오류가 발생했습니다: {e}")
            return

        if not voice_client.is_playing() and not self.music_cog.current_player:
            await self.music_cog.play_song(voice_client)  # 곡 재생
            await interaction.followup.send(f"Now playing: {title}")
        else:
            await interaction.followup.send(f"대기열에 추가되었습니다: {title}")

    @app_commands.command(name="skip", description="현재 재생 중인 곡을 건너뜁니다.")
    async def skip(self, interaction: discord.Interaction):
        """현재 곡 건너뛰기"""
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_playing():
            await interaction.response.send_message("현재 재생 중인 곡이 없습니다.")
            return

        await interaction.response.send_message("현재 곡을 건너뛰고 있습니다...")
        voice_client.stop()  # 현재 곡 중지

        # 다음 곡 재생
        # await self.music_cog.play_next(voice_client)
        await interaction.followup.send("곡을 건너뛰었습니다.")

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
    music_cog = MusicPlayer(bot)
    await bot.add_cog(music_cog)
    await bot.add_cog(MusicCommands(bot, music_cog))
