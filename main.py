import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentTranslator
from src.main_window import MainWindow


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

    icon_path = os.path.join(os.path.dirname(__file__), "src", "icon", "icon.ico")
    app.setWindowIcon(QIcon(icon_path))

    translator = FluentTranslator()
    app.installTranslator(translator)

    w = MainWindow()
    w.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()