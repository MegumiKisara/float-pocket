import base64
import os

from PySide6.QtCore import QByteArray, QBuffer, QIODevice
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
        self._image_b64: str | None = None

        self.setWindowTitle("OCR / 翻译")
        self.setMinimumSize(560, 520)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # ── Input area ────────────────────────────────────────
        layout.addWidget(QLabel("输入内容："))
        self._input_edit = QTextEdit()
        self._input_edit.setPlaceholderText("在此输入或粘贴文字…")
        self._input_edit.setMinimumHeight(140)
        layout.addWidget(self._input_edit)

        # ── Buttons ───────────────────────────────────────────
        btn_row = QHBoxLayout()

        self._paste_img_btn = QPushButton("粘贴图片")
        self._paste_img_btn.clicked.connect(self._paste_image)
        btn_row.addWidget(self._paste_img_btn)

        self._img_indicator = QLabel("")
        self._img_indicator.setStyleSheet("color: #4a9; font-size: 12px;")
        btn_row.addWidget(self._img_indicator)

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

        # ── Output area ───────────────────────────────────────
        layout.addWidget(QLabel("结果："))
        self._output_edit = QTextEdit()
        self._output_edit.setReadOnly(True)
        self._output_edit.setPlaceholderText("OCR 或翻译结果将显示在这里…")
        layout.addWidget(self._output_edit)

    # ── public ────────────────────────────────────────────────

    def show_and_capture(self):
        self.show()
        self.raise_()
        self.activateWindow()

    # ── image paste ───────────────────────────────────────────

    def _paste_image(self):
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()

        if not mime.hasImage():
            QMessageBox.warning(self, "提示", "剪贴板中没有图片")
            return

        qimage = clipboard.image()
        if qimage.isNull():
            QMessageBox.warning(self, "提示", "剪贴板图片无效")
            return

        # Convert to base64
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        qimage.save(buf, "PNG")
        buf.close()
        self._image_b64 = base64.b64encode(bytes(ba)).decode()

        self._img_indicator.setText("✓ 图片已就绪，可点击 OCR 识别")
        self._output_edit.setText("")

    # ── OCR ───────────────────────────────────────────────────

    def _do_ocr(self):
        text = self._input_edit.toPlaintext().strip()

        # If an image is pasted, always prefer OCR on the image
        if self._image_b64:
            agent = self._get_ocr_agent()
            if agent is None:
                return

            self._set_buttons_enabled(False)
            self._ocr_btn.setText("识别中...")
            self._output_edit.setText("正在识别...")
            QApplication.processEvents()

            try:
                result = agent.extract_text(self._image_b64)
                self._output_edit.setText(result)
                self._img_indicator.setText("")
                self._image_b64 = None
            except Exception as e:
                QMessageBox.critical(self, "OCR 失败", str(e))
            finally:
                self._ocr_btn.setText("OCR 识别")
                self._set_buttons_enabled(True)
            return

        # No image → pass input text through as OCR result
        if text:
            self._output_edit.setText(text)
        else:
            QMessageBox.warning(self, "提示", "请先输入文字或粘贴图片")

    # ── translate ─────────────────────────────────────────────

    def _do_translate(self):
        text = self._output_edit.toPlaintext().strip()
        if not text:
            text = self._input_edit.toPlaintext().strip()
        if not text:
            QMessageBox.warning(self, "提示", "没有可翻译的内容")
            return

        agent = self._get_translate_agent()
        if agent is None:
            return

        self._set_buttons_enabled(False)
        self._translate_btn.setText("翻译中...")
        QApplication.processEvents()

        try:
            translated = agent.translate(text)
            self._output_edit.setText(
                f"【原文】\n{text}\n\n"
                f"【译文】\n{translated}"
            )
        except Exception as e:
            QMessageBox.critical(self, "翻译失败", str(e))
        finally:
            self._translate_btn.setText("翻译")
            self._set_buttons_enabled(True)

    # ── copy ──────────────────────────────────────────────────

    def _copy_result(self):
        text = self._output_edit.toPlaintext().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)

    # ── helpers ───────────────────────────────────────────────

    def _set_buttons_enabled(self, enabled: bool):
        self._ocr_btn.setEnabled(enabled)
        self._translate_btn.setEnabled(enabled)
        self._paste_img_btn.setEnabled(enabled)

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
