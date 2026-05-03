import base64
import os

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QPixmap
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
        self._ocr_result: str = ""
        self._translation_result: str = ""

        self.setWindowTitle("OCR / 翻译")
        self.setMinimumSize(560, 480)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # --- Image preview ---
        self._image_label = QLabel("无剪贴板图片\n请先复制一张图片到剪贴板")
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setMinimumHeight(200)
        self._image_label.setMaximumHeight(260)
        self._image_label.setStyleSheet(
            "background-color: #f5f5f5; border: 1px solid #ddd; border-radius: 4px;"
        )
        layout.addWidget(self._image_label)

        # --- Buttons row ---
        btn_row = QHBoxLayout()

        self._refresh_btn = QPushButton("刷新剪贴板")
        self._refresh_btn.clicked.connect(self._capture_clipboard)
        btn_row.addWidget(self._refresh_btn)

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

        # --- Result area ---
        self._result_edit = QTextEdit()
        self._result_edit.setReadOnly(True)
        self._result_edit.setPlaceholderText("结果将显示在这里...")
        layout.addWidget(self._result_edit)

    # ── public ────────────────────────────────────────────────

    def show_and_capture(self):
        self._capture_clipboard()
        self.show()
        self.raise_()
        self.activateWindow()

    # ── clipboard ─────────────────────────────────────────────

    def _capture_clipboard(self):
        clipboard = QApplication.clipboard()
        qimage = clipboard.image()
        if qimage.isNull():
            self._image_label.setText("无剪贴板图片\n请先复制一张图片到剪贴板")
            self._image_label.setPixmap(QPixmap())
            self._current_image_b64 = None
            return

        pixmap = QPixmap.fromImage(qimage)
        scaled = pixmap.scaled(
            540, 240,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)

        # Convert to base64 (PNG)
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        qimage.save(buf, "PNG")
        buf.close()
        self._current_image_b64 = base64.b64encode(bytes(ba)).decode()

    # ── OCR ────────────────────────────────────────────────────

    def _do_ocr(self):
        if not self._current_image_b64:
            QMessageBox.warning(self, "提示", "请先复制一张图片到剪贴板")
            return

        agent = self._get_ocr_agent()
        if agent is None:
            return

        self._ocr_btn.setEnabled(False)
        self._ocr_btn.setText("识别中...")
        self._result_edit.setText("正在识别...")
        QApplication.processEvents()

        try:
            text = agent.extract_text(self._current_image_b64)
            self._ocr_result = text
            self._translation_result = ""
            self._result_edit.setText(text)
        except Exception as e:
            QMessageBox.critical(self, "OCR 失败", str(e))
            self._result_edit.setText("")
        finally:
            self._ocr_btn.setText("OCR 识别")
            self._ocr_btn.setEnabled(True)

    # ── translate ─────────────────────────────────────────────

    def _do_translate(self):
        text_to_translate = self._ocr_result or self._result_edit.toPlaintext().strip()
        if not text_to_translate:
            QMessageBox.warning(self, "提示", "没有可翻译的内容。请先进行 OCR 识别或输入文字。")
            return

        agent = self._get_translate_agent()
        if agent is None:
            return

        self._translate_btn.setEnabled(False)
        self._translate_btn.setText("翻译中...")
        QApplication.processEvents()

        try:
            translated = agent.translate(text_to_translate)
            self._translation_result = translated
            self._result_edit.setText(
                f"【原文】\n{text_to_translate}\n\n"
                f"【译文】\n{translated}"
            )
        except Exception as e:
            QMessageBox.critical(self, "翻译失败", str(e))
        finally:
            self._translate_btn.setText("翻译")
            self._translate_btn.setEnabled(True)

    # ── copy ──────────────────────────────────────────────────

    def _copy_result(self):
        text = self._result_edit.toPlaintext().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)

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
