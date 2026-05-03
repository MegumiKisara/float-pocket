import subprocess

from PySide6.QtCore import QFileInfo, QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFileIconProvider,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from modules.app_launch_storage import AppLaunchStorage


class AppLaunchModule(QWidget):
    def __init__(self):
        super().__init__()
        self._storage = AppLaunchStorage()
        self._grouped = True

        self.setWindowTitle("快捷应用")
        self.setMinimumSize(420, 400)
        self.resize(420, 450)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # ── Mode toggle ──────────────────────────────────────
        top_row = QHBoxLayout()
        top_row.addStretch()
        self._mode_btn = QPushButton("全部不分类")
        self._mode_btn.setCheckable(False)
        self._mode_btn.clicked.connect(self._toggle_mode)
        self._mode_btn.setStyleSheet("font-size: 12px;")
        top_row.addWidget(self._mode_btn)
        layout.addLayout(top_row)

        # ── Scrollable content ───────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("border: none;")

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setSpacing(8)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.addStretch()

        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll, 1)

    # ── public ────────────────────────────────────────────────

    def show_and_capture(self):
        self._refresh()
        self.show()
        self.raise_()
        self.activateWindow()

    # ── mode ──────────────────────────────────────────────────

    def _toggle_mode(self):
        self._grouped = not self._grouped
        self._mode_btn.setText("分类展示" if not self._grouped else "全部不分类")
        self._refresh()

    # ── render ────────────────────────────────────────────────

    def _refresh(self):
        self._storage.reload()
        # Clear all widgets except trailing stretch
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if self._grouped:
            self._render_grouped()
        else:
            self._render_flat()

    def _render_grouped(self):
        by_cat = self._storage.get_apps_by_category()
        for cat_id, group in by_cat.items():
            cat = group["category"]
            apps = group["apps"]
            if not apps:
                continue

            title = QLabel(cat["name"])
            title.setStyleSheet("font-weight: bold; font-size: 13px; padding: 4px 0;")
            self._content_layout.insertWidget(self._content_layout.count() - 1, title)

            for app in apps:
                self._add_app_button(app)

    def _render_flat(self):
        for app in self._storage.get_apps():
            self._add_app_button(app)

    def _add_app_button(self, app):
        btn = QPushButton(app["name"])
        info = QFileInfo(app["path"])
        if info.exists():
            provider = QFileIconProvider()
            icon = provider.icon(info)
            btn.setIcon(icon)
            btn.setIconSize(QSize(24, 24))
        btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px 12px;
                font-size: 13px;
                border: 1px solid transparent;
                border-radius: 4px;
            }
            QPushButton:hover {
                border: 1px solid #aaa;
                background: #f0f0f0;
            }
            QPushButton:pressed {
                background: #e0e0e0;
            }
        """)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda checked, a=app: self._launch_app(a))
        self._content_layout.insertWidget(self._content_layout.count() - 1, btn)

    # ── launch ────────────────────────────────────────────────

    def _launch_app(self, app):
        try:
            subprocess.Popen(app["path"], shell=True)
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"无法启动 {app['name']}：\n{e}")
            return
        self.close()
