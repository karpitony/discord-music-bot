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
            self.cleanup_player()  # 이전 곡 정리
            self.current_player = None  # 명시적으로 초기화

        if self.song_queue:
            next_song = self.song_queue.pop(0)
            await self.play_song(voice_client, next_song[1])
        else:
            print("대기열이 비어 있습니다.")

    async def queue_song(self, url):
        """노래를 대기열에 추가"""
        try:
            player = await YTDLSource.from_url(url, loop=self.bot.loop)
            self.song_queue.append((player.title, url))
            return player.title
        except Exception as e:
            print(f"Error queuing song: {e}")
            raise

    async def play_song(self, voice_client):
        """대기열에서 곡 재생"""
        if not self.song_queue:
            self.current_player = None
            return

        title, url = self.song_queue.pop(0)
        try:
            player = await YTDLSource.from_url(url, loop=self.bot.loop)
            voice_client.play(
                player,
                after=lambda _: asyncio.run_coroutine_threadsafe(self.play_next(voice_client), self.bot.loop).result(),
            )
            self.current_player = player
            print(f"Now playing: {title}")
        except Exception as e:
            print(f"Error playing song: {e}")
            await self.play_next(voice_client)

    def cleanup_player(self):
        """현재 플레이어 정리"""
        if self.current_player:
            print(f"Cleaning up player: {self.current_player.filename}")
            try:
                self.current_player.cleanup()
            except Exception as e:
                print(f"Error during cleanup: {e}")
                