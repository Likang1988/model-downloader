"""国际化/本地化模块 — 为项目提供中英双语翻译支持。

用法：
  from .i18n import tr

  title = tr("设置")          # 当前语言是 zh_CN 时返回 "设置"，en 时返回 "Settings"
"""

from PySide6.QtCore import QLocale
from qfluentwidgets import FluentTranslator


# ── 字符串翻译表 ──────────────────────────────────────────
# key 为中文原串，value 为英文翻译
_STRINGS: dict[str, str] = {
    # ---- 通用 ----
    "提示": "Hint",
    "错误": "Error",
    "成功": "Success",
    "完成": "Completed",
    "失败": "Failed",
    "全部": "All",
    "名称": "Name",
    "大小": "Size",
    "状态": "Status",
    "来源": "Source",
    "序号": "No.",
    "文件名": "File Name",
    "保存路径": "Save Path",
    "模型ID": "Model ID",
    "进度": "Progress",
    "已下载": "Downloaded",
    "总大小": "Total Size",
    "速度": "Speed",
    "剩余时间": "Remaining Time",
    "完成时间": "Completed Time",
    "共 0 项": "0 items",

    # ---- 导航 ----
    "下载历史": "Download History",
    "设置": "Settings",
    "大模型下载工具": "Model Downloader",

    # ---- RepoPage ----
    "获取文件": "Get Files",
    "模型": "Model",
    "数据集": "Dataset",
    "获取文件失败": "Failed to get file list",
    "添加成功": "Added successfully",
    "未找到文件。请检查仓库ID和类型是否正确，或检查网络连接": "No files found. Please check the repo ID and type, or check your network connection.",
    "请输入模型/数据集ID": "Please enter a model/dataset ID",
    "输入模型/数据集ID，如: Qwen/Qwen2.5-7B": "Enter model/dataset ID, e.g. Qwen/Qwen2.5-7B",

    # ---- 下载队列 ----
    "下载队列": "Download Queue",
    "保存路径:": "Save path:",
    "开始": "Start",
    "暂停": "Pause",
    "继续": "Resume",
    "移除": "Remove",
    "清空": "Clear",
    "重新下载": "Redownload",
    "已添加": "Added",
    "打开位置": "Open Location",
    "删除记录": "Delete Record",
    "清空全部历史": "Clear all history",

    # ---- SettingsPage ----
    "外观": "Appearance",
    "主题模式": "Theme Mode",
    "更改应用的外观": "Change the appearance of the application",
    "浅色": "Light",
    "深色": "Dark",
    "跟随系统": "Follow System",
    "界面语言": "Language",
    "语言已更改": "Language changed",
    "语言已切换": "Language switched",
    "切换应用的显示语言": "Switch the display language of the application",
    "使用 HF-Mirror 镜像（国内加速访问 Hugging Face）": "Use HF-Mirror (faster access in China)",
    "认证": "Authentication",
    "HuggingFace Token": "HuggingFace Token",
    "ModelScope Token": "ModelScope Token",
    "输入 HF Token（私有仓库需要）": "Enter HF Token (required for private repos)",
    "输入 ModelScope Token（私有仓库需要）": "Enter ModelScope Token (required for private repos)",
    "获取 HuggingFace Token（打开 huggggingface.co/settings/tokens）": "Get HuggingFace Token (opens huggingface.co/settings/tokens)",
    "获取 ModelScope Token（打开 www.modelscope.cn/my/myaccesstoken）": "Get ModelScope Token (opens modelscope.cn/my/myaccesstoken)",
    "Token 仅用于 API 认证，安全存储在本地配置文件中": "Token is only used for API authentication, stored securely in the local config file",
    "保存认证信息": "Save Auth Info",
    "认证信息已保存": "Auth info saved",
    "Token 已安全存储在本地配置文件中": "Token has been securely stored in the local config file",
    "关于": "About",
    "大模型下载工具 v1.0\n\n"
    "支持从 Hugging Face 和 ModelScope 下载模型与数据集。\n"
    "可自主选择需要下载的文件，支持断点续传、暂停/恢复。\n\n"
    "提示：国内用户建议开启 HF-Mirror 镜像以加速下载。": (
        "Model Downloader v1.0\n\n"
        "Download models and datasets from Hugging Face and ModelScope.\n"
        "Select files you need, with resume, pause/restart support.\n\n"
        "Tip: Enable HF-Mirror for faster downloads in China."
    ),

    # ---- 下载历史 ----
    "确认删除": "Confirm Delete",
    "清空历史": "Clear History",
    "暂无历史记录": "No history records",
    "请先选择一条历史记录": "Please select a history record first",
    "请先选择要重新下载的记录": "Please select a record to redownload first",
    "请先选择要删除的记录": "Please select a record to delete first",
    "已将": "Added",
    "个文件添加到下载队列": "file(s) to the download queue",
    "确定要删除选中的": "Are you sure you want to delete ",
    "条历史记录吗？": " history record(s)?",
    "确定要清空全部下载历史吗？此操作不可恢复。": "Are you sure you want to clear all download history? This cannot be undone.",
    "文件路径不存在": "File path does not exist",

    # ---- 下载日志 ----
    "下载日志": "Download Log",
}

# ── 单例翻译器引用 ──
_current_locale: QLocale = QLocale(QLocale.Language.Chinese)
_current_app = None
_old_translator = None


def tr(text: str) -> str:
    """翻译 API — 返回当前语言对应的文本。

    Args:
        text: 中文原文（代码中的字符串原文）

    Returns:
        当前语言下的翻译文本。语言为 zh_CN 时返回原文本。
    """
    code = _current_locale.name()
    if code.startswith("zh"):
        return text
    return _STRINGS.get(text, text)


def install_language(locale: QLocale, app=None) -> FluentTranslator:
    """安装新的语言环境，更新 FluentTranslator。

    Args:
        locale: 目标 QLocale
        app: QApplication 实例（用于安装 translator）

    Returns:
        新的 FluentTranslator 实例
    """
    global _current_locale, _current_app, _old_translator

    _current_locale = locale
    if app is not None:
        _current_app = app

    # 移除旧的 FluentTranslator
    if _current_app is not None and _old_translator is not None:
        _current_app.removeTranslator(_old_translator)

    # 安装新的 FluentTranslator
    fl_trans = FluentTranslator(locale)
    if _current_app is not None:
        _current_app.installTranslator(fl_trans)
    _old_translator = fl_trans

    return fl_trans


def current_locale() -> QLocale:
    return _current_locale
