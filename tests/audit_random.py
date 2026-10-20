# Slow audit: python3 -m tests.NAME (QT_QPA_PLATFORM=offscreen). Prints "problems: 0" when clean.
import os, sys, tempfile, traceback, random, json, faulthandler
faulthandler.dump_traceback_later(500, exit=True)
h = tempfile.mkdtemp(); os.environ["XDG_CONFIG_HOME"] = h + "/c"; os.environ["XDG_DATA_HOME"] = h + "/d"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QImage
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
app = QApplication(sys.argv); app.setProperty("quiet_errors", True)
from folio import theme, fonts, fileio, exporter
fonts.load_bundled(); theme.apply(app)
from folio.window import MainWindow
from folio.scene import DocScene
from folio.document import cover_settings, page_settings
from folio.items import ImageItem, PathItem
from tests.test_smoke import drag
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
problems = []
sys.excepthook = lambda k, v, tb: problems.append("".join(traceback.format_exception(k, v, tb)))
win = MainWindow(); win.resize(1400, 900); win.show(); QTest.qWait(30)

def snap(win):
    s = win.scene.snapshot()
    return json.dumps({"items": s["items"], "doc": s["doc"], "guides": s["guides"], "slices": s["slices"]}, sort_keys=True)

KINDS = ["rect", "ellipse", "rounded", "triangle", "diamond", "star", "polygon", "arrow", "heart"]
def step(win, rnd):
    sc = win.scene; items = sc.folio_items(); r = sc.doc.page_rect()
    pt = lambda: QPointF(rnd.uniform(r.left(), r.right()), rnd.uniform(r.top(), r.bottom()))
    def box():
        a = pt(); return QRectF(a, QPointF(a.x() + rnd.uniform(60, 700), a.y() + rnd.uniform(60, 700)))
    pick = lambda n=1: sc.select_only(rnd.sample(items, min(n, len(items)))) if items else None
    op = rnd.choice(["shape"] * 4 + ["text", "image", "delete", "dup", "group", "ungroup", "front", "back",
        "fwd", "bwd", "flip", "rot", "lock", "hide", "showall", "align", "dist", "move", "geo", "curves",
        "separate", "paste_inside", "release", "style", "colour", "stroke", "opacity", "blend", "guide",
        "slice", "undo", "undo", "redo", "px", "px", "copy_paste", "select_all", "invert"])
    if op == "shape": win.create_shape(rnd.choice(KINDS), box())
    elif op == "text": win.create_text(pt(), text=rnd.choice(["Title", "A", "Long words here", "ÀÉ"]))
    elif op == "image":
        im = QImage(rnd.randint(50, 400), rnd.randint(50, 400), QImage.Format_RGB32); im.fill(QColor(rnd.randint(0, 0xffffff)))
        win.place_qimage(im)
    elif op == "delete": pick(rnd.randint(1, 3)); win.delete_selection()
    elif op == "dup": pick(2); win.duplicate()
    elif op == "group": pick(3); win.group_selection()
    elif op == "ungroup": pick(3); win.ungroup_selection()
    elif op in ("front", "back", "fwd", "bwd"): pick(2); win.arrange({"front": "front", "back": "back", "fwd": "forward", "bwd": "backward"}[op])
    elif op == "flip": pick(2); win.flip(rnd.random() < .5)
    elif op == "rot": pick(2); win.rotate_by(rnd.choice([90, -90, 37]))
    elif op == "lock": pick(2); win.toggle_lock()
    elif op == "hide": pick(1); win.hide_selection()
    elif op == "showall": win.show_all()
    elif op == "align":
        pick(3); win.align(rnd.choice(["left", "hcenter", "right", "top", "vcenter", "bottom"]))
    elif op == "dist": pick(4); win.distribute(rnd.choice("hv"))
    elif op == "move": pick(2); win.nudge(rnd.randint(-30, 30), rnd.randint(-30, 30))
    elif op == "geo": pick(3); win.geometry(rnd.choice(["add", "subtract", "intersect", "xor", "divide"]))
    elif op == "curves": pick(2); win.convert_to_curves()
    elif op == "separate": pick(2); win.separate_curves()
    elif op == "paste_inside":
        pick(1); win.copy(); pick(1); win.paste_inside()
    elif op == "release": pick(3); win.release_clip()
    elif op == "style":
        pick(1); win.copy(); pick(2); win.paste_style()
    elif op == "colour": pick(2); win.apply_colour(QColor(rnd.randint(0, 0xffffff)), merge=rnd.random() < .5, target=rnd.choice(["fill", "stroke"]))
    elif op == "stroke":
        pick(2); win.strokep.on_button("style", rnd.choice(["none", "solid", "dash"])); win.strokep.on_width(rnd.choice([0, 1, 8]))
        win.strokep.on_button("align", rnd.choice(["center", "inside", "outside"]))
    elif op == "opacity": pick(2); win.layers.opacity.setEditText(f"{rnd.randint(0, 100)} %"); win.layers.on_opacity()
    elif op == "blend":
        pick(2); win.layers.blend.setCurrentIndex(rnd.randrange(win.layers.blend.count())); win.layers.on_blend()
    elif op == "guide": win.add_guide(rnd.choice("xy"), rnd.uniform(0, 3000))
    elif op == "slice": win.add_slice(box())
    elif op == "undo": win.do_undo()
    elif op == "redo": win.do_redo()
    elif op == "px":
        win.set_persona("pixel"); win.set_tool(rnd.choice(["px-brush", "px-erase", "px-blur", "px-dodge", "px-burn"]))
        win.use_brush(rnd.choice(list(__import__("folio.brushes", fromlist=["x"]).BY_NAME.values())))
        a = pt(); drag(win.view, a, a + QPointF(rnd.uniform(-300, 300), rnd.uniform(-300, 300)), steps=3)
        win.set_persona("design")
    elif op == "copy_paste": pick(2); win.copy(); win.paste()
    elif op == "select_all": win.select_all()
    elif op == "invert": win.invert_selection()
    return op

total = 0
for seed in (1, 2, 3, 4):
    rnd = random.Random(seed)
    win.set_scene(DocScene(rnd.choice([cover_settings(), page_settings(1200, 900, "px", 150), cover_settings(binding="hardcover")])))
    win.set_persona("design"); QTest.qWait(10); win.undo.clear()
    ops = []
    for i in range(160):
        try:
            ops.append(step(win, rnd))
        except Exception:
            problems.append(f"seed {seed} step {i} op {ops[-1:] }:\n" + traceback.format_exc())
        total += 1
        app.processEvents()
    if win.view.editing_text is not None: win.stop_text_editing()
    # 1. undo everything, redo everything: must come back identical
    final = snap(win)
    n = win.undo.count()
    try:
        while win.undo.canUndo(): win.do_undo()
        while win.undo.canRedo(): win.do_redo()
    except Exception:
        problems.append(f"seed {seed} undo/redo walk:\n" + traceback.format_exc())
    after = snap(win)
    if after != final:
        a = json.loads(final); b = json.loads(after)
        diff = [k for k in a if a[k] != b[k]]
        problems.append(f"seed {seed}: undo-all/redo-all changed the document ({n} steps) in {diff}")
    # 2. save, open, compare
    path = os.path.join(h, f"fuzz{seed}.folio")
    try:
        fileio.save_document(win.scene, path)
        snapd, assets = fileio.load_document(path)
        win.open_path(path, checked=True)
        reopened = snap(win)
        if json.loads(reopened)["items"] != json.loads(final)["items"]:
            problems.append(f"seed {seed}: save then open changed the objects")
    except Exception:
        problems.append(f"seed {seed} save/open:\n" + traceback.format_exc())
    # 3. export every format
    try:
        for fmt in ("pdf", "png", "jpeg"):
            exporter.export(win.scene, {"format": fmt, "area": "page", "dpi": 50, "quality": 80, "outline_text": True},
                            os.path.join(h, f"o.{fmt}"))
        win.export_slices(win.scene.slices, tempfile.mkdtemp())
    except Exception:
        problems.append(f"seed {seed} export:\n" + traceback.format_exc())
    print("seed", seed, "ok:", len(win.scene.folio_items()), "objects,", n, "undo steps, ops used:", len(set(ops)), flush=True)
print("random actions:", total, "problems:", len(problems))
seen = set()
for p in problems:
    k = p.strip().splitlines()[-1]
    if k in seen: continue
    seen.add(k); print("-----"); print(p[-1800:])
