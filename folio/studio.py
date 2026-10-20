"""Studio panels laid out the way pro design apps do it: Colour (a hue ring
around a triangle), Swatches, Stroke and Navigator, plus the small
fill-and-outline picker they share.

Colours always go to the "target": the fill or the outline of what is
selected, or, when nothing is selected, the look new shapes get.
"""

import json
import math

from PyQt5.QtCore import QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (QBrush, QColor, QConicalGradient, QImage, QLinearGradient,
                         QPainter, QPainterPath, QPen)
from PyQt5.QtWidgets import (QButtonGroup, QComboBox, QGridLayout, QHBoxLayout, QLabel,
                             QLineEdit, QSizePolicy, QSlider, QSpinBox, QToolButton,
                             QVBoxLayout, QWidget)

from .icons import icon
from .items import TextItem, color_str, qcolor
from .panels import PanelBase, ColorButton, spin

ACCENT = QColor("#4a8fe7")


def _checker(p, rect, cell=4):
    p.save()
    p.setClipRect(rect)
    p.fillRect(rect, QColor("#ffffff"))
    y, j = rect.top(), 0
    while y < rect.bottom():
        x = rect.left() + (cell if j % 2 else 0)
        while x < rect.right():
            p.fillRect(QRectF(x, y, cell, cell), QColor("#c8c8c8"))
            x += 2 * cell
        y += cell
        j += 1
    p.restore()


def _foot(p, a, b):
    """The point on the line through a and b nearest to p."""
    d = b - a
    t = ((p.x() - a.x()) * d.x() + (p.y() - a.y()) * d.y()) / max(d.x() ** 2 + d.y() ** 2, 1e-9)
    return a + d * t


class ColourWheel(QWidget):
    """A hue ring with a triangle inside for how strong and how bright."""

    colourChanged = pyqtSignal(QColor)   # while dragging
    colourPicked = pyqtSignal(QColor)    # when the mouse is let go

    def __init__(self):
        super().__init__()
        self.h, self.s, self.v, self.alpha = 0.0, 1.0, 1.0, 255
        self._drag = None
        self._cache = None
        self.setMinimumSize(170, 170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.CrossCursor)

    def sizeHint(self):
        return QSize(220, 220)

    def set_colour(self, c):
        c = QColor(c)
        if c.hsvHueF() >= 0:
            self.h = c.hsvHueF()
        self.s, self.v, self.alpha = c.hsvSaturationF(), c.valueF(), c.alpha()
        self.update()

    def colour(self):
        return QColor.fromHsvF(self.h % 1.0, self.s, self.v, self.alpha / 255.0)

    def _geometry(self):
        side = min(self.width(), self.height()) - 6
        c = QPointF(self.width() / 2, self.height() / 2)
        outer = side / 2
        return c, outer, outer * 0.8

    def _vertices(self):
        c, _, inner = self._geometry()
        r = inner - 3

        def at(deg):
            a = math.radians(deg)
            return QPointF(c.x() + r * math.cos(a), c.y() - r * math.sin(a))

        base = self.h * 360.0
        return at(base), at(base + 240.0), at(base + 120.0)   # hue, white, black

    def _triangle_image(self, hv, wv, bv):
        key = (self.width(), self.height(), round(self.h, 4))
        if self._cache and self._cache[0] == key:
            return self._cache[1]
        image = QImage(self.size(), QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        p = QPainter(image)
        # colour = (hue weight) x hue + (white weight) x white; each weight is a straight ramp
        g = QLinearGradient(hv, _foot(hv, wv, bv))
        g.setColorAt(0, QColor.fromHsvF(self.h % 1.0, 1, 1))
        g.setColorAt(1, QColor(0, 0, 0))
        p.fillRect(image.rect(), g)
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        g = QLinearGradient(wv, _foot(wv, hv, bv))
        g.setColorAt(0, QColor(255, 255, 255))
        g.setColorAt(1, QColor(0, 0, 0))
        p.fillRect(image.rect(), g)
        p.end()
        self._cache = (key, image)
        return image

    def _point(self):
        hv, wv, bv = self._vertices()
        edge = wv + (hv - wv) * self.s
        return bv + (edge - bv) * self.v

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c, outer, inner = self._geometry()
        ring = QPainterPath()
        ring.addEllipse(c, outer, outer)
        hole = QPainterPath()
        hole.addEllipse(c, inner, inner)
        grad = QConicalGradient(c, 0)
        for i in range(13):
            grad.setColorAt(i / 12.0, QColor.fromHsvF((i / 12.0) % 1.0, 1, 1))
        p.fillPath(ring.subtracted(hole), QBrush(grad))
        hv, wv, bv = self._vertices()
        tri = QPainterPath()
        tri.moveTo(hv)
        tri.lineTo(wv)
        tri.lineTo(bv)
        tri.closeSubpath()
        p.fillPath(tri, QBrush(self._triangle_image(hv, wv, bv)))
        # where the hue is on the ring
        a = math.radians(self.h * 360.0)
        mid = (outer + inner) / 2
        mark = QPointF(c.x() + mid * math.cos(a), c.y() - mid * math.sin(a))
        size = (outer - inner) * 0.42
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(0, 0, 0, 160), 3))
        p.drawEllipse(mark, size, size)
        p.setPen(QPen(QColor("#ffffff"), 1.5))
        p.drawEllipse(mark, size, size)
        # the chosen colour in the triangle
        pt = self._point()
        p.setPen(QPen(QColor(0, 0, 0, 170), 3))
        p.drawEllipse(pt, 5, 5)
        p.setPen(QPen(QColor("#ffffff"), 1.5))
        p.drawEllipse(pt, 5, 5)
        p.end()

    def _pick(self, pos):
        c, outer, inner = self._geometry()
        if self._drag == "ring":
            ang = math.degrees(math.atan2(-(pos.y() - c.y()), pos.x() - c.x())) % 360.0
            self.h = ang / 360.0
        else:
            hv, wv, bv = self._vertices()
            dx, dy = pos.x() - bv.x(), pos.y() - bv.y()
            ax, ay = wv.x() - bv.x(), wv.y() - bv.y()
            bx, by = hv.x() - wv.x(), hv.y() - wv.y()
            det = ax * by - bx * ay
            if abs(det) < 1e-9:
                return
            a = (dx * by - bx * dy) / det
            b = (ax * dy - dx * ay) / det
            a = min(max(a, 0.0), 1.0)
            b = min(max(b, 0.0), a)
            self.v = a
            if a > 1e-6:
                self.s = b / a
        self.update()
        self.colourChanged.emit(self.colour())

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        c, outer, inner = self._geometry()
        d = math.hypot(e.pos().x() - c.x(), e.pos().y() - c.y())
        self._drag = "ring" if inner - 2 <= d <= outer + 4 else "tri" if d < inner else None
        if self._drag:
            self._pick(QPointF(e.pos()))

    def mouseMoveEvent(self, e):
        if self._drag:
            self._pick(QPointF(e.pos()))

    def mouseReleaseEvent(self, e):
        if self._drag:
            self._drag = None
            self.colourPicked.emit(self.colour())


class FillStrokeSelector(QWidget):
    """Two circles: the fill (solid) and the outline (a ring). Click one
    to choose which the colour panels change. The arrow swaps them; the
    crossed circle takes the colour away."""

    targetChanged = pyqtSignal(str)
    swapClicked = pyqtSignal()
    noneClicked = pyqtSignal()

    FILL = QRectF(2, 2, 26, 26)
    STROKE = QRectF(20, 18, 26, 26)
    SWAP = QRectF(38, 1, 12, 12)
    NONE = QRectF(2, 39, 12, 12)

    def __init__(self, scale=1.0):
        super().__init__()
        self.scale = scale
        self.setFixedSize(round(54 * scale), round(54 * scale))
        self.target = "fill"
        self.fill = QColor("#3d7bd9")
        self.stroke = QColor("#000000")
        self.fill_none = False
        self.stroke_none = True
        self.setToolTip("Click the solid circle to colour the fill, the ring to colour "
                        "the outline. The arrow swaps them.")

    def set_state(self, fill, stroke, fill_none, stroke_none):
        self.fill, self.stroke = QColor(fill), QColor(stroke)
        self.fill_none, self.stroke_none = fill_none, stroke_none
        self.update()

    def set_target(self, target):
        self.target = target
        self.update()

    def _slash(self, p, r):
        p.setPen(QPen(QColor("#e05555"), 2))
        p.drawLine(QPointF(r.left() + 4, r.bottom() - 4), QPointF(r.right() - 4, r.top() + 4))

    def _draw_fill(self, p):
        r = self.FILL
        path = QPainterPath()
        path.addEllipse(r)
        if self.fill_none:
            p.fillPath(path, QColor("#ffffff"))
        else:
            p.save()
            p.setClipPath(path)
            _checker(p, r)
            p.restore()
            p.fillPath(path, self.fill)
        p.setPen(QPen(ACCENT if self.target == "fill" else QColor("#6b6b73"), 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(r)
        if self.fill_none:
            self._slash(p, r)

    def _draw_stroke(self, p):
        r = self.STROKE
        ring = QPainterPath()
        ring.addEllipse(r)
        hole = QPainterPath()
        hole.addEllipse(r.adjusted(7, 7, -7, -7))
        band = ring.subtracted(hole)
        if self.stroke_none:
            p.fillPath(band, QColor("#ffffff"))
        else:
            p.save()
            p.setClipPath(band)
            _checker(p, r)
            p.restore()
            p.fillPath(band, self.stroke)
        p.setPen(QPen(ACCENT if self.target == "stroke" else QColor("#6b6b73"), 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(r)
        p.drawEllipse(r.adjusted(7, 7, -7, -7))
        if self.stroke_none:
            self._slash(p, r)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(self.scale, self.scale)
        if self.target == "fill":
            self._draw_stroke(p)
            self._draw_fill(p)
        else:
            self._draw_fill(p)
            self._draw_stroke(p)
        # swap arrow
        p.setPen(QPen(QColor("#c9ccd2"), 1.3))
        s = self.SWAP
        path = QPainterPath()
        path.moveTo(s.left() + 1, s.bottom() - 2)
        path.quadTo(s.left() + 1, s.top() + 2, s.right() - 2, s.top() + 2)
        p.drawPath(path)
        p.drawLine(QPointF(s.right() - 4.5, s.top()), QPointF(s.right() - 2, s.top() + 2))
        p.drawLine(QPointF(s.right() - 4.5, s.top() + 4.5), QPointF(s.right() - 2, s.top() + 2))
        # "no colour"
        n = self.NONE
        p.setBrush(QColor("#ffffff"))
        p.setPen(QPen(QColor("#6b6b73"), 1))
        p.drawEllipse(n)
        p.setPen(QPen(QColor("#e05555"), 1.5))
        p.drawLine(QPointF(n.left() + 2, n.bottom() - 2), QPointF(n.right() - 2, n.top() + 2))
        p.end()

    def mousePressEvent(self, e):
        pos = QPointF(e.pos()) / self.scale
        if self.SWAP.adjusted(-2, -2, 2, 2).contains(pos):
            self.swapClicked.emit()
            return
        if self.NONE.adjusted(-2, -2, 2, 2).contains(pos):
            self.noneClicked.emit()
            return
        on_top = self.FILL if self.target == "fill" else self.STROKE

        def inside(r):
            c = r.center()
            return math.hypot(pos.x() - c.x(), pos.y() - c.y()) <= r.width() / 2
        if inside(on_top):
            pick = self.target
        elif inside(self.FILL):
            pick = "fill"
        elif inside(self.STROKE):
            pick = "stroke"
        else:
            return
        if pick != self.target:
            self.targetChanged.emit(pick)


class ColourPanel(QWidget):
    """Colour: the wheel, the colour code and how see-through it is."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.updating = False
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)
        top = QHBoxLayout()
        self.selector = FillStrokeSelector()
        top.addWidget(self.selector)
        top.addStretch(1)
        for name, tip in (("#000000", "Black"), ("#ffffff", "White")):
            b = QToolButton()
            b.setFixedSize(16, 16)
            b.setToolTip(tip)
            b.setStyleSheet("QToolButton { background: %s; border: 1px solid #5a5a5a; "
                            "border-radius: 0; padding: 0; }" % name)
            b.clicked.connect(lambda _=False, c=name: self.quick(c))
            top.addWidget(b)
        top.addSpacing(6)
        self.picker = QToolButton()
        self.picker.setIcon(icon("eyedropper"))
        self.picker.setToolTip("Pick a colour from the page: click this, then click the page")
        top.addWidget(self.picker)
        v.addLayout(top)
        self.wheel = ColourWheel()
        v.addWidget(self.wheel, 1)
        info = QHBoxLayout()
        self.hsb = QLabel()
        self.hsb.setObjectName("hint")
        info.addWidget(self.hsb)
        info.addStretch(1)
        info.addWidget(QLabel("#"))
        self.hex = QLineEdit()
        self.hex.setMaximumWidth(84)
        self.hex.setToolTip("The colour code, like FF0000 for red")
        info.addWidget(self.hex)
        v.addLayout(info)
        op = QHBoxLayout()
        label = QLabel("Opacity")
        label.setObjectName("hint")
        op.addWidget(label)
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(0, 100)
        op.addWidget(self.opacity, 1)
        self.opacity_val = QSpinBox()
        self.opacity_val.setRange(0, 100)
        self.opacity_val.setSuffix(" %")
        self.opacity_val.setKeyboardTracking(False)
        op.addWidget(self.opacity_val)
        v.addLayout(op)

        self.selector.targetChanged.connect(win.set_colour_target)
        self.selector.swapClicked.connect(win.swap_fill_stroke)
        self.selector.noneClicked.connect(win.clear_colour)
        self.picker.clicked.connect(win.start_colour_pick)
        self.wheel.colourChanged.connect(self.on_wheel)
        self.wheel.colourPicked.connect(win.remember_colour)
        self.hex.editingFinished.connect(self.on_hex)
        self.opacity.valueChanged.connect(self.on_opacity)
        self.opacity_val.valueChanged.connect(self.on_opacity)

    def refresh(self):
        self.updating = True
        try:
            fill, stroke, fill_none, stroke_none = self.win.colour_state()
            self.selector.set_state(fill, stroke, fill_none, stroke_none)
            self.selector.set_target(self.win.colour_target)
            c = fill if self.win.colour_target == "fill" else stroke
            self.wheel.set_colour(c)
            self.show_values(c)
        finally:
            self.updating = False

    def quick(self, name):
        c = QColor(name)
        c.setAlpha(round(self.opacity_val.value() * 2.55))
        self.wheel.set_colour(c)
        self.win.apply_colour(c, merge=False)
        self.win.remember_colour(c)

    def show_values(self, c):
        h = max(c.hslHue(), 0)
        self.hsb.setText(f"H: {h}   S: {round(c.hslSaturationF() * 100)}   "
                         f"L: {round(c.lightnessF() * 100)}")
        if not self.hex.hasFocus():
            self.hex.setText(c.name()[1:].upper())
        pct = round(c.alphaF() * 100)
        for w in (self.opacity, self.opacity_val):
            w.blockSignals(True)
            w.setValue(pct)
            w.blockSignals(False)

    def on_wheel(self, c):
        if self.updating:
            return
        c.setAlpha(round(self.opacity_val.value() * 2.55))
        self.show_values(c)
        self.win.apply_colour(c)

    def on_hex(self):
        c = QColor("#" + self.hex.text().strip().lstrip("#"))
        if not c.isValid():
            return
        c.setAlpha(round(self.opacity_val.value() * 2.55))
        self.wheel.set_colour(c)
        self.win.apply_colour(c, merge=False)
        self.win.remember_colour(c)

    def on_opacity(self, value):
        if self.updating:
            return
        for w in (self.opacity, self.opacity_val):
            w.blockSignals(True)
            w.setValue(value)
            w.blockSignals(False)
        c = self.wheel.colour()
        c.setAlpha(round(value * 2.55))
        self.wheel.set_colour(c)
        self.win.apply_colour(c, label="Colour opacity")


# ---- swatches --------------------------------------------------------------------

def _hue_palette():
    out = []
    rows = [(0.35, 1.0), (0.6, 1.0), (0.85, 1.0), (1.0, 1.0), (1.0, 0.78), (1.0, 0.55), (1.0, 0.35)]
    for sat, val in rows:
        for i in range(16):
            out.append(QColor.fromHsvF(i / 16.0, sat, val))
    for i in range(16):
        g = round(255 * i / 15)
        out.append(QColor(g, g, g))
    return out


BOOK_COLOURS = ["#0b132b", "#14213d", "#1d3557", "#274c77", "#1b6f73", "#2d4a22",
                "#556b2f", "#8a9a5b", "#d4a82f", "#e1ad01", "#c8a27a", "#5d3a1a",
                "#6d1a36", "#a4161a", "#d00000", "#ff6f59", "#f4c2c2", "#5b2a86",
                "#b8a1d9", "#2b2d42", "#6c757d", "#f3e9d2", "#fffff0", "#ffffff",
                "#000000"]


class SwatchGrid(QWidget):
    """Little squares of colour; click one to use it."""

    picked = pyqtSignal(QColor)
    removeRequested = pyqtSignal(int)

    GAP = 2
    COLUMNS = 16

    def __init__(self):
        super().__init__()
        self.colours = []
        self.removable = False
        self.setMouseTracking(True)
        sp = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)

    def set_colours(self, colours):
        self.colours = [QColor(c) for c in colours]
        self.updateGeometry()
        self.update()

    def cell(self, width=None):
        """Squares are sized so 16 fit across, like a row of hues."""
        width = width or self.width()
        return max(10, min(24, (width + self.GAP) // self.COLUMNS - self.GAP))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        rows = max(1, math.ceil(len(self.colours) / self.COLUMNS))
        return rows * (self.cell(width) + self.GAP)

    def sizeHint(self):
        return QSize(280, self.heightForWidth(280))

    def minimumSizeHint(self):
        return QSize(16 * 12, self.heightForWidth(16 * 12))

    def cell_rect(self, i):
        size = self.cell()
        x = (i % self.COLUMNS) * (size + self.GAP)
        y = (i // self.COLUMNS) * (size + self.GAP)
        return QRectF(x, y, size, size)

    def index_at(self, pos):
        for i in range(len(self.colours)):
            if self.cell_rect(i).contains(QPointF(pos)):
                return i
        return -1

    def paintEvent(self, e):
        p = QPainter(self)
        for i, c in enumerate(self.colours):
            r = self.cell_rect(i)
            if c.alpha() < 255:
                _checker(p, r)
            p.fillRect(r, c)
            p.setPen(QColor(0, 0, 0, 90))
            p.drawRect(r.adjusted(0, 0, -1, -1))
        p.end()

    def mouseMoveEvent(self, e):
        i = self.index_at(e.pos())
        self.setToolTip("#" + self.colours[i].name()[1:].upper() if i >= 0 else "")

    def mousePressEvent(self, e):
        i = self.index_at(e.pos())
        if i < 0:
            return
        if e.button() == Qt.RightButton and self.removable:
            self.removeRequested.emit(i)
        elif e.button() == Qt.LeftButton:
            self.picked.emit(QColor(self.colours[i]))


class SwatchesPanel(PanelBase):
    """Swatches: recent colours and ready-made palettes."""

    PALETTES = ["Colours", "Book cover colours", "Colours in this document", "My colours"]

    def __init__(self, win):
        super().__init__(win)
        L = self.layout_
        top = QHBoxLayout()
        self.selector = FillStrokeSelector()
        top.addWidget(self.selector)
        top.addStretch(1)
        L.addLayout(top)
        recent = QLabel("Recent")
        recent.setObjectName("hint")
        L.addWidget(recent)
        self.recent = SwatchGrid()
        L.addWidget(self.recent)
        self.recent_hint = QLabel("Colours you use show up here.")
        self.recent_hint.setObjectName("hint")
        L.addWidget(self.recent_hint)
        row_ = QHBoxLayout()
        self.palette = QComboBox()
        self.palette.addItems(self.PALETTES)
        row_.addWidget(self.palette, 1)
        self.add_btn = QToolButton()
        self.add_btn.setIcon(icon("plus"))
        self.add_btn.setToolTip("Add the current colour to My colours")
        row_.addWidget(self.add_btn)
        L.addLayout(row_)
        self.grid = SwatchGrid()
        L.addWidget(self.grid)
        self.hint = QLabel()
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        L.addWidget(self.hint)
        L.addStretch(1)
        self.selector.targetChanged.connect(win.set_colour_target)
        self.selector.swapClicked.connect(win.swap_fill_stroke)
        self.selector.noneClicked.connect(win.clear_colour)
        for grid in (self.recent, self.grid):
            grid.picked.connect(self.on_pick)
        self.grid.removeRequested.connect(self.remove_mine)
        self.palette.currentIndexChanged.connect(lambda _: self.fill_grid())
        self.add_btn.clicked.connect(self.add_current)
        self.fill_grid()

    def mine(self):
        try:
            return json.loads(self.win.settings.value("my_colours", "[]") or "[]")
        except ValueError:
            return []

    def fill_grid(self):
        which = self.palette.currentText()
        self.grid.removable = which == "My colours"
        if which == "Colours":
            colours = _hue_palette()
            hint = ""
        elif which == "Book cover colours":
            colours = [QColor(c) for c in BOOK_COLOURS]
            hint = "Colours that suit book covers: deep blues, greens, golds and creams."
        elif which == "Colours in this document":
            colours = self.document_colours()
            hint = "" if colours else "Nothing coloured on the page yet."
        else:
            colours = [QColor(c) for c in self.mine()]
            hint = ("Right-click a colour to remove it." if colours else
                    "Click + to keep the current colour here.")
        self.grid.set_colours(colours)
        self.hint.setText(hint)
        self.hint.setVisible(bool(hint))

    def document_colours(self):
        seen = []
        for item in self.win.scene.folio_items():
            values = []
            if item.has_fill and item.fill.get("type") != "none":
                values.append(item.fill.get("color"))
                if item.fill.get("type") in ("linear", "radial"):
                    values.append(item.fill.get("color2"))
            if item.stroke_width() > 0:
                values.append(item.stroke.get("color"))
            for v in values:
                c = qcolor(v)
                if c.alpha() > 0 and c.name(QColor.HexArgb) not in [s.name(QColor.HexArgb) for s in seen]:
                    seen.append(c)
        return seen[:64]

    def refresh(self):
        fill, stroke, fill_none, stroke_none = self.win.colour_state()
        self.selector.set_state(fill, stroke, fill_none, stroke_none)
        self.selector.set_target(self.win.colour_target)
        self.recent.set_colours([QColor(c) for c in self.win.recent_colours])
        self.recent.setVisible(bool(self.win.recent_colours))
        self.recent_hint.setVisible(not self.win.recent_colours)
        if self.palette.currentText() == "Colours in this document":
            self.fill_grid()

    def on_pick(self, c):
        self.win.apply_colour(c, merge=False)
        self.win.remember_colour(c)

    def add_current(self):
        fill, stroke, _, _ = self.win.colour_state()
        c = fill if self.win.colour_target == "fill" else stroke
        mine = self.mine()
        name = color_str(c)
        if name not in mine:
            mine.append(name)
            self.win.settings.setValue("my_colours", json.dumps(mine))
        self.palette.setCurrentText("My colours")
        self.fill_grid()

    def remove_mine(self, index):
        mine = self.mine()
        if 0 <= index < len(mine):
            del mine[index]
            self.win.settings.setValue("my_colours", json.dumps(mine))
            self.fill_grid()


# ---- stroke ------------------------------------------------------------------------

class StrokePanel(PanelBase):
    """Stroke: the outline's style, width, ends, corners and where it sits."""

    STYLES = [("none", "No outline"), ("solid", "Solid"), ("dash", "Dashed"),
              ("dot", "Dotted"), ("dashdot", "Dash and dot")]
    CAPS = [("butt", "Flat ends"), ("round", "Round ends"), ("square", "Square ends")]
    JOINS = [("miter", "Sharp corners"), ("round", "Round corners"), ("bevel", "Cut-off corners")]
    ALIGNS = [("center", "Outline centred on the edge"), ("inside", "Outline inside the edge"),
              ("outside", "Outline outside the edge")]

    def __init__(self, win):
        super().__init__(win)
        g = QGridLayout()
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(8)
        self.groups = {}

        def buttons(key, choices, prefix):
            box = QHBoxLayout()
            box.setSpacing(2)
            group = QButtonGroup(self)
            group.setExclusive(True)
            for value, tip in choices:
                b = QToolButton()
                b.setIcon(icon(prefix + value))
                b.setToolTip(tip)
                b.setCheckable(True)
                b.setProperty("value", value)
                group.addButton(b)
                box.addWidget(b)
            box.addStretch(1)
            group.buttonClicked.connect(lambda b, k=key: self.on_button(k, b.property("value")))
            self.groups[key] = group
            return box

        def label(text):
            lab = QLabel(text)
            lab.setObjectName("hint")
            return lab

        g.addWidget(label("Style"), 0, 0)
        g.addLayout(buttons("style", self.STYLES, "stroke-"), 0, 1)
        self.width = QSlider(Qt.Horizontal)
        self.width.setRange(0, 200)   # half points
        self.width_val = spin(0, 1000, 1, 0.5, " pt")
        wrow = QHBoxLayout()
        wrow.addWidget(self.width, 1)
        wrow.addWidget(self.width_val)
        g.addWidget(label("Width"), 1, 0)
        g.addLayout(wrow, 1, 1)
        g.addWidget(label("Cap"), 2, 0)
        g.addLayout(buttons("cap", self.CAPS, "cap-"), 2, 1)
        jrow = buttons("join", self.JOINS, "join-")
        self.miter = spin(1, 20, 1, 0.5)
        self.miter.setToolTip("How far sharp corners may stick out before they are cut off")
        self.miter.setMinimumWidth(64)
        jrow.addWidget(label("Miter"))
        jrow.addWidget(self.miter)
        g.addWidget(label("Join"), 3, 0)
        g.addLayout(jrow, 3, 1)
        g.addWidget(label("Align"), 4, 0)
        g.addLayout(buttons("align", self.ALIGNS, "stroke-"), 4, 1)
        self.colour = ColorButton("Outline colour")
        g.addWidget(label("Colour"), 5, 0)
        g.addWidget(self.colour, 5, 1)
        self.layout_.addLayout(g)
        self.note = QLabel()
        self.note.setObjectName("hint")
        self.note.setWordWrap(True)
        self.layout_.addWidget(self.note)
        self.layout_.addStretch(1)
        self.width.valueChanged.connect(lambda v: self.on_width(v / 2.0))
        self.width_val.valueChanged.connect(self.on_width)
        self.miter.valueChanged.connect(lambda v: self.set_key("miter", v))
        self.colour.colorChanged.connect(lambda c: self.set_key("color", color_str(c)))

    def stroke(self):
        sel = self.selection()
        return dict(sel[0].stroke) if sel else dict(self.win.style_stroke)

    def refresh(self):
        self.updating = True
        try:
            s = self.stroke()
            pt = self.pt(float(s.get("width", 0.0)))
            style = "none" if pt <= 0 else s.get("dash", "solid")
            values = {"style": style, "cap": s.get("cap") or ("round" if style == "dot" else "butt"),
                      "join": s.get("join") or "miter", "align": s.get("align", "center")}
            for key, group in self.groups.items():
                for b in group.buttons():
                    b.setChecked(b.property("value") == values[key])
            self.width.setValue(min(200, round(pt * 2)))
            self.width_val.setValue(pt)
            self.miter.setValue(float(s.get("miter", 2.0)))
            self.colour.setColor(qcolor(s.get("color")))
            sel = self.selection()
            text = sel and all(isinstance(i, TextItem) for i in sel)
            self.note.setText("For text, the outline goes round each letter." if text else
                              "" if sel else "Nothing selected: this sets how new shapes look.")
            self.note.setVisible(bool(self.note.text()))
        finally:
            self.updating = False

    def apply(self, fn, label, merge):
        if self.updating:
            return
        items = [i for i in self.selection() if not i.locked and i.has_stroke]
        if not items:
            fn(self.win.style_stroke)
            self.refresh()
            return
        with self.win.change(label, merge=merge):
            for item in items:
                fn(item.stroke)
                item.prepareGeometryChange()
                if isinstance(item, TextItem):
                    item.apply_style()
                else:
                    item.changed()
        self.win.remember_style(items[-1])
        self.refresh()

    def set_key(self, key, value):
        self.apply(lambda s: s.__setitem__(key, value), "Outline", "stroke-" + key)

    def on_width(self, pt):
        px = self.px(pt)
        self.apply(lambda s: s.__setitem__("width", px), "Outline width", "stroke-width")

    def on_button(self, key, value):
        if key == "style":
            one_pt = self.px(1.0)

            def fn(s):
                if value == "none":
                    s["width"] = 0.0
                else:
                    s["dash"] = value
                    if float(s.get("width", 0.0)) <= 0:
                        s["width"] = one_pt
            self.apply(fn, "Outline style", None)
        else:
            self.set_key(key, value)


# ---- navigator ---------------------------------------------------------------------

class _NavView(QWidget):
    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.setMinimumHeight(150)
        self.setCursor(Qt.OpenHandCursor)

    def page_box(self):
        thumb = self.panel.thumb
        if thumb is None:
            return QRectF()
        avail = QRectF(self.rect()).adjusted(6, 6, -6, -6)
        s = min(avail.width() / thumb.width(), avail.height() / thumb.height())
        w, h = thumb.width() * s, thumb.height() * s
        return QRectF(avail.center().x() - w / 2, avail.center().y() - h / 2, w, h)

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#1c1c1f"))
        thumb = self.panel.thumb
        if thumb is None:
            return
        box = self.page_box()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(box, thumb)
        view = self.panel.win.view
        page = self.panel.win.scene.doc.page_rect()
        seen = view.mapToScene(view.viewport().rect()).boundingRect()
        sx, sy = box.width() / page.width(), box.height() / page.height()
        r = QRectF(box.left() + (seen.left() - page.left()) * sx,
                   box.top() + (seen.top() - page.top()) * sy,
                   seen.width() * sx, seen.height() * sy)
        p.setPen(QPen(QColor("#ff4d4d"), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawRect(r.intersected(QRectF(self.rect()).adjusted(1, 1, -1, -1)))
        p.end()

    def _go(self, pos):
        box = self.page_box()
        if box.isEmpty():
            return
        page = self.panel.win.scene.doc.page_rect()
        x = page.left() + (pos.x() - box.left()) / box.width() * page.width()
        y = page.top() + (pos.y() - box.top()) / box.height() * page.height()
        self.panel.win.view.centerOn(QPointF(x, y))
        self.update()

    def mousePressEvent(self, e):
        self._go(e.pos())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self._go(e.pos())


class NavigatorPanel(QWidget):
    """Navigator: a small picture of the whole page. The red box is what
    you see; drag it to move around. The slider zooms."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.thumb = None
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        self.nav = _NavView(self)
        v.addWidget(self.nav, 1)
        row_ = QHBoxLayout()
        out_btn = QToolButton()
        out_btn.setIcon(icon("zoom-out"))
        out_btn.setToolTip("Zoom out")
        in_btn = QToolButton()
        in_btn.setIcon(icon("zoom-in"))
        in_btn.setToolTip("Zoom in")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.zoom_label = QLabel()
        self.zoom_label.setMinimumWidth(48)
        row_.addWidget(out_btn)
        row_.addWidget(self.slider, 1)
        row_.addWidget(in_btn)
        row_.addWidget(self.zoom_label)
        v.addLayout(row_)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.render_thumb)
        out_btn.clicked.connect(lambda: win.view.zoom_by(0.8))
        in_btn.clicked.connect(lambda: win.view.zoom_by(1.25))
        self.slider.valueChanged.connect(self.on_slider)
        win.view.zoomChanged.connect(self.on_zoom)
        win.view.horizontalScrollBar().valueChanged.connect(lambda _: self.nav.update())
        win.view.verticalScrollBar().valueChanged.connect(lambda _: self.nav.update())

    LOW, HIGH = math.log(0.01), math.log(64.0)

    def on_zoom(self, z):
        self.slider.blockSignals(True)
        self.slider.setValue(round((math.log(max(z, 0.01)) - self.LOW) / (self.HIGH - self.LOW) * 1000))
        self.slider.blockSignals(False)
        self.zoom_label.setText(f"{z * 100:.0f}%")
        self.nav.update()

    def on_slider(self, value):
        z = math.exp(self.LOW + (self.HIGH - self.LOW) * value / 1000.0)
        self.win.view.set_zoom(z)

    def schedule(self):
        self.timer.start(300)

    def render_thumb(self):
        if not self.isVisible():
            self.thumb = None
            return
        scene = self.win.scene
        page = scene.doc.page_rect()
        if page.isEmpty():
            return
        s = min(320 / page.width(), 240 / page.height())
        image = QImage(max(1, int(page.width() * s)), max(1, int(page.height() * s)),
                       QImage.Format_ARGB32_Premultiplied)
        image.fill(QColor("#ffffff"))
        p = QPainter(image)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        scene.exporting = True
        try:
            scene.render(p, QRectF(image.rect()), page)
        finally:
            scene.exporting = False
            p.end()
        self.thumb = image
        self.nav.update()

    def showEvent(self, e):
        super().showEvent(e)
        self.schedule()
        self.on_zoom(self.win.view.zoom())
