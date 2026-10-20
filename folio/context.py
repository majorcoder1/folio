"""The context toolbar: the second row of the toolbar, which changes with
the tool and with what is selected, as in pro design apps.

* Nothing selected (Move tool): "No Selection", Auto-select, and buttons for
  Document Setup and Settings.
* Something selected: its fill, outline and opacity, plus corners for a
  rectangle and font, size and style for text.
* Drawing tools: the fill and outline new shapes get.
"""

from PyQt5.QtCore import QSize
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (QComboBox, QFontComboBox, QLabel, QPushButton, QSizePolicy,
                             QToolBar, QToolButton, QWidget)

from . import shapes
from .icons import icon
from .items import ImageItem, RectItem, TextItem
from .panels import ColorButton, spin

KIND_NAMES = {"rect": "Rectangle", "ellipse": "Ellipse", "path": "Curve", "text": "Text",
              "image": "Picture"}
DRAWING_TOOLS = {"pen", "line", "pencil"} | {k for k, _, _ in shapes.SHAPE_TOOLS}


class ContextBar(QToolBar):
    def __init__(self, win):
        super().__init__("Context", win)
        self.win = win
        self.updating = False
        self.setObjectName("toolbar_context")
        self.setMovable(False)
        self.setIconSize(QSize(18, 18))
        self.parts = {}

        self.label = QLabel()
        self.label.setObjectName("contextLabel")
        self.label.setMinimumWidth(110)
        self.add("label", self.label)

        auto = QLabel(" Auto-select:")
        auto.setObjectName("hint")
        self.auto = QComboBox()
        self.auto.addItem("Default", "group")
        self.auto.addItem("Objects", "object")
        self.auto.addItem("Groups", "group")
        self.auto.setToolTip("Default and Groups: a click picks a whole group.\n"
                             "Objects: a click picks one object inside a group "
                             "(Ctrl-click always does).")
        self.add("auto", auto, self.auto)

        self.setup_btn = QPushButton("Document Setup…")
        self.settings_btn = QPushButton("Settings…")
        self.add("doc", self.setup_btn, self.settings_btn)

        self.fill_label = QLabel(" Fill")
        self.fill_label.setObjectName("hint")
        self.fill = ColorButton("Fill colour")
        self.fill.setFixedSize(40, 22)
        self.add("fill", self.fill_label, self.fill)

        self.stroke_label = QLabel(" Outline")
        self.stroke_label.setObjectName("hint")
        self.stroke = ColorButton("Outline colour")
        self.stroke.setFixedSize(40, 22)
        self.width = spin(0, 1000, 1, 0.5, " pt")
        self.width.setMinimumWidth(78)
        self.width.setToolTip("Outline width")
        self.add("stroke", self.stroke_label, self.stroke, self.width)

        op = QLabel(" Opacity")
        op.setObjectName("hint")
        self.opacity = QComboBox()
        self.opacity.setEditable(True)
        self.opacity.addItems([f"{v} %" for v in range(100, -1, -10)])
        self.opacity.setMinimumWidth(80)
        self.add("opacity", op, self.opacity)

        corners = QLabel(" Corners")
        corners.setObjectName("hint")
        self.corners = spin(0, 10000, 1, 1, " pt")
        self.corners.setMinimumWidth(78)
        self.add("corners", corners, self.corners)

        self.font_box = QFontComboBox()
        self.font_box.setMaximumWidth(220)
        self.size = spin(1, 2000, 1, 1, " pt")
        self.size.setMinimumWidth(78)
        self.bold = self._toggle("B", "Bold", bold=True)
        self.italic = self._toggle("I", "Italic", italic=True)
        self.align = {}
        aligns = []
        for key, tip in (("left", "Line up on the left"), ("center", "Centre each line"),
                         ("right", "Line up on the right")):
            b = QToolButton()
            b.setIcon(icon("text-" + key))
            b.setCheckable(True)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, k=key: self.on_text("align", k))
            self.align[key] = b
            aligns.append(b)
        font_label = QLabel(" Font")
        font_label.setObjectName("hint")
        self.add("text", font_label, self.font_box, self.size, self.bold, self.italic, *aligns)

        self.info = QLabel()
        self.info.setObjectName("hint")
        self.add("info", self.info)

        # Pixel persona: brush settings
        def number(lo, hi, suffix, tip, decimals=0, width=70):
            box = spin(lo, hi, decimals, 1, suffix)
            box.setMinimumWidth(width)
            box.setToolTip(tip)
            return box

        def hint(text):
            lab = QLabel(text)
            lab.setObjectName("hint")
            return lab
        self.b_size = number(1, 3000, " px", "Brush width", width=78)
        self.b_opacity = number(1, 100, " %", "How strong each stroke is")
        self.b_flow = number(1, 100, " %", "How much paint each touch of the brush lays down")
        self.b_hard = number(0, 100, " %", "Hard edge (100 %) or soft edge (0 %)")
        self.add("brush", hint(" Width"), self.b_size, hint(" Opacity"), self.b_opacity,
                 hint(" Flow"), self.b_flow, hint(" Hardness"), self.b_hard)
        self.b_tol = number(0, 255, "", "How different a colour may be and still count", width=60)
        self.b_sample = QComboBox()
        self.b_sample.addItem("Whole page", "page")
        self.b_sample.addItem("Chosen layer", "layer")
        self.b_sample.setToolTip("Look at everything on the page, or only the chosen layer")
        self.add("tolerance", hint(" Tolerance"), self.b_tol, hint(" Source"), self.b_sample)
        self.px_buttons = []
        for text, tip, fn in (("Deselect", "Clear the pixel selection (Ctrl+D)", win.pixel_deselect),
                              ("Invert", "Select everything else", win.pixel_invert),
                              ("Fill", "Fill the selection with the fill colour", win.pixel_fill),
                              ("Clear", "Make the selected pixels see-through (Delete)",
                               win.pixel_clear)):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            self.px_buttons.append(b)
        self.add("pxsel", *self.px_buttons)
        self.new_layer_btn = QPushButton("New Pixel Layer")
        self.new_layer_btn.setToolTip("Add an empty, see-through layer to paint on")
        self.new_layer_btn.clicked.connect(win.new_pixel_layer)
        self.add("pxlayer", self.new_layer_btn)

        # Export persona: the chosen slice
        self.slice_info = QLabel()
        self.slice_info.setObjectName("hint")
        self.add("slice", self.slice_info)

        self.curves_btn = QPushButton("Convert to Curves")
        self.curves_btn.setToolTip("Turn this into curves whose points you can edit")
        self.add("curves", self.curves_btn)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.addWidget(spacer)

        self.auto.currentIndexChanged.connect(self.on_auto)
        self.setup_btn.clicked.connect(win.document_setup)
        self.settings_btn.clicked.connect(win.show_settings)
        self.fill.colorChanged.connect(lambda c: self.on_colour("fill", c))
        self.stroke.colorChanged.connect(lambda c: self.on_colour("stroke", c))
        self.width.valueChanged.connect(self.on_width)
        self.opacity.activated.connect(lambda _: self.on_opacity())
        self.opacity.lineEdit().editingFinished.connect(self.on_opacity)
        self.corners.valueChanged.connect(self.on_corners)
        self.font_box.currentFontChanged.connect(lambda f: self.on_text("family", f.family()))
        self.size.valueChanged.connect(lambda v: self.on_text("size", self.win.textp.px(v)))
        self.bold.toggled.connect(lambda v: self.on_text("bold", bool(v)))
        self.italic.toggled.connect(lambda v: self.on_text("italic", bool(v)))
        self.curves_btn.clicked.connect(win.convert_to_curves)
        for box, key in ((self.b_size, "size"), (self.b_opacity, "opacity"),
                         (self.b_flow, "flow"), (self.b_hard, "hardness"),
                         (self.b_tol, "tolerance")):
            box.valueChanged.connect(lambda v, k=key: self.on_brush(k, v))
        self.b_sample.currentIndexChanged.connect(
            lambda _: self.on_brush("sample", self.b_sample.currentData()))

    def _toggle(self, text, tip, bold=False, italic=False):
        b = QToolButton()
        b.setText(text)
        b.setCheckable(True)
        b.setToolTip(tip)
        f = QFont(b.font())
        f.setBold(bold)
        f.setItalic(italic)
        b.setFont(f)
        return b

    def add(self, key, *widgets):
        self.parts[key] = [self.addWidget(w) for w in widgets]

    def show_part(self, key, on):
        for action in self.parts[key]:
            action.setVisible(on)

    # ---- showing what fits ------------------------------------------------

    def refresh(self):
        self.updating = True
        try:
            self._refresh()
        finally:
            self.updating = False

    def _refresh(self):
        persona = getattr(self.win, "persona", "design")
        if persona != "design" and not (persona == "pixel" and (self.win.tool_name or "") == "move"):
            for key in self.parts:
                self.show_part(key, False)
            self.show_part("label", True)
            if persona == "pixel":
                self._refresh_pixel()
            else:
                self._refresh_export()
            return
        for key in ("brush", "tolerance", "pxsel", "pxlayer", "slice"):
            self.show_part(key, False)
        self._refresh_design()

    def _refresh_pixel(self):
        win = self.win
        tool = win.tool_name or ""
        title = next((t for n, t, _, _ in win.tool_list() if n == tool), "")
        if tool == "px-brush" and getattr(win, "brush_name", ""):
            title = f"{title}: {win.brush_name}"
        self.label.setText(title)
        brushes = tool in ("px-brush", "px-erase", "px-blur", "px-dodge", "px-burn")
        self.show_part("brush", brushes)
        self.show_part("tolerance", tool in ("px-wand", "px-fill"))
        self.show_part("pxsel", win.pixel_selection is not None)
        self.show_part("pxlayer", True)
        b = win.brush
        self.b_size.setValue(b["size"])
        self.b_opacity.setValue(b["opacity"])
        self.b_flow.setValue(b["flow"])
        self.b_hard.setValue(b["hardness"] * 100)
        self.b_tol.setValue(b["tolerance"])
        self.b_sample.setCurrentIndex(max(0, self.b_sample.findData(b["sample"])))

    def _refresh_export(self):
        s = self.win.current_slice()
        self.show_part("slice", True)
        if s is None:
            self.label.setText("No slice")
            self.slice_info.setText("Draw a slice with the Slice tool, or pick one in Slices.")
            return
        from .slices import pixel_size
        w, h = pixel_size(self.win.scene.doc, s)
        self.label.setText(s["name"])
        self.slice_info.setText(f"{w} × {h}, “{s['name']}”, {s['format'].upper()}, "
                                f"RGB 8-bit, {s.get('dpi', 300):g} dpi")

    def on_brush(self, key, value):
        if self.updating:
            return
        self.win.brush[key] = value / 100.0 if key == "hardness" else value

    def _refresh_design(self):
        win = self.win
        tool = win.tool_name or "move"
        sel = win.scene.selected_folio()
        drawing = tool in DRAWING_TOOLS
        if sel:
            kinds = {i.kind for i in sel}
            if len(sel) == 1:
                name = sel[0].display_name()
                if len(name) > 28:
                    name = name[:27] + "…"
            elif len(kinds) == 1:
                name = f"{len(sel)} × {KIND_NAMES.get(sel[0].kind, 'objects')}"
            else:
                name = f"{len(sel)} objects"
            self.label.setText(name)
        elif drawing:
            self.label.setText("New shapes:")
        else:
            self.label.setText("No Selection")
        show_doc = not sel and not drawing
        self.show_part("auto", tool == "move")
        self.show_part("doc", show_doc)
        fillable = [i for i in sel if i.has_fill] if sel else []
        self.show_part("fill", bool(fillable) or (drawing and not sel))
        self.show_part("stroke", bool(sel) or drawing)
        self.show_part("opacity", bool(sel))
        rects = [i for i in sel if isinstance(i, RectItem)]
        self.show_part("corners", bool(rects))
        texts = [i for i in sel if isinstance(i, TextItem)]
        self.show_part("text", bool(texts) or tool == "text")
        images = [i for i in sel if isinstance(i, ImageItem)]
        self.show_part("info", len(images) == 1 and len(sel) == 1)
        self.show_part("curves", bool(sel) and any(
            isinstance(i, (TextItem, RectItem)) or i.kind == "ellipse" for i in sel))

        fill_c, stroke_c, no_fill, no_stroke = win.colour_state()
        fc = QColor(fill_c)
        if no_fill:
            fc.setAlpha(0)
        self.fill.setColor(fc)
        self.stroke.setColor(stroke_c)
        stroke = sel[0].stroke if sel else win.style_stroke
        self.width.setValue(win.textp.pt(float(stroke.get("width", 0.0))))
        if sel:
            self.opacity.setEditText(f"{round(sel[0].opacity() * 100)} %")
        if rects:
            self.corners.setValue(win.textp.pt(rects[0].radius))
        style = texts[0].style if texts else win.text_defaults
        self.font_box.setCurrentFont(QFont(style["family"]))
        self.size.setValue(win.textp.pt(style["size"]))
        self.bold.setChecked(bool(style["bold"]))
        self.italic.setChecked(bool(style["italic"]))
        for key, b in self.align.items():
            b.setChecked(style["align"] == key)
        if images:
            px = images[0].pixel_size()
            self.info.setText(f"  {px.width()} × {px.height()} pixels")

    # ---- changes ---------------------------------------------------------------

    def on_auto(self):
        self.win.auto_select = self.auto.currentData()

    def on_colour(self, target, c):
        if self.updating:
            return
        self.win.apply_colour(c, target=target)

    def on_width(self, pt):
        if not self.updating:
            self.win.strokep.on_width(pt)

    def on_opacity(self):
        if self.updating:
            return
        try:
            value = float(self.opacity.currentText().replace("%", "").strip())
        except ValueError:
            return
        items = [i for i in self.win.scene.selected_folio() if not i.locked]
        if not items:
            return
        with self.win.change("Opacity", merge="opacity"):
            for item in items:
                item.setOpacity(min(max(value, 0.0), 100.0) / 100.0)

    def on_corners(self, pt):
        if self.updating:
            return
        items = [i for i in self.win.scene.selected_folio()
                 if isinstance(i, RectItem) and not i.locked]
        if not items:
            return
        with self.win.change("Corners", merge="radius"):
            for item in items:
                item.radius = self.win.textp.px(pt)
                item.prepareGeometryChange()
                item.changed()

    def on_text(self, key, value):
        if not self.updating:
            self.win.textp.set_style(key, value)
