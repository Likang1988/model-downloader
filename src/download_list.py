from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QListWidgetItem
)
from PySide6.QtCore import Qt, QThread
from qfluentwidgets import (
    ProgressBar, PushButton, ToolButton, BodyLabel, CaptionLabel
)
from .downloader import FileInfo, DownloadTask


class DownloadItemWidget(QWidget):
    def __init__(self, file_info: FileInfo):
        super().__init__()
        self.file_info = file_info
        self.task = None
        self.thread = None

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        self.name_label = BodyLabel(self.file_info.name)
        self.size_label = CaptionLabel(self.format_size(self.file_info.size))

        self.cancel_btn = ToolButton()
        self.cancel_btn.setText("取消")
        self.cancel_btn.clicked.connect(self.on_cancel)
        self.cancel_btn.setEnabled(False)

        header_layout.addWidget(self.name_label)
        header_layout.addWidget(self.size_label)
        header_layout.addStretch()
        header_layout.addWidget(self.cancel_btn)

        self.progress_bar = ProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.status_label = CaptionLabel("等待下载")

        layout.addLayout(header_layout)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)

        self.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 8px;
                padding: 4px;
            }
        """)

    def format_size(self, size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.2f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.2f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"

    def start_download(self, save_path: str, mirror_enabled: bool):
        self.task = DownloadTask(self.file_info, save_path, mirror_enabled)
        self.thread = QThread()
        self.task.moveToThread(self.thread)

        self.task.progress_updated.connect(self.on_progress_updated)
        self.task.download_completed.connect(self.on_download_completed)
        self.task.download_failed.connect(self.on_download_failed)
        self.task.download_canceled.connect(self.on_download_canceled)

        self.thread.started.connect(self.task.run)
        self.thread.start()

        self.status_label.setText("下载中...")
        self.cancel_btn.setEnabled(True)

    def on_progress_updated(self, task_id, current, total):
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)
            self.status_label.setText(f"下载中: {self.format_size(current)} / {self.format_size(total)}")

    def on_download_completed(self, task_id):
        self.progress_bar.setValue(100)
        self.status_label.setText("下载完成")
        self.cancel_btn.setEnabled(False)
        if self.thread:
            self.thread.quit()
            self.thread.wait()

    def on_download_failed(self, task_id, error):
        self.status_label.setText(f"下载失败: {error}")
        self.cancel_btn.setEnabled(False)
        if self.thread:
            self.thread.quit()
            self.thread.wait()

    def on_download_canceled(self, task_id):
        self.status_label.setText("已取消")
        self.cancel_btn.setEnabled(False)
        if self.thread:
            self.thread.quit()
            self.thread.wait()

    def on_cancel(self):
        if self.task:
            self.task.cancel()

    def is_completed(self):
        return self.status_label.text() in ["下载完成", "已取消", "下载失败"]


class DownloadList(QWidget):
    def __init__(self):
        super().__init__()
        self.download_items = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
            }
            QListWidget::item {
                border: none;
                padding: 4px;
            }
        """)

        self.clear_btn = PushButton("清空列表")
        self.clear_btn.clicked.connect(self.on_clear)

        layout.addWidget(self.list_widget)
        layout.addWidget(self.clear_btn)

    def add_download(self, file_info: FileInfo):
        item = QListWidgetItem()
        widget = DownloadItemWidget(file_info)
        item.setSizeHint(widget.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)
        self.download_items.append(widget)

    def start_downloads(self, save_path: str, mirror_enabled: bool):
        for item in self.download_items:
            if not item.is_completed():
                item.start_download(save_path, mirror_enabled)

    def has_tasks(self):
        return len(self.download_items) > 0

    def on_clear(self):
        self.list_widget.clear()
        self.download_items.clear()