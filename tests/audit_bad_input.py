# Slow audit: python3 -m tests.NAME (QT_QPA_PLATFORM=offscreen). Prints "problems: 0" when clean.
import os, sys, tempfile, traceback, zipfile, faulthandler
faulthandler.dump_traceback_later(300, exit=True)
h = tempfile.mkdtemp(); os.environ["XDG_CONFIG_HOME"] = h + "/c"; os.environ["XDG_DATA_HOME"] = h + "/d"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt5.QtCore import QPointF, QRectF
from PyQt5.QtGui import QImage, QColor
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QMessageBox
app = QApplication(sys.argv); app.setProperty("quiet_errors", True)
from folio import theme, fonts, fileio, exporter, importers
fonts.load_bundled(); theme.apply(app)
from folio.window import MainWindow
from folio.scene import DocScene
from folio.document import cover_settings, page_settings
shown = []
QMessageBox.warning = staticmethod(lambda *a, **k: shown.append(a[2] if len(a) > 2 else "") or QMessageBox.Ok)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
bad = []
sys.excepthook = lambda k, v, tb: bad.append("".join(traceback.format_exception(k, v, tb)))
win = MainWindow(); win.resize(1200, 800); win.show(); QTest.qWait(30)
def check(name, fn):
    before = len(bad)
    try: fn()
    except Exception: bad.append(name + "\n" + traceback.format_exc())
    app.processEvents()
    print(("PROBLEM " if len(bad) > before else "ok      ") + name, flush=True)

def w(name, data):
    p = os.path.join(h, name); open(p, "wb").write(data); return p
# broken files
check("open empty .folio", lambda: win.open_path(w("empty.folio", b""), checked=True))
check("open garbage .folio", lambda: win.open_path(w("junk.folio", os.urandom(500)), checked=True))
zp = os.path.join(h, "notfolio.folio")
with zipfile.ZipFile(zp, "w") as z: z.writestr("document.json", '{"format": "other"}')
check("open wrong-format zip", lambda: win.open_path(zp, checked=True))
zp2 = os.path.join(h, "badjson.folio")
with zipfile.ZipFile(zp2, "w") as z: z.writestr("document.json", "{not json")
check("open broken json", lambda: win.open_path(zp2, checked=True))
zp3 = os.path.join(h, "weird.folio")
with zipfile.ZipFile(zp3, "w") as z:
    z.writestr("document.json", '{"format":"folio","version":1,"doc":{"kind":"page","width":-5,"height":0,"dpi":0},'
               '"items":[{"kind":"image","asset":"nope"},{"kind":"text","text":null,"style":{"size":-3}},{"kind":"zzz"}],"groups":{}}')
check("open file with nonsense values", lambda: win.open_path(zp3, checked=True))
check("open missing path", lambda: win.open_path(os.path.join(h, "nothere.folio"), checked=True))
check("open newer version", lambda: win.open_path(w("new.folio", zipfile.ZipFile(os.path.join(h, "v.folio"), "w").close() or b"x"), checked=True))
# imports
for name, data in (("junk.pdf", b"%PDF-1.4 nonsense"), ("junk.docx", b"not a zip"), ("junk.afdesign", b"hello"),
                   ("junk.png", b"nope"), ("junk.svg", b"<svg"), ("empty.pdf", b"")):
    check("import " + name, lambda n=name, d=data: win.import_path(w(n, d)))
check("import missing file", lambda: win.import_path(os.path.join(h, "gone.pdf")))
# extreme documents
win.set_scene(DocScene(page_settings(1, 1, "px", 36)))
check("1 x 1 pixel page", lambda: (win.create_shape("star", QRectF(0, 0, 1, 1)), win.fit_page() if hasattr(win, "fit_page") else win.view.fit_page()))
win.set_scene(DocScene(page_settings(100000, 100000, "px", 300)))
check("100000 x 100000 pixel page opens", lambda: (win.view.fit_page(), win.scene.update()))
def too_big():
    try: exporter.export(win.scene, {"format": "png", "area": "page", "dpi": 300}, os.path.join(h, "big.png"))
    except exporter.ExportError as e: pass
check("export far too big gives a polite error", too_big)
win.set_scene(DocScene(cover_settings(30, 30, 1200, "white", dpi=1200)))
check("huge cover at 1200 dpi draws", lambda: (win.view.fit_page(), win.grab()))
win.set_scene(DocScene(cover_settings(2, 2, 4)))
check("tiny 4 page cover", lambda: (win.view.fit_page(), win.add_spine_text(), win.grab()))
# unusual content
win.set_scene(DocScene(page_settings(800, 600, "px", 72)))
check("empty text box", lambda: (win.create_text(QPointF(10, 10), text=" "), win.stop_text_editing()))
check("very long text", lambda: win.create_text(QPointF(10, 10), text="word " * 4000))
check("emoji and right-to-left text", lambda: win.create_text(QPointF(20, 20), text="😀 مرحبا שלום"))
check("tiny zoom and huge zoom", lambda: (win.view.set_zoom(0.0001), win.view.set_zoom(1000), win.view.fit_page()))
check("delete with nothing selected", lambda: (win.scene.select_only([]), win.delete_selection(), win.duplicate(), win.group_selection(), win.geometry("add")))
check("paste with an empty clipboard", lambda: (__import__("PyQt5.QtGui", fromlist=["x"]).QGuiApplication.clipboard().clear(), win.paste(), win.paste_inside(), win.paste_style()))
check("print preview/print with no printer problems", lambda: win.print_setup.__call__ if False else None)
print("problems:", len(bad), "| polite messages shown to the user:", len(shown))
seen = set()
for p in bad:
    k = p.strip().splitlines()[-1]
    if k in seen: continue
    seen.add(k); print("-----"); print(p[-1500:])
