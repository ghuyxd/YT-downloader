import os
import subprocess
import re
import shutil
import yt_dlp

def get_script_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_ffmpeg_path():
    """Get ffmpeg full path from system PATH. Cross-platform."""
    path = shutil.which('ffmpeg')
    return path if path else 'ffmpeg'

def check_ffmpeg():
    """Check if ffmpeg is available in system PATH. Returns True if found."""
    return shutil.which('ffmpeg') is not None

def sanitize_filename(filename):
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
    filename = filename.strip('. ')
    return filename[:200]

def detect_url_type(url):
    if any(x in url.lower() for x in ['playlist', 'list=', '&list=']):
        return 'playlist'
    elif any(x in url.lower() for x in ['watch?v=', 'youtu.be/', '/watch/']):
        return 'video'
    elif any(x in url.lower() for x in ['channel/', '/c/', '/@']):
        return 'channel'
    else:
        try:
            opts = {'quiet': True, 'no_warnings': True}
            ffmpeg_path = get_ffmpeg_path()
            if os.path.exists(ffmpeg_path):
                opts['ffmpeg_location'] = ffmpeg_path
                
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False, process=False)
                if info.get('_type') == 'playlist':
                    return 'playlist'
                elif info.get('_type') == 'video' or 'entries' not in info:
                    return 'video'
        except:
            pass
        return 'unknown'
