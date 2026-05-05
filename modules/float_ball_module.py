from PySide6.QtCore import QSize, Qt, QEvent, QPoint, QPropertyAnimation, QRect, QTimer
from PySide6.QtGui import QAction, QBitmap, QBrush, QColor, QCursor, QImage, QLinearGradient, QPainter, QPainterPath, QRadialGradient
from PySide6.QtWidgets import QApplication, QMenu, QWidget

import ctypes
import sys
import time

from modules.settings_module import SettingsDialog

_EXPANDED_SIZE = 150
_BIG_BALL_RECT = QRect(25, 45, 60, 60)

_BALL_ITEMS = [
    ("OCR / 翻译", "O",  QRect(44, 10, 36, 36)),
    ("计划表",     "计", QRect(68, 28, 36, 36)),
    ("快捷应用",   "快", QRect(76, 66, 36, 36)),
    ("设置",       "设", QRect(62, 92, 36, 36)),
]


class FloatBallModule(QWidget):
    def __init__(self, config_module, ocr_module=None, plan_module=None, app_launch_module=None):
        super().__init__()
        self._config = config_module
        self._ocr_module = ocr_module
        self._plan_module = plan_module
        self._app_launch_module = app_launch_module
        self._dragging = False
        self._drag_offset = None
        self._suppress_dock = False
        self._was_drag = False
        self._press_time = 0.0
        self._expanded_drag = False
        self._drag_global_offset = QPoint()
        self._show_balls = False
        self._orig_pos = QPoint()
        self._orig_size = QSize(60, 60)

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

        w, h = self.width(), self.height()

        if not self._show_balls:
            self._draw_ball(painter, 0, 0, w, h, None)
        else:
            # Fill entire area with near-invisible color so Windows doesn't
            # pass clicks through transparent pixels (WS_EX_LAYERED per-pixel alpha)
            painter.fillRect(0, 0, w, h, QColor(0, 0, 0, 1))

            self._draw_ball(painter, _BIG_BALL_RECT.x(), _BIG_BALL_RECT.y(),
                            _BIG_BALL_RECT.width(), _BIG_BALL_RECT.height(), None)

            cb = self._config.get("float_ball", {}).get("child_ball", {})
            child_size = cb.get("size", 36)
            child_opacity = cb.get("opacity", 0.85)
            child_radius = min(cb.get("corner_radius", 18), child_size // 2)

            for _, char, rect in _BALL_ITEMS:
                self._draw_ball(painter, rect.x(), rect.y(),
                                child_size, child_size,
                                (char, child_opacity, child_radius))

    def _draw_ball(self, painter, x, y, w, h, overlay=None):
        fb = self._config.get("float_ball", {})
        opacity = fb.get("opacity", 0.8)
        r = min(fb.get("corner_radius", 8), w // 2)
        rect = QRect(x, y, w, h)

        cb = self._config.get("float_ball", {}).get("child_ball", {})
        child_radius = min(cb.get("corner_radius", 18), w // 2)

        if overlay:
            opacity = overlay[1]
            r = overlay[2]

        # Clip path
        clip = QPainterPath()
        clip.addRoundedRect(x, y, w, h, r, r)

        # 1. Shadow
        painter.save()
        painter.setClipPath(clip)
        painter.translate(2, 4)
        painter.setOpacity(opacity * 0.2)
        painter.fillRect(QRect(x, y, w, h), QColor(0, 0, 0, 50))
        painter.restore()

        # 2. Gradient fill
        painter.setClipPath(clip)
        painter.setOpacity(opacity)
        gradient = QLinearGradient(x, y, x, y + h)
        gradient.setColorAt(0, QColor("#6CB4EE"))
        gradient.setColorAt(1, QColor("#3A7BD5"))
        painter.fillRect(QRect(x, y, w, h), QBrush(gradient))

        # 3. Highlight
        highlight = QRadialGradient(x + w // 2, y + int(h * 0.35), int(w * 0.65))
        highlight.setColorAt(0, QColor(255, 255, 255, 130))
        highlight.setColorAt(0.5, QColor(255, 255, 255, 25))
        highlight.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(QRect(x, y, w, h), QBrush(highlight))

        if overlay:
            # 4. Character text for child balls
            char = overlay[0]
            painter.setClipRect(QRect(x, y, w, h))
            painter.setOpacity(1.0)
            painter.setPen(QColor("white"))
            font = painter.font()
            font.setPixelSize(int(w * 0.5))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRect(x, y, w, h), Qt.AlignmentFlag.AlignCenter, char)
        else:
            # 4. "F" text for main ball
            painter.setClipRect(QRect(x, y, w, h))
            painter.setOpacity(1.0)
            painter.setPen(QColor("white"))
            font = painter.font()
            font.setPixelSize(int(w * 0.4))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRect(x, y, w, h), Qt.AlignmentFlag.AlignCenter, "F")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._anim.stop()
            self._was_drag = False
            self._press_time = time.monotonic()

            if self._show_balls:
                # Check if a child ball was clicked
                cb = self._config.get("float_ball", {}).get("child_ball", {})
                child_size = cb.get("size", 36)
                pt = event.position().toPoint()
                for i, (_, _, rect) in enumerate(_BALL_ITEMS):
                    ball_rect = QRect(rect.x(), rect.y(), child_size, child_size)
                    if ball_rect.contains(pt):
                        self._open_ball_module(i)
                        self._collapse_balls()
                        return

                # Click on big ball → collapse
                if _BIG_BALL_RECT.contains(pt):
                    self._collapse_balls()
                    return

                return

            self._suppress_dock = self._docked or self._dock_edge is not None
            if self._docked:
                self._docked = False
                self._hover_timer.stop()
                self.move(self._visible_pos)
            self._dragging = True
            self._drag_offset = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._was_drag = True
            self._dock_edge = None
            self._suppress_dock = False
            new_pos = self.mapToParent(event.position().toPoint()) - self._drag_offset
            self.move(new_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False

            # Dead code path – eventFilter swallows all expanded-state events
            if self._expanded_drag:
                self._expanded_drag = False
                self._dragging = False
                self._collapse_balls()
                return

            if self._show_balls:
                return

            elapsed = time.monotonic() - self._press_time

            # Quick click → expand balls; drag or long hold → move the ball
            if not self._was_drag and elapsed < 0.3:
                self._expand_balls()
                return

            self._snap_to_edge()
            if self._docked:
                self._hover_timer.start()

    def _get_child_ball_rect(self, index):
        cb = self._config.get("float_ball", {}).get("child_ball", {})
        child_size = cb.get("size", 36)
        _, _, rect = _BALL_ITEMS[index]
        return QRect(rect.x(), rect.y(), child_size, child_size)

    def _open_ball_module(self, index):
        if index == 0 and self._ocr_module:
            self._ocr_module.show_and_capture()
        elif index == 1 and self._plan_module:
            self._plan_module.show_and_capture()
        elif index == 2 and self._app_launch_module:
            self._app_launch_module.show_and_capture()
        elif index == 3:
            self._open_settings()

    def _expand_balls(self):
        self._orig_pos = self.pos()
        self._orig_size = QSize(self.width(), self.height())
        self._show_balls = True
        self._docked = False
        self._hover_timer.stop()

        new_x = self._orig_pos.x() - _BIG_BALL_RECT.x()
        new_y = self._orig_pos.y() - _BIG_BALL_RECT.y()
        self.setFixedSize(_EXPANDED_SIZE, _EXPANDED_SIZE)
        self.move(new_x, new_y)
        self._remove_window_border()
        self.update()

    def _collapse_balls(self):
        self._show_balls = False
        self.setFixedSize(self._orig_size)
        self.move(self._orig_pos)
        self._remove_window_border()
        self.update()

    def _dock_after_collapse(self):
        self._docked = True
        self._dock_edge = "right"
        self._expanded = False
        self._dock_cooldown = True
        QTimer.singleShot(500, self._clear_dock_cooldown)
        self._hover_timer.start()
        self._animate_to(self._hidden_pos)

    def _show_dock_menu(self):
        menu = QMenu(self)
        ocr_action = QAction("OCR / 翻译", self)
        ocr_action.triggered.connect(self._open_ocr)
        menu.addAction(ocr_action)
        plan_action = QAction("计划表", self)
        plan_action.triggered.connect(self._open_plan)
        menu.addAction(plan_action)
        app_action = QAction("快捷应用", self)
        app_action.triggered.connect(self._open_app_launch)
        menu.addAction(app_action)
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
        plan_action = QAction("计划表", self)
        plan_action.triggered.connect(self._open_plan)
        menu.addAction(plan_action)
        app_action = QAction("快捷应用", self)
        app_action.triggered.connect(self._open_app_launch)
        menu.addAction(app_action)
        menu.addSeparator()
        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def _open_ocr(self):
        if self._ocr_module:
            self._ocr_module.show_and_capture()

    def _open_plan(self):
        if self._plan_module:
            self._plan_module.show_and_capture()

    def _open_app_launch(self):
        if self._app_launch_module:
            self._app_launch_module.show_and_capture()

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
        if not self._show_balls:
            self.setFixedSize(size, size)
        self._remove_window_border()
        self.update()

    def _remove_window_border(self):
        if sys.platform != "win32":
            return
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32

            GWL_STYLE = -16
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            style &= ~(0x00C00000 | 0x00040000 | 0x00400000 | 0x00800000)
            style |= 0x80000000  # WS_POPUP
            user32.SetWindowLongW(hwnd, GWL_STYLE, style)

            GWL_EXSTYLE = -20
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex &= ~(0x00000100 | 0x00000200 | 0x00020000)
            ex |= 0x00080000 | 0x00000080  # WS_EX_LAYERED | WS_EX_TOOLWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)

            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0020 | 0x0002 | 0x0001 | 0x0004 | 0x0010)

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
            accent = ACCENTPOLICY(4, 0, 0, 0)
            data = WINCOMPATTRDATA(19, ctypes.pointer(accent), ctypes.sizeof(ACCENTPOLICY))
            user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))

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
                # Only swallow hit-test when NOT expanded (balls need real hit-tests)
                if msg.message == 0x0083 and not self._show_balls:
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
                click_global = event.globalPosition().toPoint()

                # When expanded, handle clicks within the window ourselves
                if self._show_balls:
                    if QRect(self.pos(), self.size()).contains(click_global):
                        local_pt = self.mapFromGlobal(click_global)
                        cb = self._config.get("float_ball", {}).get("child_ball", {})
                        child_size = cb.get("size", 36)
                        for i, (_, _, rect) in enumerate(_BALL_ITEMS):
                            ball_rect = QRect(rect.x(), rect.y(), child_size, child_size)
                            if ball_rect.contains(local_pt):
                                self._open_ball_module(i)
                                self._collapse_balls()
                                return True
                        if _BIG_BALL_RECT.contains(local_pt):
                            self._collapse_balls()
                            self._was_drag = False
                            self._expanded_drag = True
                            self._dragging = True
                            self._drag_global_offset = click_global - self.pos()
                            return True
                        # Empty space → collapse then start drag
                        self._collapse_balls()
                        self._was_drag = False
                        self._expanded_drag = True
                        self._dragging = True
                        self._drag_global_offset = click_global - self.pos()
                        return True
                    # Click outside expanded window → collapse and hide
                    self._collapse_balls()
                    self.hide()
                    return True

                target = QApplication.widgetAt(click_global)
                if target != self and not self.isAncestorOf(target):
                    self.hide()
        elif self._expanded_drag and event.type() == QEvent.MouseMove:
            self._was_drag = True
            new_pos = QCursor.pos() - self._drag_global_offset
            self.move(new_pos)
            return True
        elif self._expanded_drag and event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            self._expanded_drag = False
            self._dragging = False
            # Click without drag → already collapsed, done.
            # Drag → stay where dropped (no snap/dock).
            return True
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
        # Initialize dock positions so _dock_after_collapse() doesn't animate to (0,0)
        strip = 6
        screen_right = geo.x() + geo.width()
        self._visible_pos = QPoint(int(x), int(y))
        self._hidden_pos = QPoint(screen_right - strip, int(y))

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
