from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
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

        self._title_edit = QLineEdit(self._task["title"])
        self._title_edit.setReadOnly(True)
        self._title_edit.setStyleSheet("border: none; background: transparent;")
        self._update_style()
        self._title_edit.returnPressed.connect(self._save_edit)
        layout.addWidget(self._title_edit, 1)

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

    def _update_style(self):
        if self._task["completed"]:
            self._title_edit.setStyleSheet(
                "border: none; background: transparent; color: #86909C; text-decoration: line-through;"  # 新增样式
            )
        else:
            self._title_edit.setStyleSheet("border: none; background: transparent;")

    def _toggle_completed(self, state):
        completed = state == Qt.CheckState.Checked.value
        self._storage.update(self._task["id"], completed=completed)
        self._task["completed"] = completed
        self._update_style()

    def _toggle_edit(self):
        if self._editing:
            self._save_edit()
        else:
            self._editing = True
            self._title_edit.setReadOnly(False)
            self._title_edit.setStyleSheet(
                "border: 1px solid #165DFF; background: white; padding: 2px 4px; border-radius: 4px;"  # 新增样式
            )
            self._title_edit.setFocus()
            self._title_edit.selectAll()
            self._edit_btn.setText("保存")

    def _save_edit(self):
        title = self._title_edit.text().strip()
        if title:
            self._storage.update(self._task["id"], title=title)
            self._task["title"] = title
        self._editing = False
        self._title_edit.setReadOnly(True)
        self._update_style()
        self._edit_btn.setText("编辑")

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
        self._clear_btn = QPushButton("清空已完成")
        self._clear_btn.setStyleSheet("background: #F0F2F5; color: #1D2129; border: none; border-radius: 8px; padding: 8px 16px; font-size: 14px;")  # 新增样式
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
