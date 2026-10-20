"""Checks for the Designer, Pixel and Export personas.

    QT_QPA_PLATFORM=offscreen python3 -m tests.test_personas
"""

import os
import sys
import tempfile

_HOME = tempfile.mkdtemp(prefix="folio-home-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_HOME, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_HOME, "data")

from PyQt5.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PyQt5.QtGui import QColor, QImage, QPainterPath  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app = QApplication.instance() or QApplication(sys.argv)
app.setProperty("quiet_errors", True)

from folio import exporter, fileio, fonts, importers, theme  # noqa: E402
from folio.document import cover_settings, page_settings  # noqa: E402
from folio.items import ImageItem, RectItem  # noqa: E402
from folio.scene import DocScene  # noqa: E402
from folio.window import MainWindow  # noqa: E402
from tests.test_smoke import check, drag  # noqa: E402

ERRORS = []
sys.excepthook = lambda *a: ERRORS.append(a)


def layer_pixel(item, x, y):
    """The colour of a pixel layer at a page point."""
    image = item.assets.full(item.aid)
    return image.pixelColor(int(x - item.pos().x()), int(y - item.pos().y()))


def page_pixel(scene, x, y, scale=0.25):
    image = exporter.render_image(scene, scene.doc.page_rect(), scale)
    return image.pixelColor(int(x * scale), int(y * scale))


def main():
    theme.apply(app)
    fonts.load_bundled()
    win = MainWindow()
    win.resize(1600, 1000)
    win.show()
    QTest.qWait(30)
    view = win.view

    # ---- switching personas ----------------------------------------------------------
    win.set_scene(DocScene(page_settings(2000, 1500, "px", 300)))
    QTest.qWait(20)
    scene = win.scene
    win.set_persona("pixel")
    check(win.tool_name == "px-brush" and win.tool_bars["pixel"].isVisibleTo(win)
          and not win.tool_bars["design"].isVisibleTo(win), "the Pixel persona shows pixel tools")
    check(win.tool_actions["px-rect"].isEnabled() and not win.tool_actions["rect"].isEnabled(),
          "M picks the marquee in the Pixel persona, not the rectangle")
    win.set_persona("export")
    check(win.tool_name == "slice-select" and win.dock_export.isVisibleTo(win)
          and not win.dock_colour.isVisibleTo(win), "the Export persona shows slices and export options")
    win.set_persona("design")
    check(win.tool_name == "move" and win.tool_actions["rect"].isEnabled()
          and win.dock_colour.isVisibleTo(win) and not win.dock_slices.isVisibleTo(win),
          "back in the Designer persona")

    # ---- painting --------------------------------------------------------------------------
    win.set_persona("pixel")
    view.fit_page()
    QTest.qWait(20)
    win.style_fill = {**win.style_fill, "type": "solid", "color": "#ffff0000"}
    win.brush.update(size=80, hardness=1.0, opacity=100, flow=100)
    drag(view, QPointF(200, 300), QPointF(1200, 300), steps=12)
    layers = [i for i in scene.folio_items() if isinstance(i, ImageItem)]
    check(len(layers) == 1 and scene.assets.is_live(layers[0].aid), "painting makes a pixel layer")
    layer = layers[0]
    c = layer_pixel(layer, 700, 300)
    check(c.red() > 240 and c.alpha() > 240 and c.green() < 20, "the brush paints red")
    check(layer_pixel(layer, 700, 500).alpha() == 0, "the rest of the layer is see-through")
    check(win.undo.text(win.undo.count() - 1) == "Paint", "a stroke is one undo step")
    win.do_undo()
    check(layer_pixel(layer, 700, 300).alpha() == 0, "undo takes the stroke away")
    win.do_redo()
    check(layer_pixel(layer, 700, 300).red() > 240, "redo puts it back")
    scene.select_only([layer])
    win.set_tool("px-erase")
    drag(view, QPointF(650, 200), QPointF(650, 400), steps=6)
    check(layer_pixel(layer, 650, 300).alpha() < 20 and layer_pixel(layer, 300, 300).alpha() > 240,
          "the eraser rubs out only where it goes")

    # ---- selections ---------------------------------------------------------------------------
    win.set_tool("px-rect")
    drag(view, QPointF(1000, 600), QPointF(1400, 1000))
    check(win.pixel_selection is not None
          and abs(win.pixel_selection.boundingRect().width() - 400) < 2, "the marquee selects")
    win.pixel_fill()
    check(layer_pixel(layer, 1200, 800).red() > 240 and layer_pixel(layer, 900, 800).alpha() == 0,
          "Fill fills only the selection")
    win.set_tool("px-brush")
    drag(view, QPointF(800, 1200), QPointF(1300, 1200), steps=10)
    check(layer_pixel(layer, 900, 1200).alpha() == 0, "the brush only paints inside the selection")
    win.pixel_clear()
    check(layer_pixel(layer, 1200, 800).alpha() == 0, "Clear empties the selection")
    win.pixel_invert()
    inv = win.pixel_selection
    check(inv.contains(QPointF(100, 100)) and not inv.contains(QPointF(1200, 800)),
          "Invert selects everything else")
    win.deselect()
    check(win.pixel_selection is None, "Ctrl+D deselects the pixels")
    win.set_tool("px-lasso")
    drag(view, QPointF(100, 1100), QPointF(500, 1400), steps=10)
    check(win.pixel_selection is not None, "the lasso selects")
    win.pixel_deselect()

    # ---- magic wand and flood fill --------------------------------------------------------
    win.set_persona("design")
    blue = RectItem()
    blue.fill = {"type": "solid", "color": "#ff0000ff", "color2": "#ff000000", "angle": 90.0}
    blue.stroke = {"color": "#ff000000", "width": 0.0, "dash": "solid"}
    blue.set_size(500, 400)
    blue.setPos(200, 600)
    scene.add_folio_item(blue)
    win.set_persona("pixel")
    win.brush["sample"] = "page"
    win.set_tool("px-wand")
    win.tools["px-wand"].press(type("E", (), {"modifiers": lambda self: Qt.NoModifier})(),
                               QPointF(450, 800))
    sel = win.pixel_selection
    check(sel is not None and sel.contains(QPointF(450, 800)) and not sel.contains(QPointF(800, 800))
          and abs(sel.boundingRect().width() - 500) < 12,
          f"the magic wand selects the blue box ({sel.boundingRect().width() if sel else 0:.0f} wide)")
    win.pixel_deselect()
    scene.select_only([layer])
    win.style_fill = {**win.style_fill, "color": "#ff00ff00"}
    win.tools["px-fill"].press(type("E", (), {"modifiers": lambda self: Qt.NoModifier})(),
                               QPointF(450, 800))
    check(layer_pixel(layer, 450, 800).green() > 240 and layer_pixel(layer, 800, 800).alpha() == 0,
          "flood fill fills just the blue box's area")

    # ---- blur, dodge and burn don't break ----------------------------------------------
    for tool in ("px-blur", "px-dodge", "px-burn"):
        win.set_tool(tool)
        drag(view, QPointF(300, 300), QPointF(500, 320), steps=4)
    check(win.undo.text(win.undo.count() - 1) == "Burn", "blur, dodge and burn brushes work")

    # ---- painting on a placed photo keeps the original ----------------------------------
    win.set_persona("design")
    photo = QImage(400, 300, QImage.Format_RGB32)
    photo.fill(QColor("#ffffff"))
    aid = scene.assets.add_qimage(photo, "photo.png")
    pic = ImageItem(scene.assets, aid)
    pic.setPos(1500, 1000)
    scene.add_folio_item(pic)
    scene.select_only([pic])
    win.set_persona("pixel")
    win.style_fill = {**win.style_fill, "color": "#ff000000"}
    win.set_tool("px-brush")
    drag(view, QPointF(1550, 1100), QPointF(1850, 1100), steps=6)
    check(pic.aid != aid and scene.assets.is_live(pic.aid)
          and scene.assets.full(aid).pixelColor(150, 100).red() == 255,
          "painting on a photo paints on a copy, the original stays")
    win.do_undo()
    win.do_undo()
    pic = [i for i in scene.folio_items() if isinstance(i, ImageItem) and i.pos().x() == 1500][0]
    check(pic.aid == aid, "undo goes back to the original photo")
    win.do_redo()
    win.do_redo()

    # ---- painted layers save and open ----------------------------------------------------
    path = os.path.join(_HOME, "painted.folio")
    fileio.save_document(scene, path)
    snap, assets = fileio.load_document(path)
    pixel_ids = [d["asset"] for d in snap["items"] if d.get("kind") == "image"]
    loaded = QImage.fromData(assets[pixel_ids[0]][0])
    check(not loaded.isNull() and loaded.width() == 2000, "a painted layer is saved as a picture")
    win.open_path(path, checked=True)
    reopened = [i for i in win.scene.folio_items()
                if isinstance(i, ImageItem) and i.pixel_size().width() == 2000][0]
    check(layer_pixel(reopened, 1200, 800).alpha() == 0 and layer_pixel(reopened, 450, 800).green() > 240,
          "the painting comes back when the file is opened")

    # ---- brushes panel -----------------------------------------------------------------
    from folio import brushes as brush_lib
    win.set_scene(DocScene(page_settings(1000, 600, "px", 300)))
    scene = win.scene
    win.set_persona("pixel")
    view.fit_page()
    QTest.qWait(20)
    panel = win.brushes_panel
    cats = [panel.category.itemText(i) for i in range(panel.category.count())]
    check(cats == ["Acrylics", "Dry Media", "Engraving", "Gouaches", "Inks", "Markers", "Oils",
                   "Patterns", "Pencils", "Pens", "Watercolors"], "all eleven brush categories")
    check(win.dock_brushes.isVisibleTo(win), "the Brushes tab shows in the Pixel persona")
    panel.category.setCurrentIndex(panel.category.findText("Pens"))
    panel.fill()
    names = [panel.list.item(i).text() for i in range(panel.list.count())]
    check("Ballpoint" in names and "Charcoal" not in names, f"a category shows its brushes: {names}")
    panel.search.setText("chalk")
    found = [panel.list.item(i).text() for i in range(panel.list.count())]
    check(found and all("chalk" in n.lower() for n in found), f"search finds brushes: {found}")
    panel.search.clear()
    check(all(not brush_lib.render_preview(b, 200).isNull() for _, b in brush_lib.ALL),
          f"every one of {len(brush_lib.ALL)} brushes draws a preview")
    win.style_fill = {**win.style_fill, "type": "solid", "color": "#ff000000"}
    win.use_brush(brush_lib.BY_NAME["Ballpoint"])
    check(win.tool_name == "px-brush" and win.brush["size"] == 6 and win.brush_name == "Ballpoint",
          "choosing a brush sets up the paint brush")
    win.set_tool("px-brush")
    win.brush["size"] = 100
    drag(view, QPointF(100, 150), QPointF(500, 150), steps=10)
    lay = [i for i in scene.folio_items() if isinstance(i, ImageItem)][0]
    solid = layer_pixel(lay, 300, 150)
    check(solid.alpha() > 250, "a hard brush paints a solid stroke")
    win.use_brush(brush_lib.BY_NAME["Chalk"])
    win.brush["size"] = 100
    drag(view, QPointF(100, 400), QPointF(500, 400), steps=10)
    img = lay.assets.full(lay.aid)
    alphas = [img.pixelColor(x, 400).alpha() for x in range(150, 450, 3)
              for _ in (0,)] + [img.pixelColor(300, y).alpha() for y in range(360, 440, 2)]
    check(any(a < 40 for a in alphas) and any(a > 150 for a in alphas),
          "Chalk is speckled: gaps and marks, not solid")
    win.use_brush(brush_lib.BY_NAME["Stars"])
    win.brush["size"] = 60
    before = win.undo.count()
    drag(view, QPointF(100, 520), QPointF(600, 520), steps=10)
    check(win.undo.count() == before + 1, "a stamp brush is one undo step")
    check(win.settings.value("brush_choice") == "Stars", "the chosen brush is remembered")
    win.set_persona("design")
    check(not win.dock_brushes.isVisibleTo(win), "Brushes hides again in the Designer persona")

    # ---- blend modes ----------------------------------------------------------------------------
    win.set_persona("design")
    win.set_scene(DocScene(page_settings(1000, 1000, "px", 300)))
    scene = win.scene
    base = RectItem()
    base.fill = {"type": "solid", "color": "#ffff8800", "color2": "#ff000000", "angle": 90.0}
    base.stroke = {"color": "#ff000000", "width": 0.0, "dash": "solid"}
    base.set_size(1000, 1000)
    scene.add_folio_item(base)
    top = RectItem()
    top.fill = {"type": "solid", "color": "#ff4080ff", "color2": "#ff000000", "angle": 90.0}
    top.stroke = dict(base.stroke)
    top.set_size(500, 500)
    top.setPos(250, 250)
    scene.add_folio_item(top)
    scene.select_only([top])
    win.layers.sync_selection()
    win.layers.blend.setCurrentIndex(win.layers.blend.findData("multiply"))
    win.layers.on_blend()
    c = page_pixel(scene, 500, 500, 0.5)
    check(top.blend == "multiply" and abs(c.red() - 0x40) < 6 and abs(c.green() - 0x44) < 8,
          f"Multiply mixes with what is under it ({c.name()})")
    pdf = os.path.join(_HOME, "blend.pdf")
    exporter.export(scene, {"format": "pdf", "area": "page", "outline_text": True}, pdf)
    shown = QImage.fromData(importers.render_pdf_page(pdf, 1, 60, transparent=False))
    c = shown.pixelColor(shown.width() // 2, shown.height() // 2)
    check(abs(c.red() - 0x40) < 10 and abs(c.green() - 0x44) < 12, "the PDF keeps the blended look")

    # ---- slices and exporting ----------------------------------------------------------
    win.set_scene(DocScene(cover_settings()))
    scene = win.scene
    names = [s["name"] for s in scene.slices]
    check(names == ["Whole cover", "Front cover", "Back cover", "Spine"], f"a cover's slices: {names}")
    win.set_persona("export")
    win.set_tool("slice")
    front = scene.doc.regions()["front"]
    drag(view, front.topLeft() + QPointF(300, 300), front.topLeft() + QPointF(900, 900))
    mine = scene.slices[-1]
    check(mine["name"] == "Slice 1" and win.chosen_slice == mine["id"]
          and abs(mine["rect"][2] - 600) < 30, "the Slice tool adds a slice")
    win.export_options.set_key("format", "jpeg")
    check(mine["format"] == "jpeg", "Export Options changes the chosen slice")
    win.do_undo()
    check(scene.slices[-1]["format"] == "png", "slice changes can be undone")
    win.do_redo()
    folder = tempfile.mkdtemp(prefix="folio-slices-")
    for s in scene.slices:
        s["export"] = s["name"] in ("Whole cover", "Front cover", "Slice 1")
    done = win.export_slices([s for s in scene.slices if s["export"]], folder)
    files = sorted(os.listdir(folder))
    check(files == ["Front cover.jpg", "Slice 1.jpg", "Whole cover.pdf"], f"slices exported: {files}")
    front_img = QImage(os.path.join(folder, "Front cover.jpg"))
    check(front_img.width() == 1800 and front_img.height() == 2700, "the front cover is 6 x 9 in at 300 dpi")
    info = importers.pdf_info(os.path.join(folder, "Whole cover.pdf"))
    check(abs(info["width_pt"] / 72 - 12.7) < 0.01, "the whole cover PDF has its bleed")
    win.set_tool("slice-select")
    win.choose_slice(mine["id"])
    win.delete_slice()
    check(all(s["id"] != mine["id"] for s in scene.slices), "a drawn slice can be deleted")
    path = os.path.join(_HOME, "slices.folio")
    win.add_slice(QRectF(100, 100, 300, 300), "Logo")
    fileio.save_document(scene, path)
    snap, _ = fileio.load_document(path)
    check(any(s["name"] == "Logo" for s in snap["slices"]), "slices are saved in the file")
    win.set_persona("design")

    # ---- rulers, guides and grid ---------------------------------------------------------
    win.set_scene(DocScene(page_settings(8.5, 11, "in", 300)))
    scene = win.scene
    QTest.qWait(30)
    win.a_rulers.setChecked(True)
    QTest.qWait(10)
    check(win.ruler_h.isVisible() and win.ruler_v.isVisible(), "Show Rulers puts rulers round the page")
    win.ruler_h.grab()
    win.ruler_v.grab()
    win.add_guide("x", 600.0)
    check(scene.guides["x"] == [600.0], "a guide is added")
    snapped = view.snap(QPointF(600 + view.tol(3), 900))
    check(abs(snapped.x() - 600) < 1e-6, "things snap to guides")
    win.set_tool("move")
    scene.select_only([])
    drag(view, QPointF(600, 900), QPointF(900, 900))
    check(abs(scene.guides["x"][0] - 900) < view.tol(2), "the Move tool drags a guide")
    far = view.mapToScene(view.viewport().rect().bottomRight()) + QPointF(400, 400)
    drag(view, QPointF(scene.guides["x"][0], 900), far)
    check(scene.guides["x"] == [], "dragging a guide off the page removes it")
    win.do_undo()
    check(len(scene.guides["x"]) == 1, "undo brings the guide back")
    win.clear_guides()
    check(scene.guides == {"x": [], "y": []}, "Clear All Guides")
    win.a_grid.setChecked(True)
    snapped = view.snap(QPointF(76.5, 1000.5))
    check(abs(snapped.x() - 75) < 1e-6, "with the grid on, things snap to it (every 0.25 in)")
    win.a_grid.setChecked(False)
    win.a_rulers.setChecked(False)

    # ---- Document Setup keeps objects sized and placed ----------------------------------
    box = RectItem()
    box.set_size(300, 300)
    box.setPos(1125, 1500)
    scene.add_folio_item(box)
    old = scene.doc
    new = page_settings(8.5, 11, "in", 150)
    win.refit_objects(old, new, "anchor")
    check(abs(box.w - 150) < 1e-6 and abs(box.pos().x() - 562.5) < 1e-6,
          "a new DPI keeps objects the same real size")
    old = new
    new = page_settings(17, 22, "in", 150)
    centre = box.center_scene()
    win.refit_objects(old, new, "rescale")
    check(abs(box.center_scene().x() - centre.x() * 2) < 1e-6 and abs(box.w - 300) < 1e-6,
          "Rescale stretches objects with the page")
    win.refit_objects(new, page_settings(19, 22, "in", 150), "anchor", 1.0, 0.0)
    check(abs(box.center_scene().x() - centre.x() * 2 - 300) < 1e-6,
          "Anchor to the right edge moves objects with it")

    # ---- Toggle UI and Close ---------------------------------------------------------------
    win.toggle_ui()
    check(not win.main_bar.isVisible() and not win.dock_colour.isVisible(), "Tab hides the panels")
    win.toggle_ui()
    check(win.main_bar.isVisible() and win.dock_colour.isVisible(), "Tab shows them again")
    from folio import window as window_module
    window_module.NewDocumentDialog.exec_ = lambda self: 0
    win.undo.setClean()
    win.close_document()
    check(win.scene.doc.kind == "cover" and not win.scene.folio_items() and win.path is None,
          "Close gives a fresh, empty document")

    win.undo.setClean()
    win.close()
    if ERRORS:
        import traceback
        for e in ERRORS:
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
