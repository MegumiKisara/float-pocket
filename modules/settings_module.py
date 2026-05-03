from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

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
        self.setWindowTitle("通用设置")
        self.setMinimumWidth(380)
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

        gl.addWidget(group3)

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
        tabs.addTab(general, "通用")

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
        self._toggle_key_btn.setFixedWidth(50)
        self._toggle_key_btn.clicked.connect(self._toggle_api_key_visible)
        fl5.addRow("", self._toggle_key_btn)

        hint = QLabel("API Key 保存在本地 .env 文件中，不会提交到代码仓库")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        fl5.addRow("", hint)

        al.addWidget(group5)
        al.addStretch()
        tabs.addTab(api_tab, "API 配置")

        # ── 数据管理 tab ───────────────────────────────────────
        data_tab = QWidget()
        dl = QVBoxLayout(data_tab)
        dl.setContentsMargins(0, 0, 0, 0)

        group6 = QGroupBox("数据管理")
        gl6 = QVBoxLayout(group6)

        self._clear_plans_btn = QPushButton("清空所有待办")
        self._clear_plans_btn.clicked.connect(self._clear_all_plans)
        gl6.addWidget(self._clear_plans_btn)

        self._reset_config_btn = QPushButton("重置所有配置为默认值")
        self._reset_config_btn.clicked.connect(self._reset_all_config)
        gl6.addWidget(self._reset_config_btn)

        dl.addWidget(group6)
        dl.addStretch()
        tabs.addTab(data_tab, "数据管理")

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

    def _toggle_api_key_visible(self):
        if self._api_key_edit.echoMode() == QLineEdit.EchoMode.Password:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._toggle_key_btn.setText("隐藏")
        else:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._toggle_key_btn.setText("显示")

    def _apply_preview(self):
        self._config.set_preview("theme", self._theme_combo.currentData())
        fb = {
            "size": self._size_slider.value(),
            "opacity": self._opacity_slider.value() / 100.0,
            "corner_radius": self._radius_slider.value(),
            "edge_adsorption": self._edge_cb.isChecked(),
        }
        self._config.set_preview("float_ball", fb)
        self.settings_changed.emit()

    def accept(self):
        self._config.set("auto_start", self._auto_start_cb.isChecked())
        self._config.set("global_hotkey", self._hotkey_edit.text())
        self._config.set("theme", self._theme_combo.currentData())
        fb = {
            "size": self._size_slider.value(),
            "opacity": self._opacity_slider.value() / 100.0,
            "corner_radius": self._radius_slider.value(),
            "edge_adsorption": self._edge_cb.isChecked(),
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
            None, "确认", "确定要清空所有待办事项吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            PlanStorage().clear_all()
            QMessageBox.information(None, "完成", "所有待办已清空")

    def _reset_all_config(self):
        reply = QMessageBox.warning(
            None, "确认重置",
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
            QMessageBox.information(None, "完成", "所有配置已重置为默认值")

    @staticmethod
    def _apply_auto_start(enabled):
        import sys
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as k:
                if enabled:
                    exe_path = sys.executable
                    if exe_path.endswith("pythonw.exe"):
                        script = __file__.rsplit("modules", 1)[0]
                        winreg.SetValueEx(k, "FloatPocket", 0, winreg.REG_SZ, f'"{exe_path}" "{script}main.py"')
                    else:
                        winreg.SetValueEx(k, "FloatPocket", 0, winreg.REG_SZ, exe_path)
                else:
                    try:
                        winreg.DeleteValue(k, "FloatPocket")
                    except FileNotFoundError:
                        pass
        except Exception:
            pass
