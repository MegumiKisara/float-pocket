from PySide6.QtCore import QByteArray, QSize, Qt, QEvent, QPoint, QPropertyAnimation, QRect, QTimer
from PySide6.QtGui import QAction, QBitmap, QBrush, QColor, QCursor, QImage, QLinearGradient, QPainter, QPainterPath, QRadialGradient, QRegion
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QMenu, QWidget

import time

from modules.settings_module import SettingsDialog
from modules.logger_module import log

_EXPANDED_SIZE = 150

# Rightward expansion (float ball on left screen half, big ball on left side)
_RIGHT_BIG_RECT = QRect(25, 45, 60, 60)

# Leftward expansion (float ball on right screen half, big ball on right side)
_LEFT_BIG_RECT = QRect(65, 45, 60, 60)

_BALL_LABELS = [
    ("OCR / 翻译", "O"),
    ("计划表", "计"),
    ("快捷应用", "快"),
    ("设置", "设"),
]


class FloatBallModule(QWidget):
    def __init__(self, config_module, ocr_module=None, plan_module=None, app_launch_module=None, hotkey_mgr=None):
        super().__init__()
        self._config = config_module
        self._ocr_module = ocr_module
        self._plan_module = plan_module
        self._app_launch_module = app_launch_module
        self._hotkey_mgr = hotkey_mgr
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
        self._rightward = True
        self._big_ball_rect = _RIGHT_BIG_RECT
        self._ball_items = []

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # /* 磨砂背景修复 */
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)  # /* 边框/锯齿修复 */
        self.setAttribute(Qt.WA_NoSystemBackground)  # /* 磨砂背景修复 */
        self.setAttribute(Qt.WA_StyledBackground, False)  # /* 磨砂背景修复 */

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
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)  # /* 边框/锯齿修复 */

        w, h = self.width(), self.height()
        fb = self._config.get("float_ball", {})
        icons = fb.get("icons", {})

        # Clear to transparent, then draw balls for smooth per-pixel alpha edges /* 边框/锯齿修复 */
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(0, 0, w, h, Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        if not self._show_balls:
            self._draw_ball(painter, 0, 0, w, h, None, icons.get("main", ""))
        else:
            self._draw_ball(painter, self._big_ball_rect.x(), self._big_ball_rect.y(),
                            self._big_ball_rect.width(), self._big_ball_rect.height(),
                            None, icons.get("main", ""))

            cb = fb.get("child_ball", {})
            child_size = cb.get("size", 36)
            child_opacity = cb.get("opacity", 0.85)
            child_radius = min(cb.get("corner_radius", 18), child_size // 2)

            for i, (_, char, rect) in enumerate(self._ball_items):
                svg = icons.get(f"child_{i}", "")
                self._draw_ball(painter, rect.x(), rect.y(),
                                child_size, child_size,
                                (char, child_opacity, child_radius), svg)

    def _draw_ball(self, painter, x, y, w, h, overlay=None, svg_data=""):
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

        if svg_data:
            # 4. SVG icon
            renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))
            margin = int(w * 0.15)
            renderer.render(painter, QRect(x + margin, y + margin, w - margin * 2, h - margin * 2))
        elif overlay:
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
                for i, (_, _, rect) in enumerate(self._ball_items):
                    ball_rect = QRect(rect.x(), rect.y(), child_size, child_size)
                    if ball_rect.contains(pt):
                        self._open_ball_module(i)
                        self._collapse_balls()
                        return

                # Click on big ball → collapse
                if self._big_ball_rect.contains(pt):
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

    def _update_ball_items(self):
        fb = self._config.get("float_ball", {})
        positions = fb.get("ball_positions", [
            {"dx": 19, "dy": -35},
            {"dx": 43, "dy": -17},
            {"dx": 51, "dy": 21},
            {"dx": 37, "dy": 47},
        ])
        child_size = fb.get("child_ball", {}).get("size", 36)

        items = []
        for i, (name, char) in enumerate(_BALL_LABELS):
            if i < len(positions):
                dx = positions[i].get("dx", 0)
                dy = positions[i].get("dy", 0)
            else:
                dx, dy = 0, 0

            if self._rightward:
                x = self._big_ball_rect.x() + dx
            else:
                x = self._big_ball_rect.x() + self._big_ball_rect.width() - dx - child_size
            y = self._big_ball_rect.y() + dy

            items.append((name, char, QRect(x, y, 0, 0)))

        self._ball_items = items

    def _update_mask(self):
        """Clear mask — per-pixel alpha handles smooth edges without 1-bit clipping /* 边框/锯齿修复 */"""
        self.clearMask()

    def _get_child_ball_rect(self, index):
        cb = self._config.get("float_ball", {}).get("child_ball", {})
        child_size = cb.get("size", 36)
        _, _, rect = self._ball_items[index]
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
        fb = self._config.get("float_ball", {})
        base_size = fb.get("size", 60)
        self._orig_size = QSize(base_size, base_size)
        self._show_balls = True
        self._docked = False
        self._hover_timer.stop()
        log(f"_expand_balls orig_pos=({self._orig_pos.x()},{self._orig_pos.y()}) orig_size=({base_size},{base_size})")

        # Determine expansion direction based on which screen half the ball is on
        screen = self.screen() or QApplication.primaryScreen()
        geo = screen.availableGeometry()
        center_x = geo.x() + geo.width() // 2
        self._rightward = (self.pos().x() + 30) < center_x
        if self._rightward:
            self._big_ball_rect = _RIGHT_BIG_RECT
        else:
            self._big_ball_rect = _LEFT_BIG_RECT
        self._update_ball_items()

        new_x = self._orig_pos.x() - self._big_ball_rect.x()
        new_y = self._orig_pos.y() - self._big_ball_rect.y()
        self.setFixedSize(_EXPANDED_SIZE, _EXPANDED_SIZE)
        self.move(new_x, new_y)
        self._update_mask()
        self.update()

    def _collapse_balls(self):
        log(f"_collapse_balls → size=({self._orig_size.width()},{self._orig_size.height()}) pos=({self._orig_pos.x()},{self._orig_pos.y()})")
        self._show_balls = False
        self.setFixedSize(self._orig_size)
        self.move(self._orig_pos)
        self._update_mask()
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
        dialog = SettingsDialog(self._config, self, self._hotkey_mgr)
        dialog.settings_changed.connect(self._apply_settings)
        dialog.exec()
        self._settings_open = False
        self._apply_settings()

    def _apply_settings(self):
        fb = self._config.get("float_ball", {})
        size = fb.get("size", 60)
        if not self._show_balls:
            self.setFixedSize(size, size)
        else:
            self._update_ball_items()
        self._update_mask()  # /* 磨砂背景修复 */
        self.update()
        if self._hotkey_mgr:
            self._hotkey_mgr.register(self._config.get("global_hotkey", ""))

    def hideEvent(self, event):
        super().hideEvent(event)
        log("hideEvent")

    def showEvent(self, event):
        super().showEvent(event)
        self._update_mask()  # /* 磨砂背景修复 */
        self._apply_settings()
        log("showEvent")

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
                        for i, (_, _, rect) in enumerate(self._ball_items):
                            ball_rect = QRect(rect.x(), rect.y(), child_size, child_size)
                            if ball_rect.contains(local_pt):
                                self._open_ball_module(i)
                                self._collapse_balls()
                                return True
                        if self._big_ball_rect.contains(local_pt):
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

    def toggle_visibility(self, expand=False):
        log(f"toggle_visibility expand={expand} isVisible={self.isVisible()} _show_balls={self._show_balls} size=({self.width()},{self.height()})")
        if self.isVisible():
            self.hide()
        else:
            self._ensure_position()
            self.show()
            self.raise_()
            if expand:
                self._expand_balls()

    def _ensure_position(self):
        screen = QApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = geo.x() + geo.width() - self.width() - 10
        y = geo.y() + (geo.height() - self.height()) // 2
        log(f"_ensure_position width={self.width()} height={self.height()} → ({x},{y})")
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
