import asyncio
from discord.ext import commands
from .music_download import YTDLSource

# Music Cog
class MusicPlayer(commands.Cog):
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