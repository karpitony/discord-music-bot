import os
import time
import asyncio
import discord
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
            print("[play_song] 대기열이 비어 있습니다.")
            self.current_player = None
            return

        title, url, filename = self.song_queue.pop(0)
        try:
            player = discord.FFmpegPCMAudio(filename)
            voice_client.play(
                player,
                after=lambda _: asyncio.run_coroutine_threadsafe(
                    self.handle_after_play(voice_client, filename), self.bot.loop
                ).result(),
            )
            self.current_player = player
            print(f"[play_song] Now playing: {title}")
        except Exception as e:
            print(f"[play_song] Error playing song: {e}")
            await self.play_next(voice_client)

    async def play_next(self, voice_client):
        """대기열에서 다음 곡 재생"""
         # 현재 곡 정리
        # if self.current_player:
        #     self.current_player.cleanup()
        #     self.current_player = None

        # 다음 곡 재생
        if self.song_queue:
            next_song = self.song_queue.pop(0)
            title, url, filename = next_song
            print(f"[play_next] Playing next song: {title}")
            try:
                player = discord.FFmpegPCMAudio(filename)
                voice_client.play(
                    player,
                    after=lambda _: asyncio.run_coroutine_threadsafe(
                        self.handle_after_play(voice_client, filename), self.bot.loop
                    ).result(),
                )
                self.current_player = player
            except Exception as e:
                print(f"[play_next] Error playing next song: {e}")
                await self.play_next(voice_client)
        else:
            print("[play_next] 대기열이 비어 있습니다.")
            
    async def handle_after_play(self, voice_client, filename):
        """곡 재생 후 처리"""
        try:
            print("[handle_after_play] is called")
            await asyncio.sleep(1)  # FFmpeg가 파일을 해제할 시간을 확보
            self.cleanup_file(filename)
            print(f"Deleted file after play: {filename}")
        except Exception as e:
            print(f"Error deleting file after play: {e}")

        # 다음 곡 재생
        await self.play_next(voice_client)

    def cleanup_file(self, filename):
        """곡 파일 삭제"""
        if filename and os.path.exists(filename):
            for attempt in range(5):
                try:
                    time.sleep(0.5)  # FFmpeg가 파일을 해제할 시간을 줌
                    os.remove(filename)
                    print(f"[cleanup_file] Deleted file: {filename}")
                    self.current_player = None
                    break
                except PermissionError:
                    print(f"[Attempt {attempt+1}] File {filename} is in use. Retrying...")
                    time.sleep(1)
            else:
                print(f"[cleanup_file] Failed to delete file: {filename}. Possible reasons: File in use, insufficient permissions.")