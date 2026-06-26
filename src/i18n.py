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
    "共 {0} 项": "{0} items",
    "确认关闭": "Confirm Close",
    "当前有 {0} 个任务正在下载中，关闭程序将暂停所有任务。": "{0} task(s) are currently downloading. Closing the program will pause all tasks.",
    "是否确定关闭？": "Are you sure you want to close?",
    "确认删除": "Confirm Delete",
    "以下文件已存在于本地：\n{0}\n\n是否同时删除本地文件？": "The following files already exist locally:\n{0}\n\nDo you want to also delete the local files?",
    "仅移除任务": "Remove Task Only",
    "同时删除文件": "Delete Files Too",
    "已删除本地文件": "Local file deleted",
    "删除失败": "Delete failed",

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
    "镜像与Token冲突": "Mirror and Token Conflict",
    "检测到您已配置 HuggingFace Token，HF-Mirror 镜像不支持 Token 认证。": "HuggingFace Token detected, but HF-Mirror does not support Token authentication.",
    "是否关闭 HF-Mirror 镜像以使用 Token 认证？": "Do you want to disable HF-Mirror to use Token authentication?",
    "是否清空 HuggingFace Token 以使用 HF-Mirror 镜像？": "Do you want to clear HuggingFace Token to use HF-Mirror?",
    "已关闭": "Disabled",
    "HF-Mirror 镜像已关闭，现在可以使用 Token 认证下载私有仓库": "HF-Mirror disabled, you can now download private repos with Token authentication",
    "已清空": "Cleared",
    "HuggingFace Token 已清空，HF-Mirror 镜像已启用": "HuggingFace Token cleared, HF-Mirror enabled",
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
    "暂无日志": "No logs",

    # ---- 文件选择对话框 ----
    "选择要下载的文件": "Select Files to Download",
    "共 {0} 个文件": "{0} files",
    "全选": "Select All",
    "展开全部": "Expand All",
    "折叠全部": "Collapse All",
    "已选择 0 项": "0 items selected",
    "已选择 {0} 项": "{0} items selected",
    "总大小: 0 B": "Total: 0 B",
    "总大小: {0}": "Total: {0}",
    "取消": "Cancel",
    "加入队列 (0)": "Add to Queue (0)",
    "加入队列 ({0})": "Add to Queue ({0})",
    "类型": "Type",
    "文件夹": "Folder",
    "单击选择保存目录": "Click to select save directory",
    "打开保存路径": "Open save path",

    # ---- RepoPage 日志 / InfoBar ----
    "正在获取 {0} 的文件列表...": "Fetching file list for {0}...",
    "❌ 未找到 {0} 的文件（已尝试model和dataset类型）": "❌ No files found for {0} (tried both model and dataset types)",
    "✅ 获取到 {0} 个文件": "✅ Retrieved {0} files",
    "已添加 {0} 个文件到下载队列": "Added {0} file(s) to the download queue",
    "获取文件列表失败: {0}": "Failed to get file list: {0}",
    "❌ 获取文件列表失败: {0}": "❌ Failed to get file list: {0}",
    "已添加": "Added",
    "已将 [{0}] 添加到下载队列": "Added [{0}] to download queue",
    "请输入模型/数据集ID": "Please enter a model/dataset ID",

    # ---- 文件类型 ----
    "模型文件": "Model file",
    "SafeTensor模型": "SafeTensor model",
    "PyTorch模型": "PyTorch model",
    "ONNX模型": "ONNX model",
    "配置文件": "Config file",
    "文本": "Text",
    "文档": "Document",
    "Python脚本": "Python script",
    "YAML配置": "YAML config",
    "Git配置": "Git config",
    "HDF5模型": "HDF5 model",
    "Pickle文件": "Pickle file",
    "文件": "file",

    # ---- 下载状态 ----
    "等待下载": "Waiting",
    "下载中": "Downloading",
    "已暂停": "Paused",
    "下载完成": "Completed",
    "下载失败": "Failed",
    "已取消": "Canceled",
    "连接中...": "Connecting...",
    "总进度: %p%": "Total: %p%",

    # ---- 下载队列内部消息 ----
    "没有可下载的任务": "No tasks available for download",
    "[{0}] 已添加: {1}": "[{0}] Added: {1}",
    "已恢复 {0} 个任务": "Resumed {0} task(s)",
    "已暂停 {0} 个任务": "Paused {0} task(s)",
    "已移除 {0} 个任务": "Removed {0} task(s)",
    "已清空下载队列": "Download queue cleared",
    "选择保存目录": "Select Save Directory",
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
