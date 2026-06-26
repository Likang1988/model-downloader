"""下载历史模块测试"""

import os
import tempfile
import pytest
from PySide6.QtCore import QLocale

from src.download_history import (
    format_size,
    HIST_STATUS_COMPLETED, HIST_STATUS_FAILED, HIST_STATUS_CANCELED,
    HIST_FILTER_ALL,
    HistoryManager, history_mgr
)


class TestFormatSize:
    """格式化大小测试"""

    def test_format_size(self):
        assert format_size(-1) == "-"
        assert format_size(0) == "0 B"
        assert format_size(1023) == "1023 B"
        assert format_size(1024) == "1.0 KB"
        assert format_size(1024 * 1024) == "1.0 MB"
        assert format_size(1024 * 1024 * 1024) == "1.00 GB"


class TestHistoryManager:
    """历史记录管理器测试"""

    def test_singleton(self):
        mgr1 = HistoryManager()
        mgr2 = HistoryManager()
        assert mgr1 is mgr2

    def test_add_record(self, tmp_path):
        mgr = HistoryManager()
        original_count = len(mgr.get_records())

        mgr.add_record(
            file_name="test.bin",
            repo_id="test/model",
            provider="huggingface",
            status=HIST_STATUS_COMPLETED,
            file_size=1024,
            save_path=str(tmp_path),
        )

        records = mgr.get_records()
        assert len(records) == original_count + 1
        assert records[0]["file_name"] == "test.bin"
        assert records[0]["repo_id"] == "test/model"
        assert records[0]["provider"] == "huggingface"
        assert records[0]["status"] == HIST_STATUS_COMPLETED
        assert records[0]["file_size"] == 1024
        assert records[0]["save_path"] == str(tmp_path)

    def test_filter_by_status(self):
        mgr = HistoryManager()

        mgr.add_record(
            file_name="success.bin",
            repo_id="test/model",
            provider="huggingface",
            status=HIST_STATUS_COMPLETED,
            file_size=1024,
            save_path="/tmp",
        )
        mgr.add_record(
            file_name="failed.bin",
            repo_id="test/model",
            provider="modelscope",
            status=HIST_STATUS_FAILED,
            file_size=512,
            save_path="/tmp",
        )

        all_records = mgr.filter_by_status(HIST_FILTER_ALL)
        completed_records = mgr.filter_by_status(HIST_STATUS_COMPLETED)
        failed_records = mgr.filter_by_status(HIST_STATUS_FAILED)

        assert len(all_records) >= 2
        assert len(completed_records) >= 1
        assert len(failed_records) >= 1

        assert any(r["file_name"] == "success.bin" for r in completed_records)
        assert any(r["file_name"] == "failed.bin" for r in failed_records)

    def test_remove_record(self):
        mgr = HistoryManager()

        mgr.add_record(
            file_name="to_remove.bin",
            repo_id="test/model",
            provider="huggingface",
            status=HIST_STATUS_COMPLETED,
            file_size=1024,
            save_path="/tmp",
        )

        records = mgr.get_records()
        record_id = records[0]["id"]
        original_count = len(records)

        mgr.remove_record(record_id)

        assert len(mgr.get_records()) == original_count - 1
        assert not any(r["id"] == record_id for r in mgr.get_records())

    def test_clear_all(self):
        mgr = HistoryManager()

        mgr.add_record(
            file_name="file1.bin",
            repo_id="test/model",
            provider="huggingface",
            status=HIST_STATUS_COMPLETED,
            file_size=1024,
            save_path="/tmp",
        )
        mgr.add_record(
            file_name="file2.bin",
            repo_id="test/model",
            provider="modelscope",
            status=HIST_STATUS_FAILED,
            file_size=512,
            save_path="/tmp",
        )

        assert len(mgr.get_records()) >= 2

        mgr.clear_all()

        assert len(mgr.get_records()) == 0