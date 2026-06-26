"""下载核心模块测试"""

import os
import tempfile
import pytest
import requests_mock

from src.downloader import FileInfo, DownloadTask, RepoProvider, get_auth_headers


class TestFileInfo:
    """文件信息类测试"""

    def test_file_info_creation(self):
        file_info = FileInfo(
            name="model.bin",
            size=1024,
            path="models/model.bin",
            repo_id="test/model",
            repo_type="model",
            provider="huggingface"
        )
        assert file_info.name == "model.bin"
        assert file_info.size == 1024
        assert file_info.path == "models/model.bin"
        assert file_info.repo_id == "test/model"
        assert file_info.repo_type == "model"
        assert file_info.provider == "huggingface"
        assert file_info.selected is False

    def test_file_info_selected(self):
        file_info = FileInfo(
            name="file.txt", size=512, path="file.txt",
            repo_id="test/repo", repo_type="model", provider="modelscope"
        )
        file_info.selected = True
        assert file_info.selected is True


class TestDownloadTask:
    """下载任务类测试"""

    def test_get_download_url_huggingface(self):
        file_info = FileInfo(
            name="model.bin", size=1024, path="model.bin",
            repo_id="test/model", repo_type="model", provider="huggingface"
        )
        task = DownloadTask(file_info, "/tmp", mirror_enabled=False)
        assert task.get_download_url() == "https://huggingface.co/test/model/resolve/main/model.bin"

    def test_get_download_url_huggingface_mirror(self):
        file_info = FileInfo(
            name="model.bin", size=1024, path="model.bin",
            repo_id="test/model", repo_type="model", provider="huggingface"
        )
        task = DownloadTask(file_info, "/tmp", mirror_enabled=True)
        assert task.get_download_url() == "https://hf-mirror.com/test/model/resolve/main/model.bin"

    def test_get_download_url_modelscope(self):
        file_info = FileInfo(
            name="model.bin", size=1024, path="model.bin",
            repo_id="test/model", repo_type="model", provider="modelscope"
        )
        task = DownloadTask(file_info, "/tmp", mirror_enabled=False)
        assert task.get_download_url() == "https://www.modelscope.cn/test/model/resolve/master/model.bin"

    def test_get_download_url_modelscope_dataset(self):
        file_info = FileInfo(
            name="data.csv", size=1024, path="data.csv",
            repo_id="test/dataset", repo_type="dataset", provider="modelscope"
        )
        task = DownloadTask(file_info, "/tmp", mirror_enabled=False)
        assert task.get_download_url() == "https://www.modelscope.cn/datasets/test/dataset/resolve/master/data.csv"

    def test_get_download_url_unknown_provider(self):
        file_info = FileInfo(
            name="model.bin", size=1024, path="model.bin",
            repo_id="test/model", repo_type="model", provider="unknown"
        )
        task = DownloadTask(file_info, "/tmp")
        assert task.get_download_url() == ""

    def test_pause_resume(self):
        file_info = FileInfo(
            name="model.bin", size=1024, path="model.bin",
            repo_id="test/model", repo_type="model", provider="huggingface"
        )
        task = DownloadTask(file_info, "/tmp")
        assert task.is_paused is False

        task.pause()
        assert task.is_paused is True

        task.resume()
        assert task.is_paused is False

    def test_cancel(self):
        file_info = FileInfo(
            name="model.bin", size=1024, path="model.bin",
            repo_id="test/model", repo_type="model", provider="huggingface"
        )
        task = DownloadTask(file_info, "/tmp")
        task.pause()
        assert task.is_paused is True

        task.cancel()
        assert task.is_paused is False


class TestGetAuthHeaders:
    """认证请求头测试"""

    def test_huggingface_auth(self):
        from src.config import cfg
        cfg.set(cfg.hf_token, "test-token")
        headers = get_auth_headers("huggingface")
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-token"
        cfg.set(cfg.hf_token, "")

    def test_modelscope_auth(self):
        from src.config import cfg
        cfg.set(cfg.ms_token, "ms-token-123")
        headers = get_auth_headers("modelscope")
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer ms-token-123"
        cfg.set(cfg.ms_token, "")

    def test_no_auth(self):
        headers = get_auth_headers("huggingface")
        assert "Authorization" not in headers


class TestRepoProvider:
    """仓库提供者测试"""

    def test_list_files_huggingface(self, requests_mock):
        requests_mock.get(
            "https://hf-mirror.com/api/models/test/model/tree/main?recursive=True",
            json=[
                {"path": "model.bin", "size": 1024, "type": "file"},
                {"path": "config.json", "size": 512, "type": "file"},
                {"path": "subdir", "type": "directory"}
            ]
        )

        files = RepoProvider.list_files("huggingface", "test/model", "model", mirror_enabled=True)
        assert len(files) == 2
        assert files[0].name == "model.bin"
        assert files[1].name == "config.json"

    def test_list_files_modelscope(self, requests_mock):
        requests_mock.get(
            "https://www.modelscope.cn/api/v1/models/test/model/repo/files?Revision=master&Recursive=True",
            json={
                "Data": {
                    "Files": [
                        {"Name": "model.bin", "Size": 1024, "Path": "model.bin", "Type": "blob"},
                        {"Name": "config.json", "Size": 512, "Path": "config.json", "Type": "blob"}
                    ]
                }
            }
        )

        files = RepoProvider.list_files("modelscope", "test/model", "model")
        assert len(files) == 2
        assert files[0].name == "model.bin"
        assert files[1].name == "config.json"

    def test_search_models_huggingface(self, requests_mock):
        requests_mock.get(
            "https://huggingface.co/api/models?search=qwen&limit=20",
            json=[
                {"id": "Qwen/Qwen2.5-7B", "description": "Test model", "downloads": 1000, "likes": 500}
            ]
        )

        results = RepoProvider.search_models("huggingface", "qwen")
        assert len(results) == 1
        assert results[0]["id"] == "Qwen/Qwen2.5-7B"
        assert results[0]["name"] == "Qwen2.5-7B"
        assert results[0]["author"] == "Qwen"

    def test_search_models_modelscope(self, requests_mock):
        requests_mock.get(
            "https://www.modelscope.cn/api/v1/models?search=qwen&limit=20",
            json={
                "Data": [
                    {"Name": "qwen/Qwen2.5-7B", "Description": "Test model", "DownloadCount": 1000, "LikeCount": 500}
                ]
            }
        )

        results = RepoProvider.search_models("modelscope", "qwen")
        assert len(results) == 1
        assert results[0]["id"] == "qwen/Qwen2.5-7B"
        assert results[0]["name"] == "Qwen2.5-7B"
        assert results[0]["author"] == "qwen"