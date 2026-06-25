"""设置页面模块 — 包含主题、语言、镜像、认证和关于等设置卡片。"""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt
from qfluentwidgets import (
    FluentIcon as FIF,
    InfoBar, InfoBarPosition,
    ComboBoxSettingCard,
    TitleLabel,
    PasswordLineEdit, ToolButton, SmoothScrollArea, LineEdit, SpinBox,
    SettingCardGroup, SwitchSettingCard, SettingCard, HyperlinkCard,
    HyperlinkButton, RangeSettingCard, PrimaryPushButton
)
from .config import cfg, Language
from .i18n import tr, install_language


class SpinBoxSettingCard(SettingCard):
    """带数字输入框的设置卡片"""
    def __init__(self, icon, title, content, config_item, suffix="", parent=None):
        super().__init__(icon, title, content, parent)
        self.config_item = config_item
        self.suffix = suffix

        # 数字输入框
        self.spin_box = SpinBox(self)
        self.spin_box.setMinimumWidth(100)
        self.spin_box.setValue(cfg.get(config_item))
        self.spin_box.setMinimum(0)
        self.spin_box.setMaximum(999999)
        self.spin_box.setSuffix(" " + suffix if suffix else "")

        self.hBoxLayout.addWidget(self.spin_box, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)

        # 监听值变化
        self.spin_box.valueChanged.connect(self._on_value_changed)

    def _on_value_changed(self, value):
        cfg.set(self.config_item, value)


class TokenSettingCard(SettingCard):
    """带密码输入框的设置卡片"""
    def __init__(self, icon, title, content, config_item, parent=None):
        super().__init__(icon, title, content, parent)
        self.config_item = config_item
        self.password_edit = PasswordLineEdit(self)
        self.password_edit.setText(cfg.get(config_item))
        self.password_edit.setClearButtonEnabled(True)
        self.password_edit.setMinimumWidth(450)
        self.hBoxLayout.addWidget(self.password_edit)
        self.hBoxLayout.addSpacing(8)
        # 保存按钮
        self.save_btn = ToolButton(FIF.SAVE, self)
        self.save_btn.setFixedHeight(30)
        self.save_btn.clicked.connect(self._on_save)
        self.hBoxLayout.addWidget(self.save_btn)
        self.hBoxLayout.addSpacing(16)

    def _on_save(self):
        cfg.set(self.config_item, self.password_edit.text().strip())
        InfoBar.success(
            title=tr("已保存"),
            content=tr("Token 已安全存储在本地配置文件中"),
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self.window()
        )

    def getValue(self):
        return self.password_edit.text().strip()


class TokenLinksCard(SettingCard):
    """包含两个 Token 获取链接的卡片"""
    def __init__(self, parent=None):
        super().__init__(FIF.LINK, tr("获取 Token"), tr("前往对应平台获取访问令牌"), parent)
        # HuggingFace 链接
        self.hf_link = HyperlinkButton(
            "https://huggingface.co/settings/tokens",
            tr("HuggingFace"),
            self
        )
        self.hf_link.setFixedHeight(30)
        # ModelScope 链接
        self.ms_link = HyperlinkButton(
            "https://www.modelscope.cn/my/myaccesstoken",
            tr("ModelScope"),
            self
        )
        self.ms_link.setFixedHeight(30)
        # 添加到布局
        self.hBoxLayout.addWidget(self.hf_link, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(8)
        self.hBoxLayout.addWidget(self.ms_link, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)


class AboutCard(SettingCard):
    """关于信息卡片"""
    def __init__(self, parent=None):
        super().__init__(FIF.INFO, tr("关于"), tr("© Likang988, v1.0"), parent)
        # GitHub 链接
        self.github_link = HyperlinkButton(
            "https://github.com/Likang1988/model-downloader",
            "GitHub",
            self
        )
        self.github_link.setFixedHeight(30)
        self.hBoxLayout.addWidget(self.github_link, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)


class SettingsPage(QWidget):
    """设置页面 — 镜像、主题、语言"""
    def __init__(self, mirror_switch=None, app=None, translator=None, main_window=None, parent=None):
        super().__init__(parent)
        self.mirror_switch = mirror_switch
        self._app = app
        self._translator = translator
        self._main_window = main_window
        self.init_ui()

    def init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = SmoothScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self.settings_title = TitleLabel(tr("设置"))
        layout.addWidget(self.settings_title)

        # ======== 外观设置组：主题 + 语言 ========
        self.appearanceGroup = SettingCardGroup(tr("外观"), self)
        # -- 主题 --
        self.themeCard = ComboBoxSettingCard(
            cfg.themeMode,
            FIF.BRUSH,
            tr("主题模式"),
            tr("更改应用的外观"),
            texts=[tr("浅色"), tr("深色"), tr("跟随系统")],
            parent=self
        )
        # -- 语言 --
        lang_options = [d for d, _ in Language.options()]
        self.langCard = ComboBoxSettingCard(
            cfg.language,
            FIF.LANGUAGE,
            tr("界面语言"),
            tr("切换应用的显示语言"),
            texts=lang_options,
            parent=self
        )
        # 语言设置 — 监听配置项值变化
        cfg.language.valueChanged.connect(self._on_language_changed)
        self.appearanceGroup.addSettingCard(self.themeCard)
        self.appearanceGroup.addSettingCard(self.langCard)
        layout.addWidget(self.appearanceGroup)

        # ======== 下载设置组：镜像开关 ========
        self.downloadGroup = SettingCardGroup(tr("下载设置"), self)
        self.mirrorCard = SwitchSettingCard(
            FIF.GLOBE,
            tr("使用 HF-Mirror 镜像"),
            tr("国内加速访问 Hugging Face"),
            cfg.mirror_enabled,
            self.downloadGroup
        )
        # 监听开关状态变化
        self.mirrorCard.switchButton.checkedChanged.connect(self._on_mirror_changed)

        # 速度限制
        self.speedLimitCard = SpinBoxSettingCard(
            FIF.DOWNLOAD,
            tr("下载速度限制"),
            tr("0 表示不限制，单位 MB/s"),
            cfg.download_speed_limit,
            "MB/s",
            self.downloadGroup
        )

        # 并发数量
        self.concurrencyCard = RangeSettingCard(
            cfg.download_concurrency,
            FIF.SYNC,
            tr("并发下载数量"),
            tr("同时下载的文件数量"),
            self.downloadGroup
        )

        self.downloadGroup.addSettingCard(self.mirrorCard)
        self.downloadGroup.addSettingCard(self.speedLimitCard)
        self.downloadGroup.addSettingCard(self.concurrencyCard)
        layout.addWidget(self.downloadGroup)

        # ======== 认证设置组：HF Token + ModelScope Token ========
        self.authGroup = SettingCardGroup(tr("认证"), self)
        # HuggingFace Token
        self.hfTokenCard = TokenSettingCard(
            FIF.FINGERPRINT,
            tr("HuggingFace Token"),
            tr("私有仓库需要认证"),
            cfg.hf_token,
            self.authGroup
        )
        # ModelScope Token
        self.msTokenCard = TokenSettingCard(
            FIF.FINGERPRINT,
            tr("ModelScope Token"),
            tr("私有仓库需要认证"),
            cfg.ms_token,
            self.authGroup
        )
        # Token 获取链接（合并两个链接到一个卡片）
        self.tokenLinksCard = TokenLinksCard(self.authGroup)
        self.authGroup.addSettingCard(self.hfTokenCard)
        self.authGroup.addSettingCard(self.msTokenCard)
        self.authGroup.addSettingCard(self.tokenLinksCard)
        layout.addWidget(self.authGroup)

        # ======== 关于卡片 ========
        self.aboutGroup = SettingCardGroup(tr("关于"), self)
        self.aboutCard = AboutCard(self.aboutGroup)
        self.aboutGroup.addSettingCard(self.aboutCard)
        layout.addWidget(self.aboutGroup)

        layout.addStretch()

        # 将内容放入滚动区域
        scroll.setWidget(content_widget)
        scroll.enableTransparentBackground()
        outer_layout.addWidget(scroll)

    def retranslateUi(self):
        self.settings_title.setText(tr("设置"))
        self.appearanceGroup.setTitle(tr("外观"))
        self.downloadGroup.setTitle(tr("下载设置"))
        self.mirrorCard.setTitle(tr("使用 HF-Mirror 镜像"))
        self.mirrorCard.setContent(tr("国内加速访问 Hugging Face"))
        self.speedLimitCard.setTitle(tr("下载速度限制"))
        self.speedLimitCard.setContent(tr("0 表示不限制，单位 MB/s"))
        self.concurrencyCard.setTitle(tr("并发下载数量"))
        self.concurrencyCard.setContent(tr("同时下载的文件数量"))
        self.authGroup.setTitle(tr("认证"))
        self.hfTokenCard.setTitle(tr("HuggingFace Token"))
        self.hfTokenCard.setContent(tr("私有仓库需要认证"))
        self.msTokenCard.setTitle(tr("ModelScope Token"))
        self.msTokenCard.setContent(tr("私有仓库需要认证"))
        self.tokenLinksCard.setTitle(tr("获取 Token"))
        self.tokenLinksCard.setContent(tr("前往对应平台获取访问令牌"))
        self.tokenLinksCard.hf_link.setText(tr("HuggingFace"))
        self.tokenLinksCard.ms_link.setText(tr("ModelScope"))
        self.aboutGroup.setTitle(tr("关于"))
        self.aboutCard.setTitle(tr("关于"))
        self.aboutCard.setContent(tr("大模型下载工具 v1.0"))

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
