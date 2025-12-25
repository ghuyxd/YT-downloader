import os
import subprocess
import shutil
import uuid
import yt_dlp
from .utils import sanitize_filename, get_ffmpeg_path, check_ffmpeg

CACHE_DIR = '.ytd-cache'

class VideoDownloader:
    def __init__(self):
        self.ffmpeg_path = get_ffmpeg_path()
    
    def check_executable_paths(self):
        """Check if ffmpeg is available in PATH. Returns list of missing executables."""
        missing = []
        if not shutil.which('ffmpeg'):
            missing.append('ffmpeg')
        return missing
    
    def _get_cache_dir(self, download_dir, session_id=None):
        """Get cache directory path inside download directory."""
        cache_path = os.path.join(download_dir, CACHE_DIR)
        if session_id:
            cache_path = os.path.join(cache_path, session_id)
        os.makedirs(cache_path, exist_ok=True)
        return cache_path
    
    def _cleanup_cache(self, cache_dir):
        """Remove cache directory and all its contents."""
        try:
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir, ignore_errors=True)
        except Exception:
            pass

    def get_video_info(self, url):
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': self.ffmpeg_path,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info
        except Exception:
            return None

    def get_quality_options(self, info):
        formats = info.get('formats', [])
        quality_options = {}
        for f in formats:
            height = f.get('height')
            has_video = f.get('vcodec') and f.get('vcodec') != 'none'
            has_audio = f.get('acodec') and f.get('acodec') != 'none'
            if has_video and height and height >= 144:
                quality_key = f"{height}p"
                if quality_key not in quality_options or (has_audio and not quality_options[quality_key].get('has_audio')):
                    quality_options[quality_key] = {
                        'format_id': f.get('format_id'),
                        'height': height,
                        'ext': f.get('ext', 'mp4'),
                        'has_audio': has_audio,
                        'fps': f.get('fps'),
                        'filesize': f.get('filesize', 0),
                        'vcodec': f.get('vcodec'),
                        'acodec': f.get('acodec')
                    }
        sorted_qualities = sorted(quality_options.items(), key=lambda x: x[1]['height'], reverse=True)
        return sorted_qualities

    def download_single_video(self, url, selected_format, target_format, title, download_dir="downloads", progress_hooks=None, channel=None, channel_id=None):
        if not download_dir:
            download_dir = "downloads"
        os.makedirs(download_dir, exist_ok=True)
        session_id = str(uuid.uuid4())
        cache_dir = self._get_cache_dir(download_dir, session_id)
        
        if channel and channel_id:
            title += f" - [{channel} - @{channel_id}]"
            
        safe_title = sanitize_filename(title)
        temp_video = os.path.join(cache_dir, f"temp_video_{safe_title}")
        temp_audio = os.path.join(cache_dir, f"temp_audio_{safe_title}")
        final_file = os.path.join(download_dir, f"{safe_title}.{target_format}")
        
        if os.path.exists(final_file):
            return True, "File already exists, skipping..."
        try:
            direct_success = self._try_direct_download(url, selected_format, target_format, final_file, cache_dir, progress_hooks)
            if direct_success:
                return True, "Downloaded successfully (direct)"
            if not check_ffmpeg():
                return False, "FFmpeg required for video+audio merge!"
            success = self._download_and_merge_video(url, selected_format, target_format,
                                                temp_video, temp_audio, final_file, progress_hooks)
            if success:
                return True, "Downloaded and merged successfully"
            else:
                return False, "Download/Merge failed"
        except Exception as e:
            return False, f"Download error: {str(e)}"

    def _try_direct_download(self, url, selected_format, target_format, output_file, cache_dir, progress_hooks=None):
        try:
            cache_output = os.path.join(cache_dir, os.path.basename(output_file))
            
            if selected_format:
                format_selector = f"best[height<={selected_format['height']}][acodec!=none]/best[height<={selected_format['height']}]/best"
            else:
                format_selector = "best[acodec!=none]/best"
            ydl_opts = {
                'format': format_selector,
                'outtmpl': cache_output.replace('.mp4', '.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'writeinfojson': False,
                'ffmpeg_location': self.ffmpeg_path,
            }
            if progress_hooks:
                ydl_opts['progress_hooks'] = progress_hooks

            if target_format.lower() != 'mp4':
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': target_format.lower(),
                }]
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Check for downloaded file in cache and move to destination
            possible_exts = [target_format, 'mp4', 'webm', 'mkv']
            for ext in possible_exts:
                cache_file = os.path.join(cache_dir, os.path.basename(output_file).replace(f'.{target_format}', f'.{ext}'))
                if os.path.exists(cache_file) and os.path.getsize(cache_file) > 1024:
                    shutil.move(cache_file, output_file)
                    self._cleanup_cache(cache_dir)
                    return True
            
            self._cleanup_cache(cache_dir)
            return False
        except Exception:
            return False

    def _download_and_merge_video(self, url, selected_format, target_format,
                                temp_video, temp_audio, final_file, progress_hooks=None):
        try:
            video_format = f"best[height<={selected_format['height']}][vcodec!=none]/best[vcodec!=none]" if selected_format else "best[vcodec!=none]"
            video_opts = {
                'format': video_format,
                'outtmpl': temp_video + '.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'ffmpeg_location': self.ffmpeg_path,
            }
            if progress_hooks:
                video_opts['progress_hooks'] = progress_hooks
            
            with yt_dlp.YoutubeDL(video_opts) as ydl:
                ydl.download([url])
            
            audio_opts = {
                'format': 'bestaudio/best',
                'outtmpl': temp_audio + '.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'ffmpeg_location': self.ffmpeg_path,
            }
            if progress_hooks:
                audio_opts['progress_hooks'] = progress_hooks

            with yt_dlp.YoutubeDL(audio_opts) as ydl:
                ydl.download([url])
            video_file = self._find_downloaded_file(temp_video)
            audio_file = self._find_downloaded_file(temp_audio)
            if not video_file or not audio_file:
                return False
            success = self._merge_files(video_file, audio_file, final_file)
            try:
                if os.path.exists(video_file):
                    os.remove(video_file)
                if os.path.exists(audio_file):
                    os.remove(audio_file)
                # Clean up cache directory
                cache_dir = os.path.dirname(video_file)
                self._cleanup_cache(cache_dir)
            except:
                pass
            return success
        except Exception:
            return False

    def _find_downloaded_file(self, base_path):
        for ext in ['mp4', 'webm', 'mkv', 'm4a', 'mp3', 'wav']:
            file_path = f"{base_path}.{ext}"
            if os.path.exists(file_path):
                return file_path
        return None

    def _merge_files(self, video_file, audio_file, output_file):
        try:
            cmd = [
                self.ffmpeg_path,
                '-i', video_file,
                '-i', audio_file,
                '-c:v', 'copy',
                '-c:a', 'aac', 
                '-y', 
                output_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and os.path.exists(output_file):
                return True
                
            cmd_copy = [
                self.ffmpeg_path,
                '-i', video_file,
                '-i', audio_file,
                '-c', 'copy',
                '-y', 
                output_file
            ]
            result = subprocess.run(cmd_copy, capture_output=True, text=True)
            return result.returncode == 0 and os.path.exists(output_file)

        except Exception:
            return False

    def download_single_audio(self, url, target_format, title, download_dir="downloads", progress_hooks=None, channel=None, channel_id=None):
        if not download_dir:
            download_dir = "downloads"
        os.makedirs(download_dir, exist_ok=True)
        session_id = str(uuid.uuid4())
        cache_dir = self._get_cache_dir(download_dir, session_id)
        
        if channel and channel_id:
            title += f" - [{channel} - @{channel_id}]"
            
        safe_title = sanitize_filename(title)
        final_file = os.path.join(download_dir, f"{safe_title}.{target_format}")
        
        if os.path.exists(final_file):
            return True, "File already exists, skipping..."
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(cache_dir, f'{safe_title}.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': target_format.lower(),
                    'preferredquality': '320',
                }],
                'quiet': True,
                'no_warnings': True,
                'ffmpeg_location': self.ffmpeg_path,
            }
            if progress_hooks:
                ydl_opts['progress_hooks'] = progress_hooks
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Check for file in cache and move to destination
            cache_file = os.path.join(cache_dir, f"{safe_title}.{target_format}")
            if os.path.exists(cache_file) and os.path.getsize(cache_file) > 1024:
                shutil.move(cache_file, final_file)
                self._cleanup_cache(cache_dir)
                return True, "Audio downloaded successfully"
            else:
                for ext in ['mp3', 'm4a', 'wav', 'flac']:
                    alt_file = os.path.join(cache_dir, f"{safe_title}.{ext}")
                    if os.path.exists(alt_file):
                        shutil.move(alt_file, final_file)
                        self._cleanup_cache(cache_dir)
                        return True, "Audio downloaded successfully (converted)"
                self._cleanup_cache(cache_dir)
                return False, "Audio download failed"
        except Exception as e:
            self._cleanup_cache(cache_dir)
            return False, f"Audio download error: {str(e)}"
