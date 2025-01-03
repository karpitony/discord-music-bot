import os
import time
import asyncio
import discord
import yt_dlp as youtube_dl

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