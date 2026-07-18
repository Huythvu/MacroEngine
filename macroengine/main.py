"""Entry point: ``python -m macroengine.main``."""

from __future__ import annotations

import sys


def _setup_logging() -> None:
    import logging
    from logging.handlers import RotatingFileHandler

    from .paths import app_data_dir

    try:
        handler = RotatingFileHandler(
            app_data_dir() / "macroengine.log", maxBytes=512_000, backupCount=2, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.basicConfig(level=logging.INFO, handlers=[handler])
    except Exception:  # noqa: BLE001  (logging must never crash startup)
        pass


def main() -> int:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from .gui.main_window import MainWindow
    from .resources import app_icon_path

    _setup_logging()

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
