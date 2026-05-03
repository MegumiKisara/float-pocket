import base64
import os

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.ocr_agent import OcrAgent
from modules.translate_agent import TranslateAgent


class OcrTranslateModule(QWidget):
    def __init__(self):
        super().__init__()
        self._ocr_agent: OcrAgent | None = None
        self._translate_agent: TranslateAgent | None = None
        self._current_image_b64: str | None = None
        self._has_image = False
        self._has_text = False

        self.setWindowTitle("OCR / 翻译")
        self.setMinimumSize(560, 480)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # --- Paste hint ---
        self._hint_label = QLabel("按 Ctrl+V 粘贴图片或文字")
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_label.setStyleSheet("color: #999; font-size: 13px; padding: 6px;")
        layout.addWidget(self._hint_label)

        # --- Image preview ---
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setMinimumHeight(200)
        self._image_label.setMaximumHeight(260)
        self._image_label.setStyleSheet(
            "background-color: #f5f5f5; border: 1px solid #ddd; border-radius: 4px;"
        )
        self._image_label.setVisible(False)
        layout.addWidget(self._image_label)

        # --- Buttons row ---
        btn_row = QHBoxLayout()

        self._clear_btn = QPushButton("清空")
        self._clear_btn.clicked.connect(self._clear_all)
        btn_row.addWidget(self._clear_btn)

        btn_row.addStretch()

        self._ocr_btn = QPushButton("OCR 识别")
        self._ocr_btn.clicked.connect(self._do_ocr)
        btn_row.addWidget(self._ocr_btn)

        self._translate_btn = QPushButton("翻译")
        self._translate_btn.clicked.connect(self._do_translate)
        btn_row.addWidget(self._translate_btn)

        self._copy_btn = QPushButton("复制结果")
        self._copy_btn.clicked.connect(self._copy_result)
        btn_row.addWidget(self._copy_btn)

        layout.addLayout(btn_row)

        # --- Result area (editable so user can also type/paste text directly) ---
        self._result_edit = QTextEdit()
        self._result_edit.setPlaceholderText("粘贴图片或文字后的内容将显示在这里…")
        layout.addWidget(self._result_edit)

        self.setFocus()

    # ── key event ──────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent | None):
        if event and event.key() == Qt.Key.Key_V and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._handle_paste()
            return
        super().keyPressEvent(event)

    # ── public ────────────────────────────────────────────────

    def show_and_capture(self):
        """Show window without auto-capturing; user pastes manually."""
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    # ── paste handling ─────────────────────────────────────────

    def _handle_paste(self):
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()

        if mime.hasImage():
            qimage = clipboard.image()
            self._set_image(qimage)
        elif mime.hasText():
            text = clipboard.text()
            self._set_text(text)
        else:
            QMessageBox.information(self, "提示", "剪贴板中没有图片或文字")

    def _set_image(self, qimage):
        self._has_image = True
        self._has_text = False
        self._current_image_b64 = None

        # Preview
        pixmap = QPixmap.fromImage(qimage)
        scaled = pixmap.scaled(
            540, 240,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)
        self._image_label.setVisible(True)

        self._hint_label.setText("图片已粘贴，可点击 OCR 识别提取文字")

        # Clear result
        self._result_edit.clear()

        # Convert to base64
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        qimage.save(buf, "PNG")
        buf.close()
        self._current_image_b64 = base64.b64encode(bytes(ba)).decode()

    def _set_text(self, text: str):
        self._has_text = True
        self._has_image = False
        self._current_image_b64 = None

        self._image_label.setVisible(False)
        self._hint_label.setText("文字已粘贴，可点击 OCR 识别或翻译")
        self._result_edit.setText(text)

    # ── OCR ────────────────────────────────────────────────────

    def _do_ocr(self):
        if self._has_image and self._current_image_b64:
            # Image → call vision API
            agent = self._get_ocr_agent()
            if agent is None:
                return

            self._ocr_btn.setEnabled(False)
            self._ocr_btn.setText("识别中...")
            self._result_edit.setText("正在识别...")
            QApplication.processEvents()

            try:
                text = agent.extract_text(self._current_image_b64)
                self._result_edit.setText(text)
                self._has_image = False
                self._has_text = True
                self._hint_label.setText("OCR 完成，可继续翻译或编辑文字")
            except Exception as e:
                QMessageBox.critical(self, "OCR 失败", str(e))
            finally:
                self._ocr_btn.setText("OCR 识别")
                self._ocr_btn.setEnabled(True)
        elif self._has_text:
            # Text → already the "OCR result", just confirm
            QMessageBox.information(self, "OCR", "文字内容不需要 OCR 识别，原文已显示在结果区域")
        else:
            QMessageBox.warning(self, "提示", "请先按 Ctrl+V 粘贴图片或文字")

    # ── translate ─────────────────────────────────────────────

    def _do_translate(self):
        text = self._result_edit.toPlaintext().strip()
        if not text:
            QMessageBox.warning(self, "提示", "没有可翻译的内容。请先粘贴文字或进行 OCR 识别。")
            return

        agent = self._get_translate_agent()
        if agent is None:
            return

        self._translate_btn.setEnabled(False)
        self._translate_btn.setText("翻译中...")
        QApplication.processEvents()

        try:
            translated = agent.translate(text)
            self._result_edit.setText(
                f"【原文】\n{text}\n\n"
                f"【译文】\n{translated}"
            )
        except Exception as e:
            QMessageBox.critical(self, "翻译失败", str(e))
        finally:
            self._translate_btn.setText("翻译")
            self._translate_btn.setEnabled(True)

    # ── copy / clear ──────────────────────────────────────────

    def _copy_result(self):
        text = self._result_edit.toPlaintext().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)

    def _clear_all(self):
        self._has_image = False
        self._has_text = False
        self._current_image_b64 = None
        self._image_label.setPixmap(QPixmap())
        self._image_label.setVisible(False)
        self._result_edit.clear()
        self._hint_label.setText("按 Ctrl+V 粘贴图片或文字")

    # ── agent helpers ─────────────────────────────────────────

    def _get_ocr_agent(self):
        key = os.environ.get("QWEN_API_KEY", "")
        if not key:
            QMessageBox.warning(self, "未配置 API Key", "请先在「设置」中配置千问 API Key")
            return None
        if self._ocr_agent is None:
            self._ocr_agent = OcrAgent(api_key=key)
        return self._ocr_agent

    def _get_translate_agent(self):
        key = os.environ.get("QWEN_API_KEY", "")
        if not key:
            QMessageBox.warning(self, "未配置 API Key", "请先在「设置」中配置千问 API Key")
            return None
        if self._translate_agent is None:
            self._translate_agent = TranslateAgent(api_key=key)
        return self._translate_agent
