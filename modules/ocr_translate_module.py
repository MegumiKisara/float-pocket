import base64
import os
import traceback
from datetime import datetime

from PySide6.QtCore import QByteArray, QBuffer, QEvent, QIODevice, Qt
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

_LOG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "debug_ocr.log")


def _log(msg: str):
    try:
        with open(_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%H:%M:%S}] {msg}\n")
    except Exception:
        pass


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
        layout.addWidget(QLabel("输入内容（可粘贴图片或文字）："))
        self._input_edit = QTextEdit()
        self._input_edit.setPlaceholderText("在此输入文字，或 Ctrl+V 粘贴图片/文字…")
        self._input_edit.setMinimumHeight(140)
        self._input_edit.installEventFilter(self)
        layout.addWidget(self._input_edit)

        # ── Buttons ───────────────────────────────────────────
        btn_row = QHBoxLayout()
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

        # ── Status hint ───────────────────────────────────────
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self._status_label)

        # ── Output area ───────────────────────────────────────
        layout.addWidget(QLabel("结果："))
        self._output_edit = QTextEdit()
        self._output_edit.setReadOnly(True)
        self._output_edit.setPlaceholderText("OCR 或翻译结果将显示在这里…")
        layout.addWidget(self._output_edit)

    # ── event filter: Ctrl+V → image paste ───────────────────

    def eventFilter(self, obj, event):
        if obj == self._input_edit and event.type() == QEvent.Type.KeyPress:
            ke = event
            if ke.key() == Qt.Key.Key_V and ke.modifiers() == Qt.KeyboardModifier.ControlModifier:
                if QApplication.clipboard().mimeData().hasImage():
                    self._paste_image()
                    return True
        return super().eventFilter(obj, event)

    # ── close / hide → clear ─────────────────────────────────

    def hideEvent(self, event):
        self._clear_all()
        super().hideEvent(event)

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
            return

        qimage = clipboard.image()
        if qimage.isNull():
            return

        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        qimage.save(buf, "PNG")
        buf.close()
        b64 = base64.b64encode(bytes(ba)).decode()
        self._image_b64 = b64

        html = (
            '<p><img src="data:image/png;base64,{}" '
            'width="520" style="max-width:100%" /></p>'.format(b64)
        )
        self._input_edit.setHtml(html)

        self._output_edit.clear()
        self._status_label.setText("图片已粘贴，可点击「OCR 识别」提取文字")

    # ── OCR ───────────────────────────────────────────────────

    def _do_ocr(self):
        try:
            self._status_label.setText("处理中...")
            self._output_edit.clear()

            if self._image_b64:
                self._call_ocr_api()
                return

            text = self._input_edit.toPlainText().strip()
            if text:
                self._output_edit.setText(text)
                self._status_label.setText("已完成")
            else:
                self._status_label.setText("")
                QMessageBox.warning(None, "提示", "请先输入文字或粘贴图片")
        except Exception as e:
            _log(f"_do_ocr error: {traceback.format_exc()}")
            QMessageBox.critical(None, "错误", f"{e}")

    def _call_ocr_api(self):
        agent = self._get_ocr_agent()
        if agent is None:
            return

        self._set_buttons_enabled(False)
        self._ocr_btn.setText("识别中...")
        self._output_edit.setText("正在识别...")
        QApplication.processEvents()

        try:
            _log(f"OCR calling API, image_b64 length={len(self._image_b64)}")
            result = agent.extract_text(self._image_b64)
            _log(f"OCR result length={len(result)}")
            self._output_edit.setText(result)
            self._clear_input()
            self._status_label.setText("OCR 完成")
        except Exception as e:
            _log(f"OCR error: {traceback.format_exc()}")
            QMessageBox.critical(None, "OCR 失败", f"{e}")
        finally:
            self._ocr_btn.setText("OCR 识别")
            self._set_buttons_enabled(True)

    # ── translate ─────────────────────────────────────────────

    def _do_translate(self):
        try:
            self._status_label.setText("处理中...")
            self._output_edit.clear()

            text = self._input_edit.toPlainText().strip()
            if not text:
                self._status_label.setText("")
                QMessageBox.warning(None, "提示", "输入框中没有可翻译的内容")
                return

            agent = self._get_translate_agent()
            if agent is None:
                self._status_label.setText("")
                return

            self._set_buttons_enabled(False)
            self._translate_btn.setText("翻译中...")
            self._output_edit.setText("正在翻译...")
            QApplication.processEvents()

            _log(f"Translate calling API, text length={len(text)}")
            translated = agent.translate(text)
            _log(f"Translate result: {translated[:100]}")
            self._output_edit.setText(
                f"【原文】\n{text}\n\n"
                f"【译文】\n{translated}"
            )
            self._clear_input()
            self._status_label.setText("翻译完成")
        except Exception as e:
            _log(f"Translate error: {traceback.format_exc()}")
            self._output_edit.setText(f"翻译失败：{e}")
            QMessageBox.critical(None, "翻译失败", f"{e}")
        finally:
            self._translate_btn.setText("翻译")
            self._set_buttons_enabled(True)

    # ── copy ──────────────────────────────────────────────────

    def _copy_result(self):
        text = self._output_edit.toPlainText().strip()
        if not text:
            text = self._input_edit.toPlainText().strip()
        if not text:
            QMessageBox.information(None, "提示", "没有可复制的内容")
            return
        QApplication.clipboard().setText(text)
        self._status_label.setText("已复制到剪贴板")

    # ── helpers ───────────────────────────────────────────────

    def _clear_input(self):
        self._input_edit.clear()
        self._image_b64 = None

    def _clear_all(self):
        self._input_edit.clear()
        self._output_edit.clear()
        self._image_b64 = None
        self._status_label.setText("")

    def _set_buttons_enabled(self, enabled: bool):
        self._ocr_btn.setEnabled(enabled)
        self._translate_btn.setEnabled(enabled)
        self._copy_btn.setEnabled(enabled)

    def _get_ocr_agent(self):
        key = os.environ.get("QWEN_API_KEY", "")
        _log(f"OCR agent: QWEN_API_KEY={'set' if key else 'NOT SET'}")
        if not key:
            QMessageBox.warning(None, "未配置 API Key", "请先在「设置」中配置千问 API Key")
            return None
        if self._ocr_agent is None:
            self._ocr_agent = OcrAgent(api_key=key)
        return self._ocr_agent

    def _get_translate_agent(self):
        key = os.environ.get("QWEN_API_KEY", "")
        _log(f"Translate agent: QWEN_API_KEY={'set' if key else 'NOT SET'}")
        if not key:
            QMessageBox.warning(None, "未配置 API Key", "请先在「设置」中配置千问 API Key")
            return None
        if self._translate_agent is None:
            self._translate_agent = TranslateAgent(api_key=key)
        return self._translate_agent
