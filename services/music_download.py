import os
import time
import asyncio
import discord
from yt_dlp import YoutubeDL

if not os.path.exists('music'):
    os.makedirs('music')

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': 'music/%(extractor)s-%(id)s-%(title)s-%(epoch)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
}
ffmpeg_options = {
    'options': '-vn -loglevel debug'
}

ytdl = YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5, filename=None):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.filename = filename

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        except Exception as e:
            print(f"Error extracting URL info: {e}")
            raise

        if 'entries' in data:
            data = data['entries'][0]


        filename = ytdl.prepare_filename(data)
        if os.path.exists(filename):
            print(f"File already exists and will be reused: {filename}")
        else:
            print(f"Downloading new file: {filename}")
        source = discord.FFmpegPCMAudio(filename, **ffmpeg_options)
        return cls(source, data=data, filename=filename)