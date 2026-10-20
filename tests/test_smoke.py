"""End-to-end checks that run without a screen.

Run from the project folder:

    QT_QPA_PLATFORM=offscreen python3 -m tests.test_smoke
"""

import os
import subprocess
import sys
import tempfile

from PyQt5.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QImage, QMouseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Keep test settings and autosaves away from the real ones.
_HOME = tempfile.mkdtemp(prefix="folio-home-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_HOME, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_HOME, "data")

app = QApplication.instance() or QApplication(sys.argv)
app.setProperty("quiet_errors", True)

from folio import exporter, fileio, theme  # noqa: E402
from folio.document import cover_settings, page_settings  # noqa: E402
from folio.items import EllipseItem, ImageItem, PathItem, RectItem, TextItem  # noqa: E402
from folio.main import install_error_handler  # noqa: E402
from folio.scene import DocScene  # noqa: E402
from folio.window import MainWindow  # noqa: E402

ERRORS = []


def _hook(kind, value, tb):
    import traceback
    ERRORS.append("".join(traceback.format_exception(kind, value, tb)))


theme.apply(app)
install_error_handler(app)
sys.excepthook = _hook
OUT = tempfile.mkdtemp(prefix="folio-test-")


def check(cond, what):
    if not cond:
        raise AssertionError(what)
    print("ok  ", what)


def mouse(view, kind, pos, button=Qt.LeftButton, buttons=None, mods=Qt.NoModifier):
    """Send a mouse event at a page position."""
    vp = view.mapFromScene(pos)
    if buttons is None:
        buttons = button if kind != QEvent.MouseButtonRelease else Qt.NoButton
    ev = QMouseEvent(kind, QPointF(vp), view.viewport().mapToGlobal(vp), button, buttons, mods)
    QApplication.sendEvent(view.viewport(), ev)


def drag(view, a, b, mods=Qt.NoModifier, steps=6):
    mouse(view, QEvent.MouseButtonPress, a, mods=mods)
    for i in range(1, steps + 1):
        p = a + (b - a) * (i / steps)
        mouse(view, QEvent.MouseMove, p, button=Qt.NoButton, buttons=Qt.LeftButton, mods=mods)
    mouse(view, QEvent.MouseButtonRelease, b, mods=mods)


def make_photo(path, w=1200, h=1800):
    from PyQt5.QtGui import QLinearGradient, QPainter
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0, QColor("#1d3b6e"))
    g.setColorAt(1, QColor("#e2803a"))
    p.fillRect(img.rect(), g)
    p.setBrush(QColor("#ffe082"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(w * 0.7, h * 0.3), w * 0.12, w * 0.12)
    p.end()
    img.save(path, "JPEG", 90)


def main():
    win = MainWindow()
    win.resize(1400, 900)
    win.show()
    QTest.qWait(50)
    view = win.view
    win.set_scene(DocScene(cover_settings(6, 9, 300, "cream")))
    QTest.qWait(50)
    view.fit_page()
    scene = win.scene
    doc = scene.doc
    regs = doc.regions()
    check(abs(doc.spine_in - 0.75) < 1e-9, "spine for 300 cream pages is 0.75 in")
    check(abs(doc.page_width - (0.125 * 2 + 12 + 0.75) * 300) < 1e-6, "full cover width")

    # --- photo on the front cover, filling it
    photo = os.path.join(OUT, "photo.jpg")
    make_photo(photo)
    win.place_image_files([photo], regs["front"].center())
    img = scene.selected_folio()[0]
    check(isinstance(img, ImageItem), "image placed and selected")
    win.size_images_to("front", cover=True)
    img = scene.selected_folio()[0]
    area = win.bleed_area("front")
    b = img.scene_bounds()
    check(abs(b.center().x() - area.center().x()) < 1, "image centred on front")
    check(b.left() <= area.left() + 1 and b.right() >= area.right() - 1
          and b.top() <= area.top() + 1 and b.bottom() >= area.bottom() - 1,
          "image fills the front cover and its bleed")

    # --- rectangle drawn with the tool
    win.set_tool("rect")
    a = QPointF(regs["back"].left() + 200, regs["back"].top() + 300)
    b = a + QPointF(900, 400)
    drag(view, a, b)
    sel = scene.selected_folio()
    check(len(sel) == 1 and isinstance(sel[0], RectItem), "rectangle drawn")
    rect = sel[0]
    check(abs(rect.w - 900) < 30 and abs(rect.h - 400) < 30, f"rectangle size {rect.w:.0f}x{rect.h:.0f}")
    check(win.tool_name == "move", "back to Move tool after drawing")

    # --- move it by dragging (snapping may pull it a little)
    before = rect.pos()
    c = rect.scene_bounds().center()
    drag(view, c, c + QPointF(300, 250))
    moved = rect.pos() - before
    check(abs(moved.x() - 300) < 40 and abs(moved.y() - 250) < 40, f"rectangle moved {moved.x():.0f},{moved.y():.0f}")

    # --- undo the move, redo it
    win.do_undo()
    r2 = scene.selected_folio()[0]
    check(abs(r2.pos().x() - before.x()) < 0.01, "undo puts it back")
    win.do_redo()
    r3 = scene.find(rect.uid)
    check(abs(r3.pos().x() - (before.x() + moved.x())) < 0.01, "redo moves it again")

    # --- resize with the bottom-right handle
    win.scene.select_only([r3])
    frame = view.selection_frame()
    h = frame["points"]["br"]
    w0 = r3.w
    drag(view, h, h + QPointF(150, 0))
    r4 = scene.find(rect.uid)
    check(abs(r4.w - (w0 + 150)) < 25, f"resize wider {w0:.0f} -> {r4.w:.0f}")

    # --- rotate with the round handle
    frame = view.selection_frame()
    rot = frame["rot"]
    centre = r4.center_scene()
    radius = (rot - centre)
    target = centre + QPointF(abs(radius.y()), 0)
    drag(view, rot, target)
    r5 = scene.find(rect.uid)
    check(abs(abs(r5.rotation()) - 90) < 3, f"rotated to {r5.rotation():.1f}")
    win.do_undo()

    # --- text: click with the text tool, type, escape
    win.set_tool("text")
    tp = QPointF(regs["front"].center().x(), regs["front"].top() + 600)
    mouse(view, QEvent.MouseButtonPress, tp)
    mouse(view, QEvent.MouseButtonRelease, tp)
    check(view.editing_text is not None, "typing started")
    view.setFocus()
    QTest.keyClicks(view, "The Long Road Home")
    QTest.keyClick(view, Qt.Key_Escape)
    texts = [i for i in scene.folio_items() if isinstance(i, TextItem)]
    check(len(texts) == 1 and texts[0].toPlainText() == "The Long Road Home", "title typed")
    check(view.editing_text is None, "typing stopped")
    title = texts[0]
    check(win.tool_name == "move", "Move tool after typing")
    # letters such as V, M or T typed into text must not switch tools
    check(texts[0].toPlainText().count("o") == 3, "letters went into the text")

    # style the title through the panels
    scene.select_only([title])
    win.refresh_panels()
    win.textp.size.setValue(60)
    win.textp.bold.setChecked(True)
    title = scene.find(title.uid)
    check(abs(title.style["size"] - 60 * 300 / 72) < 1, "font size set from panel")
    check(title.style["bold"], "bold from panel")
    win.props.shadow_on.setChecked(True)
    title = scene.find(title.uid)
    check(title.shadow["on"], "shadow switched on")
    win.align_to.setCurrentIndex(win.align_to.findData("front"))
    win.align("hcenter")
    title = scene.find(title.uid)
    check(abs(title.scene_bounds().center().x() - regs["front"].center().x()) < 1, "title centred on front")

    # --- spine text
    win.add_spine_text()
    spine_text = scene.selected_folio()[0]
    check(isinstance(spine_text, TextItem) and abs(spine_text.rotation() - 90) < 1e-6, "spine text added")
    check(abs(spine_text.center_scene().x() - regs["spine"].center().x()) < 1, "spine text centred")
    check(spine_text.scene_bounds().width() <= regs["spine"].width(), "spine text fits the spine")

    # --- pen: a closed triangle
    win.set_tool("pen")
    base = QPointF(regs["back"].left() + 300, regs["back"].bottom() - 900)
    pts = [base, base + QPointF(400, 0), base + QPointF(200, -350)]
    for p in pts:
        mouse(view, QEvent.MouseButtonPress, p)
        mouse(view, QEvent.MouseButtonRelease, p)
    mouse(view, QEvent.MouseButtonPress, pts[0])
    mouse(view, QEvent.MouseButtonRelease, pts[0])
    paths = [i for i in scene.folio_items() if isinstance(i, PathItem)]
    check(len(paths) == 1 and paths[0].closed and len(paths[0].nodes) == 3, "pen made a closed triangle")

    # --- node tool: drag a point
    tri = paths[0]
    scene.select_only([tri])
    win.set_tool("node")
    p0 = tri.mapToScene(QPointF(*tri.nodes[1]["p"]))
    drag(view, p0, p0 + QPointF(100, 0))
    tri = scene.find(tri.uid)
    q = tri.mapToScene(QPointF(*tri.nodes[1]["p"]))
    check(abs(q.x() - (p0.x() + 100)) < 25, "node moved")
    win.set_tool("move")

    # --- group, duplicate, arrange
    scene.select_only([scene.find(rect.uid), scene.find(tri.uid)])
    win.group_selection()
    g = scene.find(rect.uid).group
    check(g is not None and scene.find(tri.uid).group == g, "grouped")
    win.duplicate()
    check(len(scene.folio_items()) == 7, f"duplicate made copies ({len(scene.folio_items())} objects)")
    win.arrange("back")
    win.layers.rebuild()
    check(win.layers.tree.topLevelItemCount() >= 4, "layers panel lists objects")

    # --- save, open again
    path = os.path.join(OUT, "cover.folio")
    check(win.write_file(path), "saved")
    snap_before = scene.snapshot()
    win.open_path(path, checked=True)
    snap_after = win.scene.snapshot()
    check(snap_before["items"] == snap_after["items"], "file opens with the same objects")
    check(snap_before["doc"] == snap_after["doc"], "file keeps page settings")
    scene = win.scene

    # --- exports
    pdf = os.path.join(OUT, "cover.pdf")
    exporter.export(scene, {"format": "pdf", "area": "page", "outline_text": True}, pdf)
    info = subprocess.run(["pdfinfo", "-box", pdf], capture_output=True, text=True).stdout
    print(info)
    w_pt = doc.page_width / 300 * 72
    h_pt = doc.page_height / 300 * 72
    check(f"{w_pt:.2f} x {h_pt:.2f}" in info or f"{w_pt:g} x {h_pt:g}" in info,
          f"PDF page is exactly {w_pt:.2f} x {h_pt:.2f} pt")
    fonts = subprocess.run(["pdffonts", pdf], capture_output=True, text=True).stdout
    check(len(fonts.strip().splitlines()) <= 2, "no fonts needed in the PDF (text is shapes)")
    png = os.path.join(OUT, "front.png")
    exporter.export(scene, {"format": "png", "area": "front", "dpi": 150}, png)
    im = QImage(png)
    check(im.width() == round(regs["front"].width() / 2) and not im.isNull(), f"front PNG {im.width()}x{im.height()}")
    jpg = os.path.join(OUT, "cover.jpg")
    exporter.export(scene, {"format": "jpeg", "area": "trim", "dpi": 100, "quality": 85}, jpg)
    check(not QImage(jpg).isNull(), "JPEG exported")

    # --- a cover whose size is not a whole number of points
    odd = DocScene(cover_settings(6, 9, 200, "white"))
    r = RectItem()
    r.set_size(odd.doc.page_width, odd.doc.page_height)
    odd.add_folio_item(r)
    pdf2 = os.path.join(OUT, "odd.pdf")
    exporter.export(odd, {"format": "pdf", "area": "page", "outline_text": True}, pdf2)
    res = subprocess.run(["pdfinfo", "-box", pdf2], capture_output=True, text=True)
    want_w = odd.doc.page_width / 300 * 72
    want_h = odd.doc.page_height / 300 * 72
    line = [x for x in res.stdout.splitlines() if x.startswith("MediaBox")][0].split()
    got_w = float(line[3]) - float(line[1])
    got_h = float(line[4]) - float(line[2])
    check(abs(got_w - want_w) < 0.01 and abs(got_h - want_h) < 0.01,
          f"odd-size PDF page {got_w:.3f} x {got_h:.3f} pt (wanted {want_w:.3f} x {want_h:.3f})")
    check(res.returncode == 0 and "Syntax Error" not in res.stderr, "patched PDF reads cleanly")
    ppm = subprocess.run(["pdftoppm", "-r", "20", "-png", pdf2, os.path.join(OUT, "odd")],
                         capture_output=True, text=True)
    check(ppm.returncode == 0 and not ppm.stderr.strip(), "patched PDF renders without errors")
    oddimg = QImage(os.path.join(OUT, "odd-1.png"))
    for x, y in ((1, 1), (oddimg.width() - 3, oddimg.height() - 3)):
        c = QColor(oddimg.pixel(x, y))
        check(c.blue() > 150 and c.red() < 120, f"fill reaches page corner near {x},{y}")
    subprocess.run(["pdftoppm", "-png", "-r", "40", pdf, os.path.join(OUT, "pdfpage")])

    # --- a page document and a screenshot of the window
    win.set_scene(DocScene(page_settings(1600, 2560, "px", 300)))
    QTest.qWait(30)
    win.open_path(path, checked=True)
    QTest.qWait(80)
    win.view.fit_page()
    scene = win.scene
    scene.select_only([i for i in scene.folio_items() if isinstance(i, TextItem)][:1])
    win.refresh_panels()
    QTest.qWait(80)
    shot = os.path.join(OUT, "window.png")
    win.grab().save(shot)
    print("files in", OUT)
    win.undo.setClean()
    win.close()
    if ERRORS:
        print("\n".join(ERRORS))
        raise SystemExit("errors were raised during the run")
    print("ALL GOOD")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(1)
