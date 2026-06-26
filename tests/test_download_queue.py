"""下载队列模块测试"""

import pytest
from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from src.download_queue import (
    format_size, format_eta,
    STATUS_WAITING, STATUS_DOWNLOADING, STATUS_PAUSED,
    STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELED, STATUS_CONNECTING,
    ACTIVE_STATUS, RESTARTABLE_STATUS, STATUS_COLORS,
    TaskItem, DownloadQueueWidget
)
from src.downloader import FileInfo


class TestFormatFunctions:
    """格式化函数测试"""

    def test_format_size(self):
        assert format_size(0) == "0 B"
        assert format_size(1023) == "1023 B"
        assert format_size(1024) == "1.0 KB"
        assert format_size(1024 * 512) == "512.0 KB"
        assert format_size(1024 * 1024) == "1.0 MB"
        assert format_size(1024 * 1024 * 512) == "512.0 MB"
        assert format_size(1024 * 1024 * 1024) == "1.00 GB"

    def test_format_eta(self):
        assert format_eta(-1) == "-"
        assert format_eta(1e8) == "-"
        assert format_eta(0) == "00:00"
        assert format_eta(59) == "00:59"
        assert format_eta(60) == "01:00"
        assert format_eta(3600) == "1:00:00"
        assert format_eta(3661) == "1:01:01"


class TestStatusConstants:
    """状态常量测试"""

    def test_status_constants(self):
        assert STATUS_WAITING == "等待下载"
        assert STATUS_DOWNLOADING == "下载中"
        assert STATUS_PAUSED == "已暂停"
        assert STATUS_COMPLETED == "下载完成"
        assert STATUS_FAILED == "下载失败"
        assert STATUS_CANCELED == "已取消"
        assert STATUS_CONNECTING == "连接中..."

    def test_active_status(self):
        assert STATUS_DOWNLOADING in ACTIVE_STATUS
        assert STATUS_CONNECTING in ACTIVE_STATUS
        assert STATUS_PAUSED not in ACTIVE_STATUS
        assert STATUS_COMPLETED not in ACTIVE_STATUS

    def test_restartable_status(self):
        assert STATUS_WAITING in RESTARTABLE_STATUS
        assert STATUS_FAILED in RESTARTABLE_STATUS
        assert STATUS_CANCELED in RESTARTABLE_STATUS
        assert STATUS_COMPLETED not in RESTARTABLE_STATUS
        assert STATUS_DOWNLOADING not in RESTARTABLE_STATUS

    def test_status_colors(self):
        assert STATUS_COLORS[STATUS_WAITING] == "#9E9E9E"
        assert STATUS_COLORS[STATUS_DOWNLOADING] == "#2196F3"
        assert STATUS_COLORS[STATUS_PAUSED] == "#FF9800"
        assert STATUS_COLORS[STATUS_COMPLETED] == "#4CAF50"
        assert STATUS_COLORS[STATUS_FAILED] == "#F44336"
        assert STATUS_COLORS[STATUS_CANCELED] == "#9E9E9E"


class TestTaskItem:
    """任务项数据类测试"""

    def test_task_item_creation(self):
        file_info = FileInfo(
            name="model.bin", size=1024, path="model.bin",
            repo_id="test/model", repo_type="model", provider="huggingface"
        )
        task = TaskItem(file_info=file_info, row=0)
        assert task.file_info == file_info
        assert task.row == 0
        assert task.status == STATUS_WAITING
        assert task.progress == 0.0
        assert task.downloaded == 0
        assert task.speed == ""
        assert task.task is None
        assert task.thread is None

    def test_task_item_status_update(self):
        file_info = FileInfo(
            name="model.bin", size=1024, path="model.bin",
            repo_id="test/model", repo_type="model", provider="huggingface"
        )
        task = TaskItem(file_info=file_info)
        task.status = STATUS_DOWNLOADING
        task.progress = 50.0
        task.downloaded = 512
        task.speed = "100 KB/s"

        assert task.status == STATUS_DOWNLOADING
        assert task.progress == 50.0
        assert task.downloaded == 512
        assert task.speed == "100 KB/s"


@pytest.fixture
def app(qtbot):
    return QApplication.instance() or QApplication([])


@pytest.fixture
def queue_widget(qtbot, app):
    from i18n import install_language
    from src.config import get_config_dir
    import os
    queue_file = os.path.join(get_config_dir(), "queue.json")
    if os.path.exists(queue_file):
        os.remove(queue_file)
    install_language(QLocale(QLocale.Language.Chinese))
    widget = DownloadQueueWidget()
    qtbot.addWidget(widget)
    return widget


class TestDownloadQueueWidget:
    """下载队列组件测试"""

    def test_initial_state(self, queue_widget):
        assert queue_widget.table.rowCount() == 0
        assert len(queue_widget.tasks) == 0

    def test_add_file(self, queue_widget):
        file_info = FileInfo(
            name="model.bin", size=1024, path="model.bin",
            repo_id="test/model", repo_type="model", provider="huggingface"
        )
        queue_widget.add_file(file_info)

        assert queue_widget.table.rowCount() == 1
        assert len(queue_widget.tasks) == 1
        assert 0 in queue_widget.tasks

        task = queue_widget.tasks[0]
        assert task.file_info == file_info
        assert task.status == STATUS_WAITING

    def test_add_duplicate_file(self, queue_widget):
        file_info = FileInfo(
            name="model.bin", size=1024, path="model.bin",
            repo_id="test/model", repo_type="model", provider="huggingface"
        )
        queue_widget.add_file(file_info)
        queue_widget.add_file(file_info)

        assert queue_widget.table.rowCount() == 1
        assert len(queue_widget.tasks) == 1

    def test_set_save_path(self, queue_widget):
        queue_widget.set_save_path("/custom/path")
        assert queue_widget._save_path == "/custom/path"

    def test_remove_selected(self, queue_widget):
        file_info = FileInfo(
            name="model.bin", size=1024, path="model.bin",
            repo_id="test/model", repo_type="model", provider="huggingface"
        )
        queue_widget.add_file(file_info)

        queue_widget.table.selectRow(0)
        queue_widget.on_remove_selected()

        assert queue_widget.table.rowCount() == 0
        assert len(queue_widget.tasks) == 0

    def test_clear_all(self, queue_widget):
        for i in range(3):
            file_info = FileInfo(
                name=f"file{i}.bin", size=1024, path=f"file{i}.bin",
                repo_id="test/model", repo_type="model", provider="huggingface"
            )
            queue_widget.add_file(file_info)

        assert queue_widget.table.rowCount() == 3
        assert len(queue_widget.tasks) == 3

        queue_widget.on_clear_all()

        assert queue_widget.table.rowCount() == 0
        assert len(queue_widget.tasks) == 0

    def test_retranslate_ui(self, queue_widget, app):
        from src.i18n import install_language, tr

        install_language(QLocale(QLocale.Language.English))
        queue_widget.retranslateUi()

        assert queue_widget.queue_title.text() == "Download Queue"
        assert queue_widget.start_sel_btn.text() == "Start"
        assert queue_widget.pause_sel_btn.text() == "Pause"
        assert queue_widget.remove_sel_btn.text() == "Remove"
        assert queue_widget.clear_all_btn.text() == "Clear"

        install_language(QLocale(QLocale.Language.Chinese))
        queue_widget.retranslateUi()

        assert queue_widget.queue_title.text() == "下载队列"
        assert queue_widget.start_sel_btn.text() == "开始"
        assert queue_widget.pause_sel_btn.text() == "暂停"
        assert queue_widget.remove_sel_btn.text() == "移除"
        assert queue_widget.clear_all_btn.text() == "清空"