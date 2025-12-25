import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QLabel, 
                             QComboBox, QMessageBox,
                             QGroupBox, QListWidget, QListWidgetItem, QFileDialog)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QPalette

from core import YouTubeDownloaderCore
from .settings import SettingsManager
from .threads import ImageLoader, AnalyzeThread, DownloadThread
from .components import GradientButton


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
        config_layout.addWidget(self.browse_btn)

        config_layout.addWidget(QLabel("Playlist Limit:"))
        self.limit_combo = QComboBox()
        self.limit_combo.setFixedWidth(60)
        self.limit_combo.setEditable(True)
        self.limit_combo.addItems(["10", "50", "100", "200", "500", "1000", "Unlimited"])
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
        
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Video", "Audio"])
        self.type_combo.setCurrentIndex(self.settings.get("last_type"))
        self.type_combo.currentIndexChanged.connect(self.update_options)
        self.type_combo.setStyleSheet("QComboBox { background-color: #2b2b2b; color: white; padding: 5px; border: 1px solid #444; }")
        type_row.addWidget(self.type_combo)
        opts_layout.addLayout(type_row)
        
        qual_row = QHBoxLayout()
        qual_row.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.setStyleSheet("QComboBox { background-color: #2b2b2b; color: white; padding: 5px; border: 1px solid #444; }")
        qual_row.addWidget(self.quality_combo)
        opts_layout.addLayout(qual_row)
        
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.setStyleSheet("QComboBox { background-color: #2b2b2b; color: white; padding: 5px; border: 1px solid #444; }")
        fmt_row.addWidget(self.format_combo)
        opts_layout.addLayout(fmt_row)
        
        opts_group.setLayout(opts_layout)
        right_layout.addWidget(opts_group)
        
        # Playlist Selection
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
        
        # 4. Footer
        footer_widget = QWidget()
        footer_layout = QVBoxLayout(footer_widget)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        
        self.download_btn = GradientButton("START DOWNLOAD")
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
        self.download_btn.setVisible(False)
        self.content_area.setVisible(False)
        
        limit_str = self.limit_combo.currentText().strip()
        self.settings.set("playlist_limit", limit_str)
        
        limit = None
        if limit_str.lower() != "unlimited":
            try:
                limit = int(limit_str)
            except ValueError:
                limit = 50

        self.analyze_thread = AnalyzeThread(self.core, url, limit)
        self.analyze_thread.finished.connect(self.on_analyze_finished)
        self.analyze_thread.error.connect(self.on_analyze_error)
        self.analyze_thread.start()

    def on_analyze_finished(self, info, url_type):
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze")
        self.current_info = info
        self.current_type = url_type
        
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
            
        thumb_url = info.get('thumbnail')
        if not thumb_url and url_type == 'playlist':
            entries = info.get('entries', [])
            if entries:
                first_entry = entries[0]
                if isinstance(first_entry, dict):
                    thumb_url = first_entry.get('thumbnail')

        if thumb_url:
            self.image_loader = ImageLoader(thumb_url)
            self.image_loader.finished.connect(self.set_thumbnail)
            self.image_loader.start()
        else:
            self.thumbnail_label.setText("No Thumbnail")
            
        self.content_area.setVisible(True)
        self.download_btn.setVisible(True)
        self.download_btn.setEnabled(True)
        self.download_btn.setText("START DOWNLOAD")
        
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
                self.quality_combo.addItems(["Best Quality", "1080p", "720p", "480p"])
        
        index = self.quality_combo.findText(last_quality, Qt.MatchContains)
        if index >= 0:
            self.quality_combo.setCurrentIndex(index)

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
            
        is_audio = self.type_combo.currentIndex() == 1
        target_format = self.format_combo.currentText().lower()
        
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
                else: height = 2160
                data['quality'] = {'height': height}
            else:
                data['quality'] = None
                
            self.download_thread = DownloadThread(self.core, 'playlist', data, self.path_input.text())

        self.download_btn.setEnabled(False)
        self.download_btn.setText("Downloading...")
        
        self.download_thread.progress_update.connect(self.update_progress)
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.start()
        
    def update_progress(self, percent, text):
        pass

    def on_download_finished(self, success, msg):
        self.download_btn.setEnabled(True)
        self.download_btn.setText("START DOWNLOAD")
        if success:
            QMessageBox.information(self, "Success", msg)
        else:
            QMessageBox.critical(self, "Failed", msg)
