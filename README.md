# YT Downloader

A modern YouTube Downloader application with a beautiful GUI, built using PySide6 and yt-dlp.

## Features

- 🎬 Download YouTube videos in various quality options
- 🎵 Extract audio from videos (MP3, WAV, etc.)
- 📋 Playlist support - download entire playlists
- ⚙️ Customizable settings (output directory, format, quality)
- 🖥️ Clean and intuitive graphical interface

## Requirements

- Python 3.11+
- yt-dlp
- PySide6
- requests

## Installation

### Option 1: Using pip

```bash
pip install .
```

### Option 2: Using install scripts

**Windows:**
```bash
install.bat
```

**Linux:**
```bash
chmod +x install.sh
./install.sh
```

## Usage

### Run the GUI Application

```bash
python main.py
```

Or use the run scripts:

**Windows:**
```bash
run.bat
```

**Linux:**
```bash
./run.sh
```

## Project Structure

```
YT-downloader/
├── core/               # Core functionality
│   ├── downloader.py   # Download logic
│   ├── playlist.py     # Playlist handling
│   └── utils.py        # Utility functions
├── gui/                # GUI components
│   ├── main_window.py  # Main application window
│   ├── components.py   # Reusable UI components
│   ├── settings.py     # Settings dialog
│   └── threads.py      # Background workers
├── main.py             # Application entry point
├── install.bat         # Windows installation script
├── install.sh          # Linux installation script
├── run.bat             # Windows run script
├── run.sh              # Linux run script
└── pyproject.toml      # Project configuration
```

## License

MIT License
