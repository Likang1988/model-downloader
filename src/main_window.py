import os
import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from qfluentwidgets import (
    FluentWindow, FluentIcon as FIF, NavigationItemPosition,
    SearchLineEdit, ComboBox, SwitchButton, PrimaryPushButton,
    PushButton, InfoBar, InfoBarPosition
)
from qfluentwidgets.common.config import qconfig, Theme
from .downloader import RepoProvider, FileInfo
from .file_select_dialog import FileTreeDialog
from .download_queue import DownloadQueueWidget
from .download_log import LogWidget
from .config import cfg, Language


def resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径，兼容开发环境和 PyInstaller 打包后的运行环境。"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


class RepoPage(QWidget):
    """模型仓库页面 - 获取文件 + 下载队列 + 日志"""
    def __init__(self, provider: str, mirror_switch, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.mirror_switch = mirror_switch
        self.download_queue = DownloadQueueWidget(mirror_switch)
        self.init_ui()

        # 连接日志信号
        self.download_queue.log_message.connect(self.on_log_message)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # ========== 顶部：标题 + 搜索区域 ==========
        title = QLabel(f"{'Hugging Face' if self.provider == 'huggingface' else 'ModelScope'}")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # 搜索行：repo ID 输入 + 获取文件按钮
        search_layout = QHBoxLayout()
        self.repo_id_edit = SearchLineEdit()
        self.repo_id_edit.setPlaceholderText(
            "输入模型/数据集ID，如: Qwen/Qwen2.5-7B"
        )
        self.repo_id_edit.returnPressed.connect(self.on_browse)

        self.repo_type_combo = ComboBox()
        self.repo_type_combo.addItem("模型", "model")
        self.repo_type_combo.addItem("数据集", "dataset")

        self.browse_btn = PrimaryPushButton("📂 获取文件")
        self.browse_btn.clicked.connect(self.on_browse)

        search_layout.addWidget(self.repo_id_edit, 1)
        search_layout.addWidget(self.repo_type_combo)
        search_layout.addWidget(self.browse_btn)
        layout.addLayout(search_layout)

        # ========== 中间：下载队列 ==========
        layout.addWidget(self.download_queue, 3)

        # ========== 底部：下载日志 ==========
        self.log_widget = LogWidget()
        self.log_widget.setFixedHeight(150)
        layout.addWidget(self.log_widget, 1)

    def on_browse(self):
        repo_id = self.repo_id_edit.text().strip()
        if not repo_id:
            InfoBar.warning(
                title="提示",
                content="请输入模型/数据集ID",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )
            return

        repo_type = self.repo_type_combo.currentData()

        try:
            self.log_widget.log(f"正在获取 {repo_id} 的文件列表...")
            mirror = self.mirror_switch.isChecked() if self.mirror_switch else False
            files = RepoProvider.list_files(self.provider, repo_id, repo_type, mirror_enabled=mirror)

            if not files:
                InfoBar.warning(
                    title="提示",
                    content=f"未找到文件。请检查仓库ID和类型是否正确，或检查网络连接",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=5000,
                    parent=self
                )
                self.log_widget.log(f"❌ 未找到 {repo_id} 的文件（已尝试model和dataset类型）")
                return

            self.log_widget.log(f"✅ 获取到 {len(files)} 个文件")

            dialog = FileTreeDialog(files, self)
            if dialog.exec():
                selected = dialog.get_selected_files()
                for file_info in selected:
                    self.download_queue.add_file(file_info)
                InfoBar.success(
                    title="添加成功",
                    content=f"已添加 {len(selected)} 个文件到下载队列",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=3000,
                    parent=self
                )

        except Exception as e:
            InfoBar.error(
                title="错误",
                content=f"获取文件列表失败: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=4000,
                parent=self
            )
            self.log_widget.log(f"❌ 获取文件列表失败: {str(e)}")

    def on_log_message(self, message: str):
        self.log_widget.log(message)


class SettingsPage(QWidget):
    """设置页面 — 镜像、主题、语言"""
    def __init__(self, mirror_switch=None, app=None, translator=None, parent=None):
        super().__init__(parent)
        self.mirror_switch = mirror_switch or SwitchButton()
        self._app = app
        self._translator = translator
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("设置")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # ---- 卡片容器（统一去除白色背景，交由主题控制） ----
        def make_card():
            card = QFrame()
            card.setObjectName("settings_card")
            return card

        # ======== 外观卡片：主题 + 语言 ========
        appearance_card = make_card()
        appearance_layout = QVBoxLayout(appearance_card)
        appearance_layout.setSpacing(12)

        appearance_title = QLabel("外观")
        appearance_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        appearance_layout.addWidget(appearance_title)

        # -- 主题 --
        theme_row = QHBoxLayout()
        theme_label = QLabel("主题模式")
        theme_label.setStyleSheet("font-size: 14px;")
        self.theme_combo = ComboBox()
        self.theme_combo.addItem("浅色", "Light")
        self.theme_combo.addItem("深色", "Dark")
        self.theme_combo.addItem("跟随系统", "Auto")
        # 设置当前值
        current_theme = qconfig.get(cfg.themeMode)
        theme_map = {Theme.LIGHT: "Light", Theme.DARK: "Dark", Theme.AUTO: "Auto"}
        self.theme_combo.setCurrentIndex(
            list(theme_map.values()).index(theme_map.get(current_theme, "Light"))
        )
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(theme_label)
        theme_row.addStretch()
        theme_row.addWidget(self.theme_combo)
        appearance_layout.addLayout(theme_row)

        # -- 语言 --
        lang_row = QHBoxLayout()
        lang_label = QLabel("界面语言")
        lang_label.setStyleSheet("font-size: 14px;")
        self.lang_combo = ComboBox()
        current_lang = cfg.get(cfg.language)
        for display, code in Language.options():
            self.lang_combo.addItem(display, code)
            if code == current_lang:
                self.lang_combo.setCurrentIndex(self.lang_combo.count() - 1)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_row.addWidget(lang_label)
        lang_row.addStretch()
        lang_row.addWidget(self.lang_combo)
        appearance_layout.addLayout(lang_row)

        layout.addWidget(appearance_card)

        # ======== 下载卡片：镜像开关 ========
        mirror_card = make_card()
        mirror_layout = QHBoxLayout(mirror_card)

        mirror_label = QLabel("使用 HF-Mirror 镜像（国内加速访问 Hugging Face）")
        mirror_label.setStyleSheet("font-size: 14px;")

        # 从配置恢复镜像开关状态
        self.mirror_switch.setChecked(cfg.get(cfg.mirror_enabled))
        self.mirror_switch.checkedChanged.connect(self._on_mirror_changed)

        mirror_layout.addWidget(mirror_label)
        mirror_layout.addStretch()
        mirror_layout.addWidget(self.mirror_switch)
        layout.addWidget(mirror_card)

        # ======== 关于卡片 ========
        about_card = make_card()
        about_layout = QVBoxLayout(about_card)

        about_title = QLabel("关于")
        about_title.setStyleSheet("font-size: 16px; font-weight: bold;")

        about_text = QLabel(
            "大模型下载工具 v1.0\n\n"
            "支持从 Hugging Face 和 ModelScope 下载模型与数据集。\n"
            "可自主选择需要下载的文件，支持断点续传、暂停/恢复。\n\n"
            "提示：国内用户建议开启 HF-Mirror 镜像以加速下载。"
        )
        about_text.setWordWrap(True)
        about_text.setStyleSheet("color: #555; line-height: 1.6;")

        about_layout.addWidget(about_title)
        about_layout.addWidget(about_text)
        layout.addWidget(about_card)

        layout.addStretch()

    # ---- 事件处理 ----

    def _on_theme_changed(self, index):
        theme_map = {"Light": Theme.LIGHT, "Dark": Theme.DARK, "Auto": Theme.AUTO}
        text = self.theme_combo.itemData(index)
        new_theme = theme_map.get(text, Theme.LIGHT)
        qconfig.set(cfg.themeMode, new_theme)

    def _on_language_changed(self, index):
        code = self.lang_combo.itemData(index)
        if code == cfg.get(cfg.language):
            return
        cfg.set(cfg.language, code)
        # 提示重启生效
        InfoBar.success(
            title="语言已更改",
            content="重启应用后生效",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=5000,
            parent=self,
        )

    def _on_mirror_changed(self, checked):
        cfg.set(cfg.mirror_enabled, checked)


class MainWindow(FluentWindow):
    def __init__(self, translator=None):
        super().__init__()
        self._translator = translator
        self.setWindowTitle("大模型下载工具")
        icon_path = resource_path(os.path.join("src", "icon", "icon.ico"))
        self.setWindowIcon(QIcon(icon_path))
        self.resize(1100, 750)

        # 镜像开关
        self.mirror_switch = SwitchButton()
        self.mirror_switch.setChecked(cfg.get(cfg.mirror_enabled))

        # 创建页面
        self.hf_page = RepoPage("huggingface", self.mirror_switch)
        self.ms_page = RepoPage("modelscope", self.mirror_switch)
        self.settings_page = SettingsPage(self.mirror_switch, translator=translator)

        # 初始化导航
        self.initNavigation()

    def initNavigation(self):
        self.ms_page.setObjectName("ms_page")
        self.hf_page.setObjectName("hf_page")        
        self.settings_page.setObjectName("settings_page")
        
        self.addSubInterface(
            self.ms_page,
            QIcon(resource_path("src/icon/modelscope.svg")),
            "ModelScope"
        )
        self.addSubInterface(
            self.hf_page,
            QIcon(resource_path("src/icon/huggingface.svg")),
            "Hugging Face"
        )

        self.addSubInterface(
            self.settings_page,
            FIF.SETTING,
            "设置",
            position=NavigationItemPosition.BOTTOM
        )
