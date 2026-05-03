from PySide6.QtWidgets import QWidget


class TodoListModule(QWidget):
    def __init__(self, config_module):
        super().__init__()
        self._config = config_module
        self.setWindowTitle("计划表")
        self.resize(400, 300)
