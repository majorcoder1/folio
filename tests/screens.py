"""Save screenshots of the main screens, for checking the look.

    QT_QPA_PLATFORM=offscreen python3 -m tests.screens OUTPUT_FOLDER
"""

import os
import sys
import tempfile

_HOME = tempfile.mkdtemp(prefix="folio-home-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_HOME, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_HOME, "data")

from PyQt5.QtCore import QPointF  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app = QApplication.instance() or QApplication(sys.argv)

from folio import theme  # noqa: E402
from folio.dialogs import ExportDialog  # noqa: E402
from folio.newdoc import NewDocumentDialog  # noqa: E402
from folio.document import cover_settings  # noqa: E402
from folio.items import RectItem, TextItem  # noqa: E402
from folio.scene import DocScene  # noqa: E402
from folio.window import MainWindow  # noqa: E402


def main(out):
    os.makedirs(out, exist_ok=True)
    theme.apply(app)
    win = MainWindow()
    win.resize(1440, 900)
    win.show()
    win.set_scene(DocScene(cover_settings(6, 9, 220, "cream")))
    QTest.qWait(50)
    win.view.fit_page()
    win.grab().save(os.path.join(out, "empty.png"))

    regs = win.scene.doc.regions()
    front = regs["front"]
    band = RectItem()
    band.fill = {"type": "linear", "color": "#ff0f1f3d", "color2": "#ff3a6ea5", "angle": 90}
    band.set_size(front.width() + 37.5, front.height() + 75)
    band.setPos(front.left(), front.top() - 37.5)
    win.scene.add_folio_item(band)
    title = win.create_text(QPointF(front.center().x(), front.top() + 700), text="NIGHT HARBOR")
    title.style.update({"family": "DejaVu Serif", "size": 190, "bold": True, "align": "center",
                        "tracking": 8})
    title.fill["color"] = "#fff5e6c8"
    title.shadow.update({"on": True, "blur": 18, "dx": 0, "dy": 10})
    title.apply_style()
    title.set_center_scene(QPointF(front.center().x(), front.top() + 650))
    author = win.create_text(QPointF(0, 0), text="A NOVEL BY JANE DOE")
    author.style.update({"family": "DejaVu Sans", "size": 70, "align": "center", "tracking": 20})
    author.fill["color"] = "#ffe0e6ef"
    author.apply_style()
    author.set_center_scene(QPointF(front.center().x(), front.bottom() - 300))
    win.scene.select_only([band])
    win.refresh_panels()
    win.dock_props.raise_()
    QTest.qWait(80)
    win.grab().save(os.path.join(out, "properties.png"))

    win.scene.select_only([title])
    win.refresh_panels()
    win.dock_text.raise_()
    QTest.qWait(80)
    win.grab().save(os.path.join(out, "text.png"))

    win.dock_transform.raise_()
    QTest.qWait(50)
    win.grab().save(os.path.join(out, "transform.png"))

    dlg = NewDocumentDialog(win)
    dlg.show()
    QTest.qWait(50)
    dlg.grab().save(os.path.join(out, "new_document.png"))
    dlg.close()

    dlg = ExportDialog(win, win.scene.doc)
    dlg.show()
    QTest.qWait(50)
    dlg.grab().save(os.path.join(out, "export.png"))
    dlg.close()
    win.undo.setClean()
    win.close()
    print("saved to", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="folio-screens-"))
