"""Checks for the Affinity-style toolbars: the new tools (shapes, Pencil,
Gradient fill, Colour picker, Measure), combining shapes (Geometry),
Convert to Curves, insert modes, the context bar and the tool buttons.

    QT_QPA_PLATFORM=offscreen python3 -m tests.test_tools
"""

import os
import sys
import tempfile

_HOME = tempfile.mkdtemp(prefix="folio-home-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_HOME, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_HOME, "data")

from PyQt5.QtCore import QEvent, QPointF, QRectF, Qt  # noqa: E402
from PyQt5.QtGui import QColor  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app = QApplication.instance() or QApplication(sys.argv)
app.setProperty("quiet_errors", True)

from folio import exporter, fileio, fonts, theme  # noqa: E402
from folio.document import page_settings  # noqa: E402
from folio.items import EllipseItem, PathItem, RectItem, TextItem  # noqa: E402
from folio.scene import DocScene  # noqa: E402
from folio.window import MainWindow  # noqa: E402
from tests.test_smoke import check, drag, mouse  # noqa: E402

ERRORS = []
sys.excepthook = lambda *a: ERRORS.append(a)


def pixel(scene, x, y, scale=0.25):
    image = exporter.render_image(scene, scene.doc.page_rect(), scale)
    return image.pixelColor(int(x * scale), int(y * scale))


def shape(win, cls, x, y, w, h, colour):
    item = cls()
    item.fill = {"type": "solid", "color": colour, "color2": "#ff000000", "angle": 90.0}
    item.stroke = {"color": "#ff000000", "width": 0.0, "dash": "solid"}
    item.set_size(w, h)
    item.setPos(x, y)
    win.scene.add_folio_item(item)
    return item


def fresh(win):
    win.set_scene(DocScene(page_settings(3000, 2000, "px", 300)))
    QTest.qWait(10)
    return win.scene


def is_red(c):
    return c.red() > 200 and c.green() < 80 and c.blue() < 80


def is_white(c):
    return c.red() > 230 and c.green() > 230 and c.blue() > 230


def main():
    theme.apply(app)
    fonts.load_bundled()
    win = MainWindow()
    win.resize(1500, 950)
    win.show()
    QTest.qWait(30)
    view = win.view

    # ---- ready-made shapes -----------------------------------------------------
    scene = fresh(win)
    for kind, nodes in (("star", 10), ("triangle", 3), ("diamond", 4), ("polygon", 6),
                        ("arrow", 7), ("heart", 6)):
        win.create_shape(kind, QRectF(100, 100, 400, 300))
        item = scene.selected_folio()[0]
        check(isinstance(item, PathItem) and len(item.nodes) == nodes and item.closed
              and abs(item.w - 400) < 1 and abs(item.h - 300) < 1,
              f"the {kind} tool draws a {kind} that fills the box")
    win.create_shape("rounded", QRectF(600, 100, 400, 300))
    item = scene.selected_folio()[0]
    check(isinstance(item, RectItem) and item.radius > 0, "the rounded rectangle has round corners")
    win.set_tool("star")
    star_button = next(b for b in win.tool_buttons if "star" in b.names)
    check(star_button.current == "star" and star_button.isChecked(), "the shapes button shows the star")
    win.set_tool("move")
    check(not star_button.isChecked() and win.tool_buttons[0].isChecked(), "Move is back on")

    # ---- Geometry ------------------------------------------------------------------
    scene = fresh(win)
    a = shape(win, RectItem, 400, 400, 800, 800, "#ffff0000")
    b = shape(win, RectItem, 800, 800, 800, 800, "#ff00ff00")
    scene.select_only([a, b])
    win.geometry("add")
    sel = scene.selected_folio()
    check(len(sel) == 1 and isinstance(sel[0], PathItem) and len(scene.folio_items()) == 1,
          "Add joins two shapes into one")
    check(is_red(pixel(scene, 500, 500)) and is_red(pixel(scene, 1500, 1500))
          and is_white(pixel(scene, 1500, 500)), "the joined shape covers both, in the bottom colour")
    win.do_undo()
    check(len(scene.folio_items()) == 2, "undo brings the two shapes back")
    a, b = scene.folio_items()
    scene.select_only([a, b])
    win.geometry("intersect")
    check(is_red(pixel(scene, 1000, 1000)) and is_white(pixel(scene, 500, 500)),
          "Intersect keeps only the overlap")
    win.do_undo()
    a, b = scene.folio_items()
    scene.select_only([a, b])
    win.geometry("xor")
    check(is_white(pixel(scene, 1000, 1000)) and is_red(pixel(scene, 500, 500))
          and is_red(pixel(scene, 1500, 1500)), "Combine cuts out the overlap")
    win.do_undo()
    a, b = scene.folio_items()
    scene.select_only([a, b])
    win.geometry("divide")
    check(len(scene.folio_items()) == 3, "Divide makes three pieces")
    over = pixel(scene, 1000, 1000)
    check(over.green() > 200 and over.red() < 80, "the overlap piece takes the top colour")
    scene = fresh(win)
    big = shape(win, RectItem, 400, 400, 1200, 1200, "#ffff0000")
    hole = shape(win, EllipseItem, 800, 800, 400, 400, "#ff0000ff")
    scene.select_only([big, hole])
    win.geometry("subtract")
    result = scene.selected_folio()[0]
    check(len(result.extra) == 1 and is_white(pixel(scene, 1000, 1000))
          and is_red(pixel(scene, 500, 500)), "Subtract cuts a hole")
    snap = scene.snapshot()
    win.do_undo()
    win.do_redo()
    check(scene.snapshot()["items"][0]["extra"] == snap["items"][0]["extra"],
          "a shape with a hole survives undo and redo")
    path = os.path.join(_HOME, "hole.folio")
    fileio.save_document(scene, path)
    loaded, _ = fileio.load_document(path)
    check(len(loaded["items"][0]["extra"]) == 1, "a shape with a hole saves and opens")
    scene.select_only([scene.folio_items()[0]])     # rebuilt by undo and redo
    win.separate_curves()
    check(len(scene.folio_items()) == 2, "Separate Curves splits it into its parts")

    # ---- Convert to Curves ------------------------------------------------------------
    scene = fresh(win)
    text = win.create_text(QPointF(300, 300), text="BOOK")
    text.style["size"] = 400.0
    text.apply_style()
    text.fill["color"] = "#ffff0000"
    text.apply_style()
    before = text.scene_bounds()
    uid = text.uid
    scene.select_only([text])
    win.convert_to_curves()
    curves = scene.selected_folio()[0]
    check(isinstance(curves, PathItem) and curves.uid == uid and len(curves.parts()) >= 4,
          f"text becomes curves ({len(curves.parts())} parts)")
    after = curves.scene_bounds()
    check(abs(after.center().x() - before.center().x()) < 60 and after.width() > 600,
          "the curves sit where the words were")
    scene.select_only([curves])
    win.set_tool("node")
    win.set_tool("move")

    # ---- Pencil, Gradient fill, Colour picker, Measure ---------------------------------
    scene = fresh(win)
    view.fit_page()
    QTest.qWait(10)
    win.set_tool("pencil")
    pts = [QPointF(300 + 40 * k, 1000 + (120 if k % 2 else 0) * 0 + 300 * ((k % 6) / 6.0))
           for k in range(30)]
    mouse(view, QEvent.MouseButtonPress, pts[0])
    for p in pts[1:]:
        mouse(view, QEvent.MouseMove, p, button=Qt.NoButton, buttons=Qt.LeftButton)
    mouse(view, QEvent.MouseButtonRelease, pts[-1])
    drawn = [i for i in scene.folio_items() if isinstance(i, PathItem)]
    check(len(drawn) == 1 and 2 <= len(drawn[0].nodes) < len(pts) and not drawn[0].closed,
          f"the Pencil draws a smoothed line ({len(drawn[0].nodes) if drawn else 0} points)")
    check(drawn[0].fill["type"] == "none" and drawn[0].stroke["width"] > 0, "a pencil line has no fill")
    rect = shape(win, RectItem, 400, 400, 1200, 600, "#ffff0000")
    scene.select_only([rect])
    win.set_tool("fill")
    drag(view, QPointF(500, 700), QPointF(1500, 700))
    check(rect.fill["type"] == "linear" and (rect.fill["angle"] < 2 or rect.fill["angle"] > 358),
          f"the Gradient tool makes a left-to-right gradient ({rect.fill['angle']:.1f})")
    win.do_undo()
    check(scene.folio_items()[-1].fill["type"] == "solid", "undo takes the gradient off")
    other = shape(win, EllipseItem, 2000, 400, 500, 500, "#ff0000ff")
    rect = [i for i in scene.folio_items() if isinstance(i, RectItem)][0]
    scene.select_only([other])
    win.refresh_panels()
    win.set_colour_target("fill")
    win.set_tool("picker")
    QTest.qWait(30)
    mouse(view, QEvent.MouseButtonPress, QPointF(800, 700))
    mouse(view, QEvent.MouseButtonRelease, QPointF(800, 700))
    picked = QColor(other.fill["color"])
    check(is_red(picked), f"the Colour picker gives the selection the red it clicked ({picked.name()})")
    win.set_tool("measure")
    drag(view, QPointF(400, 1500), QPointF(1000, 1500))
    text = win.tools["measure"].text()
    check(text.startswith("600 px (2.00 in)") and "0.0°" in text, f"Measure: {text}")
    win.set_tool("move")

    # ---- insert modes ------------------------------------------------------------------
    scene = fresh(win)
    circle = shape(win, EllipseItem, 400, 400, 800, 800, "#ff0000ff")
    scene.select_only([circle])
    win.set_insert_mode("inside")
    win.create_shape("rect", QRectF(300, 300, 600, 600))
    inside = scene.selected_folio()[0]
    check(inside.clip == circle.uid and inside.group == circle.group,
          "Insert Inside puts a new shape inside the selected circle")
    check(is_white(pixel(scene, 420, 420)) and not is_white(pixel(scene, 700, 700)),
          "it only shows inside the circle")
    scene.select_only([circle])
    win.set_insert_mode("behind")
    win.create_shape("ellipse", QRectF(1500, 400, 300, 300))
    behind = scene.selected_folio()[0]
    check(scene.folio_items().index(behind) < scene.folio_items().index(circle),
          "Insert Behind puts it under the selection")
    win.set_insert_mode("top")
    check(win.insert_actions["top"].isChecked() and not win.insert_actions["inside"].isChecked(),
          "only one insert button is on")

    # ---- context bar and greyed-out buttons -------------------------------------------
    scene = fresh(win)
    win.refresh_panels()
    bar = win.context_bar

    def shown(key):
        return all(action.isVisible() for action in bar.parts[key])
    check(bar.label.text() == "No Selection" and shown("doc")
          and not shown("corners"), "nothing selected: Document Setup and Settings")
    check(not win.a_front.isEnabled() and not win.geo_actions["add"].isEnabled(),
          "selection buttons are grey with nothing selected")
    r1 = shape(win, RectItem, 400, 400, 400, 400, "#ffff0000")
    r2 = shape(win, RectItem, 600, 600, 400, 400, "#ff00ff00")
    scene.select_only([r1])
    win.refresh_panels()
    check(bar.label.text() == "Rectangle" and shown("corners")
          and not shown("doc"), "a rectangle shows its corners in the bar")
    bar.corners.setValue(12)
    check(abs(r1.radius - 50) < 0.01, "the bar rounds the corners (12 pt)")
    bar.on_colour("stroke", QColor("#ff0000ff"))
    check(r1.stroke["color"] == "#ff0000ff" and r1.stroke["width"] > 0, "the bar colours the outline")
    scene.select_only([r1, r2])
    win.refresh_panels()
    check(win.geo_actions["add"].isEnabled() and win.a_group.isEnabled(), "two selected: Geometry is on")
    t = win.create_text(QPointF(400, 1200), text="Hello")
    scene.select_only([t])
    win.refresh_panels()
    check(shown("text") and bar.label.text().startswith("Text"),
          "text shows its font in the bar")
    bar.size.setValue(36)
    check(abs(t.style["size"] - 150) < 0.01, "the bar sets the text size")
    bar.auto.setCurrentIndex(1)
    check(win.auto_select == "object", "Auto-select can pick single objects")
    bar.auto.setCurrentIndex(0)

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
