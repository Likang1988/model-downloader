"""应用配置模块 — 基于 QFluentWidgets 的 QConfig，持久化主题和语言设置。"""

import os
from PySide6.QtCore import QLocale
from qfluentwidgets.common.config import (
    QConfig,
    ConfigItem,
    OptionsConfigItem,
    OptionsValidator,
    BoolValidator,
)


class Language:
    """支持的语言"""

    ZH = QLocale(QLocale.Language.Chinese, QLocale.Script.SimplifiedChineseScript)   # zh_CN
    EN = QLocale(QLocale.Language.English)                                           # en_US

    _CODES = {"zh_CN": ZH, "en": EN}
    _DISPLAY = {"zh_CN": "简体中文", "en": "English"}

    @classmethod
    def from_code(cls, code: str) -> QLocale:
        return cls._CODES.get(code, cls.EN)

    @classmethod
    def to_code(cls, locale: QLocale) -> str:
        return locale.name()

    @classmethod
    def display_name(cls, code: str) -> str:
        return cls._DISPLAY.get(code, code)

    @classmethod
    def options(cls):
        """返回 [(显示名, code), ...] 用于 ComboBox"""
        return [(cls.display_name(c), c) for c in cls._CODES]


class AppConfig(QConfig):
    """应用自定义配置"""

    # 语言设置
    language = OptionsConfigItem(
        "App", "Language", "zh_CN",
        OptionsValidator(["zh_CN", "en"]),
    )

    # 镜像开关（持久化）
    mirror_enabled = ConfigItem(
        "Download", "MirrorEnabled", True,
        BoolValidator(),
    )


def get_config_dir():
    """配置文件存储目录 ~/.model_downloader/"""
    path = os.path.join(os.path.expanduser("~"), ".model_downloader")
    os.makedirs(path, exist_ok=True)
    return path


def get_config_path():
    """配置文件路径"""
    return os.path.join(get_config_dir(), "config.json")


# 全局唯一配置实例
cfg = AppConfig()
cfg.file = get_config_path()
cfg.load()
