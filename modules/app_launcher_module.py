from PySide6.QtWidgets import QWidget


class AppLauncherModule(QWidget):
    def __init__(self, config_module):
        super().__init__()
        self._config = config_module
        self.setWindowTitle("快捷应用")
        self.resize(400, 300)
