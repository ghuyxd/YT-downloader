import os
import json

class SettingsManager:
    DEFAULT_SETTINGS = {
        "download_dir": os.path.join(os.path.expanduser("~"), "Downloads"),
        "last_quality": "Best Quality",
        "last_format": "mp4",
        "last_type": 0,
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
