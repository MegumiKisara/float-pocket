from PySide6.QtCore import QSize, Qt, QEvent, QPoint, QPropertyAnimation, QRect, QTimer
from PySide6.QtGui import QAction, QBitmap, QBrush, QColor, QCursor, QImage, QLinearGradient, QPainter, QPainterPath, QRadialGradient
from PySide6.QtWidgets import QApplication, QMenu, QWidget

import ctypes
import sys

from modules.settings_module import SettingsDialog

class FloatBallModule(QWidget):
    def __init__(self, config_module, ocr_module=None):
        super().__init__()
        self._config = config_module
        self._ocr_module = ocr_module
        self._dragging = False
        self._drag_offset = None
        self._suppress_dock = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)

        self.setFixedSize(60, 60)
        self._has_positioned = False
        self._settings_open = False

        # Edge adsorption state
        self._docked = False
        self._dock_edge = None
        self._expanded = False
        self._visible_pos = QPoint()
        self._hidden_pos = QPoint()

        self._hover_timer = QTimer()
        self._hover_timer.setInterval(100)
        self._hover_timer.timeout.connect(self._check_hover)

        self._dock_cooldown = False

        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(120)

        QApplication.instance().installEventFilter(self)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fb = self._config.get("float_ball", {})
        opacity = fb.get("opacity", 0.8)
        r = min(fb.get("corner_radius", 8), self.width() // 2)
        w, h = self.width(), self.height()
        rect = self.rect()

        # Build clip path for the rounded shape
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, w, h, r, r)

        # 1. Soft shadow / depth offset
        painter.save()
        painter.setClipPath(clip)
        painter.translate(2, 4)
        painter.setOpacity(opacity * 0.2)
        painter.fillRect(rect, QColor(0, 0, 0, 50))
        painter.restore()

        # 2. Main vertical gradient fill
        painter.setClipPath(clip)
        painter.setOpacity(opacity)
        gradient = QLinearGradient(0, 0, 0, h)
        gradient.setColorAt(0, QColor("#6CB4EE"))
        gradient.setColorAt(1, QColor("#3A7BD5"))
        painter.fillRect(rect, QBrush(gradient))

        # 3. Glass inner highlight (top radial glow)
        highlight = QRadialGradient(w // 2, int(h * 0.35), int(w * 0.65))
        highlight.setColorAt(0, QColor(255, 255, 255, 130))
        highlight.setColorAt(0.5, QColor(255, 255, 255, 25))
        highlight.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(rect, QBrush(highlight))

        # 4. "F" text
        painter.setClipRect(rect)
        painter.setOpacity(1.0)
        painter.setPen(QColor("white"))
        font = painter.font()
        font.setPixelSize(int(w * 0.4))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "F")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._anim.stop()
            self._suppress_dock = self._docked or self._dock_edge is not None
            if self._docked:
                self._docked = False
                self._hover_timer.stop()
                self.move(self._visible_pos)
            self._dragging = True
            self._drag_offset = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._dock_edge = None
            self._suppress_dock = False
            new_pos = self.mapToParent(event.position().toPoint()) - self._drag_offset
            self.move(new_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            menu_from_dock = self._suppress_dock
            self._snap_to_edge()
            if self._docked:
                self._hover_timer.start()
            if menu_from_dock:
                self._show_dock_menu()
            else:
                self._show_menu()

    def _show_dock_menu(self):
        menu = QMenu(self)
        ocr_action = QAction("OCR / 翻译", self)
        ocr_action.triggered.connect(self._open_ocr)
        menu.addAction(ocr_action)
        menu.addAction(QAction("计划表", self))
        menu.addAction(QAction("快捷应用", self))
        menu.addSeparator()
        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)
        menu.aboutToHide.connect(self._on_menu_closed)
        menu.exec(QCursor.pos())

    def _show_menu(self):
        menu = QMenu(self)
        ocr_action = QAction("OCR / 翻译", self)
        ocr_action.triggered.connect(self._open_ocr)
        menu.addAction(ocr_action)
        menu.addAction(QAction("计划表", self))
        menu.addAction(QAction("快捷应用", self))
        menu.addSeparator()
        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def _open_ocr(self):
        if self._ocr_module:
            self._ocr_module.show_and_capture()

    def _on_menu_closed(self):
        if not self._settings_open:
            self._docked = True
            self._dock_edge = self._dock_edge or "right"
            self._expanded = False
            self._dock_cooldown = True
            QTimer.singleShot(500, self._clear_dock_cooldown)
            self._hover_timer.start()
            self._animate_to(self._hidden_pos)

    def _open_settings(self):
        self._settings_open = True
        dialog = SettingsDialog(self._config, self)
        dialog.settings_changed.connect(self._apply_settings)
        dialog.exec()
        self._settings_open = False
        self._apply_settings()

    def _apply_settings(self):
        fb = self._config.get("float_ball", {})
        size = fb.get("size", 60)
        self.setFixedSize(size, size)
        self._remove_window_border()
        self.update()

    def _remove_window_border(self):
        if sys.platform != "win32":
            return
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32

            # Strip ALL frame/border window styles
            GWL_STYLE = -16
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            style &= ~(0x00C00000 | 0x00040000 | 0x00400000 | 0x00800000)
            style |= 0x80000000  # WS_POPUP
            user32.SetWindowLongW(hwnd, GWL_STYLE, style)

            # Extended styles: remove edge, add layered + toolwindow
            GWL_EXSTYLE = -20
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex &= ~(0x00000100 | 0x00000200 | 0x00020000)
            ex |= 0x00080000 | 0x00000080  # WS_EX_LAYERED | WS_EX_TOOLWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)

            # Refresh window frame
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0020 | 0x0002 | 0x0001 | 0x0004 | 0x0010)

            # Force layered window with per-pixel alpha via composition attribute
            class ACCENTPOLICY(ctypes.Structure):
                _fields_ = [
                    ("AccentState", ctypes.c_uint),
                    ("AccentFlags", ctypes.c_uint),
                    ("GradientColor", ctypes.c_uint),
                    ("AnimationId", ctypes.c_uint),
                ]
            class WINCOMPATTRDATA(ctypes.Structure):
                _fields_ = [
                    ("Attribute", ctypes.c_int),
                    ("Data", ctypes.POINTER(ACCENTPOLICY)),
                    ("SizeOfData", ctypes.c_size_t),
                ]
            accent = ACCENTPOLICY(4, 0, 0, 0)  # ACCENT_ENABLE_TRANSPARENTGRADIENT
            data = WINCOMPATTRDATA(19, ctypes.pointer(accent), ctypes.sizeof(ACCENTPOLICY))
            user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))

            # DWM: extend frame to hide glass/classic border
            class MARGINS(ctypes.Structure):
                _fields_ = [("cxLeftWidth", ctypes.c_int), ("cxRightWidth", ctypes.c_int),
                            ("cyTopHeight", ctypes.c_int), ("cyBottomHeight", ctypes.c_int)]
            margins = MARGINS(-1, -1, -1, -1)
            ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
        except Exception:
            pass

    def nativeEvent(self, eventType, message):
        if sys.platform == "win32" and eventType == b"windows_generic_MSG":
            try:
                msg = ctypes.wintypes.MSG.from_address(message)
                if msg.message == 0x0083:
                    return True, 0
            except Exception:
                pass
        return super().nativeEvent(eventType, message)

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_settings()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            if self.isVisible() and not self._docked and not self._settings_open and QApplication.activePopupWidget() is None:
                target = QApplication.widgetAt(event.globalPosition().toPoint())
                if target != self and not self.isAncestorOf(target):
                    self.hide()
        return super().eventFilter(obj, event)

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self._ensure_position()
            self.show()
            self.raise_()

    def _ensure_position(self):
        screen = QApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = geo.x() + geo.width() - self.width() - 10
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(int(x), int(y))

    def _snap_to_edge(self):
        if self._suppress_dock:
            self._suppress_dock = False
            return

        fb = self._config.get("float_ball", {})
        if not fb.get("edge_adsorption", True):
            return

        screen = QApplication.primaryScreen()
        geo = screen.availableGeometry()
        threshold = 30
        x, y = self.x(), self.y()
        w, h = self.width(), self.height()

        edge = None
        if x - geo.x() < threshold:
            x = geo.x()
            edge = "left"
        elif geo.x() + geo.width() - (x + w) < threshold:
            x = geo.x() + geo.width() - w
            edge = "right"

        if y - geo.y() < threshold:
            y = geo.y()
        elif geo.y() + geo.height() - (y + h) < threshold:
            y = geo.y() + geo.height() - h

        if edge:
            self._docked = True
            self._dock_edge = edge
            self._visible_pos = QPoint(x, y)
            strip = 6
            hidden_x = x - (w - strip) if edge == "left" else x + (w - strip)
            self._hidden_pos = QPoint(hidden_x, y)
            self._expanded = False
            self.move(hidden_x, y)
        else:
            self.move(x, y)

    def _clear_dock_cooldown(self):
        self._dock_cooldown = False

    def _check_hover(self):
        if self._dock_cooldown:
            return
        if not self._docked or not self.isVisible():
            self._hover_timer.stop()
            return

        margin = 40
        visible_rect = QRect(self._visible_pos, QSize(self.width(), self.height()))
        trigger_rect = visible_rect.adjusted(-margin, -margin, margin, margin)

        if trigger_rect.contains(QCursor.pos()):
            if not self._expanded:
                self._expanded = True
                self._animate_to(self._visible_pos)
        else:
            if self._expanded:
                self._expanded = False
                self._animate_to(self._hidden_pos)

    def _animate_to(self, pos):
        self._anim.stop()
        self._anim.setEndValue(pos)
        self._anim.start()
