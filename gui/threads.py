import os
import requests
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QPixmap, QImage

class ImageLoader(QThread):
    finished = Signal(QPixmap)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            if not self.url:
                return
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
            image = QImage()
            image.loadFromData(response.content)
            pixmap = QPixmap.fromImage(image)
            self.finished.emit(pixmap)
        except Exception:
            pass


class AnalyzeThread(QThread):
    finished = Signal(dict, str)
    error = Signal(str)

    def __init__(self, core, url, limit=None):
        super().__init__()
        self.core = core
        self.url = url
        self.limit = limit

    def run(self):
        try:
            url_type = self.core.detect_url_type(self.url)
            if url_type == 'playlist':
                info = self.core.get_playlist_info(self.url, limit=self.limit)
                if info:
                    self.finished.emit(info, 'playlist')
                else:
                    self.error.emit("Could not analyze playlist.")
            elif url_type == 'video':
                info = self.core.get_video_info(self.url)
                if info:
                    self.finished.emit(info, 'video')
                else:
                    self.error.emit("Could not analyze video.")
            else:
                info = self.core.get_video_info(self.url)
                if info:
                    self.finished.emit(info, 'video')
                else:
                    self.error.emit("Unsupported URL or analysis failed.")
        except Exception as e:
            self.error.emit(str(e))


class DownloadThread(QThread):
    progress_update = Signal(float, str)
    finished = Signal(bool, str)

    def __init__(self, core, task_type, data, download_dir):
        super().__init__()
        self.core = core
        self.task_type = task_type
        self.data = data
        self.download_dir = download_dir

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            try:
                p = d.get('_percent_str', '0%').replace('%', '')
                percent = float(p)
                speed = d.get('_speed_str', 'N/A')
                eta = d.get('_eta_str', 'N/A')
                if eta == 'N/A' and d.get('eta'):
                    eta_sec = d.get('eta')
                    if isinstance(eta_sec, (int, float)):
                        eta = f"{int(eta_sec)//60}:{int(eta_sec)%60:02d}"
                total_bytes = d.get('_total_bytes_str') or d.get('_total_bytes_estimate_str', 'N/A')
                status_text = f"{percent}% of {total_bytes} at {speed} ETA {eta}"
                self.progress_update.emit(percent, status_text)
            except Exception:
                pass
        elif d['status'] == 'finished':
            self.progress_update.emit(100, "Processing completed. Finalizing...")

    def run(self):
        try:
            hooks = [self.progress_hook]
            
            if self.task_type == 'video':
                self._download_video(hooks)
            elif self.task_type == 'playlist':
                self._download_playlist(hooks)
        except Exception as e:
            self.finished.emit(False, str(e))

    def _download_video(self, hooks):
        url = self.data['url']
        selected_quality = self.data.get('quality')
        target_format = self.data['format']
        title = self.data['title']
        is_audio = self.data['is_audio']
        
        self.progress_update.emit(0, f"Starting download: {title}")
        
        channel = self.data.get('channel')
        channel_id = self.data.get('channel_id')
        
        if is_audio:
            success, msg = self.core.download_single_audio(url, target_format, title, self.download_dir, hooks, channel=channel, channel_id=channel_id)
        else:
            success, msg = self.core.download_single_video(url, selected_quality, target_format, title, self.download_dir, hooks, channel=channel, channel_id=channel_id)
            
        self.progress_update.emit(100, "Done")
        self.finished.emit(success, msg)

    def _download_playlist(self, hooks):
        playlist_info = self.data['info']
        media_type = self.data['media_type']
        quality = self.data.get('quality')
        target_format = self.data['format']
        selected_indices = self.data.get('selected_indices', [])
        
        entries = playlist_info.get('entries', [])
        valid_entries = []
        
        if selected_indices:
            for idx in selected_indices:
                if 0 <= idx < len(entries):
                    entry = entries[idx]
                    if entry and self.core.construct_video_url(entry):
                        entry['_constructed_url'] = self.core.construct_video_url(entry)
                        valid_entries.append(entry)
        else:
            for entry in entries:
                if entry and self.core.construct_video_url(entry):
                    entry['_constructed_url'] = self.core.construct_video_url(entry)
                    valid_entries.append(entry)
                
        total = len(valid_entries)
        playlist_title = playlist_info.get('title', 'Unknown Playlist')
        safe_playlist_name = self.core.sanitize_filename(playlist_title)
        
        final_dir = os.path.join(self.download_dir, safe_playlist_name)
        os.makedirs(final_dir, exist_ok=True)
        
        successful_count = 0
        
        for i, entry in enumerate(valid_entries, 1):
            title = entry.get('title', f'Video_{i}')
            url = entry.get('_constructed_url')
            
            self.progress_update.emit(0, f"[{i}/{total}] Downloading: {title[:30]}...")
            
            channel = entry.get('uploader')
            channel_id = entry.get('uploader_id')
            
            try:
                if media_type == 'video':
                    success, msg = self.core.download_single_video(url, quality, target_format, title, str(final_dir), hooks, channel=channel, channel_id=channel_id)
                else:
                    success, msg = self.core.download_single_audio(url, target_format, title, str(final_dir), hooks, channel=channel, channel_id=channel_id)
                
                if success:
                    successful_count += 1
            except Exception:
                pass
                
        self.progress_update.emit(100, f"Playlist finished.")
        self.finished.emit(True, f"Playlist finished. {successful_count}/{total} successful.")
