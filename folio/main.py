"""Start Folio."""

import os
import sys
import traceback

from PyQt5.QtCore import QCoreApplication, Qt
from PyQt5.QtWidgets import QApplication, QMessageBox

SPLASH_SECONDS = 1.8   # the start-up screen stays at least this long


def log_path():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    folder = os.path.join(base, "folio")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "folio.log")


def install_error_handler(app):
    """Log unexpected errors and keep going instead of closing the app."""
    showing = {"busy": False}

    def handler(kind, value, tb):
        text = "".join(traceback.format_exception(kind, value, tb))
        try:
            with open(log_path(), "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError:
            pass
        sys.stderr.write(text)
        if showing["busy"] or app.property("quiet_errors"):
            return
        showing["busy"] = True
        try:
            QMessageBox.warning(None, "Something went wrong",
                                "Folio hit a problem but your work is still open.\n"
                                "Saving now is a good idea.\n\n"
                                f"{kind.__name__}: {value}")
        finally:
            showing["busy"] = False

    sys.excepthook = handler


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(argv)
    app.setApplicationName("Folio")
    app.setOrganizationName("Folio")
    app.setDesktopFileName("folio")

    from .splash import Splash
    splash = Splash()
    splash.show()
    splash.step("Starting up\u2026", 0.12)

    from PyQt5.QtGui import QFontDatabase
    from . import theme
    from .window import MainWindow

    splash.step("Loading fonts\u2026", 0.38)
    from . import fonts
    fonts.load_bundled()            # the fonts that come with Folio
    QFontDatabase().families()      # read the font list now, not on first use
    theme.apply(app)
    install_error_handler(app)
    splash.step("Setting up your workspace\u2026", 0.68)
    win = MainWindow()
    splash.step("Ready", 1.0)
    splash.wait(SPLASH_SECONDS)
    if win.settings.value("geometry") is None:
        win.showMaximized()      # first run: use the whole screen
    else:
        win.show()
    files = [a for a in argv[1:] if not a.startswith("-")]

    def start():
        if files:
            win.open_path(os.path.abspath(files[0]), checked=True)
        elif not win.offer_rescue() and win.settings.value("show_start", True, type=bool):
            win.view.fit_page()
            win.new_document(first_run=True)
        win.view.fit_page()

    splash.fade_out(then=start)
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
