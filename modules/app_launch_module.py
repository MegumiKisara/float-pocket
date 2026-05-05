import subprocess

from PySide6.QtCore import QFileInfo, Qt
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


class _AppItem(QWidget):
    def __init__(self, app, storage):
        super().__init__()
        self._app = app
        self._storage = storage
        self.setFixedSize(80, 80)
        self.setObjectName("AppItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(4)
        layout.setContentsMargins(4, 4, 4, 4)

        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info = QFileInfo(self._app["path"])
        if info.exists():
            provider = QFileIconProvider()
            icon = provider.icon(info)
            pixmap = icon.pixmap(36, 36)
            self._icon_label.setPixmap(pixmap)
        layout.addWidget(self._icon_label)

        self._name_label = QLabel(self._app["name"])
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setWordWrap(True)
        self._name_label.setMaximumWidth(72)
        self._name_label.setStyleSheet(
            "font-size: 11px; color: #1D2129; border: none; background: transparent;"
        )
        self._name_label.hide()
        layout.addWidget(self._name_label)

        self._update_style(False)

    def _update_style(self, hovered):
        if hovered:
            self.setStyleSheet("""
                #AppItem {
                    background-color: #F5F7FA;
                    border: 1px solid #165DFF;
                    border-radius: 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                #AppItem {
                    background-color: #FFFFFF;
                    border: 1px solid #E5E6EB;
                    border-radius: 8px;
                }
            """)

    def enterEvent(self, event):
        self._name_label.show()
        self._update_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._name_label.hide()
        self._update_style(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._launch_app()

    def _launch_app(self):
        try:
            subprocess.Popen(self._app["path"], shell=True)
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"无法启动 {self._app['name']}：\n{e}")
            return
        self.window().close()


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
        self._mode_btn.setStyleSheet("font-size: 12px; background: #F0F2F5; color: #1D2129; border: none; border-radius: 8px; padding: 8px 16px;")  # 新增样式
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

        # ── 统一样式 ─────────────────────────────────────────
        self.setStyleSheet("""
            AppLaunchModule {
                background-color: #F5F6F8;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

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

            self._add_app_grid(apps)

    def _render_flat(self):
        self._add_app_grid(self._storage.get_apps())

    def _add_app_grid(self, apps):
        items_per_row = 4
        for i in range(0, len(apps), items_per_row):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setSpacing(8)
            row_layout.setContentsMargins(0, 0, 0, 0)
            for app in apps[i:i + items_per_row]:
                item = _AppItem(app, self._storage)
                row_layout.addWidget(item)
            row_layout.addStretch()
            self._content_layout.insertWidget(self._content_layout.count() - 1, row)

    # ── launch ────────────────────────────────────────────────

    def _launch_app(self, app):
        try:
            subprocess.Popen(app["path"], shell=True)
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"无法启动 {app['name']}：\n{e}")
            return
        self.close()
