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
    PushButton, InfoBar, InfoBarPosition,
    BodyLabel, TitleLabel, SubtitleLabel,
    setTheme
)
from qfluentwidgets.common.config import qconfig, Theme
from .downloader import RepoProvider, FileInfo
from .file_select_dialog import FileTreeDialog
from .download_queue import DownloadQueueWidget
from .download_log import LogWidget
from .download_history import HistoryPage
from .setting import SettingsPage
from .config import cfg
from .i18n import tr


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
        self.download_queue = DownloadQueueWidget(mirror_switch, provider)
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
        self.log_widget.retranslateUi()

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
            self.log_widget.log(tr("正在获取 {0} 的文件列表...").format(repo_id))
            mirror = self.mirror_switch.isChecked() if self.mirror_switch else False
            files = RepoProvider.list_files(self.provider, repo_id, repo_type, mirror_enabled=mirror)

            if not files:
                InfoBar.warning(
                    title=tr("提示"),
                    content=tr("未找到文件。请检查仓库ID和类型是否正确，或检查网络连接"),
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=5000,
                    parent=self
                )
                self.log_widget.log(tr("❌ 未找到 {0} 的文件（已尝试model和dataset类型）").format(repo_id))
                return

            self.log_widget.log(tr("✅ 获取到 {0} 个文件").format(len(files)))

            dialog = FileTreeDialog(files, self)
            if dialog.exec():
                selected = dialog.get_selected_files()
                for file_info in selected:
                    self.download_queue.add_file(file_info)
                InfoBar.success(
                    title=tr("添加成功"),
                    content=tr("已添加 {0} 个文件到下载队列").format(len(selected)),
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=3000,
                    parent=self
                )

        except Exception as e:
            err_msg = str(e)
            InfoBar.error(
                title=tr("错误"),
                content=tr("获取文件列表失败: {0}").format(err_msg),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=4000,
                parent=self
            )
            self.log_widget.log(tr("❌ 获取文件列表失败: {0}").format(err_msg))

    def on_log_message(self, message: str):
        self.log_widget.log(message)


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
        # 监听配置变化，同步更新主窗口的 mirror_switch
        cfg.mirror_enabled.valueChanged.connect(self.mirror_switch.setChecked)

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

    def closeEvent(self, event):
        active_count = 0
        active_count += self.hf_page.download_queue.get_active_count()
        active_count += self.ms_page.download_queue.get_active_count()
        
        if active_count > 0:
            from qfluentwidgets import MessageDialog
            dialog = MessageDialog(
                title=tr("确认关闭"),
                content=tr(f"当前有 {active_count} 个任务正在下载中，关闭程序将暂停所有任务。") + "\n\n" + tr("是否确定关闭？"),
                parent=self
            )
            if not dialog.exec():
                event.ignore()
                return
        
        self.hf_page.download_queue._shutdown()
        self.ms_page.download_queue._shutdown()
        
        event.accept()

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
            QIcon(resource_path("src/icon/history.svg")),
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
