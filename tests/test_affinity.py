"""Checks for the features modelled on Affinity Designer: the extra File and
Edit menu commands, styles, defaults, the Select menu and the studio
panels (Colour, Swatches, Stroke, Transform anchor, Layers opacity,
Navigator).

    QT_QPA_PLATFORM=offscreen python3 -m tests.test_affinity
"""

import json
import os
import sys
import tempfile

_HOME = tempfile.mkdtemp(prefix="folio-home-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_HOME, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_HOME, "data")

from PyQt5.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PyQt5.QtGui import QColor, QGuiApplication, QImage  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import QApplication, QMessageBox  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app = QApplication.instance() or QApplication(sys.argv)
app.setProperty("quiet_errors", True)

from folio import exporter, fonts, importers, theme, units, window  # noqa: E402
from folio.document import cover_settings, page_settings  # noqa: E402
from folio.items import EllipseItem, ImageItem, RectItem, TextItem  # noqa: E402
from folio.newdoc import NewDocumentDialog  # noqa: E402
from folio.scene import DocScene  # noqa: E402
from folio.window import MainWindow  # noqa: E402
from tests.test_smoke import check  # noqa: E402

ERRORS = []
sys.excepthook = lambda *a: ERRORS.append(a)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.warning = staticmethod(lambda *a, **k: ERRORS.append(("warning", a)) or QMessageBox.Ok)


def answer(text):
    window.QInputDialog.getText = staticmethod(lambda *a, **k: (text, True))


def pixel(scene, x, y, scale=0.1):
    image = exporter.render_image(scene, scene.doc.page_rect(), scale)
    return image.pixelColor(int(x * scale), int(y * scale))


def rect(win, x, y, w, h, colour):
    item = RectItem()
    item.fill = {"type": "solid", "color": colour, "color2": "#ff000000", "angle": 90.0}
    item.stroke = {"color": "#ff000000", "width": 0.0, "dash": "solid"}
    item.set_size(w, h)
    item.setPos(x, y)
    win.scene.add_folio_item(item)
    return item


def main():
    theme.apply(app)
    fonts.load_bundled()
    win = MainWindow()
    win.resize(1500, 950)
    win.show()
    QTest.qWait(30)
    clip = QGuiApplication.clipboard()
    win.set_scene(DocScene(page_settings(3000, 2000, "px", 300)))
    scene = win.scene

    # ---- Paste Inside: a photo shows only inside a circle ------------------------
    circle = EllipseItem()
    circle.set_size(800, 800)
    circle.setPos(500, 500)
    scene.add_folio_item(circle)
    photo = QImage(1200, 900, QImage.Format_RGB32)
    photo.fill(QColor("#ff0000"))
    clip.setImage(photo)
    scene.select_only([circle])
    win.paste_inside()
    pics = [i for i in scene.folio_items() if isinstance(i, ImageItem)]
    check(len(pics) == 1 and pics[0].clip == circle.uid, "picture pasted inside the circle")
    pic = pics[0]
    check(pic.group and pic.group == circle.group, "the picture and its circle move together")
    order = scene.folio_items()
    check(order.index(pic) == order.index(circle) + 1, "the picture sits just above its circle")
    check(abs(pic.scene_bounds().width() - 800) < 1, "the picture fills the circle")
    centre = pixel(scene, 900, 900)
    corner = pixel(scene, 520, 520)
    check(centre.red() > 200 and centre.green() < 60, "red shows inside the circle")
    check(corner.green() > 200, "nothing shows outside the circle")
    pdf = os.path.join(_HOME, "inside.pdf")
    exporter.export(scene, {"format": "pdf", "area": "page", "outline_text": True}, pdf)
    png = importers.render_pdf_page(pdf, 1, 30, transparent=False)
    page = QImage.fromData(png)
    s = page.width() / 3000
    inside = page.pixelColor(int(900 * s), int(900 * s))
    outside = page.pixelColor(int(520 * s), int(520 * s))
    check(inside.red() > 200 and inside.green() < 60 and outside.green() > 200,
          "the PDF keeps the picture inside the circle")
    check(win.view.item_at(QPointF(520, 520)) is not pic, "clicks outside the circle miss the picture")
    scene.select_only([circle, pic])
    win.copy()
    win.paste()
    new = scene.selected_folio()
    new_pic = [i for i in new if isinstance(i, ImageItem)]
    new_circle = [i for i in new if isinstance(i, EllipseItem)]
    check(len(new_pic) == 1 and len(new_circle) == 1 and new_pic[0].clip == new_circle[0].uid,
          "a copied circle keeps its own picture inside")
    uid = new_pic[0].uid
    scene.select_only(new_pic)
    win.release_clip()
    check(scene.find(uid).clip is None, "Take Out of Shape frees the picture")
    win.do_undo()
    check(scene.find(uid).clip == new_circle[0].uid, "undo puts it back inside")

    # ---- Paste Style and Paste Effects -------------------------------------------
    win.set_scene(DocScene(page_settings(3000, 2000, "px", 300)))
    scene = win.scene
    a = rect(win, 100, 100, 400, 300, "#ffcc2200")
    a.stroke = {"color": "#ff112233", "width": 12.0, "dash": "dash"}
    a.shadow = {**a.shadow, "on": True, "blur": 30.0}
    b = rect(win, 700, 100, 400, 300, "#ff0044cc")
    c = rect(win, 1300, 100, 400, 300, "#ff00aa00")
    scene.select_only([a])
    win.copy()
    scene.select_only([b])
    win.paste_style()
    check(b.fill["color"] == "#ffcc2200" and b.stroke["width"] == 12.0 and b.stroke["dash"] == "dash"
          and b.shadow["on"], "Paste Style copies colours, outline and shadow")
    scene.select_only([c])
    win.paste_effects()
    check(c.shadow["on"] and c.fill["color"] == "#ff00aa00" and c.stroke["width"] == 0,
          "Paste Effects copies only the shadow")
    t1 = win.create_text(QPointF(100, 800), text="Title")
    t1.style.update(family="Lobster", italic=True, size=120.0)
    t1.apply_style()
    t2 = win.create_text(QPointF(100, 1200), text="Subtitle")
    t2.style["size"] = 60.0
    t2.apply_style()
    scene.select_only([t1])
    win.copy()
    scene.select_only([t2])
    win.paste_style()
    check(t2.style["family"] == "Lobster" and t2.style["italic"] and t2.style["size"] == 60.0,
          "Paste Style on text copies the lettering, not the size")
    clip.setText("Plain words")
    scene.select_only([])
    win.paste_plain()
    sel = scene.selected_folio()
    check(len(sel) == 1 and isinstance(sel[0], TextItem) and sel[0].toPlainText() == "Plain words",
          "Paste Without Format makes a plain text box")

    # ---- Select menu -------------------------------------------------------------
    d = rect(win, 1900, 100, 300, 300, "#ffcc2200")
    scene.select_only([a])
    win.select_same("fill")
    check(set(scene.selected_folio()) == {a, b, d}, "Select Same Fill Colour")
    win.select_same("kind")
    check(all(isinstance(i, RectItem) for i in scene.selected_folio())
          and len(scene.selected_folio()) == 4, "Select Same Kind of Object")
    win.invert_selection()
    check(all(isinstance(i, TextItem) for i in scene.selected_folio()), "Invert Selection")

    # ---- Defaults ----------------------------------------------------------------
    scene.select_only([a])
    win.defaults_from_selection()
    win.create_shape("rect", QRectF(100, 1500, 200, 200))
    check(scene.selected_folio()[0].fill["color"] == "#ffcc2200", "new shapes use the chosen default")
    check(json.loads(win.settings.value("defaults"))["fill"]["color"] == "#ffcc2200",
          "the default is remembered")
    win.reset_saved_defaults()
    win.create_shape("rect", QRectF(400, 1500, 200, 200))
    check(scene.selected_folio()[0].fill["color"] == window.FACTORY_FILL["color"],
          "Reset Defaults goes back to Folio's look")

    # ---- Styles panel --------------------------------------------------------------
    styles_panel = win.stylesp
    check(styles_panel.list.count() == 8, "eight starter styles")
    gold = next(s for s in styles_panel.styles if s["name"] == "Gold lettering")
    scene.select_only([t1])
    win.apply_saved_style(gold)
    check(t1.fill["color"] == "#ffd4a82f" and t1.shadow["on"]
          and abs(t1.stroke["width"] - units.pt_to_px(0.75, 300)) < 1e-6,
          "a style goes on with one click (sizes in points)")
    answer("My red")
    scene.select_only([a])
    win.create_style()
    check(styles_panel.list.count() == 9 and styles_panel.styles[-1]["name"] == "My red",
          "Create Style adds to the Styles panel")
    check(json.loads(win.settings.value("styles"))[-1]["name"] == "My red", "styles are kept")

    # ---- Colour panel -------------------------------------------------------------
    scene.select_only([b])
    win.refresh_panels()
    win.set_colour_target("fill")
    steps = win.undo.count()
    for name in ("#ff00ff00", "#ff00ee00", "#ff00dd00"):
        win.colourp.on_wheel(QColor(name))
    check(b.fill["color"] == "#ff00dd00" and win.undo.count() == steps + 1,
          "dragging on the wheel colours the fill in one undo step")
    win.set_colour_target("stroke")
    b.stroke["width"] = 0.0
    win.swatches.on_pick(QColor("#ff0000ff"))
    check(b.stroke["color"] == "#ff0000ff" and abs(b.stroke["width"] - units.pt_to_px(1, 300)) < 1e-6,
          "a swatch colours the outline (and gives it a width)")
    check(win.recent_colours[0] == "#ff0000ff", "the swatch goes into Recent")
    win.set_colour_target("fill")
    win.clear_colour()
    check(b.fill["type"] == "none", "the crossed circle removes the fill")
    win.swap_fill_stroke()
    check(b.fill["type"] == "solid" and b.fill["color"] == "#ff0000ff" and b.stroke["width"] == 0,
          "swap turns the outline colour into the fill")
    scene.select_only([c])
    win.refresh_panels()
    QTest.qWait(30)
    win.start_colour_pick()
    vp = win.view.mapFromScene(QPointF(250, 250))
    QTest.mouseClick(win.view.viewport(), Qt.LeftButton, Qt.NoModifier, vp)
    picked = QColor(c.fill["color"])
    check(not win._picking_colour and picked.red() > 180 and picked.blue() < 60,
          f"the eyedropper picks a colour off the page ({picked.name()})")

    # ---- Stroke panel ---------------------------------------------------------------
    scene.select_only([d])
    win.refresh_panels()
    win.strokep.on_button("style", "dash")
    check(d.stroke["dash"] == "dash" and d.stroke["width"] > 0, "Stroke: dashed outline")
    win.strokep.on_width(8)
    check(abs(d.stroke["width"] - units.pt_to_px(8, 300)) < 1e-6, "Stroke: width in points")
    win.strokep.on_button("style", "solid")
    win.strokep.on_button("cap", "round")
    win.strokep.on_button("join", "bevel")
    win.strokep.set_key("color", "#ff0000ff")
    win.strokep.on_button("align", "outside")
    check(d.stroke["cap"] == "round" and d.stroke["join"] == "bevel" and d.stroke["align"] == "outside",
          "Stroke: cap, join and align")
    out = pixel(scene, 1900 - 15, 250, 1.0)
    inn = pixel(scene, 1900 + 15, 250, 1.0)
    check(out.blue() > 200 and out.red() < 60 and inn.red() > 180,
          "an outside outline sits outside the edge")
    win.strokep.on_button("align", "inside")
    out = pixel(scene, 1900 - 15, 250, 1.0)
    inn = pixel(scene, 1900 + 15, 250, 1.0)
    check(inn.blue() > 200 and out.green() > 200, "an inside outline sits inside the edge")
    win.strokep.on_button("style", "none")
    check(d.stroke["width"] == 0, "Stroke: no outline")

    # ---- Transform anchor, layer opacity, navigator, history ----------------------
    scene.select_only([d])
    win.transform.anchor.fx = win.transform.anchor.fy = 0.5
    win.transform.refresh()
    check(abs(win.transform.x.value() - 2050) < 0.01, "the anchor makes X measure the centre")
    win.transform.x.setValue(1000)
    check(abs(d.center_scene().x() - 1000) < 0.01, "typing X moves the centre there")
    win.layers.sync_selection()
    win.layers.opacity.setEditText("40 %")
    win.layers.on_opacity()
    check(abs(d.opacity() - 0.4) < 1e-6, "the Layers opacity box changes opacity")
    win.dock_navigator.raise_()
    QTest.qWait(20)
    win.navigator.render_thumb()
    check(win.navigator.thumb is not None and win.navigator.thumb.width() > 50,
          "Navigator shows the page")
    check(win.history.model().rowCount() > 5, "History lists the steps")
    names = [dock.windowTitle() for dock in win.docks()]
    check(names == ["Colour", "Swatches", "Stroke", "Text", "Export Options", "Layers",
                    "Brushes", "Fill and FX", "Styles", "Slices", "Transform", "History", "Navigator"],
          "the panels are all there")

    # ---- File menu: new from clipboard, last preset, templates, package -------------
    clip.setImage(QImage(640, 480, QImage.Format_RGB32))
    win.undo.setClean()
    win.new_from_clipboard()
    doc = win.scene.doc
    check(abs(doc.page_width - 640) < 0.5 and abs(doc.page_height - 480) < 0.5
          and len(win.scene.folio_items()) == 1, "New from Clipboard: a picture's own size")
    check(not win.undo.isClean(), "the new document counts as unsaved")
    win.undo.setClean()
    win.settings.setValue("last_preset", json.dumps(cover_settings(5, 8, 120).to_dict()))
    win.new_from_last_preset()
    check(win.scene.doc.kind == "cover" and win.scene.doc.trim_w_in == 5, "New from Last Preset")

    scene = win.scene
    text = win.create_text(scene.doc.regions()["front"].center(), text="Cover")
    text.style["family"] = "Lobster"
    text.apply_style()
    win.place_qimage(QImage(200, 300, QImage.Format_RGB32), name="author.png")
    answer("Novel cover")
    win.save_as_template()
    path = os.path.join(window.templates_dir(), "Novel cover.folio")
    check(os.path.exists(path), "Export as Template saves a template")
    dlg = NewDocumentDialog(win, templates=win.list_templates())
    dlg.show_page("templates")
    check(dlg.template_path() == path, "the template is offered under New, Templates")
    dlg.close()
    # every row of the size list draws (wide screens, covers, pages, headings)
    from PyQt5.QtCore import QRect
    from PyQt5.QtGui import QPainter
    from PyQt5.QtWidgets import QStyle, QStyleOptionViewItem
    dlg = NewDocumentDialog(win)
    dlg.toggle_favourite("page:Website banner  1920 x 1080 px  (most popular)")
    canvas = QImage(380, 40, QImage.Format_ARGB32_Premultiplied)
    delegate = dlg.presets.itemDelegate()
    drawn = 0
    for i in range(dlg.presets.count()):
        for state in (QStyle.State_None, QStyle.State_Selected, QStyle.State_MouseOver):
            opt = QStyleOptionViewItem()
            opt.rect = QRect(0, 0, 380, 36)
            opt.font = dlg.presets.font()
            opt.state = state
            painter = QPainter(canvas)
            try:
                delegate.paint(painter, opt, dlg.presets.model().index(i, 0))
            finally:
                painter.end()
            drawn += 1
    check(drawn > 300, f"every row of the size list draws ({dlg.presets.count()} rows)")
    for name in ("page:Website banner  1920 x 1080 px  (most popular)", "cover:lulu:hardcover",
                 "page:Banner  2 x 6 feet", "page:Square post  1080 x 1080"):
        check(dlg.select_preset(name), f"{name.split(':')[-1].strip()} can be chosen")
        dlg.grab()
    dlg.close()
    dlg = NewDocumentDialog(win, recent=[path])
    dlg.show_page("recent")
    check(dlg.recent_path() == path and dlg.primary.text() == "Open",
          "Recent shows files to open again")
    dlg.close()
    win.undo.setClean()
    count = len(win.scene.folio_items())
    win.start_from_template(path)
    check(win.path is None and len(win.scene.folio_items()) == count,
          "starting from a template gives an untitled copy")
    folder = os.path.join(_HOME, "Cover package")
    window.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (folder, ""))
    win.save_as_package()
    fonts_dir = os.path.join(folder, "Fonts", "Lobster")
    files = os.listdir(fonts_dir) if os.path.isdir(fonts_dir) else []
    check(any(f.endswith(".ttf") for f in files) and any("OFL" in f or "icense" in f for f in files),
          f"the package has the font and its licence: {files}")
    check(len(os.listdir(os.path.join(folder, "Images"))) == 1, "the package has the picture")
    check(any(f.endswith(".folio") for f in os.listdir(folder))
          and os.path.exists(os.path.join(folder, "Fonts used.txt")), "the package has the design")

    win.undo.setClean()
    win.close()
    if ERRORS:
        import traceback
        for e in ERRORS:
            if e and e[0] == "warning":
                print("warning shown:", e[1][2:])
            else:
                traceback.print_exception(*e)
        raise SystemExit("problems")
    print("ALL GOOD")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(1)
