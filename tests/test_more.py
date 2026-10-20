"""More checks: layers, multi-select, curves, clipboard, setup and autosave.

    QT_QPA_PLATFORM=offscreen python3 -m tests.test_more
"""

import os
import sys
import tempfile
import time

_HOME = tempfile.mkdtemp(prefix="folio-home-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_HOME, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_HOME, "data")

from PyQt5.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PyQt5.QtGui import QColor, QImage, QPainter  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app = QApplication.instance() or QApplication(sys.argv)
app.setProperty("quiet_errors", True)

from folio import theme, units  # noqa: E402
from folio.document import cover_settings, page_settings  # noqa: E402
from folio.items import EllipseItem, PathItem, RectItem, TextItem  # noqa: E402
from folio.scene import DocScene  # noqa: E402
from folio.window import MainWindow  # noqa: E402
from tests.test_smoke import check, drag, mouse  # noqa: E402

ERRORS = []
sys.excepthook = lambda *a: ERRORS.append(a)


def rect_at(win, x, y, w=300, h=200, colour="#ff3366cc"):
    r = RectItem()
    r.fill = {**r.fill, "color": colour}
    r.set_size(w, h)
    r.setPos(x, y)
    with win.change("test"):
        win.scene.add_folio_item(r)
    return r


def main():
    theme.apply(app)
    win = MainWindow()
    win.resize(1400, 900)
    win.show()
    QTest.qWait(30)
    win.set_scene(DocScene(page_settings(3000, 2000, "px", 300)))
    QTest.qWait(30)
    view, scene = win.view, win.scene
    view.fit_page()

    a = rect_at(win, 200, 200)
    b = rect_at(win, 800, 400)
    c = rect_at(win, 1600, 300)

    # rubber band selects things it touches
    win.set_tool("move")
    drag(view, QPointF(100, 100), QPointF(900, 450))
    sel = scene.selected_folio()
    check(set(sel) == {a, b}, "rubber band picked the two rectangles it touched")

    # space evenly needs three
    scene.select_only([a, b, c])
    win.distribute("h")
    gaps = [b.scene_bounds().left() - a.scene_bounds().right(),
            c.scene_bounds().left() - b.scene_bounds().right()]
    check(abs(gaps[0] - gaps[1]) < 0.01, f"even spacing {gaps[0]:.1f} / {gaps[1]:.1f}")

    # multi resize from a corner scales everything together
    frame = view.selection_frame()
    box0 = scene.items_rect([a, b, c])
    br = frame["points"]["br"]
    drag(view, br, br + QPointF(box0.width() * 0.5, box0.height() * 0.5))
    box1 = scene.items_rect(scene.selected_folio())
    ratio = box1.width() / box0.width()
    check(abs(ratio - 1.5) < 0.08, f"group of three grew by {ratio:.2f}x")
    check(abs(box1.left() - box0.left()) < 1 and abs(box1.top() - box0.top()) < 1,
          "top-left corner stayed put")
    win.do_undo()
    a, b, c = (scene.find(i.uid) for i in (a, b, c))

    # flip a group: positions mirror
    scene.select_only([a, c])
    before = (a.center_scene().x(), c.center_scene().x())
    win.flip(True)
    a, c = scene.find(a.uid), scene.find(c.uid)
    check(abs(a.center_scene().x() - before[1]) < 0.5 and abs(c.center_scene().x() - before[0]) < 0.5,
          "flipping two objects swaps their places")
    check(a.flip_h and c.flip_h, "both are flipped")

    # hidden and locked objects cannot be clicked
    win.toggle_lock()
    scene.select_only([])
    mouse(view, QEvent.MouseButtonPress, a.center_scene())
    mouse(view, QEvent.MouseButtonRelease, a.center_scene())
    check(scene.selected_folio() == [], "locked object ignores clicks")
    scene.select_only([a, c])
    win.toggle_lock()
    scene.select_only([b])
    win.hide_selection()
    b = scene.find(b.uid)
    mouse(view, QEvent.MouseButtonPress, b.center_scene())
    mouse(view, QEvent.MouseButtonRelease, b.center_scene())
    check(b not in scene.selected_folio() and not b.isVisible(), "hidden object ignores clicks")
    win.show_all()
    b = scene.find(b.uid)
    check(b.isVisible(), "show all brings it back")

    # layers: drag order is read back from the tree
    win.layers.rebuild()
    tree = win.layers.tree
    order_before = [i.uid for i in scene.folio_items()]
    top = tree.takeTopLevelItem(0)
    tree.addTopLevelItem(top)   # move the top object to the bottom of the list
    win.layers.on_dropped()
    order_after = [i.uid for i in scene.folio_items()]
    check(order_after[0] == order_before[-1], "layer dragged to the bottom went to the back")
    win.do_undo()
    check([i.uid for i in scene.folio_items()] == order_before, "undo restores the stacking order")

    # group through the layers panel: drop an object into a group
    scene.select_only([scene.find(a.uid), scene.find(b.uid)])
    win.group_selection()
    win.layers.rebuild()
    gnode = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
                 if tree.topLevelItem(i).data(0, win.layers.GID))
    loose = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
                 if tree.topLevelItem(i).data(0, win.layers.UID))
    tree.takeTopLevelItem(tree.indexOfTopLevelItem(loose))
    gnode.addChild(loose)
    win.layers.on_dropped()
    gid = scene.find(a.uid).group
    check(gid and scene.find(c.uid).group == gid, "object dropped into a group joins it")
    win.ungroup_selection()

    # clicking one member selects the whole group; Ctrl-click picks one
    scene.select_only([scene.find(a.uid), scene.find(b.uid)])
    win.group_selection()
    scene.select_only([])
    pa = scene.find(a.uid).center_scene()
    mouse(view, QEvent.MouseButtonPress, pa)
    mouse(view, QEvent.MouseButtonRelease, pa)
    check(len(scene.selected_folio()) == 2, "click selects the whole group")
    scene.select_only([])
    mouse(view, QEvent.MouseButtonPress, pa, mods=Qt.ControlModifier)
    mouse(view, QEvent.MouseButtonRelease, pa, mods=Qt.ControlModifier)
    check(len(scene.selected_folio()) == 1, "Ctrl-click selects one member")

    # colour picking merges into one undo step, and a cancelled pick leaves nothing
    scene.select_only([scene.find(c.uid)])
    win.refresh_panels()
    steps = win.undo.count()
    original = scene.find(c.uid).fill["color"]
    for col in ("#ffff0000", "#ff00ff00", "#ff0000ff"):
        win.props.fill_c1._live(QColor(col))
    check(win.undo.count() == steps + 1, "live colour changes make one undo step")
    win.props.fill_c1._live(QColor(original))
    check(scene.find(c.uid).fill["color"] == original, "colour put back")
    check(win.undo.count() == steps, "putting the colour back leaves no undo step behind")

    # curves: add a point on a line, make it smooth, delete it
    win.create_path([{"p": [300, 1500], "i": None, "o": None, "t": "corner"},
                     {"p": [1500, 1500], "i": None, "o": None, "t": "corner"}],
                    closed=False, line=True)
    line = scene.selected_folio()[0]
    check(isinstance(line, PathItem) and line.is_line(), "line made")
    win.set_tool("node")
    mid = line.mapToScene(QPointF(line.w / 2, 0))
    mouse(view, QEvent.MouseButtonPress, mid)
    mouse(view, QEvent.MouseButtonRelease, mid)
    line = scene.find(line.uid)
    check(len(line.nodes) == 3, "clicking the line added a point")
    p1 = line.mapToScene(QPointF(*line.nodes[1]["p"]))
    QTest.mouseDClick(view.viewport(), Qt.LeftButton, Qt.NoModifier, view.mapFromScene(p1))
    line = scene.find(line.uid)
    check(line.nodes[1]["t"] == "smooth" and line.nodes[1]["o"] is not None, "double-click made it smooth")
    win.tools["node"].chosen = 1
    view.setFocus()
    QTest.keyClick(view, Qt.Key_Delete)
    line = scene.find(line.uid)
    check(len(line.nodes) == 2, "Delete removed the point")
    win.set_tool("move")

    # text: wrap width from a side handle, size from a corner handle
    t = win.create_text(QPointF(400, 900), text="A long line of words to wrap")
    scene.select_only([t])
    w0 = t.w
    frame = view.selection_frame()
    rp = frame["points"]["r"]
    drag(view, rp, rp - QPointF(w0 * 0.5, 0))
    t = scene.find(t.uid)
    check(t.frame_width is not None and t.h > 1.5 * t.style["size"], "side handle makes text wrap")
    size0 = t.style["size"]
    frame = view.selection_frame()
    corner = frame["points"]["br"]
    drag(view, corner, corner + QPointF(t.w * 0.5, t.h * 0.5))
    t = scene.find(t.uid)
    check(t.style["size"] > size0 * 1.3, f"corner handle grows the letters ({size0:.0f} -> {t.style['size']:.0f})")

    # clipboard: copy, paste offsets; plain text pastes as text
    scene.select_only([scene.find(c.uid)])
    win.copy()
    win.paste()
    pasted = scene.selected_folio()[0]
    check(pasted.uid != c.uid and pasted.pos().x() > scene.find(c.uid).pos().x(), "paste lands nearby")
    QApplication.clipboard().setText("Hello from the clipboard")
    win.paste()
    sel = scene.selected_folio()
    check(len(sel) == 1 and isinstance(sel[0], TextItem)
          and sel[0].toPlainText() == "Hello from the clipboard", "pasted words become text")
    img = QImage(400, 300, QImage.Format_RGB32)
    img.fill(QColor("#22aa66"))
    QApplication.clipboard().setImage(img)
    win.paste()
    sel = scene.selected_folio()
    check(len(sel) == 1 and sel[0].kind == "image", "pasted picture becomes an image")

    # document setup on a cover: front-cover objects follow the front cover
    win.set_scene(DocScene(cover_settings(6, 9, 100, "white")))
    QTest.qWait(20)
    scene = win.scene
    old = scene.doc
    front = old.regions()["front"]
    f = rect_at(win, front.left() + 100, front.top() + 100)
    back = old.regions()["back"]
    bk = rect_at(win, back.left() + 100, back.top() + 100)
    new = cover_settings(6, 9, 400, "white")
    with win.change("Document setup"):
        win.shift_for_settings(old, new)
        scene.set_settings(new)
    nf = new.regions()["front"]
    check(abs(scene.find(f.uid).pos().x() - (nf.left() + 100)) < 0.01, "front object moved with the front cover")
    check(abs(scene.find(bk.uid).pos().x() - (back.left() + 100)) < 0.01, "back object stayed")
    win.do_undo()
    check(abs(scene.doc.page_width - old.page_width) < 0.01, "undo puts the old cover size back")

    # autosave and rescue
    win.autosave()
    check(os.path.exists(win.autosave_path), "autosave written")
    data_dir = os.path.dirname(win.autosave_path)
    fake = os.path.join(data_dir, "autosave-999999.folio")
    os.replace(win.autosave_path, fake)
    found = [n for n in os.listdir(data_dir) if n.startswith("autosave-")]
    check("autosave-999999.folio" in found and not win._pid_alive("autosave-999999.folio"),
          "a crashed session's rescue file is recognised")

    # fonts from a zip, into a test folder
    import zipfile
    fontzip = os.path.join(_HOME, "fonts.zip")
    src = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    if os.path.exists(src):
        with zipfile.ZipFile(fontzip, "w") as z:
            z.write(src, "static/DejaVuSansMono.ttf")
            z.writestr("OFL.txt", "licence")
        names = win.install_fonts([fontzip], folder=os.path.join(_HOME, "fonts"))
        check("DejaVu Sans Mono" in names, f"font installed from a zip: {names}")

    # unusual photo formats go through ImageMagick
    import shutil
    import subprocess
    if shutil.which("convert"):
        webp = os.path.join(_HOME, "pic.webp")
        subprocess.run(["convert", "-size", "640x480", "gradient:red-blue", webp], check=True)
        win.place_image_files([webp])
        sel = scene.selected_folio()
        check(len(sel) == 1 and sel[0].kind == "image" and sel[0].pixel_size().width() == 640,
              "WebP picture placed")

    # New Document: every ready-made size works
    from folio import newdoc
    from folio.newdoc import NewDocumentDialog
    dlg = NewDocumentDialog(win)
    made = 0
    for it in list(dlg.row_items()):
        dlg.presets.setCurrentItem(it)
        st = dlg.settings()
        assert st.page_width > 10 and st.page_height > 10, it.text()
        made += 1
    check(made > 90, f"New Document offers {made} ready-made sizes, all working")
    dlg.select_preset("cover:kdp:hardcover")
    select = [i for i in range(dlg.trim.count())
              if isinstance(dlg.trim.itemData(i), tuple) and dlg.trim.itemData(i)[1:] == (6.0, 9.0)][0]
    dlg.trim.setCurrentIndex(select)
    dlg.pages_box.setValue(200)
    dlg.paper.setCurrentIndex(dlg.paper.findData("white"))
    hc = dlg.settings()
    check(hc.binding == "hardcover" and abs(hc.spine_in - 0.6394) < 1e-4
          and abs(hc.page_width / hc.dpi - 14.2154) < 1e-3 and abs(hc.page_height / hc.dpi - 10.418) < 1e-3,
          f"hardcover 6x9, 200 pages: {hc.page_width / hc.dpi:.4f} x {hc.page_height / hc.dpi:.4f} in")
    check(len(hc.hinge_rects()) == 2, "hardcover shows its two hinges")
    dlg.select_preset("cover:kdp:paperback")
    pb = dlg.settings()
    check(pb.binding == "paperback" and pb.dpi == 300 and abs(pb.page_width / pb.dpi - 12.7004) < 1e-3,
          f"paperback 6x9, 200 pages: {pb.page_width / pb.dpi:.4f} in wide")
    # every printer, both bindings, every size
    covers = 0
    for binding in ("paperback", "hardcover"):
        for key, _ in units.PRINTERS:
            check(dlg.select_preset(f"cover:{key}:{binding}"), f"{key} {binding} is listed")
            for i in range(dlg.trim.count()):
                data = dlg.trim.itemData(i)
                if isinstance(data, tuple):
                    dlg.trim.setCurrentIndex(i)
                    st = dlg.settings()
                    assert st.page_width > st.trim_w_in * st.dpi * 2 and st.printer == key, data
                    covers += 1
    check(covers >= 126, f"{covers} printer cover sizes, all working")
    letter = "page:Letter  8.5 x 11 in  (most popular)"
    dlg.search.setText("arch")
    shown = [it.data(newdoc.ROW_ROLE)["name"] for it in dlg.row_items() if not it.isHidden()]
    check(shown and all(n.startswith("Arch") for n in shown), f"search finds {shown}")
    dlg.search.clear()
    dlg.toggle_favourite(letter)
    dlg.fav_only.setChecked(True)
    shown = [it for it in dlg.row_items() if not it.isHidden()]
    check(len(shown) == 1 and shown[0].data(newdoc.ROW_ROLE)["id"] == letter, "the heart keeps a favourite")
    dlg.fav_only.setChecked(False)
    check(dlg.select_preset(letter) and dlg.title.text() == "Letter", "Letter chosen")
    dlg.set_orientation(True)
    st = dlg.settings()
    check(abs(st.trim_width - 3300) < 1 and abs(st.trim_height - 2550) < 1 and dlg.title.text() == "Letter*",
          "landscape turns the page and marks it changed")
    newdoc.QInputDialog.getText = staticmethod(lambda *a, **k: ("Wide letter", True))
    dlg.save_preset()
    again = NewDocumentDialog(win)
    mine = [it for it in again.row_items() if it.data(newdoc.ROW_ROLE)["name"] == "Wide letter"]
    check(len(mine) == 1 and again.headers.get("My presets") is not None, "a saved preset is listed")
    again.presets.setCurrentItem(mine[0])
    check(abs(again.settings().trim_width - 3300) < 1, "a saved preset opens with its size")
    again.close()
    dlg.close()
    lulu = cover_settings(6, 9, 630, "standard", binding="hardcover", printer="lulu")
    check(abs(lulu.page_width / 300 * 25.4 - 392.112) < 0.05 and abs(lulu.page_height / 300 * 25.4 - 273.05) < 0.05,
          "Lulu 6x9 hardcover matches a real Lulu template (392.1 x 273.1 mm)")
    ing = cover_settings(6, 9, 200, "white50", binding="hardcover", printer="ingram")
    want = 0.625 + 5.815 + 0.5 + ing.spine_in + 0.5 + 5.815 + 0.625
    check(abs(ing.page_width / 300 - want) < 1e-6 and abs(ing.page_height / 300 - 10.5) < 1e-6,
          "IngramSpark hardcover follows its guide's formula")
    pb = cover_settings(6, 9, 188, "standard", printer="lulu")
    check(abs(pb.spine_in - 0.4834) < 1e-4, "Lulu paperback spine matches its guide")
    setup = NewDocumentDialog(win, current=hc)
    check(setup.settings() == hc, "Document Setup shows a hardcover as it is")
    setup.close()

    # printing: send the page to a "printer" that writes a PDF
    from PyQt5.QtPrintSupport import QPrinter, QPrintPreviewDialog
    printed = os.path.join(_HOME, "printed.pdf")
    pr = win.printer()
    pr.setOutputFormat(QPrinter.PdfFormat)
    pr.setOutputFileName(printed)
    check(win.paint_for_printer(pr) and os.path.getsize(printed) > 1000, "Print sends the page out")
    info = subprocess.run(["pdfinfo", printed], capture_output=True, text=True).stdout
    check("Pages:           1" in info, "one printed page")
    preview = QPrintPreviewDialog(pr, win)
    preview.paintRequested.connect(win.paint_for_printer)
    preview.show()
    QTest.qWait(150)
    preview.close()
    check(True, "print preview opens")

    # the fonts that come with Folio
    from folio import fonts as bundled
    from PyQt5.QtGui import QFontInfo
    fams = bundled.bundled_families()
    check(len(fams) >= 85, f"{len(fams)} font families come with Folio")
    check({"serif", "sans", "script", "display"} <= set(fams.values()), "fonts are sorted into groups")
    t = win.create_text(QPointF(300, 300), text="Wedding Bells")
    scene.select_only([t])
    win.refresh_panels()
    picker = win.textp.family
    picker.group.setCurrentIndex(picker.group.findData("script"))
    check(picker.box.findData("Great Vibes") >= 0 and picker.box.findData("Montserrat") < 0,
          "the Script group lists script fonts only")
    picker.box.setCurrentIndex(picker.box.findData("Great Vibes"))
    t = scene.find(t.uid)
    check(t.style["family"] == "Great Vibes", "picking a font changes the text")
    check(QFontInfo(t.make_font()).family() == "Great Vibes", "the bundled font is really used")
    check(not t.text_path().isEmpty(), "the bundled font turns into shapes for PDF")

    # drawing speed with a big photo and a shadow
    big = QImage(6000, 4000, QImage.Format_RGB32)
    big.fill(QColor("#336699"))
    p = QPainter(big)
    p.fillRect(0, 0, 3000, 2000, QColor("#ffcc00"))
    p.end()
    win.place_qimage(big)
    t = win.create_text(QPointF(500, 500), text="SPEED TEST")
    t.shadow["on"] = True
    t.apply_style()
    view.fit_page()
    QTest.qWait(30)
    t0 = time.perf_counter()
    for _ in range(10):
        view.viewport().repaint()
    per = (time.perf_counter() - t0) / 10 * 1000
    print(f"     full repaint: {per:.1f} ms")
    check(per < 120, "the page redraws quickly")

    win.undo.setClean()
    win.close()
    if ERRORS:
        import traceback
        for e in ERRORS:
            traceback.print_exception(*e)
        raise SystemExit("errors were raised")
    print("ALL GOOD")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(1)
