import os
import time
import asyncio
import discord
import subprocess
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
            print(f"[queue_song] Error queuing song: {e}")
            raise

    async def play_song(self, voice_client):
        """대기열에서 곡 재생"""
        if not self.song_queue:
            print("[play_song] 대기열이 비어 있습니다.")
            self.current_player = None
            return

        title, url, filename = self.song_queue.pop(0)
        try:
            player = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(filename))
            voice_client.play(
                player,
                after=lambda e: self.bot.loop.create_task(
                    self.handle_after_play(voice_client, filename)
                ) if not e else print(f"[play_song] Player error: {e}"),
                # after=lambda _: asyncio.run_coroutine_threadsafe(
                #     self.handle_after_play(voice_client, filename),
                #     self.bot.loop
                # ).result(),
            )
            self.current_player = player
            print(f"[play_song] Now playing: {title}")
        except Exception as e:
            print(f"[play_song] Error playing song: {e}")
            await self.play_next(voice_client)

    async def play_next(self, voice_client):
        """대기열에서 다음 곡 재생"""

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
            
    def skip_song(self, voice_client):
        """현재 곡을 건너뜁니다."""
        if voice_client.is_playing() or voice_client.is_paused():
            print("[skip_song] Stopping current song...")
            if voice_client.source and hasattr(voice_client.source, 'process'):
                process = voice_client.source.process
                if process.poll() is None:  # FFmpeg 프로세스가 실행 중
                    print("[terminate_ffmpeg] Terminating FFmpeg process...")
                    process.terminate()
                    try:
                        process.wait(timeout=5)  # 최대 5초 대기
                        print("[terminate_ffmpeg] FFmpeg process terminated.")
                    except subprocess.TimeoutExpired:
                        print("[terminate_ffmpeg] FFmpeg process termination timed out.")
                        process.kill()  
            voice_client.stop()  # 재생 중지

            
    async def handle_after_play(self, voice_client, filename):
        """곡 재생 후 처리"""
        await self.play_next(voice_client)
        
        try:
            print("[handle_after_play] is called")
            await asyncio.sleep(5)  # FFmpeg가 파일을 해제할 시간을 확보
            self.cleanup_file(filename)
            print(f"[handle_after_play] Deleted file after play: {filename}")
        except Exception as e:
            print(f"[handle_after_play] Error deleting file after play: {e}") 

    def cleanup_file(self,  filename):
        """곡 파일 삭제"""
        if filename and os.path.exists(filename):
            for attempt in range(5):
                try:
                    time.sleep(1)  # 대기 시간
                    os.remove(filename)
                    print(f"[cleanup_file] Deleted file: {filename}")
                    break
                except PermissionError as e:
                    print(f"PermissionError: {e}")
                    print(f"[cleanup_file] Attempt {attempt+1} File {filename} is in use. Retrying...")
            else:
                # 마지막으로 한 번 더 삭제 시도
                try:
                    os.remove(filename)
                    print(f"[cleanup_file] Deleted file on final attempt: {filename}")
                except Exception as e:
                    error_msg = f"Failed to delete file: {filename}. File in use or insufficient permissions."
                    print(f"[cleanup_file] {error_msg}")
                    raise e