import os
import sys
from PySide6.QtCore import Qt, QLockFile
from PySide6.QtWidgets import QApplication, QMessageBox

from modules.config_module import DATA_DIR, ConfigModule, env_init
from modules.float_ball_module import FloatBallModule
from modules.app_launch_module import AppLaunchModule
from modules.hotkey_module import HotkeyManager
from modules.ocr_translate_module import OcrTranslateModule
from modules.plan_module import PlanModule
from modules.tray_module import TrayModule


class SingleInstanceGuard:
    def __init__(self):
        path = os.path.join(DATA_DIR, "instance.lock")
        self._lock = QLockFile(path)
        self._locked = self._lock.tryLock(100)
        if not self._locked:
            self._lock.removeStaleLockFile()
            self._locked = self._lock.tryLock(100)

    @property
    def ok(self):
        return self._locked

    def release(self):
        if self._locked:
            self._lock.unlock()
            self._locked = False


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    env_init()

    guard = SingleInstanceGuard()
    if not guard.ok:
        QMessageBox.warning(None, "FloatPocket", "FloatPocket 已在运行中")
        sys.exit(0)

    # Windows 托盘右键必加！！！
    app.setAttribute(Qt.AA_DontShowIconsInMenus, False)

    # ✅ Windows 去掉白边框
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings, True)

    config_module = ConfigModule()
    ocr_module = OcrTranslateModule()
    plan_module = PlanModule()
    app_launch_module = AppLaunchModule()
    hotkey_mgr = HotkeyManager()
    app.installNativeEventFilter(hotkey_mgr)
    hotkey_mgr.register(config_module.get("global_hotkey", ""))

    float_ball = FloatBallModule(config_module, ocr_module, plan_module, app_launch_module, hotkey_mgr)
    hotkey_mgr.triggered.connect(float_ball.toggle_visibility)

    tray_module = TrayModule(app, float_ball, config_module)
    tray_module.show()

    app.aboutToQuit.connect(guard.release)
    sys.exit(app.exec())