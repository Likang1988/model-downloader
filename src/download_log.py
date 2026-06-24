from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt, QDateTime
from qfluentwidgets import SubtitleLabel, TextEdit
from .i18n import tr


class LogWidget(QWidget):
    """下载日志组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.title_label = SubtitleLabel(tr("下载日志"))
        layout.addWidget(self.title_label)

        self.log_area = TextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area, 1)

    def retranslateUi(self):
        self.title_label.setText(tr("下载日志"))

    def log(self, message: str):
        """添加日志"""
        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.log_area.append(f"[{timestamp}] {message}")

    def clear(self):
        self.log_area.clear()