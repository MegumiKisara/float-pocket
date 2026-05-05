from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from modules.app_launch_storage import AppLaunchStorage
from modules.config_module import CONFIG_FILE, DEFAULT_CONFIG, env_get_api_key, env_set_api_key
from modules.plan_storage import PlanStorage


class _HotkeyEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("点击此处设置快捷键")

    def keyPressEvent(self, event):
        keys = []
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            keys.append("ctrl")
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            keys.append("alt")
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            keys.append("shift")
        if event.modifiers() & Qt.KeyboardModifier.MetaModifier:
            keys.append("meta")

        key = event.key()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift, Qt.Key.Key_Meta):
            return
        if key == Qt.Key.Key_Delete or key == Qt.Key.Key_Backspace:
            self.setText("")
            return
        if key in range(Qt.Key.Key_A, Qt.Key.Key_Z + 1):
            keys.append(event.text().lower())
        elif key in range(Qt.Key.Key_F1, Qt.Key.Key_F24 + 1):
            keys.append(f"f{key - Qt.Key.Key_F1 + 1}")
        else:
            return

        self.setText("+".join(keys))


class SettingsDialog(QDialog):
    settings_changed = Signal()

    def __init__(self, config_module, parent=None):
        super().__init__(parent)
        self._config = config_module
        self._app_storage = AppLaunchStorage()
        self._icon_svgs = {}
        self._icon_loading = False
        self._icon_prev_idx = 0
        self.setWindowTitle("通用设置")
        self.setFixedSize(540, 620)
        self._setup_ui()
        self._load_values()

    def showEvent(self, event):
        super().showEvent(event)
        screen = self.screen().availableGeometry()
        self.move(screen.center() - self.rect().center())

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # ── 通用 tab ─────────────────────────────────────────
        general_scroll = QScrollArea()
        general_scroll.setWidgetResizable(True)
        general_scroll.setStyleSheet("QScrollArea { border: none; }")
        general = QWidget()
        gl = QVBoxLayout(general)
        gl.setContentsMargins(0, 0, 0, 0)

        # --- 开机自启 ---
        group1 = QGroupBox("开机自启")
        gl1 = QVBoxLayout(group1)
        self._auto_start_cb = QCheckBox("开机后自动运行 FloatPocket")
        gl1.addWidget(self._auto_start_cb)
        gl.addWidget(group1)

        # --- 全局快捷键 ---
        group2 = QGroupBox("全局快捷键")
        fl2 = QFormLayout(group2)
        self._hotkey_edit = _HotkeyEdit()
        fl2.addRow("唤起悬浮球", self._hotkey_edit)
        gl.addWidget(group2)

        # --- 主题 ---
        group4 = QGroupBox("主题")
        fl4 = QFormLayout(group4)
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("浅色", "light")
        self._theme_combo.addItem("深色", "dark")
        self._theme_combo.currentIndexChanged.connect(self._apply_preview)
        fl4.addRow("主题切换", self._theme_combo)
        gl.addWidget(group4)

        gl.addStretch()
        general_scroll.setWidget(general)
        tabs.addTab(general_scroll, "通用")

        # ── 样式 tab ─────────────────────────────────────────
        style_scroll = QScrollArea()
        style_scroll.setWidgetResizable(True)
        style_scroll.setStyleSheet("QScrollArea { border: none; }")
        style_tab = QWidget()
        sl = QVBoxLayout(style_tab)
        sl.setContentsMargins(0, 0, 0, 0)

        # --- 悬浮球样式 ---
        group3 = QGroupBox("悬浮球样式")
        fl3 = QFormLayout(group3)

        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._size_slider.setRange(20, 120)
        self._size_slider.valueChanged.connect(self._apply_preview)
        fl3.addRow("大小", self._size_slider)

        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(50, 100)
        self._opacity_slider.valueChanged.connect(self._apply_preview)
        fl3.addRow("透明度", self._opacity_slider)

        self._radius_slider = QSlider(Qt.Orientation.Horizontal)
        self._radius_slider.setRange(0, 60)
        self._radius_slider.valueChanged.connect(self._apply_preview)
        fl3.addRow("圆角", self._radius_slider)

        self._edge_cb = QCheckBox("靠边时自动吸附")
        fl3.addRow("", self._edge_cb)

        sl.addWidget(group3)

        # --- 子球样式 ---
        group_child = QGroupBox("子球样式")
        fl_child = QFormLayout(group_child)

        self._child_size_slider = QSlider(Qt.Orientation.Horizontal)
        self._child_size_slider.setRange(20, 60)
        self._child_size_slider.valueChanged.connect(self._apply_preview)
        fl_child.addRow("大小", self._child_size_slider)

        self._child_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._child_opacity_slider.setRange(50, 100)
        self._child_opacity_slider.valueChanged.connect(self._apply_preview)
        fl_child.addRow("透明度", self._child_opacity_slider)

        self._child_radius_slider = QSlider(Qt.Orientation.Horizontal)
        self._child_radius_slider.setRange(0, 30)
        self._child_radius_slider.valueChanged.connect(self._apply_preview)
        fl_child.addRow("圆角", self._child_radius_slider)

        sl.addWidget(group_child)

        # --- 子球位置 ---
        group_pos = QGroupBox("子球位置")
        fl_pos = QFormLayout(group_pos)
        self._pos_sliders = []
        ball_names = ["OCR/翻译", "计划表", "快捷应用", "设置"]
        for name in ball_names:
            hbox = QHBoxLayout()

            x_slider = QSlider(Qt.Orientation.Horizontal)
            x_slider.setRange(-60, 90)
            x_label = QLabel("0")
            x_label.setFixedWidth(28)
            x_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            x_slider.valueChanged.connect(lambda v, l=x_label: l.setText(str(v)))
            x_slider.valueChanged.connect(self._apply_preview)

            y_slider = QSlider(Qt.Orientation.Horizontal)
            y_slider.setRange(-60, 100)
            y_label = QLabel("0")
            y_label.setFixedWidth(28)
            y_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            y_slider.valueChanged.connect(lambda v, l=y_label: l.setText(str(v)))
            y_slider.valueChanged.connect(self._apply_preview)

            hbox.addWidget(x_slider, 1)
            hbox.addWidget(x_label)
            hbox.addWidget(y_slider, 1)
            hbox.addWidget(y_label)
            fl_pos.addRow(name, hbox)
            self._pos_sliders.append((x_slider, y_slider))
        sl.addWidget(group_pos)

        # --- 图标 ---
        group_icons = QGroupBox("图标")
        icons_layout = QVBoxLayout(group_icons)

        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("选择球:"))
        self._icon_combo = QComboBox()
        self._icon_combo.addItem("主球", "main")
        self._icon_combo.addItem("OCR/翻译", "child_0")
        self._icon_combo.addItem("计划表", "child_1")
        self._icon_combo.addItem("快捷应用", "child_2")
        self._icon_combo.addItem("设置", "child_3")
        selector_row.addWidget(self._icon_combo, 1)
        self._icon_clear_btn = QPushButton("清空")
        self._icon_clear_btn.setFixedWidth(60)
        self._icon_clear_btn.clicked.connect(self._clear_icon)
        selector_row.addWidget(self._icon_clear_btn)
        icons_layout.addLayout(selector_row)

        self._icon_edit = QPlainTextEdit()
        self._icon_edit.setPlaceholderText("在此粘贴 SVG 代码，留空使用默认文字图标")
        self._icon_edit.setMaximumHeight(120)
        self._icon_edit.setStyleSheet("font-family: monospace; font-size: 12px;")
        self._icon_edit.textChanged.connect(self._on_icon_text_changed)
        self._icon_combo.currentIndexChanged.connect(self._on_icon_ball_changed)
        icons_layout.addWidget(self._icon_edit)

        preview_row = QHBoxLayout()
        preview_row.addWidget(QLabel("预览:"))
        self._icon_preview = QLabel()
        self._icon_preview.setFixedSize(48, 48)
        self._icon_preview.setStyleSheet("border: 1px solid #E5E6EB; border-radius: 6px; background: white;")
        preview_row.addWidget(self._icon_preview)
        preview_row.addStretch()
        icons_layout.addLayout(preview_row)

        sl.addWidget(group_icons)

        sl.addStretch()
        style_scroll.setWidget(style_tab)
        tabs.addTab(style_scroll, "样式")

        # ── API 配置 tab ──────────────────────────────────────
        api_tab = QWidget()
        al = QVBoxLayout(api_tab)
        al.setContentsMargins(0, 0, 0, 0)

        group5 = QGroupBox("API 配置（千问）")
        fl5 = QFormLayout(group5)

        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("输入 DashScope API Key")
        fl5.addRow("API Key", self._api_key_edit)

        self._toggle_key_btn = QPushButton("显示")
        self._toggle_key_btn.setFixedWidth(60)
        self._toggle_key_btn.setStyleSheet("background: #F0F2F5; color: #1D2129; border: none; border-radius: 8px; padding: 8px 16px; font-size: 14px;")  # 新增样式
        self._toggle_key_btn.clicked.connect(self._toggle_api_key_visible)
        fl5.addRow("", self._toggle_key_btn)

        hint = QLabel("API Key 保存在本地 .env 文件中，不会提交到代码仓库")
        hint.setStyleSheet("color: #86909C; font-size: 11px;")  # 新增样式
        fl5.addRow("", hint)

        al.addWidget(group5)
        al.addStretch()
        tabs.addTab(api_tab, "API 配置")

        # ── 快捷应用 tab ───────────────────────────────────────
        app_tab = QWidget()
        al2 = QVBoxLayout(app_tab)
        al2.setContentsMargins(0, 0, 0, 0)

        # --- 分类管理 ---
        cat_group = QGroupBox("分类管理")
        cat_layout = QVBoxLayout(cat_group)

        add_cat_row = QHBoxLayout()
        self._new_cat_input = QLineEdit()
        self._new_cat_input.setPlaceholderText("新分类名称...")
        add_cat_row.addWidget(self._new_cat_input, 1)
        add_cat_btn = QPushButton("新增分类")
        add_cat_btn.clicked.connect(self._add_category)
        add_cat_row.addWidget(add_cat_btn)
        cat_layout.addLayout(add_cat_row)

        cat_manage_row = QHBoxLayout()
        self._cat_combo = QComboBox()
        cat_manage_row.addWidget(self._cat_combo, 1)
        rename_cat_btn = QPushButton("重命名")
        rename_cat_btn.setStyleSheet("background: #F0F2F5; color: #1D2129; border: none; border-radius: 8px; padding: 8px 16px; font-size: 14px;")  # 新增样式
        rename_cat_btn.clicked.connect(self._rename_category)
        cat_manage_row.addWidget(rename_cat_btn)
        del_cat_btn = QPushButton("删除分类")
        del_cat_btn.setStyleSheet("background: #F0F2F5; color: #1D2129; border: none; border-radius: 8px; padding: 8px 16px; font-size: 14px;")  # 新增样式
        del_cat_btn.clicked.connect(self._delete_category)
        cat_manage_row.addWidget(del_cat_btn)
        cat_layout.addLayout(cat_manage_row)

        al2.addWidget(cat_group)

        # --- 应用管理 ---
        app_group = QGroupBox("应用管理")
        app_layout = QVBoxLayout(app_group)

        add_app_row = QHBoxLayout()
        add_app_btn = QPushButton("+ 添加应用")
        add_app_btn.clicked.connect(self._add_app)
        add_app_row.addWidget(add_app_btn)
        add_app_hint = QLabel("选择 .exe 可执行文件路径")
        add_app_hint.setStyleSheet("color: #86909C; font-size: 11px;")  # 新增样式
        add_app_row.addWidget(add_app_hint)
        add_app_row.addStretch()
        app_layout.addLayout(add_app_row)

        # Scrollable app list
        self._app_scroll = QScrollArea()
        self._app_scroll.setWidgetResizable(True)
        self._app_scroll.setStyleSheet("border: none;")
        self._app_list = QWidget()
        self._app_list_layout = QVBoxLayout(self._app_list)
        self._app_list_layout.setSpacing(4)
        self._app_list_layout.setContentsMargins(0, 0, 0, 0)
        self._app_list_layout.addStretch()
        self._app_scroll.setWidget(self._app_list)
        app_layout.addWidget(self._app_scroll, 1)

        al2.addWidget(app_group, 1)
        tabs.addTab(app_tab, "快捷应用")

        # ── 数据管理 tab ───────────────────────────────────────
        data_tab = QWidget()
        dl = QVBoxLayout(data_tab)
        dl.setContentsMargins(0, 0, 0, 0)

        group6 = QGroupBox("数据管理")
        gl6 = QVBoxLayout(group6)

        self._clear_plans_btn = QPushButton("清空所有待办")
        self._clear_plans_btn.setStyleSheet("background: #F0F2F5; color: #1D2129; border: none; border-radius: 8px; padding: 8px 16px; font-size: 14px;")  # 新增样式
        self._clear_plans_btn.clicked.connect(self._clear_all_plans)
        gl6.addWidget(self._clear_plans_btn)

        self._reset_config_btn = QPushButton("重置所有配置为默认值")
        self._reset_config_btn.setStyleSheet("background: #F0F2F5; color: #1D2129; border: none; border-radius: 8px; padding: 8px 16px; font-size: 14px;")  # 新增样式
        self._reset_config_btn.clicked.connect(self._reset_all_config)
        gl6.addWidget(self._reset_config_btn)

        dl.addWidget(group6)
        dl.addStretch()
        tabs.addTab(data_tab, "数据管理")

        # ── 统一样式 ─────────────────────────────────────────
        self.setStyleSheet("""
            SettingsDialog {
                background-color: #F5F6F8;
            }
            QGroupBox {
                background-color: #FFFFFF;
                border: 1px solid #E5E6EB;
                border-radius: 8px;
                margin-top: 12px;
                padding: 16px 12px 12px 12px;
                font-size: 14px;
                font-weight: bold;
                color: #1D2129;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 8px;
                color: #1D2129;
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
            QLineEdit[readOnly="true"] {
                background-color: #F5F6F8;
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
            QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #E5E6EB;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
                color: #1D2129;
            }
            QComboBox:focus {
                border: 1px solid #165DFF;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 1px solid #E5E6EB;
                border-radius: 4px;
                selection-background-color: #E8F0FE;
                selection-color: #165DFF;
            }
            QTabWidget::pane {
                background-color: #FFFFFF;
                border: 1px solid #E5E6EB;
                border-radius: 8px;
                padding: 8px;
            }
            QTabBar::tab {
                background-color: #F0F2F5;
                color: #1D2129;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                margin-right: 4px;
                font-size: 14px;
            }
            QTabBar::tab:selected {
                background-color: #E8F0FE;
                color: #165DFF;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background-color: #E5E6EB;
            }
            QScrollArea {
                border: none;
            }
            QCheckBox {
                font-size: 14px;
                color: #1D2129;
                spacing: 6px;
            }
            QSlider::groove:horizontal {
                border: none;
                height: 6px;
                background: #E5E6EB;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #165DFF;
                border: none;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #3A7BD5;
            }
            QDialogButtonBox QPushButton {
                background-color: #F0F2F5;
                color: #1D2129;
            }
            QDialogButtonBox QPushButton:hover {
                background-color: #E5E6EB;
            }
        """)

        # --- 按钮 ---
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _load_values(self):
        fb = self._config.get("float_ball", {})
        self._size_slider.blockSignals(True)
        self._size_slider.setValue(fb.get("size", 60))
        self._size_slider.blockSignals(False)

        self._opacity_slider.blockSignals(True)
        self._opacity_slider.setValue(int(fb.get("opacity", 0.8) * 100))
        self._opacity_slider.blockSignals(False)

        self._radius_slider.blockSignals(True)
        self._radius_slider.setValue(fb.get("corner_radius", 8))
        self._radius_slider.blockSignals(False)

        cb = fb.get("child_ball", {})
        self._child_size_slider.blockSignals(True)
        self._child_size_slider.setValue(cb.get("size", 36))
        self._child_size_slider.blockSignals(False)

        self._child_opacity_slider.blockSignals(True)
        self._child_opacity_slider.setValue(int(cb.get("opacity", 0.85) * 100))
        self._child_opacity_slider.blockSignals(False)

        self._child_radius_slider.blockSignals(True)
        self._child_radius_slider.setValue(cb.get("corner_radius", 18))
        self._child_radius_slider.blockSignals(False)

        positions = fb.get("ball_positions", [])
        for i, (x_slider, y_slider) in enumerate(self._pos_sliders):
            x_slider.blockSignals(True)
            y_slider.blockSignals(True)
            if i < len(positions):
                x_slider.setValue(positions[i].get("dx", 0))
                y_slider.setValue(positions[i].get("dy", 0))
            else:
                x_slider.setValue(0)
                y_slider.setValue(0)
            x_slider.blockSignals(False)
            y_slider.blockSignals(False)

        self._icon_svgs = dict(fb.get("icons", {}))
        self._icon_loading = True
        self._icon_combo.setCurrentIndex(0)
        self._icon_edit.setPlainText(self._icon_svgs.get("main", ""))
        self._icon_loading = False
        self._update_icon_preview()

        self._edge_cb.blockSignals(True)
        self._edge_cb.setChecked(fb.get("edge_adsorption", True))
        self._edge_cb.blockSignals(False)

        self._auto_start_cb.blockSignals(True)
        self._auto_start_cb.setChecked(self._config.get("auto_start", False))
        self._auto_start_cb.blockSignals(False)

        self._hotkey_edit.setText(self._config.get("global_hotkey", "ctrl+alt+s"))

        self._theme_combo.blockSignals(True)
        themes = {"light": 0, "dark": 1}
        self._theme_combo.setCurrentIndex(themes.get(self._config.get("theme", "light"), 0))
        self._theme_combo.blockSignals(False)

        self._api_key_edit.setText(env_get_api_key())
        self._refresh_app_tab()

    def _toggle_api_key_visible(self):
        if self._api_key_edit.echoMode() == QLineEdit.EchoMode.Password:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._toggle_key_btn.setText("隐藏")
        else:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._toggle_key_btn.setText("显示")

    def _on_icon_ball_changed(self, idx):
        if self._icon_loading:
            return
        prev_key = self._icon_combo.itemData(getattr(self, "_icon_prev_idx", 0))
        self._icon_svgs[prev_key] = self._icon_edit.toPlainText()
        key = self._icon_combo.itemData(idx)
        self._icon_edit.blockSignals(True)
        self._icon_edit.setPlainText(self._icon_svgs.get(key, ""))
        self._icon_edit.blockSignals(False)
        self._icon_prev_idx = idx
        self._update_icon_preview()

    def _on_icon_text_changed(self):
        if self._icon_loading:
            return
        key = self._icon_combo.currentData()
        self._icon_svgs[key] = self._icon_edit.toPlainText()
        self._update_icon_preview()
        self._apply_preview()

    def _clear_icon(self):
        self._icon_edit.clear()

    def _update_icon_preview(self):
        svg = self._icon_edit.toPlainText()
        if svg:
            try:
                from PySide6.QtCore import QByteArray
                from PySide6.QtGui import QPixmap, QPainter
                from PySide6.QtSvg import QSvgRenderer
                renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
                pixmap = QPixmap(48, 48)
                pixmap.fill(Qt.GlobalColor.transparent)
                p = QPainter(pixmap)
                renderer.render(p)
                p.end()
                self._icon_preview.setPixmap(pixmap)
            except Exception:
                self._icon_preview.clear()
        else:
            self._icon_preview.clear()

    def _apply_preview(self):
        self._config.set_preview("theme", self._theme_combo.currentData())
        cb = {
                "size": self._child_size_slider.value(),
                "opacity": self._child_opacity_slider.value() / 100.0,
                "corner_radius": self._child_radius_slider.value(),
            }
        self._icon_svgs[self._icon_combo.currentData()] = self._icon_edit.toPlainText()
        fb = {
            "size": self._size_slider.value(),
            "opacity": self._opacity_slider.value() / 100.0,
            "corner_radius": self._radius_slider.value(),
            "edge_adsorption": self._edge_cb.isChecked(),
            "child_ball": cb,
            "ball_positions": [
                {"dx": s[0].value(), "dy": s[1].value()}
                for s in self._pos_sliders
            ],
            "icons": dict(self._icon_svgs),
        }
        self._config.set_preview("float_ball", fb)
        self.settings_changed.emit()

    def accept(self):
        self._config.set("auto_start", self._auto_start_cb.isChecked())
        self._config.set("global_hotkey", self._hotkey_edit.text())
        self._config.set("theme", self._theme_combo.currentData())
        cb = {
            "size": self._child_size_slider.value(),
            "opacity": self._child_opacity_slider.value() / 100.0,
            "corner_radius": self._child_radius_slider.value(),
        }
        self._icon_svgs[self._icon_combo.currentData()] = self._icon_edit.toPlainText()
        fb = {
            "size": self._size_slider.value(),
            "opacity": self._opacity_slider.value() / 100.0,
            "corner_radius": self._radius_slider.value(),
            "edge_adsorption": self._edge_cb.isChecked(),
            "child_ball": cb,
            "ball_positions": [
                {"dx": s[0].value(), "dy": s[1].value()}
                for s in self._pos_sliders
            ],
            "icons": dict(self._icon_svgs),
        }
        self._config.set("float_ball", fb)
        self._apply_auto_start(self._auto_start_cb.isChecked())
        api_key = self._api_key_edit.text().strip()
        if api_key:
            env_set_api_key(api_key)
        super().accept()

    def reject(self):
        self._config.reload()
        self._load_values()
        self._apply_preview()
        super().reject()

    # ── data management ─────────────────────────────────────

    def _clear_all_plans(self):
        reply = QMessageBox.question(
            self, "确认", "确定要清空所有待办事项吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            PlanStorage().clear_all()
            QMessageBox.information(self, "完成", "所有待办已清空")

    def _reset_all_config(self):
        reply = QMessageBox.warning(
            self, "确认重置",
            "确定要重置所有配置为默认值吗？\n此操作不可撤销，API Key 等信息将被清除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            import os
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)
            self._config.reload()
            self._load_values()
            self._apply_preview()
            QMessageBox.information(self, "完成", "所有配置已重置为默认值")

    # ── app management tab ──────────────────────────────────

    def _refresh_app_tab(self):
        # Refresh category combo
        self._cat_combo.blockSignals(True)
        self._cat_combo.clear()
        for cat in self._app_storage.get_categories():
            self._cat_combo.addItem(cat["name"], cat["id"])

        # Get index of "默认未分类" and set it
        default_idx = self._cat_combo.findData("default")
        if default_idx >= 0:
            self._cat_combo.setCurrentIndex(default_idx)
        self._cat_combo.blockSignals(False)

        # Refresh app list
        while self._app_list_layout.count() > 1:
            item = self._app_list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        for app in self._app_storage.get_apps():
            self._add_app_row(app)

    def _add_app_row(self, app):
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(4, 2, 4, 2)
        rl.setSpacing(6)

        name_label = QLabel(app["name"])
        name_label.setMinimumWidth(80)
        rl.addWidget(name_label)

        path_label = QLabel(app["path"])
        path_label.setStyleSheet("color: #86909C; font-size: 11px;")  # 新增样式
        path_label.setWordWrap(True)
        rl.addWidget(path_label, 1)

        cat_combo = QComboBox()
        for cat in self._app_storage.get_categories():
            cat_combo.addItem(cat["name"], cat["id"])
        cat_combo.setCurrentIndex(cat_combo.findData(app.get("category_id", "default")))
        cat_combo.currentIndexChanged.connect(
            lambda idx, aid=app["id"], cb=cat_combo: self._change_app_category(aid, cb.currentData())
        )
        rl.addWidget(cat_combo)

        edit_btn = QPushButton("编辑")
        edit_btn.setFixedWidth(60)
        edit_btn.setStyleSheet("background: #F0F2F5; color: #1D2129; border: none; border-radius: 8px; padding: 8px 16px; font-size: 14px;")  # 新增样式
        edit_btn.clicked.connect(lambda checked, a=app: self._edit_app(a))
        rl.addWidget(edit_btn)

        del_btn = QPushButton("×")
        del_btn.setFixedWidth(28)
        del_btn.setStyleSheet("background: #F0F2F5; color: #1D2129; border: none; border-radius: 8px; padding: 8px 12px; font-size: 14px;")  # 新增样式
        del_btn.clicked.connect(lambda checked, a=app: self._delete_app(a))
        rl.addWidget(del_btn)

        self._app_list_layout.insertWidget(self._app_list_layout.count() - 1, row)

    def _add_category(self):
        name = self._new_cat_input.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入分类名称")
            return
        self._app_storage.add_category(name)
        self._new_cat_input.clear()
        self._refresh_app_tab()

    def _rename_category(self):
        name, ok = QInputDialog.getText(self, "重命名分类", "新名称：")
        if ok and name.strip():
            cat_id = self._cat_combo.currentData()
            if cat_id:
                self._app_storage.rename_category(cat_id, name.strip())
                self._refresh_app_tab()

    def _delete_category(self):
        cat_id = self._cat_combo.currentData()
        if not cat_id or cat_id == "default":
            QMessageBox.warning(self, "提示", "默认分类无法删除")
            return
        if self._app_storage.has_apps_in_category(cat_id):
            reply = QMessageBox.question(
                self, "确认",
                "该分类下有应用，删除后应用将移至「默认未分类」。继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._app_storage.delete_category(cat_id)
        self._refresh_app_tab()

    def _add_app(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择应用程序", "", "程序 (*.exe);;所有文件 (*)"
        )
        if not path:
            return
        import os
        default_name = os.path.splitext(os.path.basename(path))[0]
        name, ok = QInputDialog.getText(self, "应用别名", "显示名称：", text=default_name)
        if not ok or not name.strip():
            return
        self._app_storage.add_app(name.strip(), path)
        self._refresh_app_tab()

    def _edit_app(self, app):
        name, ok = QInputDialog.getText(self, "编辑别名", "显示名称：", text=app["name"])
        if ok and name.strip():
            path, ok2 = QInputDialog.getText(self, "编辑路径", "路径：", text=app["path"])
            if ok2 and path.strip():
                self._app_storage.update_app(app["id"], name=name.strip(), path=path.strip())
                self._refresh_app_tab()

    def _delete_app(self, app):
        reply = QMessageBox.question(
            self, "确认删除", f"删除「{app['name']}」？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._app_storage.delete_app(app["id"])
            self._refresh_app_tab()

    def _change_app_category(self, app_id, cat_id):
        self._app_storage.update_app(app_id, category_id=cat_id)

    @staticmethod
    def _apply_auto_start(enabled):
        import os
        import sys
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as k:
                if enabled:
                    exe = sys.executable
                    # Prefer pythonw.exe to avoid console window on startup
                    if exe.endswith("python.exe"):
                        pyw = exe[:-4] + "w.exe"
                        if os.path.exists(pyw):
                            exe = pyw
                    script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
                    winreg.SetValueEx(k, "FloatPocket", 0, winreg.REG_SZ,
                                      f'"{exe}" "{script}"')
                else:
                    try:
                        winreg.DeleteValue(k, "FloatPocket")
                    except FileNotFoundError:
                        pass
        except Exception:
            pass
