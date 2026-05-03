import sys
from PySide6.QtCore import Qt  # 必须加
from PySide6.QtWidgets import QApplication

from modules.config_module import ConfigModule
from modules.float_ball_module import FloatBallModule
from modules.tray_module import TrayModule

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Windows 托盘右键必加！！！
    app.setAttribute(Qt.AA_DontShowIconsInMenus, False)

    # ✅ Windows 去掉白边框
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings, True)

    config_module = ConfigModule()
    float_ball = FloatBallModule(config_module)
    tray_module = TrayModule(app, float_ball, config_module)
    tray_module.show()

    sys.exit(app.exec())