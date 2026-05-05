import ctypes
import ctypes.wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

_VK_TABLE = {
    **{chr(ord("a") + i): 0x41 + i for i in range(26)},
    **{str(i): 0x30 + i for i in range(10)},
    **{f"f{i}": 0x70 + i for i in range(1, 13)},
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


class HotkeyManager(QObject, QAbstractNativeEventFilter):
    triggered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._id = 1
        self._registered = False

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

    def register(self, hotkey_str: str):
        self.unregister()
        mods, vk = self.parse(hotkey_str)
        if not vk:
            return False
        user32 = ctypes.windll.user32
        ret = user32.RegisterHotKey(None, self._id, mods, vk)
        self._registered = bool(ret)
        return self._registered

    def unregister(self):
        if self._registered:
            ctypes.windll.user32.UnregisterHotKey(None, self._id)
            self._registered = False

    def nativeEventFilter(self, eventType, message):
        if eventType in (b"windows_generic_MSG", "windows_generic_MSG"):
            msg = ctypes.cast(message, ctypes.POINTER(ctypes.wintypes.MSG)).contents
            if msg.message == WM_HOTKEY and msg.wParam == self._id:
                self.triggered.emit()
                return True, 0
        return False, 0
