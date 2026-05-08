import os
import sys
from datetime import datetime

DATA_DIR = os.path.join(
    os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)
    else os.path.dirname(os.path.dirname(__file__)),
    "data"
)
LOG_FILE = os.path.join(DATA_DIR, "debug.log")


def log(msg: str):
    os.makedirs(DATA_DIR, exist_ok=True)
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
