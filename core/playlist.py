import os
import re
import yt_dlp
from .utils import get_ffmpeg_path

class PlaylistExtractor:
    def __init__(self):
        self.ffmpeg_path = get_ffmpeg_path()

    def get_playlist_info(self, url, limit=None):
        url = self.preprocess_playlist_url(url)
        
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
