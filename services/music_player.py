import asyncio
from discord.ext import commands
from .music_download import YTDLSource

# Music Cog
class MusicPlayer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.song_queue = []  # [(title, url, filename)]
        self.current_player = None

    async def queue_song(self, url):
        """노래를 대기열에 추가"""
        try:
            # 새로 다운로드
            player = await YTDLSource.from_url(url, loop=self.bot.loop)
            self.song_queue.append((player.title, url, player.filename))
            return player.title
        except Exception as e:
            print(f"Error queuing song: {e}")
            raise

    async def play_song(self, voice_client):
        """대기열에서 곡 재생"""
        if not self.song_queue:
            self.current_player = None
            return

        title, url, filename = self.song_queue.pop(0)
        try:
            player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=False)
            voice_client.play(
                player,
                after=lambda _: asyncio.run_coroutine_threadsafe(self.play_next(voice_client), self.bot.loop).result(),
            )
            self.current_player = player
            print(f"Now playing: {title}")
        except Exception as e:
            print(f"Error playing song: {e}")
            await self.play_next(voice_client)

    async def play_next(self, voice_client):
        """대기열에서 다음 곡 재생"""
        if self.current_player:
            self.cleanup_player()

        if self.song_queue:
            next_song = self.song_queue.pop(0)
            title, url, filename = next_song
            print(f"Playing next song: {title}")
            try:
                player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=False)
                voice_client.play(
                    player,
                    after=lambda _: asyncio.run_coroutine_threadsafe(self.play_next(voice_client), self.bot.loop).result(),
                )
                self.current_player = player
            except Exception as e:
                print(f"Error playing next song: {e}")
                await self.play_next(voice_client)
        else:
            print("대기열이 비어 있습니다.")

    def cleanup_player(self):
        """현재 플레이어 정리"""
        if self.current_player:
            print(f"Cleaning up player: {self.current_player.filename}")
            try:
                self.current_player.cleanup()
            except Exception as e:
                print(f"Error during cleanup: {e}")
            finally:
                self.current_player = None
