"""应用配置模块 — 基于 QFluentWidgets 的 QConfig，持久化主题和语言设置。"""

import os
from PySide6.QtCore import QLocale
from qfluentwidgets.common.config import (
    QConfig,
    ConfigItem,
    OptionsConfigItem,
    RangeConfigItem,
    OptionsValidator,
    BoolValidator,
    RangeValidator,
    qconfig,
    Theme,
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

    # HuggingFace Token（用于访问私有仓库和 gated repo）
    hf_token = ConfigItem(
        "Auth", "HuggingFaceToken", "",
    )

    # ModelScope Token（用于访问私有模型/数据集）
    ms_token = ConfigItem(
        "Auth", "ModelScopeToken", "",
    )

    # 下载速度限制（0 表示不限制，单位：MB/s）
    download_speed_limit = ConfigItem(
        "Download", "SpeedLimit", 0,
    )

    # 并发下载数量（1-8）
    download_concurrency = RangeConfigItem(
        "Download", "Concurrency", 4,
        RangeValidator(1, 8),
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

# 设置默认主题（QConfig 内置的 themeMode 属性）
cfg.themeMode.value = Theme.AUTO

# 加载配置（使用 qconfig.load 确保内置配置项如 themeMode 也被正确加载）
qconfig.load(get_config_path(), cfg)
