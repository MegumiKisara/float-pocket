from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from modules.settings_module import SettingsDialog

class TrayModule(QSystemTrayIcon):
    def __init__(self, app, float_ball, config_module):
        super().__init__()
        self.app = app
        self.float_ball = float_ball
        self.config = config_module

        self.setIcon(self._make_icon())
        self.menu = QMenu()  # 固定写法
        self._init_menu()

    @staticmethod
    def _make_icon():
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#4A90D9"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(4, 4, 24, 24, 6, 6)
        painter.setPen(QColor("white"))
        font = painter.font()
        font.setPixelSize(18)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "F")
        painter.end()
        return QIcon(pixmap)

    def _init_menu(self):
        self.menu.clear()

        # 调出悬浮球
        show_action = QAction("调出悬浮球", self)
        show_action.triggered.connect(self.toggle_float_ball)
        self.menu.addAction(show_action)

        # 设置
        setting_action = QAction("打开设置", self)
        setting_action.triggered.connect(self._open_settings)
        self.menu.addAction(setting_action)

        self.menu.addSeparator()

        # 退出
        quit_action = QAction("退出程序", self)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)

        self.setContextMenu(self.menu)
        self.activated.connect(self.on_activated)

    def on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.toggle_float_ball()

    def _open_settings(self):
        if not self.float_ball.isVisible():
            self.float_ball.toggle_visibility()
        self.float_ball._settings_open = True
        dialog = SettingsDialog(self.config, self.float_ball)
        dialog.settings_changed.connect(self.float_ball._apply_settings)
        dialog.exec()
        self.float_ball._settings_open = False
        self.float_ball._apply_settings()

    def toggle_float_ball(self):
        self.float_ball.toggle_visibility()