import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QComboBox, QLabel
from qfluentwidgets import setTheme, Theme, qconfig
from qfluentwidgets.common.config import QConfig, OptionsConfigItem, OptionsValidator

class Config(QConfig):
    themeMode = OptionsConfigItem(
        "MainWindow", "ThemeMode", "Light",
        OptionsValidator(["Light", "Dark", "Auto"])
    )

cfg = Config()
qconfig.load("test_config.json", cfg)

class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.label = QLabel("主题测试")
        layout.addWidget(self.label)
        
        self.combo = QComboBox()
        self.combo.addItem("浅色", Theme.LIGHT)
        self.combo.addItem("深色", Theme.DARK)
        self.combo.addItem("跟随系统", Theme.AUTO)
        self.combo.currentIndexChanged.connect(self.on_theme_changed)
        layout.addWidget(self.combo)
        
        self.setWindowTitle("主题切换测试")
        self.resize(300, 200)
    
    def on_theme_changed(self, index):
        theme = self.combo.itemData(index)
        print(f"切换主题: {theme}")
        setTheme(theme)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
