from PySide6.QtWidgets import QWidget


class OcrTranslateModule(QWidget):
    def __init__(self, config_module):
        super().__init__()
        self._config = config_module
        self.setWindowTitle("OCR / 翻译")
        self.resize(500, 400)
