import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QLabel, 
                             QComboBox, QMessageBox,
                             QGroupBox, QListWidget, QListWidgetItem, QFileDialog, QStackedWidget)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QPalette

from core import YouTubeDownloaderCore
from .settings import SettingsManager
from .threads import ImageLoader, AnalyzeThread, DownloadThread
from .components import GradientButton
from .queue_ui import QueueItemWidget


class MediaDownloaderGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.core = YouTubeDownloaderCore()
        self.settings = SettingsManager()
        self.current_info = None
        self.current_type = None
        self.queue_active = False
        
        self.analysis_queue = []
        self.is_analyzing_bg = False
        self.active_threads = set() # Track running threads to prevent GC
        
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
        
        self.url_input.returnPressed.connect(self.add_url_to_queue)
        
        input_layout.addWidget(self.url_input)
        
        self.queue_add_btn = GradientButton("Add to Queue")
        self.queue_add_btn.setFixedWidth(120)
        self.queue_add_btn.clicked.connect(self.add_url_to_queue)
        input_layout.addWidget(self.queue_add_btn)
        
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

        # Default Preferences
        config_layout.addSpacing(20)
        config_layout.addWidget(QLabel("Default:"))
        
        self.def_fmt_combo = QComboBox()
        self.def_fmt_combo.addItems(["Video (Best)", "Audio (MP3)", "Video (1080p)", "Video (720p)"])
        self.def_fmt_combo.setStyleSheet("QComboBox { background-color: #2b2b2b; color: #fff; border: 1px solid #444; padding: 5px; }")
        config_layout.addWidget(self.def_fmt_combo)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # 3. Content Area (Split View)
        self.content_area = QWidget()
        content_layout_grid = QHBoxLayout(self.content_area)
        content_layout_grid.setContentsMargins(0, 0, 0, 0)
        content_layout_grid.setSpacing(20)
        
        # LEFT: Thumbnail & Info
        left_panel = QWidget()
        left_panel.setMinimumWidth(340)
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
        self.info_label.setMinimumWidth(320)
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
        
        # wrapper for content + queue
        center_widget = QWidget()
        center_layout = QHBoxLayout(center_widget)
        center_layout.setContentsMargins(0,0,0,0)
        center_layout.setSpacing(15)
        
        # Left Stack (Placeholder vs Content)
        self.left_stack = QStackedWidget()
        
        # 0. Placeholder
        self.placeholder = QLabel("Ready to Download\n\nEnter a URL above to Analyze or Add to Queue")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("color: #444; font-size: 16px; font-weight: bold; border: 2px dashed #333; border-radius: 10px;")
        self.left_stack.addWidget(self.placeholder)
        
        # 1. Content Area
        self.content_area.setVisible(True) # Always visible within stack
        self.left_stack.addWidget(self.content_area)
        
        self.left_stack.setCurrentIndex(0)
        
        center_layout.addWidget(self.left_stack, stretch=6)
        
        # Queue Panel
        queue_panel = QGroupBox("Queue")
        # Removed setFixedWidth to allow flexible sizing or use stretch
        queue_panel.setMinimumWidth(320)
        queue_panel.setMaximumWidth(400)
        queue_layout = QVBoxLayout()
        queue_layout.setContentsMargins(10, 15, 10, 10)
        
        self.queue_list = QListWidget()
        self.queue_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 6px;
            }
            QListWidget::item {
                background: transparent;
                margin-bottom: 5px;
            }
        """)
        self.queue_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.queue_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.queue_list.setSpacing(4)
        self.queue_list.itemClicked.connect(self.on_queue_item_clicked)
        queue_layout.addWidget(self.queue_list)
        
        self.queue_start_btn = GradientButton("Process Queue")
        self.queue_start_btn.clicked.connect(self.process_queue)
        queue_layout.addWidget(self.queue_start_btn)
        
        queue_panel.setLayout(queue_layout)
        center_layout.addWidget(queue_panel, stretch=4)
        
        layout.addWidget(center_widget, stretch=1)
        
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
        # self.content_area.setVisible(False) # Removed
        
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

    def display_video_info(self, info, url_type):
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
            desc = info.get('description', '')
            # Show a snippet of description if available
            short_desc = (desc[:200] + '...') if len(desc) > 200 else desc
            self.info_label.setText(f"🎬 Video: {title}\n⏱️ Duration: {duration_str}\n\n📝 {short_desc}")
            self.playlist_group.setVisible(False)
            
        thumb_url = info.get('thumbnail')
        if not thumb_url and url_type == 'playlist':
            entries = info.get('entries', [])
            if entries:
                first_entry = entries[0]
                if isinstance(first_entry, dict):
                    thumb_url = first_entry.get('thumbnail')

        if thumb_url:
            loader = ImageLoader(thumb_url)
            self.active_threads.add(loader)
            loader.finished.connect(self.set_thumbnail)
            loader.finished.connect(lambda: self.cleanup_thread(loader))
            loader.start()
        else:
            self.thumbnail_label.setText("No Thumbnail")
            
        self.left_stack.setCurrentIndex(1) # Show content
        self.update_options()

    def on_analyze_finished(self, info, url_type):
        if self.queue_active and getattr(self, 'current_queue_item', None):
            self.process_queue_download(info, url_type)
            return
            
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze")
        
        self.display_video_info(info, url_type)
        
        self.download_btn.setVisible(True)
        self.download_btn.setEnabled(True)
        self.download_btn.setText("START DOWNLOAD")
        
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
        if self.queue_active and getattr(self, 'current_queue_item', None):
            status = "Done" if success else "Failed"
            if getattr(self, 'current_queue_widget', None):
                 self.current_queue_widget.set_status(status, 100 if success else 0)
            
            self.queue_active = False
            self.current_queue_item = None
            self.check_queue_processing()
            return

        self.download_btn.setEnabled(True)
        self.download_btn.setText("START DOWNLOAD")
        if success:
            QMessageBox.information(self, "Success", msg)
        else:
            QMessageBox.critical(self, "Failed", msg)

    # QUEUE LOGIC ------------------------
    
    def process_queue(self):
        self.check_queue_processing()

    def add_url_to_queue(self):
        url = self.url_input.text().strip()
        if not url: return
        item = self.add_queue_item(url)
        self.url_input.clear()
        
        # Trigger background analysis
        self.analysis_queue.append(item)
        self.process_next_analysis()

    def add_queue_item(self, url, status="Waiting..."):
        item = QListWidgetItem()
        widget = QueueItemWidget(url)
        widget.set_status(status)
        item.setSizeHint(widget.sizeHint())
        
        self.queue_list.addItem(item)
        self.queue_list.setItemWidget(item, widget)
        
        widget.move_up.connect(lambda: self.move_queue_item(item, -1))
        widget.move_down.connect(lambda: self.move_queue_item(item, 1))
        widget.remove.connect(lambda: self.remove_queue_item(item))
        return item

    def move_queue_item(self, item, direction):
        row = self.queue_list.row(item)
        new_row = row + direction
        if 0 <= new_row < self.queue_list.count():
            widget = self.queue_list.itemWidget(item)
            if widget.status_label.text() != "Pending": return
            
            url = widget.url
            self.queue_list.takeItem(row)
            self.queue_list.insertItem(new_row, item)
            
            new_widget = QueueItemWidget(url)
            new_widget.set_status("Pending")
            item.setSizeHint(new_widget.sizeHint())
            self.queue_list.setItemWidget(item, new_widget)
            
            new_widget.move_up.connect(lambda: self.move_queue_item(item, -1))
            new_widget.move_down.connect(lambda: self.move_queue_item(item, 1))
            new_widget.remove.connect(lambda: self.remove_queue_item(item))
            
            self.queue_list.setCurrentRow(new_row)

    def remove_queue_item(self, item):
        row = self.queue_list.row(item)
        self.queue_list.takeItem(row)

    def check_queue_processing(self):
        if self.queue_active: return
        
        for i in range(self.queue_list.count()):
            item = self.queue_list.item(i)
            widget = self.queue_list.itemWidget(item)
            if widget.status_label.text() == "Ready" or widget.status_label.text() == "Waiting...":
                self.start_queue_processing(item, widget)
                break
                
    def process_next_analysis(self):
        if self.is_analyzing_bg: return
        if not self.analysis_queue: return
        
        item = self.analysis_queue[0] # Don't pop yet, wait for finish
        widget = self.queue_list.itemWidget(item)
        
        if not widget: # Item removed?
            self.analysis_queue.pop(0)
            self.process_next_analysis()
            return

        self.is_analyzing_bg = True
        widget.set_status("Analyzing...")
        
        # Use a separate thread for background analysis
        thread = AnalyzeThread(self.core, widget.url)
        thread.finished.connect(lambda i, t: self.on_bg_analyze_finished(item, i, t))
        thread.error.connect(lambda e: self.on_bg_analyze_error(item, e))
        self.run_thread_safe(thread)

    def run_thread_safe(self, thread):
        self.active_threads.add(thread)
        thread.finished.connect(lambda: self.cleanup_thread(thread))
        thread.start()

    def cleanup_thread(self, thread):
        if thread in self.active_threads:
            self.active_threads.remove(thread)
        thread.deleteLater()

    def on_bg_analyze_finished(self, item, info, url_type):
        if item in self.analysis_queue:
            self.analysis_queue.remove(item)
            
        widget = self.queue_list.itemWidget(item)
        if widget:
            title = info.get('title', 'Unknown')
            widget.set_title(title)
            widget.set_status("Ready")
            # Store info in item
            item.setData(Qt.UserRole, {'info': info, 'type': url_type})
            
            # If this is the currently selected item or single item, show it?
            if self.queue_list.currentItem() == item:
                self.display_video_info(info, url_type)

        self.is_analyzing_bg = False
        self.process_next_analysis()

    def on_bg_analyze_error(self, item, err):
        if item in self.analysis_queue:
            self.analysis_queue.remove(item)
        widget = self.queue_list.itemWidget(item)
        if widget:
            widget.set_status("Analyze Failed")
        self.is_analyzing_bg = False
        self.process_next_analysis()

    def on_queue_item_clicked(self, item):
        try:
            if item is None:
                return
            
            # Check if widget still exists
            widget = self.queue_list.itemWidget(item)
            if widget is None:
                return
            
            data = item.data(Qt.UserRole)
            if data and isinstance(data, dict):
                info = data.get('info')
                url_type = data.get('type')
                if info and url_type:
                    self.display_video_info(info, url_type)
            else:
                # Item not yet analyzed, show URL in info label
                self.left_stack.setCurrentIndex(1)
                self.thumbnail_label.setText("Analyzing...")
                self.info_label.setText(f"🔄 Waiting for analysis...\\n\\n📎 {widget.url}")
                self.playlist_group.setVisible(False)
        except RuntimeError:
            # Widget was deleted during click handling
            pass

    def start_queue_processing(self, item, widget):
        self.queue_active = True
        self.current_queue_item = item
        self.current_queue_widget = widget
        
        # Check if already analyzed
        data = item.data(Qt.UserRole)
        if data and isinstance(data, dict):
            # Already has info, skip analyze step
            self.process_queue_download(data['info'], data['type'])
        else:
            # Not analyzed? Wait for BG analyze or Force?
            # Force analyze now (using main loop)
            widget.set_status("Analyzing (Active)...", 0)
            thread = AnalyzeThread(self.core, widget.url)
            thread.finished.connect(self.on_analyze_finished)
            thread.error.connect(self.on_queue_error)
            self.run_thread_safe(thread)

    def on_queue_error(self, err):
        if getattr(self, 'current_queue_widget', None):
            self.current_queue_widget.set_status("Error")
        self.queue_active = False
        self.current_queue_item = None
        self.check_queue_processing()

    def process_queue_download(self, info, url_type):
        if not getattr(self, 'current_queue_widget', None): return
        
        # Display Info in Left Panel
        self.display_video_info(info, url_type)
        
        self.current_queue_widget.set_status("Downloading...", 0)
        
        # Use Default Settings from UI
        def_setting = self.def_fmt_combo.currentText()
        is_audio = "Audio" in def_setting
        
        # "Video (Best)", "Audio (MP3)", "Video (1080p)", "Video (720p)"
        target_format = "mp3" if is_audio else "mp4"
        quality_pref = None
        
        if "1080p" in def_setting: quality_pref = 1080
        elif "720p" in def_setting: quality_pref = 720
        
        data = {
            'is_audio': is_audio,
            'format': target_format,
            'url': info.get('webpage_url', self.current_queue_widget.url),
            'title': info.get('title', 'Unknown'),
            'channel': info.get('uploader'),
            'channel_id': info.get('uploader_id')
        }
        
        path = self.path_input.text()
        
        if url_type == 'video':
            # Auto-select quality based on preference
            options = self.core.get_quality_options(info)
            data['quality'] = None
            if options:
                if quality_pref:
                    # Find closest match
                    for key, details in options:
                        if details['height'] == quality_pref:
                            data['quality'] = details
                            break
                    if not data['quality']: data['quality'] = options[0][1] # Fallback to best
                else:
                    data['quality'] = options[0][1] # Best available
            
            thread = DownloadThread(self.core, 'video', data, path)
            
        elif url_type == 'playlist':
            data['info'] = info
            data['media_type'] = 'audio' if is_audio else 'video'
            data['selected_indices'] = [] 
            if quality_pref:
                data['quality'] = {'height': quality_pref}
            else:
                data['quality'] = None
            thread = DownloadThread(self.core, 'playlist', data, path)

        thread.progress_update.connect(self.update_queue_progress)
        thread.finished.connect(self.on_download_finished)
        self.run_thread_safe(thread)

    def update_queue_progress(self, percent, text):
        if getattr(self, 'current_queue_widget', None):
            self.current_queue_widget.set_status(text, percent)
