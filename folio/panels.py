"""Side panels: Properties, Text, Transform and Layers."""

from PyQt5.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox,
                             QColorDialog, QComboBox,
                             QFormLayout, QGridLayout, QGroupBox,
                             QHBoxLayout, QHeaderView, QLabel, QMenu, QPushButton,
                             QScrollArea, QSlider, QSpinBox, QToolButton,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                             QWidget)

from . import fonts, units
from .numberbox import NumberBox
from .icons import icon
from .items import BLENDS, ImageItem, RectItem, TextItem, color_str, qcolor


def spin(lo, hi, decimals=1, step=1.0, suffix=""):
    box = NumberBox()
    box.setRange(lo, hi)
    box.setDecimals(decimals)
    box.setSingleStep(step)
    box.setSuffix(suffix)
    box.setKeyboardTracking(False)
    box.setAccelerated(True)
    box.setMinimumWidth(80)
    return box


def refresh_item(item):
    if isinstance(item, TextItem):
        item.apply_style()
    else:
        item.prepareGeometryChange()
        item.changed()


class ColorButton(QToolButton):
    """A colour swatch. Click to pick a colour (with see-through amount)."""

    colorChanged = pyqtSignal(QColor)

    def __init__(self, title="Choose colour", parent=None):
        super().__init__(parent)
        self.title = title
        self._color = QColor("#000000")
        self.setFixedSize(52, 26)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self.pick)

    def color(self):
        return QColor(self._color)

    def setColor(self, color):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        s = 6
        for i in range(int(r.width() // s) + 1):
            for j in range(int(r.height() // s) + 1):
                c = QColor("#ffffff") if (i + j) % 2 else QColor("#c8c8c8")
                cell = QRectF(r.left() + i * s, r.top() + j * s, s, s).intersected(r)
                p.fillRect(cell, c)
        p.fillRect(r, self._color)
        p.setPen(QColor("#6b6b73") if not self.underMouse() else QColor("#4a8fe7"))
        p.drawRoundedRect(r, 3, 3)
        if not self.isEnabled():
            p.fillRect(r, QColor(40, 40, 44, 170))

    def pick(self):
        original = QColor(self._color)
        dlg = QColorDialog(original, self.window())
        dlg.setWindowTitle(self.title)
        dlg.setOption(QColorDialog.ShowAlphaChannel, True)
        dlg.setOption(QColorDialog.DontUseNativeDialog, True)
        dlg.currentColorChanged.connect(self._live)
        if dlg.exec_():
            self._live(dlg.selectedColor())
        else:
            self._live(original)

    def _live(self, color):
        if color.isValid() and color != self._color:
            self._color = QColor(color)
            self.update()
            self.colorChanged.emit(QColor(color))


class Section(QGroupBox):
    def __init__(self, title):
        super().__init__(title)
        self.form = QFormLayout(self)
        self.form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.form.setHorizontalSpacing(10)
        self.form.setVerticalSpacing(6)


def row(*widgets, stretch=True):
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    for x in widgets:
        h.addWidget(x)
    if stretch:
        h.addStretch(1)
    return w


class PanelBase(QScrollArea):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.inner = QWidget()
        self.layout_ = QVBoxLayout(self.inner)
        self.layout_.setContentsMargins(8, 8, 8, 8)
        self.layout_.setSpacing(8)
        self.setWidget(self.inner)
        self.updating = False

    @property
    def scene(self):
        return self.win.scene

    @property
    def dpi(self):
        return self.scene.doc.dpi

    def pt(self, px):
        return units.px_to_pt(px, self.dpi)

    def px(self, pt):
        return units.pt_to_px(pt, self.dpi)

    def selection(self):
        return self.scene.selected_folio()


class PropertiesPanel(PanelBase):
    """Fill, outline, opacity, shadow and image settings."""

    FILL_TYPES = [("None", "none"), ("Solid colour", "solid"),
                  ("Linear gradient", "linear"), ("Radial gradient", "radial")]
    DASHES = [("Solid", "solid"), ("Dashed", "dash"), ("Dotted", "dot"),
              ("Dash-dot", "dashdot")]

    def __init__(self, win):
        super().__init__(win)
        L = self.layout_
        self.empty = QLabel("Select an object on the page to change its fill, "
                            "gradient, opacity and shadow.")
        self.empty.setObjectName("hint")
        self.empty.setWordWrap(True)
        L.addWidget(self.empty)

        self.fill_box = Section("Fill")
        self.fill_type = QComboBox()
        for title, key in self.FILL_TYPES:
            self.fill_type.addItem(title, key)
        self.fill_c1 = ColorButton("Fill colour")
        self.fill_c2 = ColorButton("Gradient end colour")
        self.fill_angle = spin(0, 360, 0, 15, "°")
        self.swap = QToolButton()
        self.swap.setText("⇄")
        self.swap.setToolTip("Swap the two gradient colours")
        self.fill_box.form.addRow("Type", self.fill_type)
        self.fill_box.form.addRow("Colour", row(self.fill_c1, self.swap))
        self.fill_box.form.addRow("End colour", self.fill_c2)
        self.fill_box.form.addRow("Angle", self.fill_angle)
        L.addWidget(self.fill_box)

        self.stroke_box = Section("Outline")
        self.stroke_c = ColorButton("Outline colour")
        self.stroke_w = spin(0, 1000, 1, 0.5, " pt")
        self.stroke_dash = QComboBox()
        for title, key in self.DASHES:
            self.stroke_dash.addItem(title, key)
        self.stroke_box.form.addRow("Colour", self.stroke_c)
        self.stroke_box.form.addRow("Width", self.stroke_w)
        self.stroke_box.form.addRow("Style", self.stroke_dash)
        L.addWidget(self.stroke_box)

        self.layer_box = Section("Layer")
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity_val = QSpinBox()
        self.opacity_val.setRange(0, 100)
        self.opacity_val.setSuffix(" %")
        self.opacity_val.setKeyboardTracking(False)
        self.radius = spin(0, 10000, 1, 1, " pt")
        self.layer_box.form.addRow("Opacity", row(self.opacity, self.opacity_val, stretch=False))
        self.layer_box.form.addRow("Corners", self.radius)
        L.addWidget(self.layer_box)

        self.shadow_box = Section("Shadow")
        self.shadow_on = QCheckBox("Drop shadow")
        self.shadow_c = ColorButton("Shadow colour")
        self.shadow_blur = spin(0, 500, 1, 1, " pt")
        self.shadow_x = spin(-1000, 1000, 1, 1, " pt")
        self.shadow_y = spin(-1000, 1000, 1, 1, " pt")
        self.shadow_box.form.addRow("", self.shadow_on)
        self.shadow_box.form.addRow("Colour", self.shadow_c)
        self.shadow_box.form.addRow("Softness", self.shadow_blur)
        self.shadow_box.form.addRow("Across", self.shadow_x)
        self.shadow_box.form.addRow("Down", self.shadow_y)
        L.addWidget(self.shadow_box)

        self.image_box = Section("Image")
        self.image_info = QLabel()
        self.image_info.setWordWrap(True)
        self.image_warn = QLabel()
        self.image_warn.setObjectName("warn")
        self.image_warn.setWordWrap(True)
        self.fit_target = QComboBox()
        self.fill_btn = QPushButton("Fill")
        self.fill_btn.setToolTip("Cover the whole area, cutting off what hangs over")
        self.fit_btn = QPushButton("Fit")
        self.fit_btn.setToolTip("Show the whole image inside the area")
        self.image_box.form.addRow(self.image_info)
        self.image_box.form.addRow(self.image_warn)
        self.image_box.form.addRow("Size to", self.fit_target)
        self.image_box.form.addRow("", row(self.fill_btn, self.fit_btn))
        L.addWidget(self.image_box)
        L.addStretch(1)

        self.fill_type.currentIndexChanged.connect(self.on_fill_type)
        self.fill_c1.colorChanged.connect(lambda c: self.set_fill("color", color_str(c)))
        self.fill_c2.colorChanged.connect(lambda c: self.set_fill("color2", color_str(c)))
        self.fill_angle.valueChanged.connect(lambda v: self.set_fill("angle", v))
        self.swap.clicked.connect(self.on_swap)
        self.stroke_c.colorChanged.connect(lambda c: self.set_stroke("color", color_str(c)))
        self.stroke_w.valueChanged.connect(lambda v: self.set_stroke("width", self.px(v)))
        self.stroke_dash.currentIndexChanged.connect(
            lambda i: self.set_stroke("dash", self.stroke_dash.itemData(i)))
        self.opacity.valueChanged.connect(self.on_opacity)
        self.opacity_val.valueChanged.connect(self.on_opacity)
        self.radius.valueChanged.connect(self.on_radius)
        self.shadow_on.toggled.connect(lambda v: self.set_shadow("on", bool(v)))
        self.shadow_c.colorChanged.connect(lambda c: self.set_shadow("color", color_str(c)))
        self.shadow_blur.valueChanged.connect(lambda v: self.set_shadow("blur", self.px(v)))
        self.shadow_x.valueChanged.connect(lambda v: self.set_shadow("dx", self.px(v)))
        self.shadow_y.valueChanged.connect(lambda v: self.set_shadow("dy", self.px(v)))
        self.fill_btn.clicked.connect(lambda: self.win.size_images_to(
            self.fit_target.currentData(), cover=True))
        self.fit_btn.clicked.connect(lambda: self.win.size_images_to(
            self.fit_target.currentData(), cover=False))
        self.refresh()

    def refresh(self):
        self.updating = True
        try:
            self._refresh()
        finally:
            self.updating = False

    def _refresh(self):
        sel = self.selection()
        has = bool(sel)
        self.empty.setVisible(not has)
        for box in (self.fill_box, self.layer_box, self.shadow_box):
            box.setVisible(has)
        self.stroke_box.setVisible(False)   # the Stroke panel does outlines
        images = [i for i in sel if isinstance(i, ImageItem)]
        self.image_box.setVisible(bool(images))
        if not has:
            return
        first = sel[0]
        fillable = [i for i in sel if i.has_fill]
        self.fill_box.setVisible(bool(fillable))
        if fillable:
            f = fillable[0].fill
            texts_only = all(isinstance(i, TextItem) for i in fillable)
            self.fill_box.setTitle("Text colour" if texts_only else "Fill")
            for idx in (2, 3):
                item = self.fill_type.model().item(idx)
                item.setEnabled(any(i.gradient_fill for i in fillable))
            self.fill_type.setCurrentIndex(max(0, self.fill_type.findData(f.get("type"))))
            self.fill_c1.setColor(qcolor(f.get("color")))
            self.fill_c2.setColor(qcolor(f.get("color2")))
            self.fill_angle.setValue(float(f.get("angle", 90)))
            gradient = f.get("type") in ("linear", "radial")
            self.fill_c1.setEnabled(f.get("type") != "none")
            self.fill_c2.setEnabled(gradient)
            self.swap.setEnabled(gradient)
            self.fill_angle.setEnabled(f.get("type") == "linear")
        self.stroke_box.setTitle("Letter outline" if isinstance(first, TextItem)
                                 else "Outline")
        s = first.stroke
        self.stroke_c.setColor(qcolor(s.get("color")))
        self.stroke_w.setValue(self.pt(float(s.get("width", 0))))
        self.stroke_dash.setCurrentIndex(max(0, self.stroke_dash.findData(s.get("dash", "solid"))))
        self.stroke_dash.setEnabled(not isinstance(first, TextItem))
        op = int(round(first.opacity() * 100))
        self.opacity.setValue(op)
        self.opacity_val.setValue(op)
        rects = [i for i in sel if isinstance(i, RectItem)]
        self.radius.setEnabled(bool(rects))
        self.radius.setValue(self.pt(rects[0].radius) if rects else 0)
        sh = first.shadow
        self.shadow_on.setChecked(bool(sh.get("on")))
        self.shadow_c.setColor(qcolor(sh.get("color")))
        self.shadow_blur.setValue(self.pt(float(sh.get("blur", 0))))
        self.shadow_x.setValue(self.pt(float(sh.get("dx", 0))))
        self.shadow_y.setValue(self.pt(float(sh.get("dy", 0))))
        for w in (self.shadow_c, self.shadow_blur, self.shadow_x, self.shadow_y):
            w.setEnabled(bool(sh.get("on")))
        if images:
            self._refresh_image(images[0])

    def _refresh_image(self, item):
        size = item.pixel_size()
        doc = self.scene.doc
        dpi_x = size.width() * doc.dpi / max(item.w, 1e-6)
        dpi_y = size.height() * doc.dpi / max(item.h, 1e-6)
        eff = min(dpi_x, dpi_y)
        self.image_info.setText(f"{size.width()} x {size.height()} pixels.\n"
                                f"Prints at about {eff:.0f} dpi at this size.")
        if doc.kind == "cover" or doc.dpi >= 200:
            if eff < 200:
                self.image_warn.setText("Low for print: it may look blurry. "
                                        "Use a bigger image or make it smaller.")
            elif eff < 290:
                self.image_warn.setText("A little low for print (300 dpi is best).")
            else:
                self.image_warn.setText("")
        else:
            self.image_warn.setText("")
        self.image_warn.setVisible(bool(self.image_warn.text()))
        current = self.fit_target.currentData()
        self.fit_target.blockSignals(True)
        self.fit_target.clear()
        names = [("Whole page (with bleed)", "page")]
        if doc.kind == "cover":
            names += [("Front cover", "front"), ("Back cover", "back"), ("Spine", "spine")]
        elif doc.bleed > 0:
            names += [("Trimmed page", "trim")]
        for title, key in names:
            self.fit_target.addItem(title, key)
        idx = self.fit_target.findData(current)
        self.fit_target.setCurrentIndex(max(0, idx))
        self.fit_target.blockSignals(False)

    # ---- changes ------------------------------------------------------------

    def apply(self, label, merge, fn, items=None):
        if self.updating:
            return
        items = items if items is not None else self.selection()
        if not items:
            return
        with self.win.change(label, merge=merge):
            for item in items:
                fn(item)
                refresh_item(item)
        self.win.remember_style(items[-1])
        self.refresh()

    def on_fill_type(self, index):
        key = self.fill_type.itemData(index)

        def fn(item):
            if not item.has_fill:
                return
            kind = key
            if kind in ("linear", "radial") and not item.gradient_fill:
                kind = "solid"
            if kind == "none" and isinstance(item, TextItem):
                kind = "solid"
            item.fill["type"] = kind
        self.apply("Fill type", None, fn)

    def set_fill(self, key, value):
        def fn(item):
            if item.has_fill:
                item.fill[key] = value
        self.apply("Fill", "fill-" + key, fn)

    def on_swap(self):
        def fn(item):
            if item.has_fill:
                f = item.fill
                f["color"], f["color2"] = f.get("color2"), f.get("color")
        self.apply("Swap colours", None, fn)

    def set_stroke(self, key, value):
        def fn(item):
            if item.has_stroke:
                item.stroke[key] = value
        self.apply("Outline", "stroke-" + key, fn)

    def on_opacity(self, value):
        if self.updating:
            return
        self.opacity.blockSignals(True)
        self.opacity_val.blockSignals(True)
        self.opacity.setValue(value)
        self.opacity_val.setValue(value)
        self.opacity.blockSignals(False)
        self.opacity_val.blockSignals(False)
        self.apply("Opacity", "opacity", lambda item: item.setOpacity(value / 100.0))

    def on_radius(self, value):
        def fn(item):
            if isinstance(item, RectItem):
                item.radius = self.px(value)
        self.apply("Corners", "radius", fn)

    def set_shadow(self, key, value):
        self.apply("Shadow", "shadow-" + key,
                   lambda item: item.shadow.__setitem__(key, value))


class FontPicker(QWidget):
    """Pick a font: first a group (classic, modern, script...), then the font.
    Each name in the list is shown in its own lettering."""

    familyChanged = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        self.group = QComboBox()
        for title, key in fonts.GROUPS:
            self.group.addItem(title, key)
        self.group.setToolTip("Show a kind of font")
        self.box = QComboBox()
        self.box.setMaxVisibleItems(18)
        self.box.setMinimumContentsLength(10)
        self.box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        v.addWidget(self.group)
        v.addWidget(self.box)
        self.group.currentIndexChanged.connect(lambda _: self.refill())
        self.box.currentIndexChanged.connect(self._picked)
        self.refill()

    def current(self):
        return self.box.currentData()

    def refill(self, select=None):
        want = select or self.current()
        self.box.blockSignals(True)
        self.box.clear()
        for name in fonts.families_in(self.group.currentData()):
            self.box.addItem(name, name)
            preview = QFont(name)
            preview.setPixelSize(17)
            self.box.setItemData(self.box.count() - 1, preview, Qt.FontRole)
        idx = self.box.findData(want) if want else -1
        if idx < 0 and want:
            self.box.insertItem(0, want, want)
            idx = 0
        self.box.setCurrentIndex(max(idx, 0))
        self.box.blockSignals(False)

    def set_family(self, name):
        if self.box.findData(name) < 0 and self.group.currentData() is not None:
            self.group.blockSignals(True)
            self.group.setCurrentIndex(0)
            self.group.blockSignals(False)
        self.refill(select=name)

    def _picked(self, index):
        name = self.box.itemData(index)
        if name:
            self.familyChanged.emit(name)


class TextPanel(PanelBase):
    """Font, size, spacing and alignment for text."""

    ALIGNS = [("left", "Left", "Line up on the left"),
              ("center", "Centre", "Centre each line"),
              ("right", "Right", "Line up on the right"),
              ("justify", "Justify", "Stretch lines to both edges")]

    def __init__(self, win):
        super().__init__(win)
        L = self.layout_
        self.note = QLabel()
        self.note.setObjectName("hint")
        self.note.setWordWrap(True)
        L.addWidget(self.note)

        box = Section("Character")
        self.family = FontPicker()
        self.size = spin(1, 2000, 1, 1, " pt")
        self.bold = QToolButton()
        self.bold.setText("B")
        self.bold.setCheckable(True)
        f = QFont(self.bold.font())
        f.setBold(True)
        self.bold.setFont(f)
        self.bold.setToolTip("Bold")
        self.italic = QToolButton()
        self.italic.setText("I")
        self.italic.setCheckable(True)
        f = QFont(self.italic.font())
        f.setItalic(True)
        self.italic.setFont(f)
        self.italic.setToolTip("Italic")
        self.caps = QToolButton()
        self.caps.setText("AA")
        self.caps.setCheckable(True)
        self.caps.setToolTip("All capitals")
        self.color = ColorButton("Text colour")
        self.more_fonts = QPushButton("More fonts")
        self.more_fonts.setToolTip("Add fonts you downloaded, or find free ones online")
        menu = QMenu(self.more_fonts)
        menu.addAction("Add font files you downloaded (.ttf, .otf, .zip)…",
                       lambda: self.win.add_fonts())
        menu.addAction("Find free fonts online (Google Fonts)…",
                       lambda: self.win.get_free_fonts())
        self.more_fonts.setMenu(menu)
        box.form.addRow("Font", self.family)
        box.form.addRow("", self.more_fonts)
        box.form.addRow("Size", self.size)
        box.form.addRow("Style", row(self.bold, self.italic, self.caps))
        box.form.addRow("Colour", self.color)
        L.addWidget(box)

        para = Section("Spacing and alignment")
        self.tracking = spin(-50, 300, 1, 1, " %")
        self.tracking.setToolTip("Space between letters")
        self.line = spin(50, 400, 0, 5, " %")
        self.line.setToolTip("Space between lines")
        self.align_group = QButtonGroup(self)
        buttons = []
        for key, text, tip in self.ALIGNS:
            b = QToolButton()
            b.setIcon(icon("text-" + key))
            b.setIconSize(QSize(20, 20))
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setProperty("align", key)
            self.align_group.addButton(b)
            buttons.append(b)
        self.align_group.setExclusive(True)
        para.form.addRow("Letters", self.tracking)
        para.form.addRow("Lines", self.line)
        para.form.addRow("Align", row(*buttons))
        L.addWidget(para)

        self.wrap_box = Section("Text box")
        self.wrap = QCheckBox("Wrap to a fixed width")
        self.wrap.setToolTip("Off: the text box grows as you type.\n"
                             "On: lines wrap at the box width (drag the side handles).")
        self.wrap_box.form.addRow("", self.wrap)
        L.addWidget(self.wrap_box)
        L.addStretch(1)

        self.family.familyChanged.connect(lambda name: self.set_style("family", name))
        self.size.valueChanged.connect(lambda v: self.set_style("size", self.px(v)))
        self.bold.toggled.connect(lambda v: self.set_style("bold", bool(v)))
        self.italic.toggled.connect(lambda v: self.set_style("italic", bool(v)))
        self.caps.toggled.connect(lambda v: self.set_style("caps", bool(v)))
        self.tracking.valueChanged.connect(lambda v: self.set_style("tracking", v))
        self.line.valueChanged.connect(lambda v: self.set_style("line", v))
        self.align_group.buttonClicked.connect(
            lambda b: self.set_style("align", b.property("align")))
        self.color.colorChanged.connect(self.on_color)
        self.wrap.toggled.connect(self.on_wrap)
        self.refresh()

    def texts(self):
        return [i for i in self.selection() if isinstance(i, TextItem)]

    def reload_fonts(self):
        self.updating = True
        try:
            self.family.refill()
        finally:
            self.updating = False

    def refresh(self):
        self.updating = True
        try:
            texts = self.texts()
            if texts:
                style = texts[0].style
                color = qcolor(texts[0].fill.get("color"))
                self.note.setText("")
                self.note.hide()
                self.wrap_box.show()
                self.wrap.setChecked(texts[0].frame_width is not None)
            else:
                style = self.win.text_defaults
                color = qcolor(self.win.text_color)
                self.note.setText("No text selected. These settings are used for the "
                                  "next text you add with the Text tool (T).")
                self.note.show()
                self.wrap_box.hide()
            self.family.set_family(style["family"])
            self.size.setValue(self.pt(style["size"]))
            self.bold.setChecked(bool(style["bold"]))
            self.italic.setChecked(bool(style["italic"]))
            self.caps.setChecked(bool(style["caps"]))
            self.tracking.setValue(float(style["tracking"]))
            self.line.setValue(float(style["line"]))
            for b in self.align_group.buttons():
                b.setChecked(b.property("align") == style["align"])
            self.color.setColor(color)
        finally:
            self.updating = False

    def set_style(self, key, value):
        if self.updating:
            return
        texts = self.texts()
        if not texts:
            self.win.text_defaults[key] = value
            return
        with self.win.change("Text style", merge="text-" + key):
            for item in texts:
                item.style[key] = value
                item.apply_style()
        self.win.text_defaults.update({key: value})
        self.win.after_change()

    def on_color(self, color):
        if self.updating:
            return
        texts = self.texts()
        self.win.text_color = color_str(color)
        if not texts:
            return
        with self.win.change("Text colour", merge="text-color"):
            for item in texts:
                item.fill["type"] = "solid"
                item.fill["color"] = color_str(color)
                item.apply_style()
        self.win.after_change()

    def on_wrap(self, on):
        if self.updating:
            return
        texts = self.texts()
        with self.win.change("Text box"):
            for item in texts:
                item.set_frame_width(item.w if on else None)
        self.win.after_change()


class AnchorGrid(QWidget):
    """Nine squares: which point of the selection X and Y measure, and
    which point stays still when a new size is typed in."""

    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedSize(46, 46)
        self.fx, self.fy = 0.0, 0.0
        self.setToolTip("Which point X and Y measure, and which point stays still "
                        "when you type a new size")

    @staticmethod
    def _dot(i, j):
        return QPointF(7 + i * 16, 7 + j * 16)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#6b6b73"), 1))
        p.drawRect(QRectF(7, 7, 32, 32))
        for i in range(3):
            for j in range(3):
                on = abs(i / 2 - self.fx) < 1e-6 and abs(j / 2 - self.fy) < 1e-6
                p.setBrush(QColor("#4a8fe7") if on else QColor("#2b2b2e"))
                p.setPen(QPen(QColor("#4a8fe7") if on else QColor("#9aa1ab"), 1.2))
                c = self._dot(i, j)
                p.drawRect(QRectF(c.x() - 3.5, c.y() - 3.5, 7, 7))
        p.end()

    def mousePressEvent(self, e):
        best = min(((i, j) for i in range(3) for j in range(3)),
                   key=lambda ij: (self._dot(*ij) - QPointF(e.pos())).manhattanLength())
        self.fx, self.fy = best[0] / 2, best[1] / 2
        self.update()
        self.changed.emit()


class TransformPanel(PanelBase):
    """Exact position, size and rotation."""

    def __init__(self, win):
        super().__init__(win)
        L = self.layout_
        self.x = spin(-1e6, 1e6, 3, 0.1)
        self.y = spin(-1e6, 1e6, 3, 0.1)
        self.w = spin(0.001, 1e6, 3, 0.1)
        self.h = spin(0.001, 1e6, 3, 0.1)
        self.r = spin(-360, 360, 1, 1, "°")
        for box in (self.x, self.y, self.w, self.h, self.r):
            box.setMinimumWidth(70)
        self.lock = QToolButton()
        self.lock.setCheckable(True)
        self.lock.setIcon(icon("lock"))
        self.lock.setToolTip("Keep the width and height in proportion")
        self.anchor = AnchorGrid()
        grid = QGridLayout()
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(4)

        def label(text):
            lab = QLabel(text)
            lab.setObjectName("hint")
            lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            return lab
        grid.addWidget(self.anchor, 0, 0, 2, 1, Qt.AlignTop)
        grid.addWidget(label("X:"), 0, 1)
        grid.addWidget(self.x, 0, 2)
        grid.addWidget(label("W:"), 0, 3)
        grid.addWidget(self.w, 0, 4)
        grid.addWidget(self.lock, 0, 5, 2, 1)
        grid.addWidget(label("Y:"), 1, 1)
        grid.addWidget(self.y, 1, 2)
        grid.addWidget(label("H:"), 1, 3)
        grid.addWidget(self.h, 1, 4)
        grid.addWidget(label("R:"), 2, 1)
        grid.addWidget(self.r, 2, 2)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(4, 1)
        L.addLayout(grid)
        self.hint = QLabel("Measured from the top-left corner of the page, bleed included. "
                           "The anchor picks which point X and Y give.")
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        L.addWidget(self.hint)
        L.addStretch(1)
        self.x.valueChanged.connect(lambda v: self.on_pos("x", v))
        self.y.valueChanged.connect(lambda v: self.on_pos("y", v))
        self.w.valueChanged.connect(lambda v: self.on_size("w", v))
        self.h.valueChanged.connect(lambda v: self.on_size("h", v))
        self.r.valueChanged.connect(self.on_rot)
        self.anchor.changed.connect(self.refresh)
        self.refresh()

    def unit(self):
        return self.scene.doc.unit

    def to_u(self, px):
        return units.from_px(px, self.unit(), self.dpi)

    def to_px(self, v):
        return units.to_px(v, self.unit(), self.dpi)

    def refresh(self):
        self.updating = True
        try:
            u = self.unit()
            dec = units.decimals(u)
            step = {"px": 1, "in": 0.05, "mm": 1, "cm": 0.1, "pt": 1}[u]
            for s in (self.x, self.y, self.w, self.h):
                s.setDecimals(dec)
                s.setSingleStep(step)
                s.setSuffix(" " + u)
            sel = self.selection()
            enabled = bool(sel) and not any(i.locked for i in sel)
            for s in (self.x, self.y, self.w, self.h, self.r, self.lock):
                s.setEnabled(enabled)
            if not sel:
                for s in (self.x, self.y, self.w, self.h, self.r):
                    s.setValue(0)
                return
            box = self.scene.items_rect(sel)
            self.x.setValue(self.to_u(box.left() + self.anchor.fx * box.width()))
            self.y.setValue(self.to_u(box.top() + self.anchor.fy * box.height()))
            if len(sel) == 1:
                it = sel[0]
                self.w.setValue(self.to_u(it.w))
                self.h.setValue(self.to_u(it.h))
                self.h.setEnabled(enabled and not isinstance(it, TextItem))
                self.r.setValue(it.rotation())
            else:
                self.w.setValue(self.to_u(box.width()))
                self.h.setValue(self.to_u(box.height()))
                self.w.setEnabled(False)
                self.h.setEnabled(False)
                self.r.setEnabled(False)
        finally:
            self.updating = False

    def on_pos(self, axis, value):
        if self.updating:
            return
        sel = [i for i in self.selection() if not i.locked]
        if not sel:
            return
        box = self.scene.items_rect(sel)
        target = self.to_px(value)
        if axis == "x":
            d = target - (box.left() + self.anchor.fx * box.width())
        else:
            d = target - (box.top() + self.anchor.fy * box.height())
        with self.win.change("Move", merge="pos-" + axis):
            for item in sel:
                p = item.pos()
                if axis == "x":
                    item.setPos(p.x() + d, p.y())
                else:
                    item.setPos(p.x(), p.y() + d)
        self.win.after_change()

    def on_size(self, axis, value):
        if self.updating:
            return
        sel = self.selection()
        if len(sel) != 1 or sel[0].locked:
            return
        it = sel[0]
        new = self.to_px(value)
        with self.win.change("Resize", merge="size-" + axis):
            fx, fy = self.anchor.fx, self.anchor.fy
            if isinstance(it, TextItem):
                fy = 0.0   # text grows downwards
            anchor = it.mapToScene(QPointF(fx * it.w, fy * it.h))
            if isinstance(it, TextItem):
                it.set_frame_width(new)
            else:
                w, h = it.w, it.h
                if axis == "w":
                    nh = h * new / w if self.lock.isChecked() and w > 0 else h
                    it.resize_content(new, nh)
                else:
                    nw = w * new / h if self.lock.isChecked() and h > 0 else w
                    it.resize_content(nw, new)
            it.place_local_at(QPointF(fx * it.w, fy * it.h), anchor)
        self.win.after_change()

    def on_rot(self, value):
        if self.updating:
            return
        sel = self.selection()
        if len(sel) != 1 or sel[0].locked:
            return
        with self.win.change("Rotate", merge="rotation"):
            sel[0].setRotation(value)
        self.win.after_change()


class LayerTree(QTreeWidget):
    dropped = pyqtSignal()

    def dropEvent(self, e):
        super().dropEvent(e)
        self.dropped.emit()


class LayersPanel(QWidget):
    """Every object, top of the stack first. Drag to restack or move into
    a group. Click the eye to hide, the lock to stop changes."""

    UID = Qt.UserRole
    GID = Qt.UserRole + 1

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.updating = False
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        head = QHBoxLayout()
        label = QLabel("Opacity")
        label.setObjectName("hint")
        head.addWidget(label)
        self.opacity = QComboBox()
        self.opacity.setEditable(True)
        self.opacity.addItems([f"{v} %" for v in range(100, -1, -10)])
        self.opacity.setToolTip("How solid the selected objects are (100 % = not see-through)")
        self.opacity.setMinimumWidth(78)
        head.addWidget(self.opacity)
        self.blend = QComboBox()
        for key, title, _ in BLENDS:
            self.blend.addItem(title, key)
        self.blend.setToolTip("How the selected objects mix with what is under them")
        head.addWidget(self.blend, 1)
        v.addLayout(head)
        self.tree = LayerTree()
        self.tree.setColumnCount(3)
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.setDefaultDropAction(Qt.MoveAction)
        self.tree.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.tree.setIconSize(QSize(18, 18))
        self.tree.setIndentation(16)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.resizeSection(1, 28)
        header.resizeSection(2, 28)
        v.addWidget(self.tree)
        bar = QHBoxLayout()
        for name, tip, fn in (("group", "Group (Ctrl+G)", win.group_selection),
                              ("ungroup", "Ungroup (Ctrl+Shift+G)", win.ungroup_selection),
                              ("forward", "Bring forward (Ctrl+])", lambda: win.arrange("forward")),
                              ("backward", "Send backward (Ctrl+[)", lambda: win.arrange("backward")),
                              ("trash", "Delete", win.delete_selection)):
            b = QToolButton()
            b.setIcon(icon(name))
            b.setToolTip(tip)
            b.clicked.connect(fn)
            bar.addWidget(b)
        bar.addStretch(1)
        v.addLayout(bar)
        self.opacity.activated.connect(lambda _: self.on_opacity())
        self.blend.activated.connect(lambda _: self.on_blend())
        self.opacity.lineEdit().editingFinished.connect(self.on_opacity)
        self.tree.itemSelectionChanged.connect(self.on_tree_selection)
        self.tree.itemClicked.connect(self.on_clicked)
        self.tree.itemChanged.connect(self.on_renamed)
        self.tree.dropped.connect(self.on_dropped)

    @property
    def scene(self):
        return self.win.scene

    def rebuild(self):
        self.updating = True
        try:
            expanded = {self.tree.topLevelItem(i).data(0, self.GID)
                        for i in range(self.tree.topLevelItemCount())
                        if self.tree.topLevelItem(i).isExpanded()}
            self.tree.clear()
            items = list(reversed(self.scene.folio_items()))
            groups = {}
            for item in items:
                if item.group:
                    node = groups.get(item.group)
                    if node is None:
                        node = QTreeWidgetItem([self.scene.groups.get(item.group, "Group"), "", ""])
                        node.setData(0, self.GID, item.group)
                        node.setIcon(0, icon("group"))
                        node.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
                                      | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
                        self.tree.addTopLevelItem(node)
                        groups[item.group] = node
                        node.setExpanded(item.group in expanded)
                    parent = node
                else:
                    parent = None
                child = QTreeWidgetItem([item.display_name(), "", ""])
                child.setData(0, self.UID, item.uid)
                child.setIcon(0, icon(self._icon_name(item)))
                child.setIcon(1, icon("eye" if item.isVisible() else "eye-off"))
                child.setIcon(2, icon("lock" if item.locked else "unlock"))
                child.setToolTip(1, "Show or hide")
                child.setToolTip(2, "Lock or unlock")
                child.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
                               | Qt.ItemIsDragEnabled)
                if parent is None:
                    self.tree.addTopLevelItem(child)
                else:
                    parent.addChild(child)
            for node in groups.values():
                members = self.scene.group_members(node.data(0, self.GID))
                visible = any(m.isVisible() for m in members)
                locked = all(m.locked for m in members)
                node.setIcon(1, icon("eye" if visible else "eye-off"))
                node.setIcon(2, icon("lock" if locked else "unlock"))
            self.sync_selection()
        finally:
            self.updating = False

    @staticmethod
    def _icon_name(item):
        return {"rect": "rect", "ellipse": "ellipse", "path": "pen", "text": "text",
                "image": "image"}.get(item.kind, "rect")

    def all_nodes(self):
        out = []
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            out.append(top)
            for j in range(top.childCount()):
                out.append(top.child(j))
        return out

    def on_opacity(self):
        if self.updating:
            return
        try:
            value = float(self.opacity.currentText().replace("%", "").strip())
        except ValueError:
            return
        value = min(max(value, 0.0), 100.0)
        items = [i for i in self.scene.selected_folio() if not i.locked]
        if not items:
            return
        with self.win.change("Opacity", merge="opacity"):
            for item in items:
                item.setOpacity(value / 100.0)
        self.win.after_change()

    def on_blend(self):
        if self.updating:
            return
        key = self.blend.currentData()
        items = [i for i in self.scene.selected_folio() if not i.locked]
        if not items:
            return
        with self.win.change("Blend mode"):
            for item in items:
                item.blend = key
                item.update()
        self.win.after_change()

    def sync_selection(self):
        was = self.updating
        self.updating = True
        try:
            sel = self.scene.selected_folio()
            self.blend.setEnabled(bool(sel))
            self.blend.setCurrentIndex(max(0, self.blend.findData(sel[0].blend if sel else "normal")))
            self.opacity.setEnabled(bool(sel))
            self.opacity.setEditText(f"{round(sel[0].opacity() * 100)} %" if sel else "100 %")
            chosen = {i.uid for i in sel}
            self.tree.blockSignals(True)
            for node in self.all_nodes():
                uid = node.data(0, self.UID)
                gid = node.data(0, self.GID)
                if uid:
                    node.setSelected(uid in chosen)
                elif gid:
                    members = self.scene.group_members(gid)
                    node.setSelected(bool(members) and all(m.uid in chosen for m in members))
            self.tree.blockSignals(False)
            self.tree.viewport().update()
        finally:
            self.updating = was

    def on_tree_selection(self):
        if self.updating:
            return
        chosen = []
        for node in self.tree.selectedItems():
            uid = node.data(0, self.UID)
            gid = node.data(0, self.GID)
            if uid:
                item = self.scene.find(uid)
                if item is not None:
                    chosen.append(item)
            elif gid:
                chosen.extend(self.scene.group_members(gid))
        self.win.stop_text_editing()
        self.scene.select_only(chosen)

    def node_items(self, node):
        uid = node.data(0, self.UID)
        gid = node.data(0, self.GID)
        if uid:
            item = self.scene.find(uid)
            return [item] if item is not None else []
        return self.scene.group_members(gid) if gid else []

    def on_clicked(self, node, column):
        if self.updating or column not in (1, 2):
            return
        items = self.node_items(node)
        if not items:
            return
        if column == 1:
            show = not any(i.isVisible() for i in items)
            with self.win.change("Show" if show else "Hide"):
                for i in items:
                    i.setVisible(show)
        else:
            lock = not all(i.locked for i in items)
            with self.win.change("Lock" if lock else "Unlock"):
                for i in items:
                    i.locked = lock
        self.win.after_change()

    def on_renamed(self, node, column):
        if self.updating or column != 0:
            return
        text = node.text(0).strip()
        uid = node.data(0, self.UID)
        gid = node.data(0, self.GID)
        with self.win.change("Rename"):
            if uid:
                item = self.scene.find(uid)
                if item is not None:
                    item.name = "" if text == item.default_name() else text
            elif gid:
                self.scene.groups[gid] = text or "Group"
        self.win.after_change()

    def on_dropped(self):
        """Read the new stacking order and grouping back from the tree."""
        order = []

        def walk(node, gid):
            uid = node.data(0, self.UID)
            own = node.data(0, self.GID)
            if uid:
                item = self.scene.find(uid)
                if item is not None:
                    order.append((item, gid))
            for j in range(node.childCount()):
                walk(node.child(j), gid or own)

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i), None)
        with self.win.change("Restack"):
            for item, gid in order:
                item.group = gid
            self.scene.set_order([item for item, _ in reversed(order)])
            self.scene.prune_groups()
        self.win.after_change()
