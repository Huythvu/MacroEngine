"""Entry point: ``python -m macroengine.main``."""

from __future__ import annotations

import sys


def main() -> int:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from .gui.main_window import MainWindow
    from .resources import app_icon_path

    # On Windows, give the process its own taskbar identity so the taskbar shows
    # our icon instead of grouping under a generic python host.
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MacroEngine")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("MacroEngine")
    icon_path = app_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    if icon_path:
        window.setWindowIcon(QIcon(icon_path))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
