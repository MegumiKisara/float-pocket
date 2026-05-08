import json
import os
import sys

from dotenv import load_dotenv, set_key

DATA_DIR = os.path.join(
    os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)
    else os.path.dirname(os.path.dirname(__file__)),
    "data"
)
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
ENV_FILE = os.path.join(DATA_DIR, ".env")

DEFAULT_CONFIG = {
    "auto_start": False,
    "global_hotkey": "ctrl+alt+s",
    "float_ball": {"size": 60, "opacity": 0.8, "edge_adsorption": True, "corner_radius": 8, "color": "#6CB4EE", "child_colors": ["#6CB4EE", "#6CB4EE", "#6CB4EE", "#6CB4EE"], "child_ball": {"size": 36, "opacity": 0.85, "corner_radius": 18}, "icons": {"main": "", "child_0": "", "child_1": "", "child_2": "", "child_3": ""}, "ball_positions": [
        {"dx": 19, "dy": -35},
        {"dx": 43, "dy": -17},
        {"dx": 51, "dy": 21},
        {"dx": 37, "dy": 47},
    ]},
    "api_config": {
        "api_url": "",
        "api_key": "",
        "timeout": 10,
    },
    "theme": "light",
}


def env_init():
    """Load .env file into os.environ at startup."""
    os.makedirs(DATA_DIR, exist_ok=True)
    load_dotenv(ENV_FILE)


def env_get_api_key() -> str:
    return os.environ.get("QWEN_API_KEY", "")


def env_set_api_key(api_key: str):
    os.environ["QWEN_API_KEY"] = api_key
    set_key(ENV_FILE, "QWEN_API_KEY", api_key)


class ConfigModule:
    def __init__(self):
        self._config = DEFAULT_CONFIG.copy()
        self._load()

    def _load(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                stored = json.load(f)
                # Deep merge float_ball to preserve new sub-keys (ball_positions, etc.)
                fb_default = DEFAULT_CONFIG.get("float_ball", {})
                fb_stored = stored.get("float_ball", {})
                stored["float_ball"] = {**fb_default, **fb_stored}
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
