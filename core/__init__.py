from .utils import sanitize_filename, detect_url_type, check_ffmpeg, get_ffmpeg_path, get_script_dir
from .downloader import VideoDownloader
from .playlist import PlaylistExtractor

class YouTubeDownloaderCore:
    def __init__(self):
        self.video_formats = ['MP4', 'MKV']
        self.audio_formats = ['MP3', 'M4A', 'WAV']
        self._downloader = VideoDownloader()
        self._playlist = PlaylistExtractor()
    
    def check_executable_paths(self):
        return self._downloader.check_executable_paths()
    
    def check_ffmpeg(self):
        return check_ffmpeg()
    
    def sanitize_filename(self, filename):
        return sanitize_filename(filename)
    
    def detect_url_type(self, url):
        return detect_url_type(url)
    
    def get_video_info(self, url):
        return self._downloader.get_video_info(url)
    
    def get_quality_options(self, info):
        return self._downloader.get_quality_options(info)
    
    def download_single_video(self, url, selected_format, target_format, title, download_dir="downloads", progress_hooks=None, channel=None, channel_id=None):
        return self._downloader.download_single_video(url, selected_format, target_format, title, download_dir, progress_hooks, channel, channel_id)
    
    def download_single_audio(self, url, target_format, title, download_dir="downloads", progress_hooks=None, channel=None, channel_id=None):
        return self._downloader.download_single_audio(url, target_format, title, download_dir, progress_hooks, channel, channel_id)
    
    def get_playlist_info(self, url, limit=None):
        return self._playlist.get_playlist_info(url, limit)
    
    def construct_video_url(self, entry):
        return self._playlist.construct_video_url(entry)
