import os
import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QIcon, QDesktopServices
from qfluentwidgets import (
    FluentWindow, FluentIcon as FIF, NavigationItemPosition,
    SearchLineEdit, ComboBox, SwitchButton, PrimaryPushButton,
    PushButton, InfoBar, InfoBarPosition, OptionsSettingCard,
    BodyLabel, TitleLabel, CaptionLabel, SubtitleLabel,
    PasswordLineEdit, ToolButton, setTheme
)
from qfluentwidgets.common.config import qconfig, Theme
from .downloader import RepoProvider, FileInfo
from .file_select_dialog import FileTreeDialog
from .download_queue import DownloadQueueWidget
from .download_log import LogWidget
from .download_history import HistoryPage
from .config import cfg, Language
from .i18n import tr, install_language


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
        self.title_label = TitleLabel(f"{'Hugging Face' if self.provider == 'huggingface' else 'ModelScope'}")
        layout.addWidget(self.title_label)

        # 搜索行：repo ID 输入 + 获取文件按钮
        search_layout = QHBoxLayout()
        self.repo_id_edit = SearchLineEdit()
        self.repo_id_edit.setPlaceholderText(
            tr("输入模型/数据集ID，如: Qwen/Qwen2.5-7B")
        )
        self.repo_id_edit.returnPressed.connect(self.on_browse)

        self.repo_type_combo = ComboBox()
        self.repo_type_combo.addItem(tr("模型"), "model")
        self.repo_type_combo.addItem(tr("数据集"), "dataset")

        self.browse_btn = PrimaryPushButton(tr("获取文件"))
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

    def retranslateUi(self):
        name = "Hugging Face" if self.provider == "huggingface" else "ModelScope"
        self.title_label.setText(name)
        self.repo_id_edit.setPlaceholderText(tr("输入模型/数据集ID，如: Qwen/Qwen2.5-7B"))
        self.browse_btn.setText(tr("获取文件"))
        # 重新填充 ComboBox 以更新显示文本
        idx = self.repo_type_combo.currentIndex()
        data = self.repo_type_combo.currentData()
        self.repo_type_combo.clear()
        self.repo_type_combo.addItem(tr("模型"), "model")
        self.repo_type_combo.addItem(tr("数据集"), "dataset")
        # 恢复选中项
        for i in range(self.repo_type_combo.count()):
            if self.repo_type_combo.itemData(i) == data:
                self.repo_type_combo.setCurrentIndex(i)
                break
        self.download_queue.retranslateUi()

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
    def __init__(self, mirror_switch=None, app=None, translator=None, main_window=None, parent=None):
        super().__init__(parent)
        self.mirror_switch = mirror_switch or SwitchButton()
        self._app = app
        self._translator = translator
        self._main_window = main_window
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self.settings_title = TitleLabel(tr("设置"))
        layout.addWidget(self.settings_title)

        # ======== 外观卡片：主题 + 语言 ========
        appearance_card = QFrame()
        appearance_card.setObjectName("settings_card")
        appearance_layout = QVBoxLayout(appearance_card)
        appearance_layout.setSpacing(12)

        self.appearance_title = SubtitleLabel(tr("外观"))
        appearance_layout.addWidget(self.appearance_title)

        # -- 主题 --
        self.themeCard = OptionsSettingCard(
            cfg.themeMode,
            FIF.BRUSH,
            tr("主题模式"),
            tr("更改应用的外观"),
            texts=[tr("浅色"), tr("深色"), tr("跟随系统")],
            parent=self
        )
        appearance_layout.addWidget(self.themeCard)

        # -- 语言（使用与主题一致的 OptionsSettingCard 样式） --
        lang_options = [d for d, _ in Language.options()]
        self.langCard = OptionsSettingCard(
            cfg.language,
            FIF.LANGUAGE,
            tr("界面语言"),
            tr("切换应用的显示语言"),
            texts=lang_options,
            parent=self
        )
        # 语言设置 — 监听配置项值变化
        cfg.language.valueChanged.connect(self._on_language_changed)
        appearance_layout.addWidget(self.langCard)

        layout.addWidget(appearance_card)

        # ======== 下载卡片：镜像开关 ========
        mirror_card = QFrame()
        mirror_card.setObjectName("settings_card")
        mirror_layout = QHBoxLayout(mirror_card)

        self.mirror_label = BodyLabel(tr("使用 HF-Mirror 镜像（国内加速访问 Hugging Face）"))

        # 从配置恢复镜像开关状态
        self.mirror_switch.setChecked(cfg.get(cfg.mirror_enabled))
        self.mirror_switch.checkedChanged.connect(self._on_mirror_changed)

        mirror_layout.addWidget(self.mirror_label)
        mirror_layout.addStretch()
        mirror_layout.addWidget(self.mirror_switch)
        layout.addWidget(mirror_card)

        # ======== 认证卡片：HF Token + ModelScope Token ========
        auth_card = QFrame()
        auth_card.setObjectName("settings_card")
        auth_layout = QVBoxLayout(auth_card)
        auth_layout.setSpacing(12)

        self.auth_title = SubtitleLabel(tr("认证"))
        auth_layout.addWidget(self.auth_title)

        # -- HuggingFace Token --
        hf_row = QHBoxLayout()
        hf_label = BodyLabel("HuggingFace Token")
        hf_label.setMinimumWidth(100)
        self.hf_token_edit = PasswordLineEdit()
        self.hf_token_edit.setPlaceholderText(tr("输入 HF Token（私有仓库需要）"))
        self.hf_token_edit.setText(cfg.get(cfg.hf_token))
        hf_row.addWidget(hf_label)
        hf_row.addWidget(self.hf_token_edit, 1)
        hf_link_btn = ToolButton(FIF.LINK)
        hf_link_btn.setToolTip(tr("获取 HuggingFace Token（打开 huggggingface.co/settings/tokens）"))
        hf_link_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://huggingface.co/settings/tokens"))
        )
        hf_row.addWidget(hf_link_btn)
        auth_layout.addLayout(hf_row)

        # -- ModelScope Token --
        ms_row = QHBoxLayout()
        ms_label = BodyLabel("ModelScope Token")
        ms_label.setMinimumWidth(100)
        self.ms_token_edit = PasswordLineEdit()
        self.ms_token_edit.setPlaceholderText(tr("输入 ModelScope Token（私有仓库需要）"))
        self.ms_token_edit.setText(cfg.get(cfg.ms_token))
        ms_row.addWidget(ms_label)
        ms_row.addWidget(self.ms_token_edit, 1)
        ms_link_btn = ToolButton(FIF.LINK)
        ms_link_btn.setToolTip(tr("获取 ModelScope Token（打开 www.modelscope.cn/my/myaccesstoken）"))
        ms_link_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://www.modelscope.cn/my/myaccesstoken")
            )
        )
        ms_row.addWidget(ms_link_btn)
        auth_layout.addLayout(ms_row)

        # -- 提示文字 --
        self.auth_hint = CaptionLabel(tr("Token 仅用于 API 认证，安全存储在本地配置文件中"))
        self.auth_hint.setStyleSheet("color: #888;")
        auth_layout.addWidget(self.auth_hint)

        # -- 保存按钮 --
        self.save_auth_btn = PushButton(FIF.SAVE, tr("保存认证信息"))
        self.save_auth_btn.setFixedHeight(32)
        self.save_auth_btn.clicked.connect(self._on_save_tokens)
        auth_layout.addWidget(self.save_auth_btn)

        layout.addWidget(auth_card)

        # ======== 关于卡片 ========
        about_card = QFrame()
        about_card.setObjectName("settings_card")
        about_layout = QVBoxLayout(about_card)

        self.about_title = SubtitleLabel(tr("关于"))

        self.about_text = BodyLabel(
            tr("大模型下载工具 v1.0\n\n"
               "支持从 Hugging Face 和 ModelScope 下载模型与数据集。\n"
               "可自主选择需要下载的文件，支持断点续传、暂停/恢复。\n\n"
               "提示：国内用户建议开启 HF-Mirror 镜像以加速下载。")
        )
        self.about_text.setWordWrap(True)

        about_layout.addWidget(self.about_title)
        about_layout.addWidget(self.about_text)
        layout.addWidget(about_card)

        layout.addStretch()

    def retranslateUi(self):
        self.settings_title.setText(tr("设置"))
        self.appearance_title.setText(tr("外观"))
        self.mirror_label.setText(tr("使用 HF-Mirror 镜像（国内加速访问 Hugging Face）"))
        self.auth_title.setText(tr("认证"))
        self.hf_token_edit.setPlaceholderText(tr("输入 HF Token（私有仓库需要）"))
        self.ms_token_edit.setPlaceholderText(tr("输入 ModelScope Token（私有仓库需要）"))
        self.auth_hint.setText(tr("Token 仅用于 API 认证，安全存储在本地配置文件中"))
        self.save_auth_btn.setText(tr("保存认证信息"))
        self.about_title.setText(tr("关于"))
        self.about_text.setText(
            tr("大模型下载工具 v1.0\n\n"
               "支持从 Hugging Face 和 ModelScope 下载模型与数据集。\n"
               "可自主选择需要下载的文件，支持断点续传、暂停/恢复。\n\n"
               "提示：国内用户建议开启 HF-Mirror 镜像以加速下载。")
        )

    # ---- 事件处理 ----

    def _on_language_changed(self, code: str):
        """语言切换回调 — 配置项值变化时触发"""
        locale = Language.from_code(code)
        install_language(locale, self._app)
        InfoBar.success(
            title=tr("成功"),
            content=tr("语言已切换"),
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self,
        )
        # 通知主窗口重绘所有页面
        if self._main_window:
            self._main_window.retranslateAll()

    def _on_mirror_changed(self, checked):
        cfg.set(cfg.mirror_enabled, checked)

    def _on_save_tokens(self):
        """保存 Token 认证信息并提示"""
        cfg.set(cfg.hf_token, self.hf_token_edit.text().strip())
        cfg.set(cfg.ms_token, self.ms_token_edit.text().strip())
        InfoBar.success(
            title="认证信息已保存",
            content="Token 已安全存储在本地配置文件中",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self,
        )


class MainWindow(FluentWindow):
    def __init__(self, translator=None, app=None):
        super().__init__()
        self._translator = translator
        self._app = app
        self.setWindowTitle(tr("大模型下载工具"))
        icon_path = resource_path(os.path.join("src", "icon", "icon.ico"))
        self.setWindowIcon(QIcon(icon_path))
        self.resize(1100, 750)

        # 镜像开关
        self.mirror_switch = SwitchButton()
        self.mirror_switch.setChecked(cfg.get(cfg.mirror_enabled))

        # 创建页面
        self.hf_page = RepoPage("huggingface", self.mirror_switch)
        self.ms_page = RepoPage("modelscope", self.mirror_switch)
        self.history_page = HistoryPage()
        self.settings_page = SettingsPage(self.mirror_switch, translator=translator, main_window=self, app=app)

        # 历史页重新下载信号连接
        self.history_page.record_double_clicked.connect(self._on_history_redownload)

        # 初始化导航
        self.initNavigation()
        
        # 监听主题变化（按照官方示例的方式）
        cfg.themeChanged.connect(setTheme)

    def retranslateAll(self):
        """所有页面重新翻译 — 语言切换时调用"""
        self.setWindowTitle(tr("大模型下载工具"))
        # 更新导航项（移除后重新添加以更新文字）
        for name in ["ms_page", "hf_page", "history_page", "settings_page"]:
            self.navigationInterface.removeWidget(name)
        self.initNavigation()

        # 通知各子页面
        self.hf_page.retranslateUi()
        self.ms_page.retranslateUi()
        self.history_page.retranslateUi()
        self.settings_page.retranslateUi()

    def initNavigation(self):
        self.ms_page.setObjectName("ms_page")
        self.hf_page.setObjectName("hf_page")
        self.history_page.setObjectName("history_page")
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
            self.history_page,
            FIF.HISTORY,
            tr("下载历史")
        )

        self.addSubInterface(
            self.settings_page,
            FIF.SETTING,
            tr("设置"),
            position=NavigationItemPosition.BOTTOM
        )

    def _on_history_redownload(self, record: dict):
        """从历史记录页重新下载"""
        page = self.hf_page if record.get("provider") == "huggingface" else self.ms_page
        file_info = FileInfo(
            name=record.get("file_name", ""),
            size=record.get("file_size", 0),
            path="",           # path 对重新下载不重要，由 download_queue 处理
            repo_id=record.get("repo_id", ""),
            repo_type="model",  # 默认 model 类型
            provider=record.get("provider", ""),
        )
        page.download_queue.add_file(file_info)
        InfoBar.success(
            title="已添加",
            content=f"已将 [{record.get('file_name')}] 添加到下载队列",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self.history_page
        )
        # 切换到对应平台页面
        self.stackedWidget.setCurrentWidget(page)
