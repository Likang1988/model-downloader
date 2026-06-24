import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentTranslator
from qfluentwidgets.common.config import qconfig, Theme
from src.config import cfg, Language
from src.main_window import MainWindow


def resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径，兼容开发环境和 PyInstaller 打包后的运行环境。"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def main():
    # Windows 任务栏图标需要设置 AppUserModelID
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ModelDownloader")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)

    icon_path = resource_path(os.path.join("src", "icon", "icon.ico"))
    app.setWindowIcon(QIcon(icon_path))

    # 应用保存的语言设置
    lang_code = cfg.get(cfg.language)
    locale = Language.from_code(lang_code)
    current_translator = FluentTranslator(locale)
    app.installTranslator(current_translator)

    # 应用保存的主题设置
    # qconfig 已自动从 config.json 恢复 themeMode，但显式应用一下确保生效
    qconfig.set(cfg.themeMode, qconfig.get(cfg.themeMode))

    w = MainWindow(current_translator)
    w.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
