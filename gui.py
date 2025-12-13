
import sys
import os
import json
import requests
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QLabel, 
                             QComboBox, QTextEdit, QProgressBar, QMessageBox,
                             QTabWidget, QGroupBox, QScrollArea, QFrame, QCheckBox,
                             QListWidget, QListWidgetItem, QFileDialog)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QSize, QSettings, QRect
from PySide6.QtGui import QIcon, QFont, QColor, QPalette, QPixmap, QImage, QPainter, QLinearGradient, QBrush, QPen, QPainterPath

from core import YouTubeDownloaderCore

# -----------------------------------------------------------------------------
# Utils & Managers
# -----------------------------------------------------------------------------

class SettingsManager:
    DEFAULT_SETTINGS = {
        "download_dir": os.path.join(os.path.expanduser("~"), "Downloads"),
        "last_quality": "Best Quality",
        "last_format": "mp4",
        "last_type": 0, # 0 for Video+Audio, 1 for Audio Only
        "playlist_limit": "50"
    }
    
    def __init__(self, filename="settings.json"):
        self.filename = filename
        self.settings = self.load()
        
    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    return {**self.DEFAULT_SETTINGS, **json.load(f)}
            except Exception:
                return self.DEFAULT_SETTINGS.copy()
        return self.DEFAULT_SETTINGS.copy()

    def save(self):
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def get(self, key):
        return self.settings.get(key, self.DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.settings[key] = value
        self.save()

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

# -----------------------------------------------------------------------------
# Work Threads
# -----------------------------------------------------------------------------

class AnalyzeThread(QThread):
    finished = Signal(dict, str) # result, type ('video' or 'playlist')
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
                # Try as video fallback
                info = self.core.get_video_info(self.url)
                if info:
                    self.finished.emit(info, 'video')
                else:
                    self.error.emit("Unsupported URL or analysis failed.")
        except Exception as e:
            self.error.emit(str(e))

class DownloadThread(QThread):
    progress_update = Signal(float, str) # percentage, status text
    finished = Signal(bool, str)

    def __init__(self, core, task_type, data, download_dir):
        super().__init__()
        self.core = core
        self.task_type = task_type # 'video' or 'playlist'
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
                
                # User requested full format: [download] 21.6% of ~ 92.31MiB at 7.03MiB/s ETA 00:10
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
        media_type = self.data['media_type'] # 'video' or 'audio'
        quality = self.data.get('quality')
        target_format = self.data['format']
        selected_indices = self.data.get('selected_indices', []) 
        
        entries = playlist_info.get('entries', [])
        valid_entries = []
        
        # Filter only selected entries
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
            except Exception as e:
                pass
                
        self.progress_update.emit(100, f"Playlist finished.")
        self.finished.emit(True, f"Playlist finished. {successful_count}/{total} successful.")


# -----------------------------------------------------------------------------
# Components
# -----------------------------------------------------------------------------

class GradientButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        self.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self._hover = False
        
    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Gradient: Cyan Theme
        gradient = QLinearGradient(0, 0, self.width(), 0)
        if self.isEnabled():
            if self._hover:
                gradient.setColorAt(0, QColor("#00E5FF")) # Cyan Accent
                gradient.setColorAt(1, QColor("#00B8D4")) 
            else:
                gradient.setColorAt(0, QColor("#00BCD4")) 
                gradient.setColorAt(1, QColor("#00838F")) 
        else:
            gradient.setColorAt(0, QColor("#555")) 
            gradient.setColorAt(1, QColor("#555")) 
            
        rect = self.rect()
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 4, 4)
        
        # Text
        painter.setPen(Qt.black if self.isEnabled() else Qt.white)
        font = self.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, self.text())

class ProgressButton(GradientButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._progress = 0.0 # 0.0 to 100.0
        self.original_text = text
        self.status_text = text

    def set_progress(self, value):
        self._progress = max(0.0, min(100.0, float(value)))
        self.update()

    def set_status(self, text):
        self.status_text = text
        self.update()
        
    def reset(self):
        self._progress = 0.0
        self.status_text = self.original_text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        
        # 1. Background
        bg = QColor("#333")
        painter.setBrush(bg)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 4, 4)
        
        # 2. Progress Fill (Cyan Gradient)
        if self._progress > 0:
            fill_width = int(rect.width() * (self._progress / 100.0))
            if fill_width > 0:
                gradient = QLinearGradient(0, 0, rect.width(), 0)
                gradient.setColorAt(0, QColor("#00E5FF")) 
                gradient.setColorAt(1, QColor("#00838F"))
                
                painter.setBrush(QBrush(gradient))
                
                # Draw only the filled portion, but clipped to rounded rect
                # Since we want simple rounded rect fill:
                painter.save()
                path = QPainterPath()
                path.addRoundedRect(rect, 4, 4)
                painter.setClipPath(path)
                
                painter.drawRect(0, 0, fill_width, rect.height())
                painter.restore()

        # 3. Text
        painter.setPen(Qt.white)
        font = self.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, self.status_text)


# -----------------------------------------------------------------------------
# Main Window
# -----------------------------------------------------------------------------

class MediaDownloaderGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.core = YouTubeDownloaderCore()
        self.settings = SettingsManager()
        self.current_info = None
        self.current_type = None
        
        self.setWindowTitle("YT Downloader")
        self.setMinimumSize(1000, 700)
        self.setup_ui()
        self.setup_dark_theme()
        
        # Check executables
        missing = self.core.check_executable_paths()
        if missing:
             QMessageBox.warning(self, "Warning", f"Missing executables: {', '.join(missing)}")

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. URL Input Area
        input_group = QGroupBox("Input URL")
        input_group.setFixedHeight(80)
        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube Video or Playlist URL here...")
        self.url_input.setMinimumHeight(40)
        self.url_input.setStyleSheet("QLineEdit { background-color: #2b2b2b; color: #fff; border: 1px solid #444; border-radius: 4px; padding: 5px; font-size: 14px;}")
        
        self.analyze_btn = GradientButton("Analyze")
        self.analyze_btn.setFixedWidth(120)
        self.analyze_btn.clicked.connect(self.start_analyze)
        
        input_layout.addWidget(self.url_input)
        input_layout.addWidget(self.analyze_btn)
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # 2. Settings & Location Area
        config_group = QGroupBox("Configuration")
        config_group.setFixedHeight(80)
        config_layout = QHBoxLayout()
        
        # Location
        config_layout.addWidget(QLabel("Save to:"))
        self.path_input = QLineEdit()
        self.path_input.setText(self.settings.get("download_dir"))
        self.path_input.setReadOnly(False)
        self.path_input.setStyleSheet("QLineEdit { background-color: #2b2b2b; color: #fff; border: 1px solid #444; border-radius: 4px; padding: 5px; }")
        self.path_input.editingFinished.connect(self.on_path_changed)
        config_layout.addWidget(self.path_input)
        
        self.browse_btn = GradientButton("Browse")
        self.browse_btn.setFixedWidth(80)
        self.browse_btn.clicked.connect(self.browse_path)
        self.browse_btn.clicked.connect(self.browse_path)
        config_layout.addWidget(self.browse_btn)

        # Playlist Limit
        config_layout.addWidget(QLabel("Limit:"))
        self.limit_combo = QComboBox()
        self.limit_combo.setFixedWidth(80)
        self.limit_combo.setEditable(True)
        self.limit_combo.addItems(["10", "20", "50", "100", "200", "Unlimited"])
        self.limit_combo.setToolTip("Max videos to load for playlist")
        last_limit = self.settings.get("playlist_limit")
        self.limit_combo.setCurrentText(str(last_limit))
        self.limit_combo.setStyleSheet("QComboBox { background-color: #2b2b2b; color: #fff; border: 1px solid #444; padding: 5px; }")
        config_layout.addWidget(self.limit_combo)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # 3. Content Area (Split View)
        self.content_area = QWidget()
        content_layout_grid = QHBoxLayout(self.content_area)
        content_layout_grid.setContentsMargins(0, 0, 0, 0)
        content_layout_grid.setSpacing(20)
        
        # LEFT: Thumbnail & Info
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setAlignment(Qt.AlignTop)
        
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(320, 180)
        self.thumbnail_label.setStyleSheet("background-color: #111; border: 1px solid #333; border-radius: 8px;")
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setText("No Thumbnail")
        left_layout.addWidget(self.thumbnail_label)
        
        self.info_label = QLabel("No content selected")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("font-size: 14px; color: #ddd; font-weight: bold; margin-top: 10px;")
        left_layout.addWidget(self.info_label)
        
        content_layout_grid.addWidget(left_panel, stretch=1)
        
        # RIGHT: Options & Playlist Checklist
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setAlignment(Qt.AlignTop)
        
        # Download Options
        opts_group = QGroupBox("Download Options")
        opts_layout = QVBoxLayout()
        
        # Type
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Video + Audio", "Audio Only"])
        self.type_combo.setCurrentIndex(self.settings.get("last_type"))
        self.type_combo.currentIndexChanged.connect(self.update_options)
        self.type_combo.setStyleSheet("QComboBox { background-color: #2b2b2b; color: white; padding: 5px; border: 1px solid #444; }")
        type_row.addWidget(self.type_combo)
        opts_layout.addLayout(type_row)
        
        # Quality
        qual_row = QHBoxLayout()
        qual_row.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.setStyleSheet("QComboBox { background-color: #2b2b2b; color: white; padding: 5px; border: 1px solid #444; }")
        qual_row.addWidget(self.quality_combo)
        opts_layout.addLayout(qual_row)
        
        # Format
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.setStyleSheet("QComboBox { background-color: #2b2b2b; color: white; padding: 5px; border: 1px solid #444; }")
        fmt_row.addWidget(self.format_combo)
        opts_layout.addLayout(fmt_row)
        
        opts_group.setLayout(opts_layout)
        right_layout.addWidget(opts_group)
        
        # Playlist Selection (Conditional)
        self.playlist_group = QGroupBox("Select Videos")
        playlist_layout = QVBoxLayout()
        
        list_controls = QHBoxLayout()
        self.chk_all = GradientButton("Select All")
        self.chk_all.clicked.connect(self.select_all_items)
        self.chk_all.setFixedHeight(30)
        
        self.btn_invert = GradientButton("Invert")
        self.btn_invert.clicked.connect(self.invert_selection)
        self.btn_invert.setFixedHeight(30)
        
        list_controls.addWidget(self.chk_all)
        list_controls.addWidget(self.btn_invert)
        playlist_layout.addLayout(list_controls)
        
        self.playlist_widget = QListWidget()
        self.playlist_widget.setStyleSheet("QListWidget { background-color: #2b2b2b; color: white; border: 1px solid #444; padding: 5px; } QListWidget::item { padding: 5px; }")
        playlist_layout.addWidget(self.playlist_widget)
        
        self.playlist_group.setLayout(playlist_layout)
        self.playlist_group.setVisible(False)
        right_layout.addWidget(self.playlist_group, stretch=1)
        
        content_layout_grid.addWidget(right_panel, stretch=2)
        
        self.content_area.setVisible(False)
        layout.addWidget(self.content_area, stretch=1)
        
        # 4. Footer (Progress & Actions)
        footer_widget = QWidget()
        footer_layout = QVBoxLayout(footer_widget)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        
        # Replaced Standard Button with ProgressButton
        self.download_btn = ProgressButton("START DOWNLOAD")
        self.download_btn.setFixedHeight(50)
        self.download_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setVisible(False)
        footer_layout.addWidget(self.download_btn)
        
        layout.addWidget(footer_widget)

    def setup_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.WindowText, Qt.white)
        self.setPalette(palette)
        
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; }
            QGroupBox {
                border: 1px solid #444;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
                color: #ddd;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
    
    def browse_path(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Download Directory", self.path_input.text())
        if directory:
            self.path_input.setText(directory)
            self.settings.set("download_dir", directory)
            
    def on_path_changed(self):
        new_path = self.path_input.text().strip()
        if new_path and os.path.exists(new_path):
             self.settings.set("download_dir", new_path)
            
    def select_all_items(self):
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            item.setCheckState(Qt.Checked)

    def invert_selection(self):
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            current = item.checkState()
            item.setCheckState(Qt.Unchecked if current == Qt.Checked else Qt.Checked)

    def start_analyze(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL")
            return
            
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("Analyzing...")
        self.download_btn.reset()
        self.download_btn.setVisible(False)
        self.content_area.setVisible(False)
        
        self.content_area.setVisible(False)
        
        # Get Limit
        limit_str = self.limit_combo.currentText().strip()
        self.settings.set("playlist_limit", limit_str)
        
        limit = None
        if limit_str.lower() != "unlimited":
            try:
                limit = int(limit_str)
            except ValueError:
                limit = 50 # Default fallback

        self.analyze_thread = AnalyzeThread(self.core, url, limit)
        self.analyze_thread.finished.connect(self.on_analyze_finished)
        self.analyze_thread.error.connect(self.on_analyze_error)
        self.analyze_thread.start()

    def on_analyze_finished(self, info, url_type):
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze")
        self.current_info = info
        self.current_type = url_type
        
        # Display Info
        title = info.get('title', 'Unknown')
        
        if url_type == 'playlist':
            count = len(info.get('entries', []))
            self.info_label.setText(f"📂 Playlist: {title}\n📊 Items: {count} videos detected")
            self.playlist_group.setVisible(True)
            self.populate_playlist_list(info.get('entries', []))
        else:
            duration = info.get('duration', 0)
            duration_str = f"{duration//60}:{duration%60:02d}"
            self.info_label.setText(f"🎬 Video: {title}\n⏱️ Duration: {duration_str}")
            self.playlist_group.setVisible(False)
            
        # Load Thumbnail
        thumb_url = info.get('thumbnail')
        if not thumb_url and url_type == 'playlist':
            entries = info.get('entries', [])
            if entries:
                first_entry = entries[0]
                if isinstance(first_entry, dict):
                    thumb_url = first_entry.get('thumbnail') # Try to get from first entry

        if thumb_url:
            self.image_loader = ImageLoader(thumb_url)
            self.image_loader.finished.connect(self.set_thumbnail)
            self.image_loader.start()
        else:
            self.thumbnail_label.setText("No Thumbnail")
            
        self.content_area.setVisible(True)
        self.download_btn.setVisible(True)
        self.download_btn.setEnabled(True)
        self.download_btn.reset()
        
        self.update_options()
        
    def set_thumbnail(self, pixmap):
        scaled = pixmap.scaled(self.thumbnail_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.thumbnail_label.setPixmap(scaled)

    def populate_playlist_list(self, entries):
        self.playlist_widget.clear()
        for i, entry in enumerate(entries, 1):
            if not entry: continue
            title = entry.get('title', f"Video {i}")
            item = QListWidgetItem(f"{i}. {title}")
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, i-1) 
            self.playlist_widget.addItem(item)
            
    def on_analyze_error(self, error_msg):
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze")
        QMessageBox.critical(self, "Analysis Failed", error_msg)

    def update_options(self):
        if not self.current_info:
            return
            
        is_audio = self.type_combo.currentIndex() == 1
        
        # Update Qualities
        self.quality_combo.clear()
        
        last_quality = self.settings.get("last_quality")
        
        if is_audio:
            self.quality_combo.addItem("Best Audio")
            self.quality_combo.setEnabled(False)
        else:
            self.quality_combo.setEnabled(True)
            if self.current_type == 'video':
                qualities = self.core.get_quality_options(self.current_info)
                if qualities:
                    for key, details in qualities:
                        fps = f" {details['fps']}fps" if details.get('fps') else ""
                        self.quality_combo.addItem(f"{key}{fps}", details)
                else:
                    self.quality_combo.addItem("Best Available")
            else:
                # Playlist simplified options
                self.quality_combo.addItems(["Best Quality", "1080p", "720p", "480p"])
        
        # Restore last quality selection if possible
        index = self.quality_combo.findText(last_quality, Qt.MatchContains)
        if index >= 0:
            self.quality_combo.setCurrentIndex(index)

        # Update Formats
        self.format_combo.clear()
        if is_audio:
            self.format_combo.addItems(self.core.audio_formats)
        else:
            self.format_combo.addItems(self.core.video_formats)
            
        last_format = self.settings.get("last_format")
        idx = self.format_combo.findText(last_format, Qt.MatchContains)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)

    def start_download(self):
        if not self.current_info:
            return
            
        # Get settings
        is_audio = self.type_combo.currentIndex() == 1
        target_format = self.format_combo.currentText().lower()
        
        # Save settings
        self.settings.set("last_type", self.type_combo.currentIndex())
        self.settings.set("last_format", target_format)
        if not is_audio:
            self.settings.set("last_quality", self.quality_combo.currentText())

        data = {
            'is_audio': is_audio,
            'format': target_format
        }
        
        if self.current_type == 'video':
            data['url'] = self.url_input.text().strip()
            data['url'] = self.url_input.text().strip()
            data['title'] = self.current_info.get('title', 'video')
            data['channel'] = self.current_info.get('uploader')
            data['channel_id'] = self.current_info.get('uploader_id')
            if not is_audio:
                idx = self.quality_combo.currentIndex()
                if idx >= 0:
                    data['quality'] = self.quality_combo.itemData(idx)
                else:
                    data['quality'] = None
        
            self.download_thread = DownloadThread(self.core, 'video', data, self.path_input.text())
            
        elif self.current_type == 'playlist':
            data['info'] = self.current_info
            data['media_type'] = 'audio' if is_audio else 'video'
            
            # Get selected indices
            selected_indices = []
            for i in range(self.playlist_widget.count()):
                item = self.playlist_widget.item(i)
                if item.checkState() == Qt.Checked:
                    selected_indices.append(item.data(Qt.UserRole))
            
            if not selected_indices:
                QMessageBox.warning(self, "Warning", "No videos selected in playlist!")
                return
                
            data['selected_indices'] = selected_indices
            
            if not is_audio:
                q_text = self.quality_combo.currentText()
                if "1080" in q_text: height = 1080
                elif "720" in q_text: height = 720
                elif "480" in q_text: height = 480
                else: height = 2160 # Best
                data['quality'] = {'height': height}
            else:
                data['quality'] = None
                
            self.download_thread = DownloadThread(self.core, 'playlist', data, self.path_input.text())

        self.download_btn.setEnabled(False)
        self.download_btn.set_status("Initializing...")
        
        self.download_thread.progress_update.connect(self.update_progress)
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.start()
        
    def update_progress(self, percent, text):
        self.download_btn.set_progress(percent)
        self.download_btn.set_status(str(text))

    def on_download_finished(self, success, msg):
        self.download_btn.setEnabled(True)
        if success:
            self.download_btn.set_progress(100)
            self.download_btn.set_status("DOWNLOAD COMPLETE")
            QMessageBox.information(self, "Success", msg)
        else:
            self.download_btn.set_progress(0)
            self.download_btn.set_status("FAILED - RETRY")
            QMessageBox.critical(self, "Failed", msg)
        self.download_btn.reset()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MediaDownloaderGUI()
    window.show()
    sys.exit(app.exec())
