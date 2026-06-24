import sys
import os
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt
from qfluentwidgets import (
    FluentWindow, FluentIcon as FIF, NavigationItemPosition,
    ComboBox, setTheme, Theme, qconfig, QConfig, ConfigItem, 
    OptionsConfigItem, OptionsValidator, BoolValidator
)


class AppConfig(QConfig):
    """应用自定义配置"""
    language = OptionsConfigItem(
        "App", "Language", "zh_CN",
        OptionsValidator(["zh_CN", "en"]),
    )
    mirror_enabled = ConfigItem(
        "Download", "MirrorEnabled", True,
        BoolValidator(),
    )


def get_config_path():
    path = os.path.join(os.path.expanduser("~"), ".model_downloader_test")
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, "config.json")


cfg = AppConfig()
cfg.themeMode.value = Theme.AUTO
qconfig.load(get_config_path(), cfg)

print(f"初始主题: {cfg.get(cfg.themeMode)}")
print(f"cfg.themeMode: {cfg.themeMode}")
print(f"cfg._cfg: {cfg._cfg}")
print(f"cfg._cfg.themeMode: {cfg._cfg.themeMode}")
print(f"cfg.themeMode is cfg._cfg.themeMode: {cfg.themeMode is cfg._cfg.themeMode}")


class TestWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("主题切换测试")
        self.resize(800, 600)
        
        # 创建测试页面
        self.test_page = QWidget()
        self.test_page.setObjectName("test_page")
        layout = QVBoxLayout(self.test_page)
        
        self.label = QLabel("主题测试页面")
        layout.addWidget(self.label)
        
        # 主题下拉框
        self.theme_combo = ComboBox()
        self.theme_combo.addItem("浅色", "Light")
        self.theme_combo.addItem("深色", "Dark")
        self.theme_combo.addItem("跟随系统", "Auto")
        
        current_theme = cfg.get(cfg.themeMode)
        theme_map = {Theme.LIGHT: "Light", Theme.DARK: "Dark", Theme.AUTO: "Auto"}
        current_text = theme_map.get(current_theme, "Auto")
        idx_map = {"Light": 0, "Dark": 1, "Auto": 2}
        self.theme_combo.setCurrentIndex(idx_map.get(current_text, 2))
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        layout.addWidget(self.theme_combo)
        
        # 添加页面到导航
        self.addSubInterface(self.test_page, FIF.HOME, "测试")
        
        # 连接主题变化信号
        cfg.themeChanged.connect(self._on_theme_signal)
        print("已连接 cfg.themeChanged 信号")
    
    def _on_theme_changed(self, index):
        """主题下拉框变化回调"""
        text = self.theme_combo.itemData(index)
        theme_map = {"Light": Theme.LIGHT, "Dark": Theme.DARK, "Auto": Theme.AUTO}
        theme = theme_map.get(text, Theme.AUTO)
        print(f"下拉框选择: {text} -> {theme}")
        print(f"调用 cfg.set(cfg.themeMode, {theme}, save=True)")
        cfg.set(cfg.themeMode, theme, save=True)
        print(f"设置后的主题: {cfg.get(cfg.themeMode)}")
    
    def _on_theme_signal(self, theme):
        """主题变化信号回调"""
        print(f"收到 themeChanged 信号: {theme}")
        print(f"调用 setTheme({theme})")
        setTheme(theme)
        print(f"当前 isDarkTheme: {qconfig.theme == Theme.DARK}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())