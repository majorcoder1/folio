# Slow audit: python3 -m tests.NAME (QT_QPA_PLATFORM=offscreen). Prints "problems: 0" when clean.
"""Trigger every menu action and tool in every persona, with and without content."""
import os, sys, tempfile, traceback, random, faulthandler
faulthandler.dump_traceback_later(420, exit=True)
h = tempfile.mkdtemp(); os.environ["XDG_CONFIG_HOME"] = h + "/c"; os.environ["XDG_DATA_HOME"] = h + "/d"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt5.QtCore import QPointF, QRectF, Qt, QEvent
from PyQt5.QtGui import QColor, QImage
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox, QFileDialog, QInputDialog, QMenu, QColorDialog
app = QApplication(sys.argv); app.setProperty("quiet_errors", True)
from folio import theme, fonts
fonts.load_bundled(); theme.apply(app)
from folio.window import MainWindow
from folio.scene import DocScene
from folio.document import cover_settings, page_settings
from folio.items import RectItem, EllipseItem, TextItem, ImageItem
from tests.test_smoke import drag

errors = []
sys.excepthook = lambda k, v, tb: errors.append("".join(traceback.format_exception(k, v, tb)))
# never block on a dialog
QDialog.exec_ = lambda self: 0
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.exec_ = lambda self: QMessageBox.Discard
QMessageBox.about = staticmethod(lambda *a, **k: None)
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: "")
QInputDialog.getText = staticmethod(lambda *a, **k: ("Test", True))
QInputDialog.getItem = staticmethod(lambda *a, **k: (a[3][0] if len(a) > 3 else "", True))
QMenu.exec_ = lambda self, *a: None
from PyQt5.QtPrintSupport import QPrintDialog, QPageSetupDialog, QPrintPreviewDialog
QPrintDialog.exec_ = lambda self: 0; QPageSetupDialog.exec_ = lambda self: 0; QPrintPreviewDialog.exec_ = lambda self: 0

win = MainWindow(); win.resize(1500, 950); win.show(); QTest.qWait(40)

def populate(win):
    win.set_scene(DocScene(cover_settings())); QTest.qWait(20)
    regs = win.scene.doc.regions(); f = regs["front"]
    win.create_shape("rect", f.adjusted(100, 100, -100, -1500))
    win.create_shape("star", f.adjusted(200, 900, -200, -900))
    win.create_text(f.center(), text="Hello")
    img = QImage(300, 200, QImage.Format_RGB32); img.fill(QColor("#336699"))
    win.place_qimage(img)
    win.scene.select_only([win.scene.folio_items()[0]])

def all_actions(win):
    seen, out = set(), []
    def walk(menu):
        for a in menu.actions():
            if a.menu(): walk(a.menu())
            elif not a.isSeparator() and id(a) not in seen:
                seen.add(id(a)); out.append(a)
    for a in win.menuBar().actions():
        if a.menu(): walk(a.menu())
    for a in win.actions():
        if id(a) not in seen: seen.add(id(a)); out.append(a)
    for a in win.persona_actions.values():
        if id(a) not in seen: seen.add(id(a)); out.append(a)
    return out

skip_text = ("Quit", "Close All", "Close")   # would end the audit
count = 0
for persona in ("design", "pixel", "export"):
    for filled in (False, True):
        win.set_persona("design")
        if filled: populate(win)
        else: win.set_scene(DocScene(page_settings(800, 600, "px", 72))); QTest.qWait(10)
        win.set_persona(persona); QTest.qWait(20)
        for a in all_actions(win):
            name = a.text().replace("&", "")
            if any(name.startswith(s) for s in skip_text) or name == "Toggle UI":
                continue
            before = len(errors)
            print("ACTION", persona, filled, name, flush=True)
            try:
                if a.isCheckable():
                    a.setChecked(not a.isChecked()); a.setChecked(not a.isChecked())
                else:
                    a.trigger()
            except Exception:
                errors.append(traceback.format_exc())
            count += 1
            app.processEvents()
            if len(errors) > before:
                errors[-1] = f"[{persona}, filled={filled}] action '{name}':\n" + errors[-1]
            win.stop_text_editing()
        # every tool: click, drag, double click on the page
        for tname in list(win.tools):
            try:
                win.set_tool(tname)
            except Exception:
                errors.append(f"[{persona}] set_tool {tname}\n" + traceback.format_exc())
                continue
            before = len(errors)
            print("TOOL", persona, tname, flush=True)
            f = win.scene.doc.page_rect()
            for a_, b_ in ((QPointF(f.width()*.2, f.height()*.2), QPointF(f.width()*.6, f.height()*.5)),
                           (QPointF(f.width()*.3, f.height()*.7), QPointF(f.width()*.31, f.height()*.71))):
                try:
                    drag(win.view, a_, b_, steps=4)
                    win.stop_text_editing()
                except Exception:
                    errors.append(f"[{persona}] tool {tname}\n" + traceback.format_exc())
            win.view.keyPressEvent  # noqa
            app.processEvents(); count += 1
        win.set_tool(win.tool_name)
print("actions and tools exercised:", count)
print("problems:", len(errors))
seen = set()
for e in errors:
    key = e.strip().splitlines()[-1]
    if key in seen: continue
    seen.add(key); print("-----"); print(e[-1500:])
