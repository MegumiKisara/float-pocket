from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.plan_storage import PlanStorage


class _TaskItem(QWidget):
    def __init__(self, task, storage: PlanStorage, refresh_callback):
        super().__init__()
        self._task = task
        self._storage = storage
        self._refresh = refresh_callback
        self._editing = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        self._checkbox = QCheckBox()
        self._checkbox.setChecked(self._task["completed"])
        self._checkbox.stateChanged.connect(self._toggle_completed)
        layout.addWidget(self._checkbox)

        self._title_display = QLabel(self._task["title"])
        self._title_display.setWordWrap(True)
        self._update_display_style()
        layout.addWidget(self._title_display, 1)

        self._edit_btn = QPushButton("编辑")
        self._edit_btn.setFixedWidth(60)  # 加宽以完整显示"编辑"/"保存"文字
        self._edit_btn.setStyleSheet("background: #F0F2F5; color: #1D2129; border: none; border-radius: 8px; padding: 8px 16px; font-size: 14px;")  # 新增样式
        self._edit_btn.clicked.connect(self._toggle_edit)
        layout.addWidget(self._edit_btn)

        self._delete_btn = QPushButton("×")
        self._delete_btn.setFixedWidth(28)
        self._delete_btn.setStyleSheet("background: #F0F2F5; color: #1D2129; border: none; border-radius: 8px; padding: 8px 12px; font-size: 14px;")  # 新增样式
        self._delete_btn.clicked.connect(self._delete_task)
        layout.addWidget(self._delete_btn)

    def _update_display_style(self):
        if self._task["completed"]:
            self._title_display.setStyleSheet(
                "border: none; background: transparent; color: #86909C; font-size: 14px;"  # 新增样式
            )
            font = self._title_display.font()
            font.setStrikeOut(True)
            self._title_display.setFont(font)
        else:
            self._title_display.setStyleSheet("border: none; background: transparent; color: #1D2129; font-size: 14px;")
            font = self._title_display.font()
            font.setStrikeOut(False)
            self._title_display.setFont(font)

    def _toggle_completed(self, state):
        completed = state == Qt.CheckState.Checked.value
        self._storage.update(self._task["id"], completed=completed)
        self._task["completed"] = completed
        self._update_display_style()

    def _toggle_edit(self):
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, "编辑待办", "内容：", text=self._task["title"])
        if ok and text.strip():
            self._storage.update(self._task["id"], title=text.strip())
            self._task["title"] = text.strip()
            self._title_display.setText(text.strip())

    def _delete_task(self):
        reply = QMessageBox.question(
            self.window(), "确认删除", f"删除「{self._task['title']}」？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._storage.delete(self._task["id"])
            self._refresh()


class PlanModule(QWidget):
    def __init__(self):
        super().__init__()
        self._storage = PlanStorage()
        self._pinned = False

        self.setWindowTitle("计划表")
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
        self._refresh_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # ── Pin toggle (title bar area) ──────────────────────
        top_row = QHBoxLayout()
        top_row.addStretch()
        self._pin_btn = QPushButton("📌 置顶")
        self._pin_btn.setCheckable(True)
        self._pin_btn.clicked.connect(self._toggle_pin)
        self._pin_btn.setStyleSheet("font-size: 12px; background: #F0F2F5; color: #1D2129; border: none; border-radius: 8px; padding: 8px 16px;")  # 新增样式
        top_row.addWidget(self._pin_btn)
        layout.addLayout(top_row)

        # ── Add task area ────────────────────────────────────
        add_row = QHBoxLayout()
        self._add_input = QLineEdit()
        self._add_input.setPlaceholderText("输入新待办事项...")
        self._add_input.returnPressed.connect(self._add_task)
        add_row.addWidget(self._add_input, 1)

        self._add_btn = QPushButton("+ 新增")
        self._add_btn.clicked.connect(self._add_task)
        add_row.addWidget(self._add_btn)
        layout.addLayout(add_row)

        # ── Task list (scrollable) ───────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("border: none;")

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setSpacing(2)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._list_widget)
        layout.addWidget(self._scroll, 1)

        # ── Bottom actions ───────────────────────────────────
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        self._clear_all_btn = QPushButton("清空所有")
        self._clear_all_btn.setStyleSheet("""
            QPushButton { background: #F37373; color: #FFFFFF; border: none; border-radius: 8px; padding: 8px 16px; font-size: 14px; }
            QPushButton:hover { background: #E06060; }
            QPushButton:pressed { background: #CC5050; }
        """)
        self._clear_all_btn.clicked.connect(self._clear_all)
        bottom_row.addWidget(self._clear_all_btn)

        self._clear_btn = QPushButton("清空已完成")
        self._clear_btn.setStyleSheet("""
            QPushButton { background: #F0F2F5; color: #1D2129; border: none; border-radius: 8px; padding: 8px 16px; font-size: 14px; }
            QPushButton:hover { background: #E5E6EB; }
            QPushButton:pressed { background: #D5D7DD; }
        """)
        self._clear_btn.clicked.connect(self._clear_completed)
        bottom_row.addWidget(self._clear_btn)
        layout.addLayout(bottom_row)

        # ── 统一样式 ─────────────────────────────────────────
        self.setStyleSheet("""
            PlanModule {
                background-color: #F5F6F8;
            }
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #E5E6EB;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
                color: #1D2129;
            }
            QLineEdit:focus {
                border: 1px solid #165DFF;
            }
            QPushButton {
                background-color: #E8F0FE;
                color: #165DFF;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #DCE8FF;
            }
            QPushButton:pressed {
                background-color: #C9DCFA;
            }
            QPushButton:disabled {
                background-color: #F0F2F5;
                color: #C9CDD4;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

    # ── public ────────────────────────────────────────────────

    def show_and_capture(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self._refresh_list()

    # ── pin toggle ────────────────────────────────────────────

    _BASE_FLAGS = (
        Qt.WindowType.Window
        | Qt.WindowType.WindowCloseButtonHint
        | Qt.WindowType.WindowTitleHint
        | Qt.WindowType.WindowSystemMenuHint
        | Qt.WindowType.WindowMinimizeButtonHint
    )

    def _toggle_pin(self):
        self._pinned = self._pin_btn.isChecked()
        flags = self._BASE_FLAGS
        if self._pinned:
            flags |= Qt.WindowType.WindowStaysOnTopHint
            self._pin_btn.setText("📌 已置顶")
        else:
            self._pin_btn.setText("📌 置顶")
        self.setWindowFlags(flags)
        self.show()

    # ── task operations ───────────────────────────────────────

    def _add_task(self):
        title = self._add_input.text().strip()
        if not title:
            return
        self._storage.add(title)
        self._add_input.clear()
        self._refresh_list()

    def _clear_all(self):
        reply = QMessageBox.question(
            self, "确认", "确定要清空所有待办事项吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._storage.clear_all()
            self._refresh_list()

    def _clear_completed(self):
        reply = QMessageBox.question(
            self, "确认", "清空所有已完成待办？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._storage.clear_completed()
            self._refresh_list()

    def _refresh_list(self):
        # Remove all widgets except the trailing stretch
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        tasks = self._storage.get_all()
        for task in tasks:
            item = _TaskItem(task, self._storage, self._refresh_list)
            self._list_layout.insertWidget(self._list_layout.count() - 1, item)
