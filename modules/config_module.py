import json
import os


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

DEFAULT_CONFIG = {
    "auto_start": False,
    "global_hotkey": "ctrl+alt+s",
    "float_ball": {"size": 60, "opacity": 0.8, "edge_adsorption": True, "corner_radius": 8},
    "api_config": {
        "api_url": "",
        "api_key": "",
        "timeout": 10,
    },
    "theme": "light",
}


class ConfigModule:
    def __init__(self):
        self._config = DEFAULT_CONFIG.copy()
        self._load()

    def _load(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                stored = json.load(f)
                self._config = {**DEFAULT_CONFIG, **stored}

    def save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)

    def get(self, key, default=None):
        return self._config.get(key, default)

    def set(self, key, value):
        self._config[key] = value
        self.save()

    def set_preview(self, key, value):
        self._config[key] = value

    def reload(self):
        self._load()
