import ctypes

from PySide6.QtCore import QObject, QTimer, Signal

VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_SHIFT = 0x10

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

_VK_TABLE = {
    **{chr(ord("a") + i): 0x41 + i for i in range(26)},
    **{str(i): 0x30 + i for i in range(10)},
    **{f"f{i}": 0x6F + i for i in range(1, 13)},
    "space": 0x20,
    "enter": 0x0D,
    "tab": 0x09,
    "escape": 0x1B,
    "delete": 0x2E,
    "backspace": 0x08,
}

_MOD_MAP = {
    "ctrl": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "meta": MOD_WIN,
}


class HotkeyManager(QObject):
    triggered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._vk = 0
        self._mod_vks = set()
        self._was_down = False
        self._hotkey_str = ""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.setInterval(150)

    @property
    def current_hotkey(self):
        return self._hotkey_str

    def parse(self, hotkey_str: str):
        parts = hotkey_str.lower().split("+")
        mods = 0
        vk = 0
        for part in parts:
            if part in _MOD_MAP:
                mods |= _MOD_MAP[part]
            elif part in _VK_TABLE:
                vk = _VK_TABLE[part]
        return mods, vk

    def register(self, hotkey_str: str, fallback: str = "ctrl+alt+s"):
        self.unregister()
        if not hotkey_str or not hotkey_str.strip():
            hotkey_str = fallback
        mods, vk = self.parse(hotkey_str)
        if not vk:
            self._hotkey_str = ""
            return False

        self._vk = vk
        self._mod_vks = set()
        if mods & MOD_CONTROL:
            self._mod_vks.add(VK_CONTROL)
        if mods & MOD_ALT:
            self._mod_vks.add(VK_MENU)
        if mods & MOD_SHIFT:
            self._mod_vks.add(VK_SHIFT)
        self._hotkey_str = hotkey_str
        self._was_down = False
        self._timer.start()
        return True

    def unregister(self):
        self._timer.stop()
        self._hotkey_str = ""
        self._vk = 0
        self._mod_vks.clear()

    def can_register(self, hotkey_str: str) -> bool:
        if hotkey_str == self._hotkey_str:
            return True
        mods, vk = self.parse(hotkey_str)
        if not vk:
            return False
        user32 = ctypes.windll.user32
        ret = user32.RegisterHotKey(None, 0, mods, vk)
        if ret:
            user32.UnregisterHotKey(None, 0)
            return True
        return False

    def _poll(self):
        user32 = ctypes.windll.user32
        for mod_vk in self._mod_vks:
            if not (user32.GetAsyncKeyState(mod_vk) & 0x8000):
                self._was_down = False
                return
        if not (user32.GetAsyncKeyState(self._vk) & 0x8000):
            self._was_down = False
            return

        if not self._was_down:
            self._was_down = True
            self.triggered.emit()
