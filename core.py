import os
import subprocess
import re
import yt_dlp

class YouTubeDownloaderCore:
    def __init__(self):
        self.video_formats = ['MP4', 'MKV']
        self.audio_formats = ['MP3', 'M4A', 'WAV']
        
        # Determine paths for local executables
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.ffmpeg_path = os.path.join(self.script_dir, 'ffmpeg.exe')


    def check_executable_paths(self):
        """Verify that local executables exist. Returns list of missing files."""
        missing = []
        if not os.path.exists(self.ffmpeg_path):
            missing.append('ffmpeg.exe')

        return missing

    def check_ffmpeg(self):
        if not os.path.exists(self.ffmpeg_path):
            return False
        try:
            subprocess.run([self.ffmpeg_path, '-version'], capture_output=True, check=True)
            return True
        except Exception:
            return False

    def sanitize_filename(self, filename):
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
        filename = filename.strip('. ')
        return filename[:200]

    def detect_url_type(self, url):
        if any(x in url.lower() for x in ['playlist', 'list=', '&list=']):
            return 'playlist'
        elif any(x in url.lower() for x in ['watch?v=', 'youtu.be/', '/watch/']):
            return 'video'
        elif any(x in url.lower() for x in ['channel/', '/c/', '/@']):
            return 'channel'
        else:
            try:
                opts = {'quiet': True, 'no_warnings': True}
                if os.path.exists(self.ffmpeg_path):
                    opts['ffmpeg_location'] = self.ffmpeg_path
                    
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False, process=False)
                    if info.get('_type') == 'playlist':
                        return 'playlist'
                    elif info.get('_type') == 'video' or 'entries' not in info:
                        return 'video'
            except:
                pass
            return 'unknown'

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
        except Exception as e:
            # In a real app we might want to log this
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
        """
        Returns: (success, message)
        """
        if not download_dir:
            download_dir = "downloads"
        os.makedirs(download_dir, exist_ok=True)
        
        if channel and channel_id:
            title += f" - [{channel} - @{channel_id}]"
            
        safe_title = self.sanitize_filename(title)
        temp_video = os.path.join(download_dir, f"temp_video_{safe_title}")
        temp_audio = os.path.join(download_dir, f"temp_audio_{safe_title}")
        final_file = os.path.join(download_dir, f"{safe_title}.{target_format}")
        
        if os.path.exists(final_file):
            return True, "File already exists, skipping..."
        try:
            direct_success = self._try_direct_download(url, selected_format, target_format, final_file, progress_hooks)
            if direct_success:
                return True, "Downloaded successfully (direct)"
            if not self.check_ffmpeg():
                return False, "FFmpeg required for video+audio merge!"
            success = self._download_and_merge_video(url, selected_format, target_format,
                                                temp_video, temp_audio, final_file, progress_hooks)
            if success:
                return True, "Downloaded and merged successfully"
            else:
                return False, "Download/Merge failed"
        except Exception as e:
            return False, f"Download error: {str(e)}"

    def _try_direct_download(self, url, selected_format, target_format, output_file, progress_hooks=None):
        try:
            if selected_format:
                format_selector = f"best[height<={selected_format['height']}][acodec!=none]/best[height<={selected_format['height']}]/best"
            else:
                format_selector = "best[acodec!=none]/best"
            ydl_opts = {
                'format': format_selector,
                'outtmpl': output_file.replace('.mp4', '.%(ext)s'),
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
            possible_files = [
                output_file,
                output_file.replace(f'.{target_format}', '.mp4'),
                output_file.replace(f'.{target_format}', '.webm'),
                output_file.replace(f'.{target_format}', '.mkv')
            ]
            for file_path in possible_files:
                if os.path.exists(file_path) and os.path.getsize(file_path) > 1024:
                    if file_path != output_file:
                        os.rename(file_path, output_file)
                    return True
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
            except:
                pass
            return success
        except Exception as e:
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

        except Exception as e:
            return False

    def download_single_audio(self, url, target_format, title, download_dir="downloads", progress_hooks=None, channel=None, channel_id=None):
        """
        Returns: (success, message)
        """
        if not download_dir:
            download_dir = "downloads"
        os.makedirs(download_dir, exist_ok=True)
        
        if channel and channel_id:
            title += f" - [{channel} - @{channel_id}]"
            
        safe_title = self.sanitize_filename(title)
        final_file = os.path.join(download_dir, f"{safe_title}.{target_format}")
        
        if os.path.exists(final_file):
            return True, "File already exists, skipping..."
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(download_dir, f'{safe_title}.%(ext)s'),
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
            if os.path.exists(final_file) and os.path.getsize(final_file) > 1024:
                return True, "Audio downloaded successfully"
            else:
                for ext in ['mp3', 'm4a', 'wav', 'flac']:
                    alt_file = os.path.join(download_dir, f"{safe_title}.{ext}")
                    if os.path.exists(alt_file):
                        if ext != target_format.lower():
                            os.rename(alt_file, final_file)
                        return True, "Audio downloaded successfully (converted)"
                return False, "Audio download failed"
        except Exception as e:
            return False, f"Audio download error: {str(e)}"

    def get_playlist_info(self, url, limit=None):
        url = self.preprocess_playlist_url(url)
        
        # Helper to set limit
        def apply_limit(opts):
            if limit:
                opts['playlistend'] = limit
            else:
                if 'playlistend' in opts:
                     del opts['playlistend']
            return opts

        methods = [
            apply_limit({
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'ignoreerrors': True,
                'ffmpeg_location': self.ffmpeg_path,
            }),
            apply_limit({
                'quiet': True,
                'no_warnings': True,
                'extract_flat': 'in_playlist',
                'ignoreerrors': True,
                'playlistreverse': False,
                'ffmpeg_location': self.ffmpeg_path,
            }),
            apply_limit({
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,
                'ignoreerrors': True,
                'writeinfojson': False,
                'ffmpeg_location': self.ffmpeg_path,
            }),
            apply_limit({
                'quiet': True,
                'no_warnings': True,
                'flat_playlist': True,
                'ignoreerrors': True,
                'ffmpeg_location': self.ffmpeg_path,
            })
        ]
        for ydl_opts in methods:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        continue
                    if 'entries' in info:
                        entries = [e for e in info['entries'] if e is not None]
                        valid_entries = []
                        for entry in entries:
                            if self.is_valid_entry(entry):
                                valid_entries.append(entry)
                        if valid_entries:
                            info['entries'] = valid_entries
                            return info
                    elif info.get('_type') == 'video' or 'title' in info:
                        return {
                            'title': f"Single Video: {info.get('title', 'Unknown')}",
                            'entries': [info],
                            '_type': 'playlist',
                            'playlist_count': 1
                        }
                    elif 'channel' in url.lower() or '/@' in url:
                        res = self.handle_channel_url(url, ydl_opts)
                        if res: return res
            except Exception:
                continue
        return self.fallback_playlist_extraction(url)

    def preprocess_playlist_url(self, url):
        if '&list=' in url and 'watch?v=' in url:
            list_match = re.search(r'[&?]list=([^&]+)', url)
            if list_match:
                playlist_id = list_match.group(1)
                if playlist_id.startswith('RD'):
                    return url
                return f"https://www.youtube.com/playlist?list={playlist_id}"
        if '/channel/' in url or '/@' in url or '/c/' in url:
            return self.convert_channel_to_playlist(url)
        return url

    def convert_channel_to_playlist(self, url):
        try:
            opts = {'quiet': True, 'no_warnings': True}
            if os.path.exists(self.ffmpeg_path):
                opts['ffmpeg_location'] = self.ffmpeg_path
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False, process=False)
                if info and 'channel_id' in info:
                    channel_id = info['channel_id']
                    if channel_id.startswith('UC'):
                        uploads_id = 'UU' + channel_id[2:]
                        return f"https://www.youtube.com/playlist?list={uploads_id}"
        except:
            pass
        return url

    def is_valid_entry(self, entry):
        if not entry or not isinstance(entry, dict):
            return False
        if not (entry.get('id') and entry.get('title')):
            return False
        if entry.get('title') in ['[Private video]', '[Deleted video]', 'Private video', 'Deleted video']:
            return False
        if entry.get('duration') == 0:
            return False
        return True

    def handle_channel_url(self, url, ydl_opts):
        try:
            channel_opts = ydl_opts.copy()
            channel_opts['playlistend'] = 100
            with yt_dlp.YoutubeDL(channel_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info and 'entries' in info:
                    entries = [e for e in info['entries'] if self.is_valid_entry(e)]
                    if entries:
                        return {
                            'title': info.get('title', 'Channel Videos'),
                            'entries': entries,
                            '_type': 'playlist'
                        }
        except:
            pass
        return None

    def fallback_playlist_extraction(self, url):
        try:
            simple_opts = {
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'extract_flat': True,
                'playlistend': 50,
                'ffmpeg_location': self.ffmpeg_path,
            }
            with yt_dlp.YoutubeDL(simple_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    if 'entries' in info:
                        entries = [e for e in info['entries'] if e]
                        if entries:
                            return {
                                'title': info.get('title', 'Playlist'),
                                'entries': entries,
                                '_type': 'playlist'
                            }
                    else:
                        return {
                            'title': f"Single Item: {info.get('title', 'Unknown')}",
                            'entries': [info],
                            '_type': 'playlist'
                        }
        except:
            pass
        return None

    def construct_video_url(self, entry):
        if not entry:
            return None
        for url_field in ['webpage_url', 'url']:
            if entry.get(url_field):
                url = entry[url_field]
                if 'youtube.com' in url or 'youtu.be' in url:
                    return url
        video_id = entry.get('id')
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        return None
