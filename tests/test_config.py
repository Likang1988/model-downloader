"""配置模块测试"""

import os
import tempfile
import pytest
from PySide6.QtCore import QLocale

from src.config import Language, AppConfig, cfg, get_config_dir, get_config_path


class TestLanguage:
    """语言类测试"""

    def test_from_code(self):
        assert Language.from_code("zh_CN").name() == "zh_CN"
        assert Language.from_code("en").name() == "en_US"
        assert Language.from_code("unknown").name() == "en_US"

    def test_to_code(self):
        assert Language.to_code(Language.ZH) == "zh_CN"
        assert Language.to_code(Language.EN) == "en_US"

    def test_display_name(self):
        assert Language.display_name("zh_CN") == "简体中文"
        assert Language.display_name("en") == "English"
        assert Language.display_name("unknown") == "unknown"

    def test_options(self):
        options = Language.options()
        assert len(options) == 2
        assert ("简体中文", "zh_CN") in options
        assert ("English", "en") in options


class TestAppConfig:
    """应用配置测试"""

    def test_default_values(self):
        cfg.set(cfg.hf_token, "")
        cfg.set(cfg.ms_token, "")
        cfg.set(cfg.download_speed_limit, 0)
        cfg.set(cfg.download_concurrency, 4)
        cfg.set(cfg.language, "zh_CN")
        cfg.set(cfg.mirror_enabled, True)

        assert cfg.get(cfg.language) == "zh_CN"
        assert cfg.get(cfg.mirror_enabled) is True
        assert cfg.get(cfg.hf_token) == ""
        assert cfg.get(cfg.ms_token) == ""
        assert cfg.get(cfg.download_speed_limit) == 0
        assert cfg.get(cfg.download_concurrency) == 4

    def test_set_and_get(self):
        cfg.set(cfg.language, "en")
        assert cfg.get(cfg.language) == "en"

        cfg.set(cfg.mirror_enabled, False)
        assert cfg.get(cfg.mirror_enabled) is False

        cfg.set(cfg.hf_token, "test-token-123")
        assert cfg.get(cfg.hf_token) == "test-token-123"

        cfg.set(cfg.download_speed_limit, 10)
        assert cfg.get(cfg.download_speed_limit) == 10

        cfg.set(cfg.download_concurrency, 2)
        assert cfg.get(cfg.download_concurrency) == 2

        cfg.set(cfg.language, "zh_CN")
        cfg.set(cfg.mirror_enabled, True)
        cfg.set(cfg.hf_token, "")
        cfg.set(cfg.download_speed_limit, 0)
        cfg.set(cfg.download_concurrency, 4)

    def test_concurrency_range(self):
        cfg.set(cfg.download_concurrency, 1)
        assert cfg.get(cfg.download_concurrency) == 1

        cfg.set(cfg.download_concurrency, 8)
        assert cfg.get(cfg.download_concurrency) == 8

        cfg.set(cfg.download_concurrency, 4)


class TestConfigPath:
    """配置路径测试"""

    def test_get_config_dir(self):
        path = get_config_dir()
        assert os.path.isdir(path)
        assert ".model_downloader" in path

    def test_get_config_path(self):
        path = get_config_path()
        assert ".model_downloader" in path
        assert path.endswith("config.json")