"""The main window: menus, panels, files and editing commands."""

import base64
import json
import math
import os
import shutil
import subprocess
import time
import zipfile
from contextlib import contextmanager

from PyQt5.QtCore import (QByteArray, QEvent, QMimeData, QPointF, QRectF, QSettings,
                          QSize, QStandardPaths, Qt, QTimer, QUrl)
from PyQt5.QtGui import (QColor, QDesktopServices, QFontDatabase, QGuiApplication, QImage,
                         QImageReader, QKeySequence, QPainter, QPainterPath, QPageLayout,
                         QPen, QPolygonF)
from PyQt5.QtPrintSupport import (QPageSetupDialog, QPrintDialog, QPrinter,
                                  QPrintPreviewDialog)
from PyQt5.QtWidgets import (QAction, QActionGroup, QApplication, QComboBox,
                             QDockWidget, QFileDialog, QGridLayout, QInputDialog, QLabel,
                             QMainWindow, QMenu, QMessageBox, QSizePolicy, QTabWidget,
                             QToolBar, QToolButton, QUndoCommand, QUndoStack, QUndoView,
                             QWidget, QWidgetAction)

from . import __version__, exporter, fileio, fonts, shapes, styles, units
from .canvas import CanvasView
from .dialogs import (ExportDialog, PdfImportDialog, SettingsDialog, ShortcutsDialog,
                      WordImportDialog)
from .newdoc import NewDocumentDialog
from . import importers
from .document import DocSettings, cover_settings, page_settings
from .icons import app_icon, icon
from .items import (DEFAULT_TEXT_STYLE, EllipseItem, ImageItem, PathItem, RectItem,
                    TextItem, color_str, item_from_dict, new_uid, parts_from_path,
                    path_item_from_scene_path, qcolor)
from .panels import LayersPanel, PropertiesPanel, TextPanel, TransformPanel, refresh_item
from .scene import DocScene
from .brushes import BY_NAME, BrushesPanel
from .context import ContextBar
from .rulers import wrap_with_rulers
from .pixel import DEFAULT_BRUSH, PIXEL_TOOL_CLASSES, Stroke
from .slices import (EXPORT_KEYS, ExportOptionsPanel, SliceSelectTool, SlicesPanel, SliceTool,
                     draw_slices, export_slice, new_slice)
from .studio import (ColourPanel, FillStrokeSelector, NavigatorPanel, StrokePanel,
                     SwatchesPanel)
from .styles import StylesPanel
from .tools import make_tools

MIME = "application/x-folio-items"
TOOLS = [
    ("move", "Move", "V", "Click to select. Drag to move. Drag a square handle to resize, "
     "the round handle to rotate. Shift keeps proportions. Double-click text to type."),
    ("node", "Edit points", "A", "Drag the points of a curve. Click the line to add a point. "
     "Double-click a point to make it smooth or sharp. Delete removes it."),
    ("pen", "Pen", "P", "Click for sharp corners, drag for smooth curves. Click the first "
     "point to close the shape. Press Enter to finish."),
    ("line", "Line", "L", "Drag to draw a straight line. Shift keeps it level or at 45 degrees."),
    ("pencil", "Pencil", "N", "Draw freehand. The line is smoothed when you let go. "
     "End where you started for a closed shape."),
    ("fill", "Gradient fill", "G", "Drag across a shape to fill it with a gradient running "
     "that way. Hold Shift for a round gradient."),
    ("rect", "Rectangle", "M", "Drag to draw a rectangle. Shift makes a square, "
     "Ctrl draws from the centre."),
    ("ellipse", "Ellipse", "E", "Drag to draw an ellipse. Shift makes a circle, "
     "Ctrl draws from the centre."),
    ("rounded", "Rounded rectangle", "U", "Drag to draw a rectangle with rounded corners. "
     "Change the corners in the bar at the top."),
    ("triangle", "Triangle", None, "Drag to draw a triangle. Shift keeps it even."),
    ("diamond", "Diamond", None, "Drag to draw a diamond. Shift keeps it even."),
    ("star", "Star", None, "Drag to draw a five-pointed star. Shift keeps it even."),
    ("polygon", "Polygon", None, "Drag to draw a six-sided shape. Shift keeps it even."),
    ("arrow", "Arrow", None, "Drag to draw an arrow. Flip it to point the other way."),
    ("heart", "Heart", None, "Drag to draw a heart. Shift keeps it even."),
    ("text", "Text", "T", "Click to type. Drag a box first for text that wraps. "
     "Press Esc when you are done."),
    ("picker", "Colour picker", "I", "Click anything on the page to give the selection "
     "that colour (fill, or outline if the outline circle is chosen)."),
    ("measure", "Measure", None, "Drag to measure a distance. Shift keeps to 45 degrees."),
    ("zoom", "Zoom", "Z", "Click to zoom in, Ctrl-click to zoom out, drag a box to zoom to it."),
    ("hand", "Hand", "H", "Drag to move around. You can also hold Space with any tool."),
    # Pixel persona
    ("px-rect", "Rectangular marquee", "M", "Drag to select a rectangle of pixels. Shift adds, "
     "Alt takes away, Ctrl makes a square."),
    ("px-ellipse", "Elliptical marquee", None, "Drag to select an oval of pixels. Shift adds, "
     "Alt takes away."),
    ("px-row", "Row marquee", None, "Click to select one row of pixels across the page."),
    ("px-column", "Column marquee", None, "Click to select one column of pixels down the page."),
    ("px-lasso", "Freehand selection", "L", "Draw round the pixels you want. Shift adds, Alt "
     "takes away."),
    ("px-wand", "Flood select", None, "Click to select the area of nearly the same colour. "
     "Change Tolerance in the bar at the top."),
    ("px-brush", "Paint brush", "B", "Paint with the fill colour. Width, opacity, flow and "
     "hardness are in the bar at the top."),
    ("px-erase", "Erase brush", "E", "Rub out pixels, making them see-through."),
    ("px-fill", "Flood fill", "G", "Click to fill the area of nearly the same colour with the "
     "fill colour."),
    ("px-blur", "Blur brush", None, "Brush over pixels to soften them."),
    ("px-dodge", "Dodge brush", "O", "Brush over pixels to lighten them."),
    ("px-burn", "Burn brush", None, "Brush over pixels to darken them."),
    # Export persona
    ("slice", "Slice", "S", "Drag out an area of the page to export on its own."),
    ("slice-select", "Slice selection", "K", "Click a slice to choose it; drag one you drew to "
     "move it."),
]
TOOL_ICONS = {"arrow": "arrow-shape", "heart": "heart-shape", "text": "artistic-text"}
# The left tool bar, top to bottom; tools in one list share a button
# (hold the button, or right-click it, to pick another).
TOOL_BUTTONS = [["move"], ["node"], ["pen", "line"], ["pencil"], ["fill"], "place",
                ["rect"], ["ellipse"],
                ["rounded", "triangle", "diamond", "star", "polygon", "arrow", "heart"],
                ["text"], ["picker"], ["measure"], "-", ["zoom", "hand"]]
PERSONA_TOOLS = {
    "design": TOOL_BUTTONS,
    "pixel": [["move"], ["px-rect", "px-ellipse", "px-row", "px-column"], ["px-lasso"],
              ["px-wand"], ["px-brush"], ["px-erase"], ["px-fill"], ["px-blur"],
              ["px-dodge", "px-burn"], ["picker"], "-", ["hand"], ["zoom"]],
    "export": [["slice"], ["slice-select"], "-", ["hand"], ["zoom"]],
}
PERSONAS = [("design", "Designer Persona", "Draw and lay out your page"),
            ("pixel", "Pixel Persona", "Paint and retouch pixels"),
            ("export", "Export Persona", "Choose areas of the page (slices) and export them")]
PERSONA_DEFAULT_TOOL = {"design": "move", "pixel": "px-brush", "export": "slice-select"}


def tool_icon(name):
    return icon(TOOL_ICONS.get(name, name))


class ToolButton(QToolButton):
    """A tool on the left bar. When it holds several tools, a small
    triangle shows; hold the button (or right-click) to choose."""

    def __init__(self, win, names):
        super().__init__()
        self.win = win
        self.names = names
        self.current = names[0]
        self.setCheckable(True)
        self.setAutoRaise(True)
        self.setIconSize(QSize(20, 20))
        if len(names) > 1:
            menu = QMenu(self)
            for n in names:
                title, key = next((t, k) for nn, t, k, _ in TOOLS if nn == n)
                a = menu.addAction(tool_icon(n), title + (f"\t{key}" if key else ""))
                a.triggered.connect(lambda _=False, n=n: self.choose(n))
            self.setMenu(menu)
            self.setPopupMode(QToolButton.DelayedPopup)
            self.setStyleSheet("QToolButton::menu-indicator { image: none; width: 0; }")
        self.clicked.connect(lambda: win.set_tool(self.current))
        self.show_current()

    def choose(self, name):
        self.current = name
        self.show_current()
        self.win.set_tool(name)

    def show_current(self):
        title, key, hint = next((t, k, h) for n, t, k, h in TOOLS if n == self.current)
        self.setIcon(tool_icon(self.current))
        more = "\nHold the button for more tools." if len(self.names) > 1 else ""
        self.setToolTip(f"{title}" + (f"  ({key})" if key else "") + f"\n{hint}{more}")

    def contextMenuEvent(self, e):
        if self.menu() is not None:
            self.menu().exec_(e.globalPos())

    def paintEvent(self, e):
        super().paintEvent(e)
        if len(self.names) > 1:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            r = self.rect()
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#d8dbe0"))
            p.drawPolygon(QPolygonF([QPointF(r.right() - 2, r.bottom() - 7),
                                     QPointF(r.right() - 2, r.bottom() - 2),
                                     QPointF(r.right() - 7, r.bottom() - 2)]))
            p.end()


IMAGE_FILTER = ("Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tif *.tiff *.svg *.svgz "
                "*.heic *.heif *.avif *.psd)")
IMPORT_FILTER = ("Everything Folio can bring in (*.pdf *.docx *.doc *.odt *.rtf *.afdesign *.af "
                 "*.afphoto *.afpub *.png *.jpg *.jpeg *.gif *.bmp *.webp *.tif *.tiff *.svg *.heic *.psd)"
                 ";;PDF files (*.pdf);;Word documents (*.docx *.doc *.odt *.rtf)"
                 ";;Affinity files (*.afdesign *.af *.afphoto *.afpub);;" + IMAGE_FILTER)
OFFICE_EXTS = ("docx", "doc", "odt", "rtf")
AFFINITY_EXTS = ("afdesign", "af", "afphoto", "afpub")
FONT_EXTS = (".ttf", ".otf", ".ttc")


class SnapshotCommand(QUndoCommand):
    """One undo step: the document before and after."""

    def __init__(self, win, before, after, sel_before, sel_after, label, merge):
        super().__init__(label)
        self.win = win
        self.before, self.after = before, after
        self.sel_before, self.sel_after = sel_before, sel_after
        self.merge = merge
        self.time = time.monotonic()
        self.first = True

    def redo(self):
        if self.first:
            self.first = False
            return
        self.win.restore_snapshot(self.after, self.sel_after)

    def undo(self):
        self.win.restore_snapshot(self.before, self.sel_before)

    def id(self):
        return 4242 if self.merge else -1

    def mergeWith(self, other):
        if other.merge != self.merge or other.time - self.time > 2.0:
            return False
        self.after = other.after
        self.sel_after = other.sel_after
        self.time = other.time
        if self.before == self.after:
            self.setObsolete(True)
        return True


LAYOUT_VERSION = 4

# How new shapes look until the user picks their own defaults.
FACTORY_FILL = {"type": "solid", "color": "#ff3d7bd9", "color2": "#ff10233f", "angle": 90.0}
FACTORY_STROKE = {"color": "#ff000000", "width": 0.0, "dash": "solid"}
FACTORY_TEXT_COLOR = "#ff1a1a1a"


def data_dir():
    base = QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation)
    folder = os.path.join(base or os.path.expanduser("~/.local/share"), "folio")
    os.makedirs(folder, exist_ok=True)
    return folder


def templates_dir():
    folder = os.path.join(data_dir(), "templates")
    os.makedirs(folder, exist_ok=True)
    return folder


def safe_filename(name):
    """A name that is safe to use for a file or folder."""
    cleaned = "".join("-" if c in '/\\:*?"<>|' else c for c in name).strip(" .")
    return cleaned or "Untitled"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(app_icon())
        self.settings = QSettings("Folio", "Folio")
        self.undo_steps = self.settings.value("undo_steps", 400, type=int)
        self.nudge_step = self.settings.value("nudge", 1.0, type=float)
        self.undo = QUndoStack(self)
        self.undo.setUndoLimit(self.undo_steps)
        self.path = None
        self._depth = 0
        self._before = None
        self._sel_before = []
        self.text_defaults = dict(DEFAULT_TEXT_STYLE)
        self.text_color = FACTORY_TEXT_COLOR
        self.style_fill = dict(FACTORY_FILL)
        self.style_stroke = dict(FACTORY_STROKE)
        self.line_stroke = None
        try:
            self.saved_defaults = json.loads(self.settings.value("defaults", "{}") or "{}")
        except ValueError:
            self.saved_defaults = {}
        self.style_fill.update(self.saved_defaults.get("fill", {}))
        self.style_stroke.update(self.saved_defaults.get("stroke", {}))
        self.text_color = self.saved_defaults.get("text_color", self.text_color)
        self.colour_target = "fill"
        self.insert_mode = "top"
        self.auto_select = "group"
        self._picking_colour = False
        try:
            self.recent_colours = json.loads(self.settings.value("recent_colours", "[]") or "[]")
        except ValueError:
            self.recent_colours = []
        self.last_export = json.loads(self.settings.value("last_export", "{}") or "{}")
        self.paste_count = 0
        self._last_kind = None
        self.autosave_path = os.path.join(data_dir(), f"autosave-{os.getpid()}.folio")

        fonts.load_bundled()
        self.scene = DocScene(cover_settings())
        self.view = CanvasView(self.scene, self)
        self.setCentralWidget(wrap_with_rulers(self, self.view))
        self.tools = make_tools(self.view)
        for name, make in PIXEL_TOOL_CLASSES.items():
            self.tools[name] = make(self.view)
        self.tools["slice"] = SliceTool(self.view)
        self.tools["slice-select"] = SliceSelectTool(self.view)
        self.persona = "design"
        self.brush = dict(DEFAULT_BRUSH)
        self.pixel_selection = None
        self.brush_name = ""
        self.chosen_slice = None
        try:
            self.slice_defaults = json.loads(self.settings.value("slice_defaults", "") or "{}")
        except ValueError:
            self.slice_defaults = {}
        if not self.slice_defaults:
            self.slice_defaults = {"format": "png", "quality": 92, "outline_text": True,
                                   "pixel_format": "document", "resample": "bilinear",
                                   "matte": "", "icc": True, "bleed": False}
        self.tool_name = None

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.refresh_panels)
        self._layers_timer = QTimer(self)
        self._layers_timer.setSingleShot(True)
        self._layers_timer.timeout.connect(self.rebuild_layers)

        self.build_panels()
        saved_brush = BY_NAME.get(self.settings.value("brush_choice", ""))
        if saved_brush is not None:
            from .brushes import settings_of
            self.brush.update({k: v for k, v in settings_of(saved_brush).items()
                               if k in self.brush})
            self.brush_name = saved_brush["name"]
        self.build_actions()
        self.build_toolbars()
        self.build_menus()
        self.build_status()
        rulers = self.settings.value("rulers", False, type=bool)
        self.a_rulers.setChecked(rulers)
        self.set_rulers(rulers)
        self.connect_scene()
        self.reset_defaults()
        self.set_tool("move")
        self.undo.cleanChanged.connect(self.update_title)
        self.undo.indexChanged.connect(lambda _: self.update_title())
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start(self.settings.value("autosave_min", 2, type=int) * 60_000)
        self.resize(1440, 900)
        self._default_state = self.saveState()
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        state = self.settings.value("window_state")
        if state is not None and self.settings.value("layout_version", 0, type=int) == LAYOUT_VERSION:
            self.restoreState(state)
        self.update_title()

    # ---- layout ---------------------------------------------------------------

    def make_dock(self, title, widget, name):
        dock = QDockWidget(title, self)
        dock.setObjectName(name)
        dock.setWidget(widget)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable
                         | QDockWidget.DockWidgetFloatable)
        dock.setMinimumWidth(250)
        return dock

    def build_panels(self):
        self.colourp = ColourPanel(self)
        self.swatches = SwatchesPanel(self)
        self.strokep = StrokePanel(self)
        self.textp = TextPanel(self)
        self.layers = LayersPanel(self)
        self.props = PropertiesPanel(self)
        self.stylesp = StylesPanel(self)
        self.transform = TransformPanel(self)
        self.history = QUndoView(self.undo)
        self.history.setEmptyLabel("Start")
        self.history.setToolTip("Click a step to go back to it")
        self.history.viewport().installEventFilter(self)
        self.navigator = NavigatorPanel(self)
        self.dock_colour = self.make_dock("Colour", self.colourp, "dock_colour")
        self.dock_swatches = self.make_dock("Swatches", self.swatches, "dock_swatches")
        self.dock_stroke = self.make_dock("Stroke", self.strokep, "dock_stroke")
        self.dock_text = self.make_dock("Text", self.textp, "dock_text")
        self.dock_layers = self.make_dock("Layers", self.layers, "dock_layers")
        self.dock_props = self.make_dock("Fill and FX", self.props, "dock_props")
        self.dock_styles = self.make_dock("Styles", self.stylesp, "dock_styles")
        self.dock_transform = self.make_dock("Transform", self.transform, "dock_transform")
        self.dock_history = self.make_dock("History", self.history, "dock_history")
        self.dock_navigator = self.make_dock("Navigator", self.navigator, "dock_navigator")
        self.brushes_panel = BrushesPanel(self)
        self.dock_brushes = self.make_dock("Brushes", self.brushes_panel, "dock_brushes")
        self.export_options = ExportOptionsPanel(self)
        self.slices_panel = SlicesPanel(self)
        self.dock_export = self.make_dock("Export Options", self.export_options, "dock_export")
        self.dock_slices = self.make_dock("Slices", self.slices_panel, "dock_slices")
        # Three stacks of tabs down the right, as in pro design apps:
        # colour on top, layers in the middle, transform at the bottom.
        self.setTabPosition(Qt.RightDockWidgetArea, QTabWidget.North)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_colour)
        self.splitDockWidget(self.dock_colour, self.dock_layers, Qt.Vertical)
        self.splitDockWidget(self.dock_layers, self.dock_transform, Qt.Vertical)
        for group in ((self.dock_colour, self.dock_swatches, self.dock_stroke, self.dock_text,
                       self.dock_export),
                      (self.dock_layers, self.dock_brushes, self.dock_props, self.dock_styles,
                       self.dock_slices),
                      (self.dock_transform, self.dock_history, self.dock_navigator)):
            for a, b in zip(group, group[1:]):
                self.tabifyDockWidget(a, b)
            group[0].raise_()
        # The tabs name these panels, so their own title bars are hidden.
        for dock in self.docks():
            dock.setTitleBarWidget(QWidget())
        self.resizeDocks([self.dock_colour, self.dock_layers, self.dock_transform],
                         [360, 330, 230], Qt.Vertical)
        self.resizeDocks([self.dock_colour], [270], Qt.Horizontal)
        self.dock_export.hide()
        self.dock_slices.hide()
        self.dock_brushes.hide()

    def docks(self):
        return (self.dock_colour, self.dock_swatches, self.dock_stroke, self.dock_text,
                self.dock_export, self.dock_layers, self.dock_brushes, self.dock_props,
                self.dock_styles, self.dock_slices, self.dock_transform, self.dock_history,
                self.dock_navigator)

    def persona_docks(self, persona):
        if persona == "export":
            return [self.dock_export, self.dock_layers, self.dock_slices, self.dock_transform,
                    self.dock_history, self.dock_navigator]
        if persona == "pixel":
            return [self.dock_colour, self.dock_swatches, self.dock_layers, self.dock_brushes,
                    self.dock_props, self.dock_transform, self.dock_history, self.dock_navigator]
        return [self.dock_colour, self.dock_swatches, self.dock_stroke, self.dock_text,
                self.dock_layers, self.dock_props, self.dock_styles, self.dock_transform,
                self.dock_history, self.dock_navigator]

    def tool_list(self):
        return TOOLS

    def eventFilter(self, obj, e):
        # Finish typing before jumping back in History, so the typing is kept as a step.
        if e.type() == QEvent.MouseButtonPress and obj is self.history.viewport():
            self.stop_text_editing()
        if self._picking_colour and obj in (self.view.viewport(), self.view):
            if e.type() == QEvent.MouseButtonPress:
                if e.button() == Qt.LeftButton:
                    image = self.view.viewport().grab().toImage()
                    ratio = image.devicePixelRatio() or 1.0
                    c = image.pixelColor(int(e.pos().x() * ratio), int(e.pos().y() * ratio))
                    self.end_colour_pick()
                    self.apply_colour(c, merge=False)
                    self.remember_colour(c)
                else:
                    self.end_colour_pick()
                return True
            if e.type() == QEvent.KeyPress and e.key() == Qt.Key_Escape:
                self.end_colour_pick()
                return True
        return super().eventFilter(obj, e)

    def act(self, text, slot, shortcut=None, icon_name=None, checkable=False, tip=None):
        a = QAction(text, self)
        if shortcut:
            if isinstance(shortcut, (list, tuple)):
                a.setShortcuts([QKeySequence(s) for s in shortcut])
                first = shortcut[0]
            else:
                a.setShortcut(QKeySequence(shortcut))
                first = shortcut
            a.setToolTip(f"{tip or text.replace('&', '').rstrip('.…')}  ({first})")
        elif tip:
            a.setToolTip(tip)
        if icon_name:
            a.setIcon(icon(icon_name))
        a.setCheckable(checkable)
        if checkable:
            a.toggled.connect(slot)
        else:
            a.triggered.connect(lambda _=False: slot())
        self.addAction(a)
        return a

    def build_actions(self):
        A = self.act
        self.a_new = A("&New…", self.new_document, "Ctrl+N", "new")
        self.a_new_clip = A("New from &Clipboard", self.new_from_clipboard, "Ctrl+Alt+Shift+N",
                            tip="Start a new document the size of the picture or objects you copied")
        self.a_new_last = A("New from &Last Preset", self.new_from_last_preset,
                            tip="Start a new document the same size as the last one you made")
        self.a_open = A("&Open…", self.open_document, "Ctrl+O", "open")
        self.a_save = A("&Save", self.save, "Ctrl+S", "save")
        self.a_save_as = A("Save &As…", self.save_as, "Ctrl+Shift+S")
        self.a_package = A("Save As Pac&kage…", self.save_as_package,
                           tip="Save the design in a folder with copies of its fonts and pictures")
        self.a_show_folder = A("Show in File &Manager", self.show_in_folder,
                               tip="Open the folder this design is saved in")
        self.a_template = A("Export as &Template…", self.save_as_template,
                            tip="Keep this design to start new ones from (New, My templates)")
        self.a_place = A("&Place Image…", self.place_image_dialog, "Ctrl+Shift+I", "image",
                         tip="Place a photo or picture")
        self.a_import = A("&Import…", self.import_dialog, "Ctrl+I", "open",
                          tip="Bring in a PDF, a Word document, an Affinity file or a picture")
        self.a_export = A("&Export…", self.export, ["Ctrl+Shift+E", "Ctrl+Alt+Shift+S"], "export",
                          tip="Export a PDF, PNG or JPEG")
        self.a_print_setup = A("Print Se&tup…", self.print_setup, None, None,
                               tip="Choose the paper size and which way round it goes")
        self.a_print_preview = A("Print Pre&view…", self.print_preview, None, None,
                                 tip="See how the page will come out of your printer")
        self.a_print = A("&Print…", self.print_document, "Ctrl+P", "print",
                         tip="Print on your own printer")
        self.a_fonts = A("Add &Fonts…", self.add_fonts, None, "text",
                         tip="Install fonts you downloaded (.ttf, .otf or a .zip)")
        self.a_get_fonts = A("Get Free Fonts Online…", self.get_free_fonts, None, None,
                             tip="Open Google Fonts in your web browser")
        self.a_setup = A("&Document Setup…", self.document_setup, ["Ctrl+Shift+P", "Ctrl+Alt+P"],
                         "cover")
        self.a_quit = A("&Quit", self.close, "Ctrl+Q")

        self.a_undo = A("&Undo", self.do_undo, "Ctrl+Z", "undo")
        self.a_redo = A("&Redo", self.do_redo, ["Ctrl+Shift+Z", "Ctrl+Y"], "redo")
        self.undo.canUndoChanged.connect(self.a_undo.setEnabled)
        self.undo.canRedoChanged.connect(self.a_redo.setEnabled)
        self.undo.undoTextChanged.connect(
            lambda t: self.a_undo.setText(f"&Undo {t}" if t else "&Undo"))
        self.undo.redoTextChanged.connect(
            lambda t: self.a_redo.setText(f"&Redo {t}" if t else "&Redo"))
        self.a_undo.setEnabled(False)
        self.a_redo.setEnabled(False)
        self.a_cut = A("Cu&t", self.cut, "Ctrl+X")
        self.a_copy = A("&Copy", self.copy, "Ctrl+C")
        self.a_paste = A("&Paste", self.paste, "Ctrl+V")
        self.a_paste_special = A("Paste &Special…", self.paste_special,
                                 tip="Choose how to paste what you copied")
        self.a_paste_style = A("Paste St&yle", self.paste_style, "Ctrl+Shift+V", "style",
                               tip="Give the selection the colours, outline, shadow and "
                                   "lettering of the object you copied")
        self.a_paste_fx = A("Paste &Effects", self.paste_effects,
                            tip="Give the selection the shadow of the object you copied")
        self.a_paste_inside = A("Paste &Inside", self.paste_inside, "Ctrl+Alt+V", "paste-inside",
                                tip="Put what you copied inside the selected shape or text, "
                                    "so it only shows there")
        self.a_paste_plain = A("Paste &Without Format", self.paste_plain, "Ctrl+Alt+Shift+V",
                               tip="Paste copied words as plain text")
        self.a_dup = A("&Duplicate", self.duplicate, "Ctrl+J")
        self.a_delete = A("De&lete", self.delete_selection, ["Delete", "Backspace"], "trash")
        self.a_defaults_set = A("&Use Selection as Default", self.defaults_from_selection,
                                tip="New shapes and text will look like the selected object")
        self.a_defaults_reset = A("&Reset Defaults", self.reset_saved_defaults,
                                  tip="New shapes and text go back to Folio's own look")
        self.a_create_style = A("Create St&yle…", self.create_style, None, "style",
                                tip="Save the look of the selected object in the Styles panel")
        self.a_settings = A("Se&ttings…", self.show_settings, "Ctrl+,")
        self.a_select_all = A("Select &All", self.select_all, "Ctrl+A")
        self.a_deselect = A("Deselect", self.deselect, "Ctrl+D")
        self.a_invert = A("&Invert Selection", self.invert_selection,
                          tip="Select everything that is not selected now")
        self.select_same_actions = [
            A(title, lambda k=key: self.select_same(k), tip=tip) for key, title, tip in (
                ("fill", "Same &Fill Colour", "Select everything filled with the same colour"),
                ("stroke", "Same &Outline Colour", "Select everything with the same outline colour"),
                ("font", "Same Fon&t", "Select all text in the same font"),
                ("kind", "Same &Kind of Object", "Select all text, all pictures, all shapes..."))]

        self.a_front = A("Bring to &Front", lambda: self.arrange("front"), "Ctrl+Shift+]", "front")
        self.a_forward = A("Bring &Forward", lambda: self.arrange("forward"), "Ctrl+]", "forward")
        self.a_backward = A("Send &Backward", lambda: self.arrange("backward"), "Ctrl+[", "backward")
        self.a_back = A("Send to Bac&k", lambda: self.arrange("back"), "Ctrl+Shift+[", "back")
        self.a_group = A("&Group", self.group_selection, "Ctrl+G", "group")
        self.a_ungroup = A("&Ungroup", self.ungroup_selection, "Ctrl+Shift+G", "ungroup")
        self.a_release = A("&Take Out of Shape", self.release_clip,
                           tip="Show the whole object again, not only inside its shape")
        self.a_lock = A("&Lock or Unlock", self.toggle_lock, "Ctrl+L", "lock")
        self.a_hide = A("&Hide", self.hide_selection, "Ctrl+H", "eye-off")
        self.a_show_all = A("Show &All", self.show_all, None, "eye")
        self.a_flip_h = A("Flip &Horizontal", lambda: self.flip(True), None, "flip-h")
        self.a_flip_v = A("Flip &Vertical", lambda: self.flip(False), None, "flip-v")
        self.a_rot_cw = A("Rotate 90° Clockwise", lambda: self.rotate_by(90), None, "rotate-cw")
        self.a_rot_ccw = A("Rotate 90° Anticlockwise", lambda: self.rotate_by(-90), None,
                           "rotate-ccw")

        self.align_actions = {}
        for key, title in (("left", "Align Left"), ("hcenter", "Align Centre"),
                           ("right", "Align Right"), ("top", "Align Top"),
                           ("vcenter", "Align Middle"), ("bottom", "Align Bottom")):
            self.align_actions[key] = A(title, lambda k=key: self.align(k), None, "align-" + key)
        self.a_dist_h = A("Space Evenly Across", lambda: self.distribute("h"), None, "dist-h")
        self.a_dist_v = A("Space Evenly Down", lambda: self.distribute("v"), None, "dist-v")

        self.a_spine = A("Add &Spine Text", self.add_spine_text, None, "spine")
        self.a_barcode = A("Show &Barcode Area", self.set_barcode, None, checkable=True)

        self.a_zoom_in = A("Zoom &In", lambda: self.view.zoom_by(1.25), ["Ctrl+=", "Ctrl++"])
        self.a_zoom_out = A("Zoom &Out", lambda: self.view.zoom_by(0.8), "Ctrl+-")
        self.a_fit = A("&Fit Page", self.view.fit_page, "Ctrl+0")
        self.a_actual = A("&Actual Pixels", lambda: self.view.set_zoom(1.0), "Ctrl+1")
        self.a_guides = A("Show &Guides", self.set_guides, "Ctrl+;", "guides", checkable=True)
        self.a_guides.setChecked(True)
        self.a_snap = A("&Snapping", self.set_snapping, None, "snap", checkable=True,
                        tip="Snap to guides and other objects")
        self.a_snap.setChecked(True)
        self.a_margins = A("Show &Margins", self.set_margins, checkable=True,
                           tip="Show the safe-area lines inside the trim")
        self.a_margins.blockSignals(True)
        self.a_margins.setChecked(True)
        self.a_margins.blockSignals(False)
        self.a_grid = A("Show G&rid", self.set_grid, "Ctrl+'", checkable=True,
                        tip="Show a grid on the page; things snap to it")
        self.a_rulers = A("Show &Rulers", self.set_rulers, "Ctrl+R", checkable=True,
                          tip="Rulers along the top and left; drag from them to make guides")
        self.a_lock_guides = A("&Lock Guides", lambda on: None, checkable=True,
                               tip="Stop guides from being moved by accident")
        self.a_clear_guides = A("Clear All Guides", self.clear_guides)
        self.a_show_context = A("Show &Context Toolbar", lambda on: self.context_bar.setVisible(on),
                                checkable=True)
        self.a_show_toolbar = A("Show &Toolbar", lambda on: self.main_bar.setVisible(on),
                                "Ctrl+Alt+T", checkable=True)
        self.a_show_tools = A("Show T&ools", self.set_tools_visible, checkable=True)
        for a in (self.a_show_context, self.a_show_toolbar, self.a_show_tools):
            a.blockSignals(True)
            a.setChecked(True)
            a.blockSignals(False)
        self.a_toggle_ui = QAction("Toggle UI", self)
        self.a_toggle_ui.setShortcut(QKeySequence("Tab"))
        self.a_toggle_ui.setShortcutContext(Qt.WidgetShortcut)
        self.a_toggle_ui.setToolTip("Hide or show the panels and toolbars (Tab on the page)")
        self.a_toggle_ui.triggered.connect(self.toggle_ui)
        self.view.addAction(self.a_toggle_ui)
        self.a_close = A("&Close", self.close_document, "Ctrl+W",
                         tip="Close this design and go back to the start window")
        self.a_close_all = A("Close All", self.close_document)
        self.a_preview = A("&Preview Trimmed", self.set_preview, "W", "preview", checkable=True,
                           tip="See the page as it will be printed and trimmed")

        self.a_zoom_sel = A("Zoom to &Selection", self.zoom_to_selection, None, "fit-selection",
                            tip="Zoom so the selection fills the window")
        self.a_fit.setIcon(icon("fit-page"))
        self.a_actual.setIcon(icon("actual-size"))
        self.a_snap_page = A("Snap to the Page, Cover and Guides", self.set_snap_options,
                             checkable=True)
        self.a_snap_objects = A("Snap to Other Objects", self.set_snap_options, checkable=True)
        self.a_snap_page.setChecked(True)
        self.a_snap_objects.setChecked(True)
        self.geo_actions = {}
        for key, title, tip in (
                ("add", "Add", "Join the selected shapes into one"),
                ("subtract", "Subtract", "Cut the top shapes out of the bottom one"),
                ("intersect", "Intersect", "Keep only where the shapes overlap"),
                ("xor", "Combine", "Join the shapes and cut out where they overlap"),
                ("divide", "Divide", "Cut the shapes into pieces where they overlap")):
            self.geo_actions[key] = A(title, lambda k=key: self.geometry(k), None, "geo-" + key,
                                      tip=tip)
        self.a_curves = A("Convert to &Curves", self.convert_to_curves, "Ctrl+Return", "node",
                          tip="Turn shapes and text into curves whose points you can edit")
        self.a_separate = A("Separate Curves", self.separate_curves,
                            tip="Split a curve made of several parts into separate curves")
        self.insert_actions = {}
        for key, title, tip in (
                ("behind", "Insert Behind Selection", "New objects go just behind the selection"),
                ("top", "Insert at Top", "New objects go on top of everything (the usual)"),
                ("inside", "Insert Inside Selection",
                 "New objects go inside the selected shape and only show there")):
            a = A(title, lambda k=key: self.set_insert_mode(k), None, "insert-" + key, tip=tip)
            a.setCheckable(True)
            self.insert_actions[key] = a
        self.insert_actions["top"].setChecked(True)
        self.a_settings.setIcon(icon("settings"))
        self.a_new_pixel_layer = A("New &Pixel Layer", self.new_pixel_layer, None, "persona-pixel",
                                   tip="Add an empty, see-through layer to paint on")
        self.a_px_deselect = A("Deselect Pixels", self.pixel_deselect, None, "px-rect",
                               tip="Clear the pixel selection")
        self.a_px_invert = A("Invert Pixel Selection", self.pixel_invert, None, "swap",
                             tip="Select every pixel that is not selected")
        self.a_px_fill = A("Fill Selection", self.pixel_fill, None, "px-fill",
                           tip="Fill the selected pixels with the fill colour")
        self.a_px_clear = A("Clear Selection", self.pixel_clear, None, "trash",
                            tip="Make the selected pixels see-through")
        self.a_shortcuts = A("&Keyboard Shortcuts", self.show_shortcuts, "F1", "help")
        self.a_about = A("&About Folio", self.show_about)

        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_actions = {}
        for name, title, key, hint in TOOLS:
            a = QAction(tool_icon(name), title, self)
            if key:
                a.setShortcut(QKeySequence(key))
            a.setCheckable(True)
            a.setToolTip(f"{title}" + (f"  ({key})" if key else "") + f"\n{hint}")
            a.triggered.connect(lambda _=False, n=name: self.set_tool(n))
            self.tool_group.addAction(a)
            self.addAction(a)
            self.tool_actions[name] = a

    def build_menus(self):
        mb = self.menuBar()
        m = mb.addMenu("&File")
        personas = m.addMenu("&Personas")
        for key, _, _ in PERSONAS:
            personas.addAction(self.persona_actions[key])
        m.addSeparator()
        for a in (self.a_new, self.a_new_clip, self.a_new_last, self.a_open):
            m.addAction(a)
        self.recent_menu = m.addMenu("Open &Recent")
        self.recent_menu.aboutToShow.connect(self.fill_recent)
        m.addSeparator()
        m.addAction(self.a_close)
        m.addAction(self.a_close_all)
        m.addSeparator()
        for a in (self.a_save, self.a_save_as, self.a_package):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_show_folder)
        m.addSeparator()
        m.addAction(self.a_import)
        m.addAction(self.a_place)
        m.addAction(self.a_fonts)
        m.addAction(self.a_get_fonts)
        m.addAction(self.a_export)
        m.addAction(self.a_template)
        m.addSeparator()
        m.addAction(self.a_print_setup)
        m.addAction(self.a_print_preview)
        m.addAction(self.a_print)
        m.addSeparator()
        m.addAction(self.a_setup)
        m.addSeparator()
        m.addAction(self.a_quit)

        m = mb.addMenu("&Edit")
        for a in (self.a_undo, self.a_redo):
            m.addAction(a)
        m.addSeparator()
        for a in (self.a_cut, self.a_copy, self.a_paste, self.a_paste_special,
                  self.a_paste_style, self.a_paste_fx, self.a_paste_inside, self.a_paste_plain,
                  self.a_dup, self.a_delete):
            m.addAction(a)
        m.addSeparator()
        defaults = m.addMenu("De&faults")
        defaults.addAction(self.a_defaults_set)
        defaults.addAction(self.a_defaults_reset)
        m.addAction(self.a_create_style)
        m.addSeparator()
        m.addAction(self.a_settings)

        m = mb.addMenu("&Arrange")
        for a in (self.a_front, self.a_forward, self.a_backward, self.a_back):
            m.addAction(a)
        m.addSeparator()
        for a in (self.a_group, self.a_ungroup, self.a_release):
            m.addAction(a)
        m.addSeparator()
        geo = m.addMenu("&Geometry")
        for a in self.geo_actions.values():
            geo.addAction(a)
        geo.addSeparator()
        geo.addAction(self.a_separate)
        m.addAction(self.a_curves)
        m.addSeparator()
        m.addAction(self.a_new_pixel_layer)
        insert = m.addMenu("&Insert New Objects")
        for a in self.insert_actions.values():
            insert.addAction(a)
        m.addSeparator()
        for a in (self.a_flip_h, self.a_flip_v, self.a_rot_cw, self.a_rot_ccw):
            m.addAction(a)
        m.addSeparator()
        for a in (self.a_lock, self.a_hide, self.a_show_all):
            m.addAction(a)

        m = mb.addMenu("A&lign")
        for key in ("left", "hcenter", "right"):
            m.addAction(self.align_actions[key])
        m.addSeparator()
        for key in ("top", "vcenter", "bottom"):
            m.addAction(self.align_actions[key])
        m.addSeparator()
        m.addAction(self.a_dist_h)
        m.addAction(self.a_dist_v)

        m = mb.addMenu("&Select")
        for a in (self.a_select_all, self.a_deselect, self.a_invert):
            m.addAction(a)
        m.addSeparator()
        same = m.addMenu("Select Sa&me")
        for a in self.select_same_actions:
            same.addAction(a)

        m = mb.addMenu("&Cover")
        m.addAction(self.a_setup)
        m.addAction(self.a_spine)
        m.addAction(self.a_barcode)

        m = mb.addMenu("&View")
        zoom = m.addMenu("&Zoom")
        for a in (self.a_zoom_in, self.a_zoom_out, self.a_fit, self.a_zoom_sel, self.a_actual):
            zoom.addAction(a)
        m.addSeparator()
        for a in (self.a_margins, self.a_guides, self.a_grid, self.a_rulers, self.a_lock_guides):
            m.addAction(a)
        m.addAction(self.a_clear_guides)
        m.addSeparator()
        snapping = m.addMenu("&Snapping")
        for a in (self.a_snap, self.a_snap_page, self.a_snap_objects):
            snapping.addAction(a)
        m.addAction(self.a_preview)
        m.addSeparator()
        for a in (self.a_show_context, self.a_show_toolbar, self.a_show_tools):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_toggle_ui)
        m = mb.addMenu("&Window")
        studio = m.addMenu("&Studio")
        for dock in self.docks():
            studio.addAction(dock.toggleViewAction())
        m.addSeparator()
        for dock in self.docks():
            m.addAction(dock.toggleViewAction())

        m = mb.addMenu("&Help")
        m.addAction(self.a_shortcuts)
        m.addAction(self.a_about)

    def build_toolbars(self):
        """The top bar and the tools down the left, laid out like the pro
        design apps: groups of buttons with space between them. Each persona
        (Designer, Pixel, Export) shows its own tools and buttons."""
        tb = QToolBar("Main", self)
        tb.setObjectName("toolbar_main")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        self.main_bar = tb
        self.bar_groups = {"all": [], "draw": [], "design": [], "pixel": []}

        def button(action, group):
            b = QToolButton()
            b.setDefaultAction(action)
            b.setAutoRaise(True)
            b.setIconSize(QSize(20, 20))
            self.bar_groups[group].append(tb.addWidget(b))
            return b

        def gap(group, width=18):
            w = QWidget()
            w.setFixedWidth(width)
            self.bar_groups[group].append(tb.addWidget(w))

        self.persona_actions = {}
        persona_group = QActionGroup(self)
        for key, title, tip in PERSONAS:
            a = QAction(app_icon() if key == "design" else icon("persona-" + key), title, self)
            a.setCheckable(True)
            a.setToolTip(f"{title}\n{tip}")
            a.triggered.connect(lambda _=False, k=key: self.set_persona(k))
            persona_group.addAction(a)
            self.persona_actions[key] = a
            button(a, "all")
        self.persona_actions["design"].setChecked(True)
        gap("all", 30)
        for a in (self.a_setup, self.a_settings):
            button(a, "all")
        gap("all")
        for a in (self.a_fit, self.a_zoom_sel, self.a_actual, self.a_preview):
            button(a, "all")
        gap("all")
        for a in (self.a_back, self.a_backward, self.a_forward, self.a_front):
            button(a, "all")
        gap("draw")
        for a in (self.a_flip_h, self.a_flip_v, self.a_rot_ccw, self.a_rot_cw):
            button(a, "draw")
        gap("all")
        self.bar_groups["all"].append(tb.addWidget(self.build_align_button()))
        gap("draw")
        button(self.a_guides, "draw")
        snap = QToolButton()
        snap.setDefaultAction(self.a_snap)
        snap.setAutoRaise(True)
        snap_menu = QMenu(snap)
        snap_menu.addAction(self.a_snap_page)
        snap_menu.addAction(self.a_snap_objects)
        snap.setMenu(snap_menu)
        snap.setPopupMode(QToolButton.MenuButtonPopup)
        self.bar_groups["draw"].append(tb.addWidget(snap))
        gap("design")
        for a in self.geo_actions.values():
            button(a, "design")
        gap("design")
        for a in self.insert_actions.values():
            button(a, "design")
        gap("pixel")
        for a in (self.a_new_pixel_layer, self.a_px_deselect, self.a_px_invert,
                  self.a_px_fill, self.a_px_clear):
            button(a, "pixel")
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        tb.addAction(self.a_shortcuts)
        self.addToolBar(Qt.TopToolBarArea, tb)
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.context_bar = ContextBar(self)
        self.addToolBar(Qt.TopToolBarArea, self.context_bar)

        self.tool_buttons = []
        self.tool_colours = []
        self.tool_bars = {}
        for persona, entries in PERSONA_TOOLS.items():
            tools = QToolBar("Tools", self)
            tools.setObjectName("toolbar_tools" if persona == "design" else f"toolbar_tools_{persona}")
            tools.setMovable(False)
            tools.setOrientation(Qt.Vertical)
            tools.setIconSize(QSize(20, 20))
            for entry in entries:
                if entry == "-":
                    tools.addSeparator()
                elif entry == "place":
                    b = QToolButton()
                    b.setDefaultAction(self.a_place)
                    b.setAutoRaise(True)
                    b.setIconSize(QSize(20, 20))
                    tools.addWidget(b)
                else:
                    b = ToolButton(self, entry)
                    self.tool_buttons.append(b)
                    tools.addWidget(b)
            if persona != "export":
                filler = QWidget()
                filler.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
                tools.addWidget(filler)
                colours = FillStrokeSelector(scale=0.8)
                colours.targetChanged.connect(self.set_colour_target)
                colours.swapClicked.connect(self.swap_fill_stroke)
                colours.noneClicked.connect(self.clear_colour)
                tools.addWidget(colours)
                self.tool_colours.append(colours)
            self.addToolBar(Qt.LeftToolBarArea, tools)
            tools.setVisible(persona == "design")
            self.tool_bars[persona] = tools
        self.fill_align_targets()
        self.show_bar_groups("design")
        designer = {n for e in PERSONA_TOOLS["design"] if isinstance(e, list) for n in e}
        for name, a in self.tool_actions.items():
            a.setEnabled(name in designer)

    def show_bar_groups(self, persona):
        visible = {"all": True, "draw": persona != "export", "design": persona == "design",
                   "pixel": persona == "pixel"}
        for group, actions in self.bar_groups.items():
            for a in actions:
                a.setVisible(visible[group])

    def set_persona(self, persona):
        """Switch between Designer, Pixel and Export, as in pro design apps."""
        if persona == self.persona:
            self.persona_actions[persona].setChecked(True)
            return
        self.stop_text_editing()
        self.end_colour_pick()
        self.persona = persona
        self.persona_actions[persona].setChecked(True)
        names = {n for entry in PERSONA_TOOLS[persona] if isinstance(entry, list) for n in entry}
        for name, a in self.tool_actions.items():
            a.setEnabled(name in names)
        for key, bar in self.tool_bars.items():
            bar.setVisible(key == persona)
        self.show_bar_groups(persona)
        wanted = self.persona_docks(persona)
        for dock in self.docks():
            dock.setVisible(dock in wanted)
        for dock in ((self.dock_export, self.dock_layers, self.dock_transform) if persona == "export"
                     else (self.dock_colour, self.dock_layers, self.dock_transform)):
            dock.raise_()
        if persona == "pixel":
            self.dock_brushes.raise_()
        if persona == "export" and self.current_slice() is None and self.scene.slices:
            self.chosen_slice = self.scene.slices[0]["id"]
        self.set_tool(PERSONA_DEFAULT_TOOL[persona])
        self.refresh_slices()
        self.schedule_refresh()
        self.view.viewport().update()
        titles = {k: t for k, t, _ in PERSONAS}
        self.statusBar().showMessage(titles[persona], 3000)

    def build_align_button(self):
        """One button that opens all the align and spacing choices."""
        button = QToolButton()
        button.setIcon(icon("align-hcenter"))
        button.setToolTip("Align and space evenly")
        button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(button)
        panel = QWidget()
        grid = QGridLayout(panel)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setSpacing(4)
        head = QLabel("Align to")
        head.setObjectName("hint")
        grid.addWidget(head, 0, 0, 1, 2)
        self.align_to = QComboBox()
        self.align_to.setToolTip("What the Align buttons line things up with")
        grid.addWidget(self.align_to, 0, 2, 1, 4)
        for col, key in enumerate(("left", "hcenter", "right", "top", "vcenter", "bottom")):
            b = QToolButton()
            b.setDefaultAction(self.align_actions[key])
            b.setIconSize(QSize(22, 22))
            grid.addWidget(b, 1, col)
        spacing = QLabel("Space evenly")
        spacing.setObjectName("hint")
        grid.addWidget(spacing, 2, 0, 1, 3)
        for col, a in enumerate((self.a_dist_h, self.a_dist_v)):
            b = QToolButton()
            b.setDefaultAction(a)
            b.setIconSize(QSize(22, 22))
            grid.addWidget(b, 2, 4 + col)
        holder = QWidgetAction(menu)
        holder.setDefaultWidget(panel)
        menu.addAction(holder)
        button.setMenu(menu)
        return button

    def set_snap_options(self, _on=None):
        self.view.snap_page = self.a_snap_page.isChecked()
        self.view.snap_objects = self.a_snap_objects.isChecked()

    def fill_align_targets(self):
        current = self.align_to.currentData()
        self.align_to.blockSignals(True)
        self.align_to.clear()
        self.align_to.addItem("Selection", "selection")
        self.align_to.addItem("Page", "trim")
        if self.scene.doc.kind == "cover":
            self.align_to.addItem("Front cover", "front")
            self.align_to.addItem("Spine", "spine")
            self.align_to.addItem("Back cover", "back")
        idx = self.align_to.findData(current)
        self.align_to.setCurrentIndex(max(0, idx))
        self.align_to.blockSignals(False)

    def build_status(self):
        sb = self.statusBar()
        self.status_hint = QLabel()
        self.status_hint.setMinimumWidth(200)
        self.status_pos = QLabel()
        self.status_doc = QLabel()
        self.status_zoom = QLabel()
        sb.addWidget(self.status_hint, 1)
        sb.addPermanentWidget(self.status_pos)
        sb.addPermanentWidget(self.status_doc)
        sb.addPermanentWidget(self.status_zoom)
        self.view.zoomChanged.connect(lambda z: self.status_zoom.setText(f"{z * 100:.0f}%"))
        self.view.cursorMoved.connect(self.on_cursor)

    def on_cursor(self, p):
        doc = self.scene.doc
        u = doc.unit
        dec = units.decimals(u)
        x = units.from_px(p.x(), u, doc.dpi)
        y = units.from_px(p.y(), u, doc.dpi)
        self.status_pos.setText(f"{x:.{dec}f}, {y:.{dec}f} {u}")
        if self.ruler_h.isVisible():
            self.ruler_h.show_cursor(p)
            self.ruler_v.show_cursor(p)

    # ---- scene wiring ---------------------------------------------------------

    def connect_scene(self):
        self.scene.selectionChanged.connect(self.schedule_refresh)
        self.scene.contentChanged.connect(self.schedule_layers)
        self.scene.docChanged.connect(self.on_doc_changed)
        self.on_doc_changed()

    def set_scene(self, scene):
        self.stop_text_editing()
        old = self.scene
        self.scene = scene
        self.view.setScene(scene)
        self.connect_scene()
        self.undo.clear()
        old.deleteLater()
        self.paste_count = 0
        self.pixel_selection = None
        self.chosen_slice = scene.slices[0]["id"] if scene.slices else None
        self.reset_defaults()
        self.schedule_refresh()
        self.schedule_layers()
        QTimer.singleShot(0, self.view.fit_page)
        self.update_title()
        self.navigator.schedule()

    def on_doc_changed(self):
        self.status_doc.setText(self.scene.doc.describe())
        self.a_barcode.blockSignals(True)
        self.a_barcode.setChecked(self.scene.doc.barcode)
        self.a_barcode.blockSignals(False)
        cover = self.scene.doc.kind == "cover"
        self.a_spine.setEnabled(cover)
        self.a_barcode.setEnabled(cover)
        if hasattr(self, "align_to"):
            self.fill_align_targets()
        self.view.viewport().update()

    def reset_defaults(self):
        doc = self.scene.doc
        self.text_defaults = dict(DEFAULT_TEXT_STYLE)
        self.text_defaults["size"] = float(max(8, round(doc.trim_height / 18)))
        if "Playfair Display" in fonts.bundled_families():
            self.text_defaults["family"] = "Playfair Display"
        self.text_defaults.update(self.saved_defaults.get("text", {}))
        self.line_stroke = {"color": "#ff1a1a1a", "width": units.pt_to_px(2, doc.dpi),
                            "dash": "solid"}

    def schedule_refresh(self):
        self._refresh_timer.start(0)

    def schedule_layers(self):
        self._layers_timer.start(0)

    def refresh_panels(self):
        self.props.refresh()
        self.textp.refresh()
        self.transform.refresh()
        self.colourp.refresh()
        self.swatches.refresh()
        self.strokep.refresh()
        self.context_bar.refresh()
        self.update_action_states()
        fill, stroke, no_fill, no_stroke = self.colour_state()
        for colours in self.tool_colours:
            colours.set_state(fill, stroke, no_fill, no_stroke)
            colours.set_target(self.colour_target)
        if self.persona == "export":
            self.export_options.refresh()
        self.layers.sync_selection()
        # Show the Text panel when text is picked, and Colour again after it,
        # but only when the kind of selection changes, so a tab the user chose stays.
        sel = self.scene.selected_folio()
        kinds = {isinstance(i, TextItem) for i in sel}
        kind = "text" if kinds == {True} else "other" if kinds == {False} else None
        if kind and kind != self._last_kind:
            if kind == "text":
                self.dock_text.raise_()
            elif self._last_kind == "text":
                self.dock_colour.raise_()
        if kind:
            self._last_kind = kind
        self.view.viewport().update()

    def update_action_states(self):
        """Grey out what needs a selection, as pro design apps do."""
        sel = self.scene.selected_folio()
        n = len(sel)
        for a in (self.a_front, self.a_forward, self.a_backward, self.a_back,
                  self.a_flip_h, self.a_flip_v, self.a_rot_cw, self.a_rot_ccw,
                  self.a_cut, self.a_copy, self.a_dup, self.a_delete, self.a_lock,
                  self.a_hide, self.a_zoom_sel, self.a_paste_style, self.a_paste_fx,
                  self.a_paste_inside, self.a_create_style, self.a_defaults_set,
                  self.a_invert, self.a_deselect, *self.select_same_actions,
                  *self.align_actions.values()):
            a.setEnabled(n > 0)
        self.a_group.setEnabled(n > 1)
        self.a_ungroup.setEnabled(any(i.group for i in sel))
        self.a_release.setEnabled(any(i.clip for i in sel) or any(
            i.clip in {s.uid for s in sel} for i in self.scene.folio_items()))
        self.a_curves.setEnabled(any(isinstance(i, (RectItem, EllipseItem, TextItem))
                                     for i in sel))
        self.a_separate.setEnabled(any(isinstance(i, PathItem) and i.extra for i in sel))
        for a in self.geo_actions.values():
            a.setEnabled(sum(not isinstance(i, ImageItem) for i in sel) > 1)
        for a in (self.a_dist_h, self.a_dist_v):
            a.setEnabled(n > 2)

    def rebuild_layers(self):
        self.layers.rebuild()

    def after_change(self):
        self.schedule_refresh()
        self.schedule_layers()
        self.update_title()
        self.view.viewport().update()
        self.navigator.schedule()

    # ---- undo -----------------------------------------------------------------

    def selected_uids(self):
        return [i.uid for i in self.scene.selected_folio()]

    def begin_change(self):
        if self._depth == 0:
            self._before = self.scene.snapshot()
            self._sel_before = self.selected_uids()
        self._depth += 1

    def end_change(self, label, merge=None):
        if self._depth == 0:
            return
        self._depth -= 1
        if self._depth > 0:
            return
        before, self._before = self._before, None
        after = self.scene.snapshot()
        if before != after:
            self.undo.push(SnapshotCommand(self, before, after, self._sel_before,
                                           self.selected_uids(), label, merge))
        self.after_change()

    def cancel_change(self):
        if self._depth > 0:
            self._depth -= 1
        if self._depth == 0:
            self._before = None

    @contextmanager
    def change(self, label, merge=None):
        self.begin_change()
        try:
            yield
        finally:
            self.end_change(label, merge)

    def restore_snapshot(self, snap, selected):
        self.scene.restore(snap, selected)
        self.after_change()

    def do_undo(self):
        if self.view.editing_text is not None:
            self.stop_text_editing()
        self.undo.undo()

    def do_redo(self):
        if self.view.editing_text is not None:
            self.stop_text_editing()
        self.undo.redo()

    # ---- tools and text editing -------------------------------------------------

    def set_tool(self, name):
        tool = self.tools[name]
        if self.view.tool is tool:
            self.tool_actions[name].setChecked(True)
            return
        self.stop_text_editing()
        if self.view.tool is not None:
            self.view.tool.deactivate()
        self.tool_name = name
        self.view.tool = tool
        tool.activate()
        self.tool_actions[name].setChecked(True)
        for b in getattr(self, "tool_buttons", []):
            if name in b.names and b.current != name:
                b.current = name
                b.show_current()
            b.setChecked(name in b.names)
        if hasattr(self, "context_bar"):
            self.context_bar.refresh()
        self.view.update_cursor()
        self.view.viewport().update()
        hint = next(h for n, _, _, h in TOOLS if n == name)
        self.status_hint.setText(hint)

    def start_text_editing(self, item, scene_pos, new=False):
        if self.view.editing_text is item:
            return
        self.stop_text_editing()
        if not new:
            self.begin_change()
        self.view.editing_text = item
        self.scene.select_only([item])
        item.start_editing(scene_pos)
        self.view.setFocus(Qt.OtherFocusReason)
        self.dock_text.raise_()
        self.status_hint.setText("Typing. Press Esc or click outside the text when you are done.")
        self.view.viewport().update()

    def stop_text_editing(self, select=False):
        item = self.view.editing_text
        if item is None:
            return
        self.view.editing_text = None
        item.stop_editing()
        if not item.toPlainText().strip():
            self.scene.remove_folio_items([item])
            select = False
        self.end_change("Edit text")
        if select:
            self.scene.select_only([item])
        if self.tool_name == "text":
            self.set_tool("move")
        else:
            hint = next(h for n, _, _, h in TOOLS if n == self.tool_name)
            self.status_hint.setText(hint)
        self.view.viewport().update()

    # ---- making objects ---------------------------------------------------------

    def insert_new(self, item):
        """Add a new object where the insert buttons say: on top (the usual),
        just behind the selection, or inside the selected shape."""
        chosen = [i for i in self.scene.selected_folio() if i is not item]
        self.scene.add_folio_item(item)
        if not chosen or self.insert_mode == "top":
            return item
        order = [i for i in self.scene.folio_items() if i is not item]
        if self.insert_mode == "behind":
            at = order.index(chosen[0])
            self.scene.set_order(order[:at] + [item] + order[at:])
            return item
        owners = [i for i in chosen if not i.clip and not isinstance(i, ImageItem)]
        if not owners:
            return item
        owner = owners[-1]
        children = [i for i in order if i.clip == owner.uid]
        after = order.index(children[-1] if children else owner) + 1
        self.scene.set_order(order[:after] + [item] + order[after:])
        item.clip = owner.uid
        if not owner.group:
            owner.group = self.scene.new_group("Shape with contents")
        item.group = owner.group
        self.scene.prune_groups()
        return item

    def set_insert_mode(self, mode):
        self.insert_mode = mode
        for key, a in self.insert_actions.items():
            a.setChecked(key == mode)

    def create_shape(self, kind, rect):
        with self.change("Add " + shapes.NAMES.get(kind, "shape").lower()):
            if kind in shapes.CURVE_SHAPES:
                item = PathItem()
                item.set_nodes_from_scene(shapes.scene_nodes(kind, rect), True)
                item.name = shapes.NAMES[kind]
            else:
                item = EllipseItem() if kind == "ellipse" else RectItem()
                item.set_size(rect.width(), rect.height())
                item.setPos(rect.topLeft())
                if kind == "rounded":
                    item.radius = shapes.rounded_radius(rect.width(), rect.height())
            item.fill = dict(self.style_fill)
            item.stroke = dict(self.style_stroke)
            self.insert_new(item)
            self.scene.select_only([item])
        self.set_tool("move")

    def create_path(self, nodes, closed=False, line=False, switch=True):
        with self.change("Add line" if line else "Add curve"):
            item = PathItem()
            item.set_nodes_from_scene(nodes, closed)
            if closed:
                item.fill = dict(self.style_fill)
                item.stroke = dict(self.style_stroke)
            else:
                item.fill = {**self.style_fill, "type": "none"}
                item.stroke = dict(self.line_stroke)
            self.insert_new(item)
            self.scene.select_only([item])
        if switch:
            self.set_tool("move")

    def create_text(self, pos, frame_width=None, centre_on_click=False, text=""):
        self.stop_text_editing()
        self.begin_change()
        item = TextItem()
        item.style = dict(self.text_defaults)
        item.fill = {**item.fill, "type": "solid", "color": self.text_color}
        item.frame_width = frame_width
        if text:
            item.setPlainText(text)
        item.apply_style()
        if centre_on_click:
            pos = QPointF(pos.x() - item.w * item.anchor_fraction(), pos.y() - item.h / 2)
        item.setPos(pos)
        self.insert_new(item)
        if text:
            self.scene.select_only([item])
            self.end_change("Add text")
            return item
        self.start_text_editing(item, None, new=True)
        return item

    def remember_style(self, item):
        if isinstance(item, TextItem):
            self.text_color = item.fill.get("color", self.text_color)
        elif isinstance(item, PathItem) and not item.closed:
            self.line_stroke = dict(item.stroke)
        elif isinstance(item, (RectItem, EllipseItem, PathItem)):
            self.style_fill = dict(item.fill)
            self.style_stroke = dict(item.stroke)

    # ---- images -----------------------------------------------------------------

    def place_image_dialog(self):
        start = self.settings.value("image_dir", os.path.expanduser("~/Pictures"))
        paths, _ = QFileDialog.getOpenFileNames(self, "Place image", start,
                                                IMAGE_FILTER + ";;All files (*)")
        if paths:
            self.settings.setValue("image_dir", os.path.dirname(paths[0]))
            self.place_image_files(paths)

    def read_image_file(self, path):
        """Return (bytes, ext) Qt can draw, converting unusual formats."""
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        with open(path, "rb") as fh:
            data = fh.read()
        vector = ext in ("svg", "svgz")
        if not vector and QImageReader.imageFormat(path):
            return data, ext
        convert = shutil.which("convert")
        if convert is None:
            if vector:
                reader = QImageReader(path)
                size = reader.size()
                if size.isValid():
                    reader.setScaledSize(size * 4)
                image = reader.read()
                if not image.isNull():
                    return self._png_bytes(image), "png"
            raise ValueError("This kind of image cannot be opened.")
        args = [convert]
        if vector:
            args += ["-density", "300", "-background", "none"]
        args += [path + "[0]", "png:-"]
        out = subprocess.run(args, capture_output=True, timeout=120)
        if out.returncode != 0 or not out.stdout:
            raise ValueError("This image could not be converted.")
        return out.stdout, "png"

    @staticmethod
    def _png_bytes(image):
        from PyQt5.QtCore import QBuffer, QIODevice
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        image.save(buf, "PNG")
        buf.close()
        return bytes(ba)

    # ---- fonts ------------------------------------------------------------------

    def add_fonts(self):
        """Install font files (or a .zip of them) for this user, ready at once."""
        start = self.settings.value("font_dir", os.path.expanduser("~/Downloads"))
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add fonts", start,
            "Fonts or zip files (*.ttf *.otf *.ttc *.TTF *.OTF *.zip);;All files (*)")
        if not paths:
            return
        self.settings.setValue("font_dir", os.path.dirname(paths[0]))
        names = self.install_fonts(paths)
        if names:
            QMessageBox.information(self, "Fonts added",
                                    "These fonts are ready to use:\n\n" + "\n".join(names))
        else:
            QMessageBox.warning(self, "No fonts added",
                                "No font files were found. Font files end in .ttf or .otf.")

    def get_free_fonts(self):
        """Open Google Fonts; downloaded zips can then go in with Add Fonts."""
        QDesktopServices.openUrl(QUrl("https://fonts.google.com/"))
        self.statusBar().showMessage(
            "Download a font family there, then use Add Fonts and pick the .zip file.", 12000)

    def install_fonts(self, paths, folder=None):
        folder = folder or os.path.expanduser("~/.local/share/fonts")
        os.makedirs(folder, exist_ok=True)
        files = []
        for path in paths:
            if path.lower().endswith(".zip"):
                try:
                    with zipfile.ZipFile(path) as z:
                        for name in z.namelist():
                            base = os.path.basename(name)
                            if base and base.lower().endswith(FONT_EXTS) and not base.startswith("."):
                                dest = os.path.join(folder, base)
                                with z.open(name) as src, open(dest, "wb") as out:
                                    shutil.copyfileobj(src, out)
                                files.append(dest)
                except (zipfile.BadZipFile, OSError):
                    continue
            elif path.lower().endswith(FONT_EXTS):
                dest = os.path.join(folder, os.path.basename(path))
                if os.path.abspath(path) != os.path.abspath(dest):
                    shutil.copy2(path, dest)
                files.append(dest)
        families = []
        for f in files:
            fid = QFontDatabase.addApplicationFont(f)
            if fid >= 0:
                families.extend(QFontDatabase.applicationFontFamilies(fid))
        try:
            subprocess.Popen(["fc-cache", "-f", folder], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except OSError:
            pass
        self.textp.reload_fonts()
        return sorted(set(families))

    def place_image_files(self, paths, at=None):
        added = []
        problems = []
        self.stop_text_editing()
        with self.change("Place image"):
            for path in paths:
                try:
                    data, ext = self.read_image_file(path)
                except (OSError, ValueError, subprocess.SubprocessError) as exc:
                    problems.append(f"{os.path.basename(path)}: {exc}")
                    continue
                aid = self.scene.assets.add(data, ext, os.path.basename(path))
                if not self.scene.assets.is_valid_image(aid):
                    problems.append(f"{os.path.basename(path)}: not a picture Folio can read.")
                    continue
                added.append(self.add_image_item(aid, at))
                if at is not None:
                    at = at + QPointF(self.scene.doc.dpi * 0.15, self.scene.doc.dpi * 0.15)
            if added:
                self.scene.select_only(added)
        if added:
            self.set_tool("move")
        if problems:
            QMessageBox.warning(self, "Some images were not placed", "\n".join(problems))

    def add_image_item(self, aid, at=None):
        item = ImageItem(self.scene.assets, aid)
        trim = self.scene.doc.trim_rect()
        limit_w, limit_h = trim.width() * 0.9, trim.height() * 0.9
        if item.w > limit_w or item.h > limit_h:
            s = min(limit_w / item.w, limit_h / item.h)
            item.set_size(item.w * s, item.h * s)
        if at is None:
            at = self.visible_centre()
        item.setPos(at - QPointF(item.w / 2, item.h / 2))
        self.insert_new(item)
        return item

    def visible_centre(self):
        c = self.view.mapToScene(self.view.viewport().rect().center())
        page = self.scene.doc.page_rect()
        if not page.contains(c):
            c = page.center()
        return c

    def place_qimage(self, image, at=None, name="pasted image"):
        if image.isNull():
            return
        with self.change("Paste image"):
            aid = self.scene.assets.add_qimage(image, name)
            item = self.add_image_item(aid, at)
            self.scene.select_only([item])
        self.set_tool("move")

    def handle_drop(self, mime, at):
        paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
        docs = [p for p in paths if p.lower().endswith(".folio")]
        if docs:
            self.open_path(docs[0])
            return
        special = [p for p in paths if self._ext(p) in ("pdf",) + OFFICE_EXTS + AFFINITY_EXTS]
        for p in special:
            self.import_path(p, at)
        pictures = [p for p in paths if p not in special]
        if pictures:
            self.place_image_files(pictures, at)
        elif mime.hasImage():
            self.place_qimage(QImage(mime.imageData()), at)

    # ---- importing PDF, Word and Affinity files ------------------------------------

    @staticmethod
    def _ext(path):
        return os.path.splitext(path)[1].lower().lstrip(".")

    def import_dialog(self):
        start = self.settings.value("import_dir", os.path.expanduser("~/Documents"))
        paths, _ = QFileDialog.getOpenFileNames(self, "Import", start, IMPORT_FILTER + ";;All files (*)")
        if not paths:
            return
        self.settings.setValue("import_dir", os.path.dirname(paths[0]))
        for path in paths:
            self.import_path(path)

    def import_path(self, path, at=None, new_document=False):
        ext = self._ext(path)
        try:
            if ext == "pdf":
                self.import_pdf(path, at, new_document)
            elif ext in OFFICE_EXTS:
                self.import_word(path, at)
            elif ext in AFFINITY_EXTS:
                self.import_affinity(path, at)
            else:
                self.place_image_files([path], at)
        except importers.ImportProblem as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Could not import", f"{os.path.basename(path)}\n\n{exc}")

    def _busy(self, text):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.statusBar().showMessage(text)
        QApplication.processEvents()

    def _done(self, text=""):
        QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(text, 6000)

    def import_pdf(self, path, at=None, new_document=False, pages=None):
        """PDF pages as pictures: here, or as a new document of the page's size."""
        self.stop_text_editing()
        name = os.path.basename(path)
        info = importers.pdf_info(path)
        if pages is None:
            dlg = PdfImportDialog(self, name, info["pages"], new_document)
            if not dlg.exec_():
                return
            choice = dlg.choice()
        else:
            choice = {"new_document": new_document, "pages": pages, "transparent": not new_document}
        if choice["new_document"]:
            page = choice["pages"][0]
            size = importers.pdf_info(path, page)
            from .document import page_settings
            self.path = None
            self.set_scene(DocScene(page_settings(size["width_pt"] / 72.0, size["height_pt"] / 72.0,
                                                  "in", 300.0)))
        dpi = min(600, max(150, int(self.scene.doc.dpi)))
        self._busy(f"Bringing in {name}…")
        made = []
        try:
            with self.change("Import PDF"):
                for n in choice["pages"]:
                    if n > info["pages"]:
                        break
                    png = importers.render_pdf_page(path, n, dpi, choice["transparent"])
                    aid = self.scene.assets.add(png, "png", f"{name} page {n}")
                    item = ImageItem(self.scene.assets, aid)
                    size = importers.pdf_info(path, n)
                    item.set_size(size["width_pt"] / 72.0 * self.scene.doc.dpi,
                                  size["height_pt"] / 72.0 * self.scene.doc.dpi)
                    item.name = f"{name}, page {n}"
                    if choice["new_document"]:
                        item.setPos(self.scene.doc.trim_rect().topLeft())
                        self.scene.add_folio_item(item)
                    else:
                        self._fit_and_place(item, at, len(made))
                    made.append(item)
                self.scene.select_only(made)
        finally:
            self._done(f"Brought in {len(made)} page{'s' if len(made) != 1 else ''} from {name}.")
        self.set_tool("move")
        if choice["new_document"]:
            self.view.fit_page()

    def _fit_and_place(self, item, at, index):
        """Real size when it fits on the page, otherwise shrunk to fit."""
        doc = self.scene.doc
        page, trim = doc.page_rect(), doc.trim_rect()
        if item.w > page.width() + 0.5 or item.h > page.height() + 0.5:
            s = min(trim.width() * 0.95 / item.w, trim.height() * 0.95 / item.h)
            item.set_size(item.w * s, item.h * s)
        centre = at if at is not None else self.visible_centre()
        if at is None and doc.kind == "cover":
            # A page the size of the book is a front cover: put it there.
            front = doc.regions()["front"]
            near = 0.2 * doc.dpi
            if abs(item.w - front.width()) < near and abs(item.h - front.height()) < near:
                centre = front.center()
        step = doc.dpi * 0.2 * index
        item.setPos(centre - QPointF(item.w / 2, item.h / 2) + QPointF(step, step))
        self.scene.add_folio_item(item)

    def import_word(self, path, at=None):
        self.stop_text_editing()
        name = os.path.basename(path)
        source = path
        if self._ext(path) != "docx":
            self._busy(f"Opening {name} with LibreOffice…")
            try:
                pdf = importers.office_to_pdf(path)
            finally:
                self._done()
            self.import_pdf(pdf, at)
            return
        paragraphs, title, pictures = importers.docx_contents(source)
        words = sum(len(p.split()) for p in paragraphs) + (len(title.split()) if title else 0)
        dlg = WordImportDialog(self, name, words, len(pictures))
        if not dlg.exec_():
            return
        choice = dlg.choice()
        if choice["as_pages"]:
            self._busy(f"Laying out {name} with LibreOffice…")
            try:
                pdf = importers.office_to_pdf(path)
            finally:
                self._done()
            self.import_pdf(pdf, at, pages=choice["pages"])
            return
        self.place_word_text(name, paragraphs, title, pictures, at)

    def place_word_text(self, name, paragraphs, title, pictures, at=None):
        """The document's words as a text box (and title), its pictures beside it."""
        doc = self.scene.doc
        safe = doc.safe_rects()[-1] if doc.safe_rects() else doc.trim_rect()
        if doc.kind == "cover":
            safe = doc.safe_rects()[0]          # the back cover
        body = "\n".join(paragraphs)
        cut = len(body) > 20000
        if cut:
            body = body[:20000].rsplit(" ", 1)[0] + " …"
        made = []
        with self.change("Import Word document"):
            top = safe.top()
            if title:
                t = TextItem()
                t.style = dict(self.text_defaults)
                t.style.update(size=units.pt_to_px(28, doc.dpi), bold=True)
                t.fill = {**t.fill, "type": "solid", "color": self.text_color}
                t.frame_width = safe.width()
                t.setPlainText(title)
                t.apply_style()
                t.setPos(safe.left(), top)
                self.scene.add_folio_item(t)
                made.append(t)
                top += t.h + units.pt_to_px(10, doc.dpi)
            if body.strip():
                t = TextItem()
                t.style = dict(self.text_defaults)
                t.style.update(size=units.pt_to_px(12, doc.dpi), bold=False, line=120.0)
                t.fill = {**t.fill, "type": "solid", "color": self.text_color}
                t.frame_width = safe.width()
                t.setPlainText(body)
                t.apply_style()
                t.setPos(safe.left(), top)
                self.scene.add_folio_item(t)
                made.append(t)
            for i, (blob, ext, pic_name) in enumerate(pictures):
                aid = self.scene.assets.add(blob, ext, pic_name)
                if not self.scene.assets.is_valid_image(aid):
                    continue
                item = ImageItem(self.scene.assets, aid)
                self._fit_and_place(item, at, i)
                made.append(item)
            self.scene.select_only(made)
        self.set_tool("move")
        msg = f"Brought in the text from {name}."
        if cut:
            msg = (f"{name} is long, so only its first part came in as text. "
                   "Use Import again and pick pages as pictures for the rest.")
            QMessageBox.information(self, "Long document", msg)
        self.statusBar().showMessage(msg, 8000)

    def import_affinity(self, path, at=None):
        """Affinity's own format is private; only its saved preview can be read."""
        self.stop_text_editing()
        name = os.path.basename(path)
        png = importers.affinity_preview(path)
        with self.change("Import Affinity preview"):
            aid = self.scene.assets.add(png, "png", f"{name} (preview)")
            item = ImageItem(self.scene.assets, aid)
            item.name = f"{name} (preview only)"
            self._fit_and_place(item, at, 0)
            self.scene.select_only([item])
        self.set_tool("move")
        size = self.scene.assets.size(aid)
        QMessageBox.information(
            self, "Affinity file",
            f"Folio brought in the small preview picture saved inside {name} "
            f"({size.width()} x {size.height()} pixels). Use it as a guide to trace over.\n\n"
            "Affinity keeps the real design in a private format that no other program can read. "
            "For full quality, open the file in Affinity, choose File, Export, PDF, "
            "then import that PDF here.")

    def size_images_to(self, target, cover=True):
        images = [i for i in self.scene.selected_folio()
                  if isinstance(i, ImageItem) and not i.locked]
        if not images:
            return
        area = self.bleed_area(target or "page")
        with self.change("Fill area" if cover else "Fit area"):
            for item in images:
                size = item.pixel_size()
                w0, h0 = float(size.width()), float(size.height())
                s = (max if cover else min)(area.width() / w0, area.height() / h0)
                item.setRotation(0)
                item.set_size(w0 * s, h0 * s)
                item.set_center_scene(area.center())

    def bleed_area(self, key):
        """An area grown into the bleed on the sides that get trimmed off,
        so a photo filling it leaves no white edge after printing."""
        doc = self.scene.doc
        regs = doc.regions()
        r = QRectF(regs.get(key, regs["page"]))
        b = doc.bleed
        grow = {"front": (0, -b, b, b), "back": (-b, -b, 0, b), "spine": (0, -b, 0, b),
                "trim": (-b, -b, b, b)}.get(key)
        return r.adjusted(*grow) if grow else r

    # ---- clipboard --------------------------------------------------------------

    def payload(self, items, with_data=True):
        data = {"items": [i.to_dict() for i in items], "groups": {}, "assets": {},
                "dpi": self.scene.doc.dpi}
        for item in items:
            if item.group:
                data["groups"][item.group] = self.scene.groups.get(item.group, "Group")
            if isinstance(item, ImageItem) and with_data and self.scene.assets.has(item.aid):
                a = self.scene.assets
                data["assets"][item.aid] = {"ext": a.ext[item.aid],
                                            "name": a.names.get(item.aid, ""),
                                            "data": base64.b64encode(a.bytes_of(item.aid)).decode()}
        return data

    def copy(self):
        items = self.scene.selected_folio()
        if not items:
            return
        md = QMimeData()
        md.setData(MIME, QByteArray(json.dumps(self.payload(items)).encode("utf-8")))
        texts = [i.toPlainText() for i in items if isinstance(i, TextItem)]
        if texts:
            md.setText("\n".join(texts))
        QGuiApplication.clipboard().setMimeData(md)
        self.paste_count = 0

    def cut(self):
        items = [i for i in self.scene.selected_folio() if not i.locked]
        if not items:
            return
        self.copy()
        with self.change("Cut"):
            self.scene.remove_folio_items(items)

    def paste(self):
        self.stop_text_editing()
        md = QGuiApplication.clipboard().mimeData()
        if md is None:
            return
        if md.hasFormat(MIME):
            try:
                payload = json.loads(bytes(md.data(MIME)).decode("utf-8"))
            except ValueError:
                return
            self.paste_count += 1
            self.paste_payload(payload, "Paste")
        elif md.hasImage():
            self.place_qimage(QImage(md.imageData()))
        elif md.hasUrls() and any(u.isLocalFile() for u in md.urls()):
            self.place_image_files([u.toLocalFile() for u in md.urls() if u.isLocalFile()])
        elif md.hasText() and md.text().strip():
            c = self.visible_centre()
            item = self.create_text(c, None, text=md.text().strip())
            item.set_center_scene(c)

    def paste_payload(self, payload, label, offset=None):
        for aid, info in payload.get("assets", {}).items():
            if not self.scene.assets.has(aid) and "data" in info:
                self.scene.assets.add(base64.b64decode(info["data"]), info.get("ext", "png"),
                                      info.get("name", ""), aid)
        existing = {i.uid: i for i in self.scene.folio_items()}
        if offset is None:
            same_place = any(d.get("uid") in existing
                             and abs(existing[d["uid"]].pos().x() - d.get("x", 0)) < 0.5
                             and abs(existing[d["uid"]].pos().y() - d.get("y", 0)) < 0.5
                             for d in payload["items"])
            step = self.scene.doc.dpi * 0.1
            n = self.paste_count if same_place else 0
            offset = QPointF(step * n, step * n)
        gid_map = {}
        uid_map = {d.get("uid"): new_uid() for d in payload["items"]}
        made = []
        with self.change(label):
            for d in payload["items"]:
                d = dict(d)
                d["uid"] = uid_map[d.get("uid")]
                if d.get("clip") in uid_map:
                    d["clip"] = uid_map[d["clip"]]    # copied together: stays inside the copy
                if d.get("group"):
                    old = d["group"]
                    if old not in gid_map:
                        gid_map[old] = self.scene.new_group(payload.get("groups", {}).get(old, "Group"))
                    d["group"] = gid_map[old]
                d["x"] = d.get("x", 0) + offset.x()
                d["y"] = d.get("y", 0) + offset.y()
                item = item_from_dict(d, self.scene.assets)
                if item is not None:
                    self.scene.add_folio_item(item)
                    made.append(item)
            self.scene.select_only(made)
        return made

    def duplicate(self):
        self.stop_text_editing()
        items = self.scene.selected_folio()
        if not items:
            return
        step = self.scene.doc.dpi * 0.1
        self.paste_payload(self.payload(items, with_data=False), "Duplicate",
                           QPointF(step, step))

    def delete_selection(self):
        if self.persona == "pixel" and self.pixel_selection is not None:
            self.pixel_clear()
            return
        if self.view.editing_text is not None:
            return
        items = [i for i in self.scene.selected_folio() if not i.locked]
        if not items:
            return
        with self.change("Delete"):
            self.scene.remove_folio_items(items)

    def select_all(self):
        if self.persona == "pixel":
            path = QPainterPath()
            path.addRect(self.scene.doc.page_rect())
            self.set_pixel_selection(path)
            return
        if self.view.editing_text is not None:
            return
        self.scene.select_only([i for i in self.scene.folio_items()
                                if i.isVisible() and not i.locked])

    def deselect(self):
        if self.persona == "pixel" and self.pixel_selection is not None:
            self.pixel_deselect()
            return
        self.stop_text_editing()
        self.scene.select_only([])

    def nudge(self, dx, dy):
        items = [i for i in self.scene.selected_folio() if not i.locked]
        if not items:
            return
        with self.change("Nudge", merge="nudge"):
            for item in items:
                item.moveBy(dx, dy)

    # ---- arrange, group, align ----------------------------------------------------

    def units_in_order(self):
        out = []
        for item in self.scene.folio_items():
            if item.group and out and out[-1][0].group == item.group:
                out[-1].append(item)
            else:
                out.append([item])
        return out

    def arrange(self, how):
        self.stop_text_editing()
        chosen = set(self.scene.selected_folio())
        if not chosen:
            return
        units_ = self.units_in_order()
        picked = [any(i in chosen for i in u) for u in units_]
        if how == "front":
            order = [u for u, p in zip(units_, picked) if not p] + [u for u, p in zip(units_, picked) if p]
        elif how == "back":
            order = [u for u, p in zip(units_, picked) if p] + [u for u, p in zip(units_, picked) if not p]
        else:
            pairs = list(zip(units_, picked))
            if how == "forward":
                for i in range(len(pairs) - 2, -1, -1):
                    if pairs[i][1] and not pairs[i + 1][1]:
                        pairs[i], pairs[i + 1] = pairs[i + 1], pairs[i]
            else:
                for i in range(1, len(pairs)):
                    if pairs[i][1] and not pairs[i - 1][1]:
                        pairs[i], pairs[i - 1] = pairs[i - 1], pairs[i]
            order = [u for u, _ in pairs]
        label = {"front": "Bring to front", "back": "Send to back",
                 "forward": "Bring forward", "backward": "Send backward"}[how]
        with self.change(label):
            self.scene.set_order([i for u in order for i in u])

    def group_selection(self):
        self.stop_text_editing()
        items = self.scene.selected_folio()
        if len(items) < 2:
            self.statusBar().showMessage("Select two or more things to group them.", 4000)
            return
        with self.change("Group"):
            gid = self.scene.new_group(f"Group {len(self.scene.groups) + 1}")
            for item in items:
                item.group = gid
            order = self.scene.folio_items()
            top = max(order.index(i) for i in items)
            rest = [i for i in order if i not in items]
            below = sum(1 for i in rest if order.index(i) < top)
            self.scene.set_order(rest[:below] + items + rest[below:])
            self.scene.prune_groups()
            self.scene.select_only(items)

    def ungroup_selection(self):
        items = [i for i in self.scene.selected_folio() if i.group]
        if not items:
            return
        with self.change("Ungroup"):
            for item in items:
                item.group = None
            self.scene.prune_groups()

    def selection_units(self, items):
        groups = {}
        out = []
        for item in items:
            if item.group:
                if item.group not in groups:
                    groups[item.group] = []
                    out.append(groups[item.group])
                groups[item.group].append(item)
            else:
                out.append([item])
        return out

    def align(self, how):
        self.stop_text_editing()
        items = [i for i in self.scene.selected_folio() if not i.locked]
        if not items:
            return
        units_ = self.selection_units(items)
        key = self.align_to.currentData() or "selection"
        if key == "selection" and len(units_) < 2:
            key = "trim"
        if key == "selection":
            target = self.scene.items_rect(items)
        else:
            target = self.scene.doc.regions().get(key, self.scene.doc.trim_rect())
        with self.change("Align"):
            for unit in units_:
                r = self.scene.items_rect(unit)
                dx = dy = 0.0
                if how == "left":
                    dx = target.left() - r.left()
                elif how == "hcenter":
                    dx = target.center().x() - r.center().x()
                elif how == "right":
                    dx = target.right() - r.right()
                elif how == "top":
                    dy = target.top() - r.top()
                elif how == "vcenter":
                    dy = target.center().y() - r.center().y()
                elif how == "bottom":
                    dy = target.bottom() - r.bottom()
                for item in unit:
                    item.moveBy(dx, dy)

    def distribute(self, axis):
        items = [i for i in self.scene.selected_folio() if not i.locked]
        units_ = self.selection_units(items)
        if len(units_) < 3:
            self.statusBar().showMessage("Select three or more things to space them evenly.", 4000)
            return
        rects = [(u, self.scene.items_rect(u)) for u in units_]
        if axis == "h":
            rects.sort(key=lambda t: t[1].center().x())
            span = rects[-1][1].right() - rects[0][1].left()
            gap = (span - sum(r.width() for _, r in rects)) / (len(rects) - 1)
        else:
            rects.sort(key=lambda t: t[1].center().y())
            span = rects[-1][1].bottom() - rects[0][1].top()
            gap = (span - sum(r.height() for _, r in rects)) / (len(rects) - 1)
        with self.change("Space evenly"):
            pos = rects[0][1].left() if axis == "h" else rects[0][1].top()
            for unit, r in rects:
                if axis == "h":
                    d = pos - r.left()
                    pos += r.width() + gap
                    for item in unit:
                        item.moveBy(d, 0)
                else:
                    d = pos - r.top()
                    pos += r.height() + gap
                    for item in unit:
                        item.moveBy(0, d)

    def flip(self, horizontal):
        items = [i for i in self.scene.selected_folio() if not i.locked]
        if not items:
            return
        centre = self.scene.items_rect(items).center()
        with self.change("Flip"):
            for item in items:
                c = item.center_scene()
                if horizontal:
                    item.set_flip(horizontal=not item.flip_h)
                    new_c = QPointF(2 * centre.x() - c.x(), c.y())
                else:
                    item.set_flip(vertical=not item.flip_v)
                    new_c = QPointF(c.x(), 2 * centre.y() - c.y())
                item.setRotation(-item.rotation())
                item.set_center_scene(new_c)

    def rotate_by(self, degrees):
        items = [i for i in self.scene.selected_folio() if not i.locked]
        if not items:
            return
        centre = self.scene.items_rect(items).center()
        a = math.radians(degrees)
        with self.change("Rotate"):
            for item in items:
                c = item.center_scene() - centre
                new_c = centre + QPointF(c.x() * math.cos(a) - c.y() * math.sin(a),
                                         c.x() * math.sin(a) + c.y() * math.cos(a))
                r = (item.rotation() + degrees) % 360
                item.setRotation(r - 360 if r > 180 else r)
                item.set_center_scene(new_c)

    def toggle_lock(self):
        items = self.scene.selected_folio()
        if not items:
            return
        lock = not all(i.locked for i in items)
        with self.change("Lock" if lock else "Unlock"):
            for item in items:
                item.locked = lock

    def hide_selection(self):
        items = self.scene.selected_folio()
        if not items:
            return
        with self.change("Hide"):
            for item in items:
                item.setVisible(False)
                item.setSelected(False)

    def show_all(self):
        hidden = [i for i in self.scene.folio_items() if not i.isVisible()]
        if not hidden:
            return
        with self.change("Show all"):
            for item in hidden:
                item.setVisible(True)

    # ---- covers -----------------------------------------------------------------

    def add_spine_text(self):
        doc = self.scene.doc
        if doc.kind != "cover":
            return
        if doc.pages < units.SPINE_TEXT_MIN_PAGES:
            answer = QMessageBox.question(
                self, "Spine text",
                f"Amazon KDP only allows spine text on books with "
                f"{units.SPINE_TEXT_MIN_PAGES} or more pages. This book has {doc.pages}.\n\n"
                "Add spine text anyway?")
            if answer != QMessageBox.Yes:
                return
        self.stop_text_editing()
        spine = doc.regions()["spine"]
        usable = max(spine.width() - 2 * doc.spine_margin_in * doc.dpi, spine.width() * 0.5)
        with self.change("Add spine text"):
            item = TextItem()
            style = dict(self.text_defaults)
            style["size"] = float(max(6, round(usable * 0.62)))
            style["align"] = "center"
            item.style = style
            item.fill = {**item.fill, "type": "solid", "color": self.text_color}
            item.setPlainText(f"{doc.title or 'BOOK TITLE'}     AUTHOR NAME")
            item.apply_style()
            item.setRotation(90)
            self.scene.add_folio_item(item)
            item.set_center_scene(spine.center())
            self.scene.select_only([item])
        self.dock_text.raise_()

    def set_barcode(self, on):
        if self.scene.doc.kind != "cover":
            return
        new = type(self.scene.doc).from_dict(self.scene.doc.to_dict())
        new.barcode = bool(on)
        with self.change("Barcode area"):
            self.scene.set_settings(new)

    def document_setup(self):
        self.stop_text_editing()
        dlg = NewDocumentDialog(self, current=self.scene.doc)
        if not dlg.exec_():
            return
        new = dlg.settings()
        old = self.scene.doc
        if new == old:
            return
        with self.change("Document setup"):
            self.refit_objects(old, new, dlg.objects_mode(), *dlg.anchor_point())
            self.scene.set_settings(new)
        self.view.fit_page()

    def refit_objects(self, old, new, mode, fx=0.0, fy=0.0):
        """Move (or resize) the objects for a new page: keep them with their
        cover parts, stretch them to the new size, or hold them to one point."""
        items = self.scene.folio_items()
        k = new.dpi / old.dpi
        if abs(k - 1.0) > 1e-9:
            # same real size at a different resolution
            for item in items:
                pos = item.pos()
                item.scale_content(k)
                item.setPos(pos * k)
            for s in self.scene.slices:
                if s.get("rect"):
                    s["rect"] = [v * k for v in s["rect"]]

        def scaled(r):
            return QRectF(r.left() * k, r.top() * k, r.width() * k, r.height() * k)
        o = {key: scaled(r) for key, r in old.regions().items()}
        n = new.regions()
        if mode == "rescale":
            sx = n["trim"].width() / max(o["trim"].width(), 1e-9)
            sy = n["trim"].height() / max(o["trim"].height(), 1e-9)
            for item in items:
                c = item.center_scene()
                if isinstance(item, TextItem):
                    item.scale_content(min(sx, sy))
                else:
                    item.resize_content(item.w * sx, item.h * sy)
                item.set_center_scene(QPointF(n["trim"].left() + (c.x() - o["trim"].left()) * sx,
                                              n["trim"].top() + (c.y() - o["trim"].top()) * sy))
            return
        if mode == "keep" and old.kind == "cover" and new.kind == "cover":
            dy = n["trim"].top() - o["trim"].top()
            for item in items:
                x = item.center_scene().x()
                if x >= o["spine"].right():
                    dx = n["front"].left() - o["front"].left()
                elif x >= o["spine"].left():
                    dx = n["spine"].center().x() - o["spine"].center().x()
                else:
                    dx = n["back"].left() - o["back"].left()
                item.moveBy(dx, dy)
            return
        dx = n["trim"].left() - o["trim"].left() + (n["trim"].width() - o["trim"].width()) * fx
        dy = n["trim"].top() - o["trim"].top() + (n["trim"].height() - o["trim"].height()) * fy
        for item in items:
            item.moveBy(dx, dy)

    def shift_for_settings(self, old, new):
        self.refit_objects(old, new, "keep" if old.kind == "cover" else "anchor")

    # ---- view toggles ---------------------------------------------------------

    def set_margins(self, on):
        self.view.show_margins = bool(on)
        self.view.viewport().update()

    def set_grid(self, on):
        self.view.show_grid = bool(on)
        self.view.viewport().update()

    def set_rulers(self, on):
        for w in (self.ruler_h, self.ruler_v, self.ruler_corner):
            w.setVisible(bool(on))
        self.settings.setValue("rulers", bool(on))

    def set_tools_visible(self, on):
        self.tool_bars[self.persona].setVisible(bool(on))

    def guides_locked(self):
        return self.a_lock_guides.isChecked()

    def guide_at(self, sp):
        """The guide under a page point, as (axis, index), or None."""
        if not self.view.show_guides or self.guides_locked() or self.view.preview:
            return None
        tol = self.view.tol(4)
        for axis, value in (("x", sp.x()), ("y", sp.y())):
            for i, g in enumerate(self.scene.guides.get(axis, [])):
                if abs(g - value) <= tol:
                    return axis, i
        return None

    def add_guide(self, axis, value):
        with self.change("Add guide"):
            self.scene.guides.setdefault(axis, []).append(float(value))
        self.view.viewport().update()

    def clear_guides(self):
        if not any(self.scene.guides.values()):
            return
        with self.change("Clear guides"):
            self.scene.guides = {"x": [], "y": []}
        self.view.viewport().update()

    def toggle_ui(self):
        """Hide the panels and toolbars to see just the page (Tab), and back."""
        hidden = getattr(self, "_ui_hidden", None)
        if hidden is None:
            showing = [w for w in (*self.docks(), self.main_bar, self.context_bar,
                                   self.tool_bars[self.persona]) if w.isVisible()]
            for w in showing:
                w.hide()
            self._ui_hidden = showing
        else:
            for w in hidden:
                w.show()
            self._ui_hidden = None

    def close_document(self):
        """Close the design (asking to save) and show the start window."""
        self.stop_text_editing()
        if not self.maybe_save():
            return
        self.path = None
        self.set_scene(DocScene(cover_settings()))
        self.undo.setClean()
        self.new_document(first_run=True)

    def set_guides(self, on):
        self.view.show_guides = bool(on)
        self.view.viewport().update()

    def set_snapping(self, on):
        self.view.snap_enabled = bool(on)

    def set_preview(self, on):
        self.view.preview = bool(on)
        self.view.viewport().update()

    # ---- files ------------------------------------------------------------------

    def display_name(self):
        return os.path.basename(self.path) if self.path else "Untitled"

    def update_title(self):
        try:
            dirty = "" if self.undo.isClean() else " *"
        except RuntimeError:   # the window is closing
            return
        self.setWindowTitle(f"{self.display_name()}{dirty} — Folio")

    def maybe_save(self):
        if self.undo.isClean():
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Save changes?")
        box.setText(f"Do you want to save the changes to {self.display_name()}?")
        box.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        box.setDefaultButton(QMessageBox.Save)
        answer = box.exec_()
        if answer == QMessageBox.Save:
            return self.save()
        return answer == QMessageBox.Discard

    def new_document(self, first_run=False):
        self.stop_text_editing()
        if not first_run and not self.maybe_save():
            return
        recent = [p for p in self.settings.value("recent", [], type=list) if os.path.exists(p)]
        dlg = NewDocumentDialog(self, templates=self.list_templates(), recent=recent,
                                show_on_start=self.settings.value("show_start", True, type=bool))
        accepted = dlg.exec_()
        self.settings.setValue("show_start", dlg.show_start.isChecked())
        if dlg.wants_open:
            self.open_document(skip_check=True)
            return
        if not accepted:
            return
        if dlg.recent_path():
            self.open_path(dlg.recent_path(), checked=True)
            return
        if dlg.template_path():
            self.start_from_template(dlg.template_path())
            return
        settings = dlg.settings()
        self.settings.setValue("last_preset", json.dumps(settings.to_dict()))
        self.path = None
        self.set_scene(DocScene(settings))

    # ---- more ways to start (like Affinity's File menu) ----------------------------

    def clipboard_payload(self):
        md = QGuiApplication.clipboard().mimeData()
        if md is None or not md.hasFormat(MIME):
            return None
        try:
            return json.loads(bytes(md.data(MIME)).decode("utf-8"))
        except ValueError:
            return None

    def new_from_clipboard(self):
        self.stop_text_editing()
        md = QGuiApplication.clipboard().mimeData()
        payload = self.clipboard_payload()
        image = None
        if payload is None and md is not None and md.hasImage():
            image = QImage(md.imageData())
        if payload is None and (image is None or image.isNull()):
            self.statusBar().showMessage(
                "Copy a picture or some objects first, then choose New from Clipboard.", 6000)
            return
        if not self.maybe_save():
            return
        dpi = self.scene.doc.dpi
        self.path = None
        if payload is None:
            bg = "" if image.hasAlphaChannel() else "#ffffffff"
            self.set_scene(DocScene(page_settings(image.width(), image.height(), "px", 300.0,
                                                  background=bg)))
            aid = self.scene.assets.add_qimage(image, "pasted image")
            self.scene.add_folio_item(ImageItem(self.scene.assets, aid))
        else:
            self.set_scene(DocScene(page_settings(100, 100, "px", dpi)))
            made = self.paste_payload(payload, "Paste", offset=QPointF(0, 0))
            r = self.scene.items_rect(made)
            self.scene.set_settings(page_settings(max(1, math.ceil(r.width())),
                                                  max(1, math.ceil(r.height())), "px", dpi))
            for item in made:
                item.moveBy(-r.left(), -r.top())
        self.undo.clear()
        self.undo.resetClean()
        self.update_title()
        QTimer.singleShot(0, self.view.fit_page)

    def new_from_last_preset(self):
        try:
            settings = DocSettings.from_dict(json.loads(self.settings.value("last_preset", "")))
        except (ValueError, TypeError):
            self.new_document()
            return
        self.stop_text_editing()
        if not self.maybe_save():
            return
        self.path = None
        self.set_scene(DocScene(settings))
        self.statusBar().showMessage("New document: " + settings.describe(), 6000)

    def list_templates(self):
        folder = templates_dir()
        return sorted((os.path.join(folder, n) for n in os.listdir(folder)
                       if n.endswith(".folio")), key=str.lower)

    def start_from_template(self, path):
        try:
            snap, assets = fileio.load_document(path)
        except (OSError, fileio.FolioFileError) as exc:
            QMessageBox.warning(self, "Could not open the template", str(exc))
            return
        scene = DocScene(DocSettings.from_dict(snap["doc"]))
        for aid, (blob, ext, name) in assets.items():
            scene.assets.add(blob, ext, name, aid)
        scene.restore(snap)
        self.path = None
        self.set_scene(scene)
        self.undo.resetClean()
        self.update_title()

    def save_as_template(self):
        self.stop_text_editing()
        name, ok = QInputDialog.getText(self, "Export as Template", "Template name:",
                                        text=os.path.splitext(self.display_name())[0])
        name = name.strip()
        if not ok or not name:
            return
        path = os.path.join(templates_dir(), safe_filename(name) + ".folio")
        if os.path.exists(path) and QMessageBox.question(
                self, "Replace template",
                f"A template called {name} already exists. Replace it?") != QMessageBox.Yes:
            return
        try:
            fileio.save_document(self.scene, path, exporter.thumbnail_png(self.scene))
        except OSError as exc:
            QMessageBox.warning(self, "Could not save the template", str(exc))
            return
        self.statusBar().showMessage("Template saved. Find it under File, New, My templates.", 8000)

    def save_as_package(self):
        """A folder holding the design plus copies of its fonts and pictures."""
        self.stop_text_editing()
        base = safe_filename(os.path.splitext(self.display_name())[0])
        start = os.path.join(self.settings.value("doc_dir", os.path.expanduser("~/Documents")),
                             base + " package")
        folder, _ = QFileDialog.getSaveFileName(self, "Save As Package (makes a folder)", start)
        if not folder:
            return
        families = sorted({i.style["family"] for i in self.scene.folio_items()
                           if isinstance(i, TextItem)})
        missing = []
        try:
            os.makedirs(folder, exist_ok=True)
            for family in families:
                files = fonts.font_files(family)
                if not files:
                    missing.append(family)
                    continue
                dest = os.path.join(folder, "Fonts", safe_filename(family))
                os.makedirs(dest, exist_ok=True)
                for f in files:
                    shutil.copy2(f, dest)
            a = self.scene.assets
            done = set()
            for item in self.scene.folio_items():
                if isinstance(item, ImageItem) and a.has(item.aid) and item.aid not in done:
                    done.add(item.aid)
                    os.makedirs(os.path.join(folder, "Images"), exist_ok=True)
                    stem = safe_filename(os.path.splitext(a.names.get(item.aid) or "picture")[0])
                    name = f"{stem}-{item.aid[:6]}.{a.ext[item.aid]}"
                    with open(os.path.join(folder, "Images", name), "wb") as fh:
                        fh.write(a.bytes_of(item.aid))
            fileio.save_document(self.scene, os.path.join(folder, base + ".folio"),
                                 exporter.thumbnail_png(self.scene))
            lines = ["Fonts used in this design:"] + [
                f"  {f}" + ("  (not found on this computer)" if f in missing else "")
                for f in families]
            with open(os.path.join(folder, "Fonts used.txt"), "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
        except OSError as exc:
            QMessageBox.warning(self, "Could not save the package", str(exc))
            return
        self.statusBar().showMessage(f"Package saved in {folder}", 8000)

    def show_in_folder(self):
        if not self.path:
            self.statusBar().showMessage("Save the design first.", 5000)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self.path)))

    # ---- more ways to paste (like Affinity's Edit menu) ------------------------------

    def paste_special(self):
        self.stop_text_editing()
        md = QGuiApplication.clipboard().mimeData()
        if md is None:
            return
        has_sel = bool(self.scene.selected_folio())
        options = []
        if md.hasFormat(MIME):
            options.append(("Folio objects, as they were", self.paste))
            if has_sel:
                options.append(("Only their style, onto the selection", self.paste_style))
        if md.hasImage():
            image = QImage(md.imageData())
            options.append(("Picture", lambda: self.place_qimage(image)))
        if has_sel and (md.hasFormat(MIME) or md.hasImage()):
            options.append(("Inside the selected shape or text", self.paste_inside))
        if md.hasText() and md.text().strip():
            options.append(("Plain text, in a new text box", self.paste_plain))
        if not options:
            self.statusBar().showMessage("There is nothing to paste.", 5000)
            return
        choice, ok = QInputDialog.getItem(self, "Paste Special", "Paste as:",
                                          [t for t, _ in options], 0, False)
        if ok:
            dict(options)[choice]()

    def _paste_look(self, parts, label):
        payload = self.clipboard_payload()
        items = [i for i in self.scene.selected_folio() if not i.locked]
        if not payload or not payload.get("items") or not items:
            self.statusBar().showMessage(
                "Copy an object, select others, then paste its look onto them.", 6000)
            return
        dpi = self.scene.doc.dpi
        look = styles.style_from_dict(payload["items"][0], float(payload.get("dpi", dpi)),
                                      parts=parts)
        with self.change(label):
            for item in items:
                styles.apply_style(item, look, dpi)
                refresh_item(item)

    def paste_style(self):
        self._paste_look(("fill", "stroke", "shadow", "opacity", "text"), "Paste style")

    def paste_effects(self):
        self._paste_look(("shadow",), "Paste effects")

    def paste_inside(self):
        """Put the clipboard inside the selected shape or text: it only shows there."""
        self.stop_text_editing()
        sel = [i for i in self.scene.selected_folio() if not i.clip]
        if not sel:
            self.statusBar().showMessage("Select the shape or text to paste into first.", 6000)
            return
        owner = sel[-1]
        md = QGuiApplication.clipboard().mimeData()
        payload = self.clipboard_payload()
        if payload is None and (md is None or not md.hasImage()):
            self.statusBar().showMessage("Copy a picture or an object first.", 6000)
            return
        box = owner.scene_bounds()
        with self.change("Paste inside"):
            if payload is not None:
                made = self.paste_payload(payload, "Paste inside", offset=QPointF(0, 0))
                r = self.scene.items_rect(made)
                if not r.intersects(box):
                    d = box.center() - r.center()
                    for i in made:
                        i.moveBy(d.x(), d.y())
            else:
                aid = self.scene.assets.add_qimage(QImage(md.imageData()), "pasted image")
                item = ImageItem(self.scene.assets, aid)
                s = max(box.width() / item.w, box.height() / item.h)
                item.set_size(item.w * s, item.h * s)
                item.set_center_scene(box.center())
                self.scene.add_folio_item(item)
                made = [item]
            gid = owner.group or self.scene.new_group("Shape with picture")
            owner.group = gid
            order = [i for i in self.scene.folio_items() if i not in made]
            at = order.index(owner) + 1
            self.scene.set_order(order[:at] + made + order[at:])
            for i in made:
                i.clip = owner.uid
                i.group = gid
                i.changed()
            self.scene.prune_groups()
            self.scene.select_only(self.scene.group_members(gid))
        self.set_tool("move")

    def release_clip(self):
        sel = self.scene.selected_folio()
        uids = {i.uid for i in sel}
        targets = [i for i in self.scene.folio_items() if i.clip and (i in sel or i.clip in uids)]
        if not targets:
            self.statusBar().showMessage("Nothing selected is inside a shape.", 5000)
            return
        with self.change("Take out of shape"):
            for i in targets:
                i.clip = None
                i.changed()

    # ---- combining shapes (Geometry) and turning things into curves --------------

    @staticmethod
    def area_of(item):
        """The area an object covers, in page coordinates."""
        return item.sceneTransform().map(item.clip_area())

    def _as_curve(self, path, source, uid=None):
        item = path_item_from_scene_path(path.simplified() if path.elementCount() else path)
        if item is None:
            return None
        item.fill = dict(source.fill) if source.has_fill else {**item.fill, "type": "solid",
                                                                  "color": "#ff808080"}
        if item.fill.get("type") == "none" and isinstance(source, TextItem):
            item.fill["type"] = "solid"
        item.stroke = {k: v for k, v in source.stroke.items()}
        item.shadow = dict(source.shadow)
        item.setOpacity(source.opacity())
        item.group = source.group
        item.clip = source.clip
        if uid:
            item.uid = uid
        return item

    def geometry(self, how):
        """Add, Subtract, Intersect, Combine (xor) or Divide the selected shapes."""
        self.stop_text_editing()
        items = [i for i in self.scene.selected_folio()
                 if not i.locked and not isinstance(i, ImageItem)]
        if len(items) < 2:
            self.statusBar().showMessage("Select two or more shapes or words first.", 5000)
            return
        areas = [self.area_of(i) for i in items]       # bottom to top
        results = []                                    # (path, look from, uid)
        if how == "add":
            path = areas[0]
            for a in areas[1:]:
                path = path.united(a)
            results = [(path, items[0], items[0].uid)]
        elif how == "subtract":
            path = areas[0]
            for a in areas[1:]:
                path = path.subtracted(a)
            results = [(path, items[0], items[0].uid)]
        elif how == "intersect":
            path = areas[0]
            for a in areas[1:]:
                path = path.intersected(a)
            results = [(path, items[0], items[0].uid)]
        elif how == "xor":
            path = areas[0]
            for a in areas[1:]:
                path = path.united(a).subtracted(path.intersected(a))
            results = [(path, items[0], items[0].uid)]
        else:   # divide: every overlap becomes its own piece, coloured like the top one
            pieces = [(areas[0], items[0])]
            for a, item in zip(areas[1:], items[1:]):
                cut = []
                rest = a
                for q, src in pieces:
                    both = q.intersected(a)
                    alone = q.subtracted(a)
                    if not both.isEmpty():
                        cut.append((both, item))
                    if not alone.isEmpty():
                        cut.append((alone, src))
                    rest = rest.subtracted(q)
                if not rest.isEmpty():
                    cut.append((rest, item))
                pieces = cut
            results = [(q, src, None) for q, src in pieces]
        made = []
        with self.change({"add": "Add shapes", "subtract": "Subtract shapes",
                          "intersect": "Intersect shapes", "xor": "Combine shapes",
                          "divide": "Divide shapes"}[how]):
            order = self.scene.folio_items()
            at = max(order.index(i) for i in items)
            for path, src, uid in results:
                if path.isEmpty():
                    continue
                item = self._as_curve(path, src, uid)
                if item is not None:
                    item.clip = None
                    made.append(item)
            below = [i for i in order[:at + 1] if i not in items]
            above = [i for i in order[at + 1:] if i not in items]
            self.scene.remove_folio_items(items)
            for item in made:
                self.scene.addItem(item)
            self.scene.set_order(below + made + above)
            self.scene.prune_groups()
            self.scene.select_only(made)
        if not made:
            self.statusBar().showMessage("Nothing was left after that.", 5000)

    def convert_to_curves(self):
        """Turn shapes and text into curves whose points can be edited."""
        self.stop_text_editing()
        items = [i for i in self.scene.selected_folio()
                 if not i.locked and isinstance(i, (RectItem, EllipseItem, TextItem))]
        if not items:
            self.statusBar().showMessage("Select a shape or some text to turn into curves.", 5000)
            return
        made = []
        with self.change("Convert to curves"):
            order = self.scene.folio_items()
            for old in items:
                path = self.area_of(old)
                path.setFillRule(Qt.WindingFill)
                parts = parts_from_path(path)
                if not parts:
                    continue
                item = PathItem()
                item.set_parts_from_scene(parts, "winding")
                src = old
                item.fill = dict(src.fill)
                item.stroke = dict(src.stroke)
                item.shadow = dict(src.shadow)
                item.setOpacity(src.opacity())
                item.group, item.clip, item.uid, item.name = src.group, src.clip, src.uid, src.name
                order[order.index(old)] = item
                made.append(item)
            self.scene.remove_folio_items(items)
            for item in made:
                self.scene.addItem(item)
            self.scene.set_order(order)
            self.scene.select_only(made)

    def separate_curves(self):
        """Split a curve made of several parts into one curve per part."""
        items = [i for i in self.scene.selected_folio()
                 if isinstance(i, PathItem) and i.extra and not i.locked]
        if not items:
            self.statusBar().showMessage("Select a curve made of several parts first.", 5000)
            return
        made = []
        with self.change("Separate curves"):
            order = self.scene.folio_items()
            for old in items:
                pieces = []
                for nodes, closed in old.parts():
                    t = old.sceneTransform()

                    def to_scene(v, t=t):
                        if v is None:
                            return None
                        q = t.map(QPointF(*v))
                        return [q.x(), q.y()]
                    scene_nodes = [{**n, "p": to_scene(n["p"]), "i": to_scene(n.get("i")),
                                    "o": to_scene(n.get("o"))} for n in nodes]
                    piece = PathItem()
                    piece.set_nodes_from_scene(scene_nodes, closed)
                    piece.fill, piece.stroke = dict(old.fill), dict(old.stroke)
                    piece.shadow = dict(old.shadow)
                    piece.setOpacity(old.opacity())
                    piece.group = old.group
                    pieces.append(piece)
                at = order.index(old)
                order[at:at + 1] = pieces
                made.extend(pieces)
            self.scene.remove_folio_items(items)
            for item in made:
                self.scene.addItem(item)
            self.scene.set_order(order)
            self.scene.select_only(made)

    def zoom_to_selection(self):
        sel = self.scene.selected_folio()
        if sel:
            r = self.scene.items_rect(sel)
            pad = max(r.width(), r.height()) * 0.08
            self.view.fit_rect(r.adjusted(-pad, -pad, pad, pad))
        else:
            self.view.fit_page()

    def paste_plain(self):
        md = QGuiApplication.clipboard().mimeData()
        text = md.text().strip() if md is not None and md.hasText() else ""
        if not text:
            self.statusBar().showMessage("There are no copied words to paste.", 5000)
            return
        editing = self.view.editing_text
        if editing is not None:
            cursor = editing.textCursor()
            cursor.insertText(text)
            editing.setTextCursor(cursor)
            return
        c = self.visible_centre()
        item = self.create_text(c, None, text=text)
        item.set_center_scene(c)

    # ---- defaults, styles and settings ------------------------------------------------

    def defaults_from_selection(self):
        sel = self.scene.selected_folio()
        if not sel:
            self.statusBar().showMessage("Select an object first.", 5000)
            return
        for item in sel:
            self.remember_style(item)
        texts = [i for i in sel if isinstance(i, TextItem)]
        if texts:
            self.text_defaults.update({k: texts[0].style[k] for k in styles.TEXT_KEYS})
        self.saved_defaults = {"fill": self.style_fill, "stroke": self.style_stroke,
                               "text_color": self.text_color,
                               "text": {k: self.text_defaults[k] for k in styles.TEXT_KEYS}}
        self.settings.setValue("defaults", json.dumps(self.saved_defaults))
        self.statusBar().showMessage("New shapes and text will now look like this.", 6000)

    def reset_saved_defaults(self):
        self.saved_defaults = {}
        self.settings.remove("defaults")
        self.style_fill = dict(FACTORY_FILL)
        self.style_stroke = dict(FACTORY_STROKE)
        self.text_color = FACTORY_TEXT_COLOR
        self.reset_defaults()
        self.statusBar().showMessage("New shapes and text are back to Folio's own look.", 6000)

    def apply_saved_style(self, style):
        items = [i for i in self.scene.selected_folio() if not i.locked]
        if not items:
            self.statusBar().showMessage("Select something on the page first, then click a style.",
                                         6000)
            return
        with self.change("Apply style"):
            for item in items:
                styles.apply_style(item, style, self.scene.doc.dpi)
                refresh_item(item)

    def create_style(self):
        sel = self.scene.selected_folio()
        if not sel:
            self.statusBar().showMessage("Select the object whose look you want to keep.", 6000)
            return
        name, ok = QInputDialog.getText(self, "Create Style", "Name for this style:",
                                        text=f"My style {len(self.stylesp.styles) + 1}")
        if ok and name.strip():
            self.stylesp.add(styles.style_from_item(sel[0], self.scene.doc.dpi, name.strip()))
            self.dock_styles.show()
            self.dock_styles.raise_()

    def show_settings(self):
        dlg = SettingsDialog(self, {"nudge": self.nudge_step, "undo_steps": self.undo_steps,
                                    "autosave_min": self.settings.value("autosave_min", 2, type=int)})
        if not dlg.exec_():
            return
        v = dlg.values()
        self.nudge_step = v["nudge"]
        self.undo_steps = v["undo_steps"]
        for key in ("nudge", "autosave_min", "undo_steps"):
            self.settings.setValue(key, v[key])
        self.autosave_timer.start(v["autosave_min"] * 60_000)
        if self.undo.count() == 0:
            self.undo.setUndoLimit(self.undo_steps)
        if v["reset_layout"]:
            self.restoreState(self._default_state)

    # ---- colour (shared by the Colour, Swatches and Stroke panels) -----------------

    def colour_state(self):
        """(fill colour, outline colour, no fill?, no outline?) for the panels."""
        sel = [] if self.persona == "pixel" else self.scene.selected_folio()
        first = next((i for i in sel if i.has_fill), None)
        fill = first.fill if first is not None else self.style_fill
        stroke = sel[0].stroke if sel else self.style_stroke
        fill_c = qcolor(fill.get("color"))
        no_fill = fill.get("type") == "none" or fill_c.alpha() == 0
        no_stroke = float(stroke.get("width", 0.0)) <= 0
        return fill_c, qcolor(stroke.get("color")), no_fill, no_stroke

    def set_colour_target(self, target):
        self.colour_target = target
        self.colourp.refresh()
        self.swatches.refresh()
        for colours in self.tool_colours:
            colours.set_target(target)

    def apply_colour(self, colour, merge=True, label=None, target=None):
        """Colour the fill or outline of the selection (or of new shapes)."""
        target = target or self.colour_target
        c = color_str(colour)
        one_pt = units.pt_to_px(1, self.scene.doc.dpi)
        items = [i for i in self.scene.selected_folio() if not i.locked
                 and (i.has_fill if target == "fill" else i.has_stroke)]
        if self.persona == "pixel":
            items = []      # in the Pixel persona the colour is the paint colour
        if not items:
            if target == "fill":
                self.style_fill = {**self.style_fill, "color": c}
                if self.style_fill.get("type") == "none":
                    self.style_fill["type"] = "solid"
                self.text_color = c
            else:
                self.style_stroke = {**self.style_stroke, "color": c}
                if float(self.style_stroke.get("width", 0.0)) <= 0:
                    self.style_stroke["width"] = one_pt
            self.schedule_refresh()
            return
        label = label or ("Fill colour" if target == "fill" else "Outline colour")
        with self.change(label, merge=("colour-" + target) if merge else None):
            for item in items:
                if target == "fill":
                    if not item.has_fill:
                        continue
                    if item.fill.get("type") == "none":
                        item.fill["type"] = "solid"
                    item.fill["color"] = c
                else:
                    if not item.has_stroke:
                        continue
                    item.stroke["color"] = c
                    if float(item.stroke.get("width", 0.0)) <= 0:
                        item.stroke["width"] = one_pt
                refresh_item(item)
        self.remember_style(items[-1])

    def clear_colour(self):
        """Take away the fill or the outline (the crossed-out circle)."""
        target = self.colour_target
        items = [i for i in self.scene.selected_folio() if not i.locked]
        if not items:
            if target == "fill":
                self.style_fill = {**self.style_fill, "type": "none"}
            else:
                self.style_stroke = {**self.style_stroke, "width": 0.0}
            self.schedule_refresh()
            return
        with self.change("No fill" if target == "fill" else "No outline"):
            for item in items:
                if target == "stroke":
                    item.stroke["width"] = 0.0
                elif isinstance(item, TextItem):
                    item.fill["color"] = "#00000000"    # outline-only letters
                elif item.has_fill:
                    item.fill["type"] = "none"
                refresh_item(item)

    def swap_fill_stroke(self):
        items = [i for i in self.scene.selected_folio() if not i.locked and i.has_fill]
        if not items:
            fill, stroke = dict(self.style_fill), dict(self.style_stroke)
            self.style_fill["color"], self.style_stroke["color"] = stroke["color"], fill["color"]
            self.schedule_refresh()
            return
        one_pt = units.pt_to_px(1, self.scene.doc.dpi)
        with self.change("Swap fill and outline"):
            for item in items:
                no_fill = item.fill.get("type") == "none" or qcolor(item.fill.get("color")).alpha() == 0
                no_stroke = float(item.stroke.get("width", 0.0)) <= 0
                fill_c, stroke_c = item.fill.get("color"), item.stroke.get("color")
                item.stroke["color"] = fill_c
                item.stroke["width"] = 0.0 if no_fill else (float(item.stroke.get("width") or 0) or one_pt)
                if no_stroke:
                    if isinstance(item, TextItem):
                        item.fill["color"] = "#00000000"
                    else:
                        item.fill["type"] = "none"
                else:
                    item.fill["color"] = stroke_c
                    if item.fill.get("type") == "none":
                        item.fill["type"] = "solid"
                refresh_item(item)

    def remember_colour(self, colour):
        name = color_str(colour)
        self.recent_colours = [name] + [c for c in self.recent_colours if c != name]
        del self.recent_colours[16:]
        self.settings.setValue("recent_colours", json.dumps(self.recent_colours))
        self.swatches.refresh()

    def start_colour_pick(self):
        if self._picking_colour:
            return
        self._picking_colour = True
        QApplication.setOverrideCursor(Qt.CrossCursor)
        self.view.viewport().installEventFilter(self)
        self.view.installEventFilter(self)
        self.statusBar().showMessage("Click anywhere on the page to pick up its colour. "
                                     "Esc cancels.")

    def end_colour_pick(self):
        if not self._picking_colour:
            return
        self._picking_colour = False
        QApplication.restoreOverrideCursor()
        self.view.viewport().removeEventFilter(self)
        self.view.removeEventFilter(self)
        self.statusBar().clearMessage()

    # ---- Pixel persona ------------------------------------------------------------------

    def use_brush(self, brush):
        """Paint with a brush from the Brushes panel."""
        from .brushes import settings_of
        s = settings_of(brush)
        for key in ("size", "hardness", "opacity", "flow", "shape", "squash", "angle",
                    "grain", "scatter", "spacing"):
            self.brush[key] = s[key]
        self.brush_name = brush["name"]
        self.settings.setValue("brush_choice", brush["name"])
        if self.persona == "pixel" and self.tool_name != "px-brush":
            self.set_tool("px-brush")
        if hasattr(self, "context_bar"):
            self.context_bar.refresh()
        self.statusBar().showMessage(f"Brush: {brush['name']}", 3000)

    def paint_colour(self):
        fill, stroke, no_fill, _ = self.colour_state()
        return stroke if self.colour_target == "stroke" else fill

    def pixel_layer(self, create=True):
        """The picture to paint on: the selected picture (copied the first time,
        so the original file stays as it was), or a new pixel layer."""
        sel = self.scene.selected_folio()
        assets = self.scene.assets
        if len(sel) == 1 and isinstance(sel[0], ImageItem) and not sel[0].locked:
            item = sel[0]
            shared = sum(1 for i in self.scene.folio_items()
                         if isinstance(i, ImageItem) and i.aid == item.aid) > 1
            if not assets.is_live(item.aid) or shared:
                with self.change("Make pixel layer"):
                    item.aid = assets.live_copy(item.aid)
                    item.changed()
            return item
        if not create:
            return None
        return self.new_pixel_layer()

    def new_pixel_layer(self):
        page = self.scene.doc.page_rect()
        with self.change("New pixel layer"):
            from .pixel import new_layer_image
            aid = self.scene.assets.new_live(new_layer_image(page.width(), page.height()), "Pixel")
            item = ImageItem(self.scene.assets, aid)
            item.name = "Pixel"
            item.setPos(page.topLeft())
            self.insert_new(item)
            self.scene.select_only([item])
        return item

    def pixels_changed(self, aid):
        self.scene.assets.touched(aid)
        for item in self.scene.folio_items():
            if isinstance(item, ImageItem) and item.aid == aid:
                item.update()
        self.view.viewport().update()
        self.navigator.schedule()

    def set_pixel_selection(self, path):
        self.pixel_selection = path if path is not None and not path.isEmpty() else None
        self.view.viewport().update()
        self.context_bar.refresh()

    def pixel_deselect(self):
        self.set_pixel_selection(None)

    def pixel_invert(self):
        page = QPainterPath()
        page.addRect(self.scene.doc.page_rect())
        if self.pixel_selection is None:
            self.set_pixel_selection(page)
        else:
            self.set_pixel_selection(page.subtracted(self.pixel_selection))

    def _pixel_edit(self, label, draw):
        if self.pixel_selection is None:
            self.statusBar().showMessage("Select some pixels first (marquee, lasso or flood select).",
                                         5000)
            return
        layer = self.pixel_layer(create=True)
        if layer is None:
            return
        stroke = Stroke(self, layer, label)
        area = stroke.to_layer.map(self.pixel_selection)
        p = stroke.painter()
        draw(p, area)
        p.end()
        stroke.touch(area.boundingRect().adjusted(-2, -2, 2, 2))
        stroke.finish()

    def pixel_fill(self):
        colour = self.paint_colour()
        self._pixel_edit("Fill selection", lambda p, area: p.fillPath(area, colour))

    def pixel_clear(self):
        def clear(p, area):
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillPath(area, QColor(0, 0, 0))
        self._pixel_edit("Clear selection", clear)

    def draw_persona_overlay(self, painter):
        """Slices in the Export persona; the moving dotted line round a
        pixel selection in the Pixel persona."""
        if self.persona == "export":
            draw_slices(painter, self.view, self.scene, self.chosen_slice)
        elif self.persona == "pixel" and self.pixel_selection is not None:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor("#000000"), 0))
            painter.drawPath(self.pixel_selection)
            painter.setPen(QPen(QColor("#ffffff"), 0, Qt.DashLine))
            painter.drawPath(self.pixel_selection)

    # ---- Export persona -----------------------------------------------------------------

    def save_slice_defaults(self):
        self.settings.setValue("slice_defaults", json.dumps(self.slice_defaults))

    def current_slice(self):
        return next((s for s in self.scene.slices if s["id"] == self.chosen_slice), None)

    def choose_slice(self, sid):
        self.chosen_slice = sid
        self.refresh_slices()

    def refresh_slices(self):
        if not hasattr(self, "slices_panel"):
            return
        if self.current_slice() is None and self.scene.slices:
            self.chosen_slice = self.scene.slices[0]["id"]
        self.slices_panel.refresh()
        self.export_options.refresh()
        self.context_bar.refresh()
        self.view.viewport().update()

    def add_slice(self, rect, name=None):
        existing = {s["name"] for s in self.scene.slices}
        n = 1
        while f"Slice {n}" in existing:
            n += 1
        s = new_slice(name or f"Slice {n}", self.scene.doc.dpi,
                      rect=[rect.x(), rect.y(), rect.width(), rect.height()])
        s.update({k: v for k, v in self.slice_defaults.items() if k in EXPORT_KEYS and k != "dpi"})
        with self.change("Add slice"):
            self.scene.slices.append(s)
        self.chosen_slice = s["id"]
        self.refresh_slices()
        return s

    def slice_from_selection(self):
        sel = self.scene.selected_folio()
        if not sel:
            self.statusBar().showMessage("Select something on the page to make a slice of it.", 5000)
            return
        r = self.scene.items_rect(sel)
        self.add_slice(r, sel[0].display_name() if len(sel) == 1 else None)

    def delete_slice(self):
        s = self.current_slice()
        if s is None or not s.get("rect"):
            self.statusBar().showMessage("Only slices you drew can be deleted.", 5000)
            return
        with self.change("Delete slice"):
            self.scene.slices.remove(s)
        self.chosen_slice = None
        self.refresh_slices()

    def export_slices(self, chosen, folder):
        self.stop_text_editing()
        done = []
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for s in chosen:
                try:
                    done.append(export_slice(self.scene, s, folder))
                except (exporter.ExportError, OSError) as exc:
                    QApplication.restoreOverrideCursor()
                    QMessageBox.warning(self, "Export failed", f"{s['name']}: {exc}")
                    QApplication.setOverrideCursor(Qt.WaitCursor)
        finally:
            QApplication.restoreOverrideCursor()
        return done

    # ---- the Select menu ------------------------------------------------------------

    def invert_selection(self):
        if self.persona == "pixel":
            self.pixel_invert()
            return
        self.stop_text_editing()
        chosen = set(self.scene.selected_folio())
        self.scene.select_only([i for i in self.scene.folio_items()
                                if i not in chosen and i.isVisible() and not i.locked])

    def select_same(self, how):
        sel = self.scene.selected_folio()
        if not sel:
            self.statusBar().showMessage("Select one object first.", 5000)
            return
        key = {"fill": lambda i: i.fill.get("color") if i.has_fill else None,
               "stroke": lambda i: i.stroke.get("color") if i.stroke_width() > 0 else None,
               "font": lambda i: i.style["family"] if isinstance(i, TextItem) else None,
               "kind": lambda i: i.kind}[how]
        want = key(sel[0])
        self.scene.select_only([i for i in self.scene.folio_items()
                                if i.isVisible() and not i.locked and key(i) == want])

    def open_document(self, skip_check=False):
        if not skip_check and not self.maybe_save():
            return
        start = self.settings.value("doc_dir", os.path.expanduser("~/Documents"))
        path, _ = QFileDialog.getOpenFileName(
            self, "Open", start,
            "Folio documents and PDFs (*.folio *.pdf);;Folio documents (*.folio);;"
            "PDF files (*.pdf);;All files (*)")
        if path:
            if self._ext(path) == "pdf":
                self.import_path(path, new_document=True)
            else:
                self.open_path(path, checked=True)

    def open_path(self, path, checked=False):
        if not checked and not self.maybe_save():
            return
        try:
            snap, assets = fileio.load_document(path)
        except (OSError, fileio.FolioFileError) as exc:
            QMessageBox.warning(self, "Could not open", f"{os.path.basename(path)}\n\n{exc}")
            return
        scene = DocScene(DocSettings.from_dict(snap["doc"]))
        for aid, (blob, ext, name) in assets.items():
            scene.assets.add(blob, ext, name, aid)
        scene.restore(snap)
        self.path = path
        self.set_scene(scene)
        self.add_recent(path)
        self.settings.setValue("doc_dir", os.path.dirname(path))

    def save(self):
        if not self.path:
            return self.save_as()
        return self.write_file(self.path)

    def save_as(self):
        self.stop_text_editing()
        start = self.path or os.path.join(
            self.settings.value("doc_dir", os.path.expanduser("~/Documents")),
            (self.scene.doc.title or "Untitled") + ".folio")
        path, _ = QFileDialog.getSaveFileName(self, "Save as", start,
                                              "Folio documents (*.folio)")
        if not path:
            return False
        if not path.lower().endswith(".folio"):
            path += ".folio"
        if self.write_file(path):
            self.path = path
            self.add_recent(path)
            self.settings.setValue("doc_dir", os.path.dirname(path))
            self.update_title()
            return True
        return False

    def write_file(self, path):
        self.stop_text_editing()
        try:
            thumb = exporter.thumbnail_png(self.scene)
        except Exception:
            thumb = None
        try:
            fileio.save_document(self.scene, path, thumb)
        except OSError as exc:
            QMessageBox.warning(self, "Could not save", f"{path}\n\n{exc}")
            return False
        self.undo.setClean()
        self.remove_autosave()
        self.statusBar().showMessage(f"Saved {os.path.basename(path)}", 4000)
        self.update_title()
        return True

    def add_recent(self, path):
        recent = [p for p in self.settings.value("recent", [], type=list) if p != path]
        recent.insert(0, path)
        self.settings.setValue("recent", recent[:12])

    def fill_recent(self):
        self.recent_menu.clear()
        recent = [p for p in self.settings.value("recent", [], type=list) if os.path.exists(p)]
        if not recent:
            a = self.recent_menu.addAction("No recent files")
            a.setEnabled(False)
            return
        for p in recent:
            a = self.recent_menu.addAction(os.path.basename(p))
            a.setToolTip(p)
            a.triggered.connect(lambda _=False, path=p: self.open_path(path))

    def export(self):
        self.stop_text_editing()
        dlg = ExportDialog(self, self.scene.doc, self.last_export)
        if not dlg.exec_():
            return
        opts = dlg.options()
        self.last_export = opts
        self.settings.setValue("last_export", json.dumps(opts))
        ext = {"pdf": "pdf", "png": "png", "jpeg": "jpg"}[opts["format"]]
        base = os.path.splitext(self.display_name())[0]
        if opts["area"] not in ("page", "trim"):
            base += "-" + opts["area"]
        folder = self.settings.value("export_dir", os.path.dirname(self.path) if self.path
                                     else os.path.expanduser("~/Documents"))
        filters = {"pdf": "PDF (*.pdf)", "png": "PNG image (*.png)", "jpg": "JPEG image (*.jpg *.jpeg)"}
        path, _ = QFileDialog.getSaveFileName(self, "Export", os.path.join(folder, f"{base}.{ext}"),
                                              filters[ext])
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += "." + ext
        self.settings.setValue("export_dir", os.path.dirname(path))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            exporter.export(self.scene, opts, path)
        except (exporter.ExportError, OSError) as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f"Exported {os.path.basename(path)}", 6000)

    # ---- printing on your own printer --------------------------------------------

    def printer(self):
        if getattr(self, "_printer", None) is None:
            self._printer = QPrinter(QPrinter.HighResolution)
            self._printer_set_up = False
        self._printer.setDocName(os.path.splitext(self.display_name())[0])
        if not self._printer_set_up:
            # Turn the paper to match the page until Print Setup says otherwise.
            trim = self.scene.doc.trim_rect()
            self._printer.setPageOrientation(
                QPageLayout.Landscape if trim.width() > trim.height() else QPageLayout.Portrait)
        return self._printer

    def print_setup(self):
        self.stop_text_editing()
        printer = self.printer()
        if QPageSetupDialog(printer, self).exec_():
            self._printer_set_up = True

    def print_preview(self):
        self.stop_text_editing()
        dlg = QPrintPreviewDialog(self.printer(), self)
        dlg.setWindowTitle("Print preview")
        dlg.paintRequested.connect(self.paint_for_printer)
        dlg.resize(1000, 820)
        dlg.exec_()

    def print_document(self):
        self.stop_text_editing()
        printer = self.printer()
        dlg = QPrintDialog(printer, self)
        dlg.setWindowTitle("Print")
        if not dlg.exec_():
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ok = self.paint_for_printer(printer)
        finally:
            QApplication.restoreOverrideCursor()
        if ok:
            self.statusBar().showMessage("Sent to the printer.", 6000)

    def paint_for_printer(self, printer):
        """Print the finished page (without bleed): actual size when it fits,
        otherwise shrunk to fit the paper, centred."""
        area = self.scene.doc.trim_rect()
        page = printer.pageRect(QPrinter.DevicePixel)
        actual = printer.resolution() / self.scene.doc.dpi
        fit = min(page.width() / area.width(), page.height() / area.height())
        scale = min(actual, fit)
        w, h = area.width() * scale, area.height() * scale
        target = QRectF((page.width() - w) / 2, (page.height() - h) / 2, w, h)
        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.warning(self, "Could not print",
                                "The printer could not be started. Check that it is on and connected.")
            return False
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform
                               | QPainter.TextAntialiasing)
        with exporter.export_mode(self.scene):
            self.scene.render(painter, target, area, Qt.IgnoreAspectRatio)
        painter.end()
        if scale < actual - 1e-6:
            self.statusBar().showMessage(
                f"The page was shrunk to {scale / actual * 100:.0f}% to fit the paper.", 8000)
        return True

    # ---- autosave -----------------------------------------------------------------

    def autosave(self):
        if self.undo.isClean() or self.view.editing_text is not None:
            return
        try:
            fileio.save_document(self.scene, self.autosave_path)
            self.settings.setValue("autosave_for", self.path or "")
        except OSError:
            pass

    def remove_autosave(self):
        try:
            os.remove(self.autosave_path)
        except OSError:
            pass

    def offer_rescue(self):
        folder = data_dir()
        found = []
        for name in os.listdir(folder):
            if not (name.startswith("autosave-") and name.endswith(".folio")):
                continue
            full = os.path.join(folder, name)
            if full == self.autosave_path or self._pid_alive(name):
                continue
            found.append(full)
        found.sort(key=os.path.getmtime, reverse=True)
        if not found:
            return False
        answer = QMessageBox.question(
            self, "Unsaved work found",
            "Folio closed last time before your work was saved.\n\n"
            "Open the rescued copy now?")
        if answer == QMessageBox.Yes:
            self.open_path(found[0], checked=True)
            self.path = None
            self.undo.resetClean()
            self.update_title()
        for f in found:
            try:
                os.remove(f)
            except OSError:
                pass
        return answer == QMessageBox.Yes

    @staticmethod
    def _pid_alive(name):
        """True if the Folio that wrote this autosave is still running."""
        try:
            pid = int(name[len("autosave-"):-len(".folio")])
            os.kill(pid, 0)
            return True
        except (ValueError, ProcessLookupError):
            return False
        except PermissionError:
            return True

    # ---- menus and help -------------------------------------------------------------

    def show_context_menu(self, global_pos, scene_pos):
        item = self.view.item_at(scene_pos)
        if item is not None and not item.isSelected():
            self.scene.select_only(self.scene.unit_of(item))
        m = QMenu(self)
        has = bool(self.scene.selected_folio())
        for a in (self.a_cut, self.a_copy):
            m.addAction(a).setEnabled(has)
        m.addAction(self.a_paste)
        if has:
            m.addAction(self.a_dup)
            m.addAction(self.a_delete)
            m.addSeparator()
            arrange = m.addMenu("Arrange")
            for a in (self.a_front, self.a_forward, self.a_backward, self.a_back):
                arrange.addAction(a)
            m.addAction(self.a_group)
            m.addAction(self.a_ungroup)
            m.addSeparator()
            m.addAction(self.a_flip_h)
            m.addAction(self.a_flip_v)
            m.addAction(self.a_lock)
            m.addAction(self.a_hide)
        else:
            m.addSeparator()
            m.addAction(self.a_place)
            m.addAction(self.a_select_all)
        m.exec_(global_pos)

    def show_shortcuts(self):
        ShortcutsDialog(self).exec_()

    def show_about(self):
        QMessageBox.about(
            self, "About Folio",
            f"<h3>Folio {__version__}</h3>"
            "<p>A graphic design app for book covers, ebook covers and more.</p>"
            "<p>Made by <b>4ThePeople Media</b>.</p>"
            "<p>Free and open source under the GNU General Public License, version 3.</p>")

    # ---- closing ----------------------------------------------------------------

    def closeEvent(self, e):
        self.stop_text_editing()
        if not self.maybe_save():
            e.ignore()
            return
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("window_state", self.saveState())
        self.settings.setValue("layout_version", LAYOUT_VERSION)
        self.remove_autosave()
        e.accept()
