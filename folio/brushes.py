"""The Brushes panel: brushes in categories (Acrylics, Dry Media, Engraving,
Gouaches, Inks, Markers, Oils, Patterns, Pencils, Pens, Watercolours), each
shown as a picture of the stroke it makes. Click one to paint with it.

A brush is just a set of settings for the paint brush: how wide, how soft,
how strong, whether the end is flat or round, speckled like chalk, or a
stamp like a star. All of them are drawn by Folio itself.
"""

import math
import random
import zlib

from PyQt5.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import (QComboBox, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QStyle, QStyledItemDelegate, QVBoxLayout, QWidget,
                             QAbstractItemView)

from .pixel import BRUSH_SHAPE_DEFAULTS, paint_dab


def B(name, size, hard=0.8, op=100, flow=100, **extra):
    d = {"name": name, "size": float(size), "hardness": hard, "opacity": float(op),
         "flow": float(flow)}
    d.update(extra)
    return d


CATEGORIES = [
    ("Acrylics", [
        B("Round Acrylic", 50, 0.9),
        B("Soft Acrylic", 60, 0.5),
        B("Flat Acrylic", 80, 0.9, shape="square", squash=0.4, angle=-30),
        B("Thick Acrylic", 100, 0.85),
        B("Dry Acrylic", 70, 0.8, grain=0.5),
        B("Glaze Acrylic", 90, 0.4, op=40),
        B("Wash Acrylic", 140, 0.3, op=30),
    ]),
    ("Dry Media", [
        B("Charcoal", 40, 0.6, grain=0.9),
        B("Chalk", 50, 0.7, grain=0.7),
        B("Soft Pastel", 60, 0.4, op=80, grain=0.6),
        B("Conté Crayon", 30, 0.8, grain=0.5),
        B("Graphite Stick", 20, 0.8, grain=0.4),
        B("Wax Crayon", 35, 0.9, grain=0.8),
        B("Chalk Smudge", 90, 0.3, op=50, grain=0.5),
    ]),
    ("Engraving", [
        B("Fine Hatch", 30, 1.0, shape="line", angle=45, spacing=0.35),
        B("Coarse Hatch", 50, 1.0, shape="line", angle=-45, spacing=0.5),
        B("Cross Hatch", 36, 1.0, shape="cross", angle=45, spacing=0.6),
        B("Etching Line", 40, 1.0, shape="line", angle=0, spacing=0.4),
        B("Burin", 24, 1.0, shape="line", angle=20, spacing=0.3),
        B("Stipple", 40, 1.0, shape="dot", scatter=0.9, spacing=0.4),
    ]),
    ("Gouaches", [
        B("Flat Gouache", 80, 0.9, shape="square", squash=0.5, angle=-20),
        B("Soft Gouache", 70, 0.6),
        B("Dry Gouache", 70, 0.8, grain=0.35),
        B("Gouache Wash", 120, 0.5, op=50),
        B("Gouache Detail", 20, 0.9),
    ]),
    ("Inks", [
        B("Ink Pen", 12, 1.0),
        B("Ink Brush", 30, 0.95, squash=0.8),
        B("Calligraphy", 24, 1.0, shape="square", squash=0.25, angle=-45),
        B("Dip Pen", 16, 1.0, squash=0.7, angle=-30),
        B("Ink Wash", 80, 0.2, op=25),
        B("Ink Splatter", 40, 1.0, shape="dot", scatter=1.4, spacing=0.8),
    ]),
    ("Markers", [
        B("Felt Tip", 14, 1.0, op=90),
        B("Chisel Marker", 30, 1.0, op=90, shape="square", squash=0.35, angle=-35),
        B("Highlighter", 40, 1.0, op=45, shape="square", squash=0.3, angle=-30),
        B("Brush Marker", 22, 0.8, op=90),
        B("Fine Liner", 6, 1.0),
        B("Bullet Marker", 20, 0.95, op=85),
    ]),
    ("Oils", [
        B("Flat Oil", 90, 0.9, shape="square", squash=0.5, angle=-25, grain=0.15),
        B("Round Oil", 60, 0.8),
        B("Bristle Oil", 100, 0.85, grain=0.45),
        B("Palette Knife", 130, 0.95, shape="square", squash=0.2, angle=-60),
        B("Oil Glaze", 110, 0.3, op=35),
        B("Impasto", 70, 1.0, grain=0.2),
    ]),
    ("Patterns", [
        B("Dots", 24, 1.0, shape="dot", spacing=2.2),
        B("Stars", 30, 1.0, shape="star", spacing=2.4),
        B("Hearts", 30, 1.0, shape="heart", spacing=2.6),
        B("Diamonds", 28, 1.0, shape="diamond", spacing=2.4),
        B("Crosses", 26, 1.0, shape="cross", spacing=2.0),
        B("Triangles", 28, 1.0, shape="triangle", spacing=2.4),
        B("Confetti", 36, 1.0, shape="square", squash=0.5, scatter=1.0, spacing=1.8),
    ]),
    ("Pencils", [
        B("HB Pencil", 10, 0.9, grain=0.6),
        B("2B Pencil", 14, 0.85, grain=0.7),
        B("6B Soft Pencil", 20, 0.7, grain=0.75),
        B("Coloured Pencil", 12, 0.85, op=90, grain=0.55),
        B("Mechanical Pencil", 5, 1.0, grain=0.3),
        B("Carpenter Pencil", 24, 0.9, shape="square", squash=0.3, angle=0, grain=0.6),
    ]),
    ("Pens", [
        B("Ballpoint", 6, 1.0),
        B("Gel Pen", 8, 1.0),
        B("Fineliner", 4, 1.0),
        B("Fountain Pen", 10, 1.0, squash=0.7, angle=-30),
        B("Technical Pen", 3, 1.0),
        B("Rollerball", 7, 1.0, op=95),
    ]),
    ("Watercolors", [
        B("Wash", 160, 0.2, op=25),
        B("Wet Round", 70, 0.3, op=35),
        B("Dry Brush", 60, 0.8, op=60, grain=0.5),
        B("Glaze", 120, 0.2, op=20),
        B("Blot", 50, 0.5, op=45, scatter=0.5, spacing=0.8),
        B("Granulating", 90, 0.4, op=40, grain=0.55),
    ]),
]
ALL = [(cat, b) for cat, brushes in CATEGORIES for b in brushes]
BY_NAME = {b["name"]: b for _, b in ALL}
ROW = 52


def settings_of(brush):
    """The paint-brush settings a brush stands for."""
    s = dict(BRUSH_SHAPE_DEFAULTS)
    s.update({k: v for k, v in brush.items() if k != "name"})
    return s


class _Canvas:
    """Stands in for a painted-on layer so a stroke can be drawn into a picture."""

    def __init__(self, image):
        self.image = image
        self.scale = 1.0
        self.clip = None

    def painter(self):
        p = QPainter(self.image)
        p.setRenderHint(QPainter.Antialiasing)
        return p

    def touch(self, rect):
        pass


def render_preview(brush, width, height=34):
    """A picture of the stroke the brush makes: a gentle wave, light on dark."""
    image = QImage(max(60, int(width)), height, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    canvas = _Canvas(image)
    s = settings_of(brush)
    radius = max(1.2, min(11.0, s["size"] * 0.16))
    state = random.getstate()
    random.seed(zlib.crc32(brush["name"].encode()))
    try:
        left, right = radius + 6, image.width() - radius - 6
        spacing = max(0.05, float(s["spacing"]))
        step = max(1.0, radius * spacing)
        n = max(2, int((right - left) / step))
        for k in range(n + 1):
            t = k / n
            x = left + (right - left) * t
            y = height / 2 + 5 * math.sin(t * 2 * math.pi * 1.2)
            paint_dab(canvas, "brush", QPointF(x, y), radius, s, QColor("#f2f2f2"))
    finally:
        random.setstate(state)
    return image


class BrushDelegate(QStyledItemDelegate):
    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel

    def sizeHint(self, option, index):
        return QSize(240, ROW)

    def paint(self, p, option, index):
        brush = index.data(Qt.UserRole)
        r = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        p.save()
        p.fillRect(r, QColor("#3d5f8f") if selected else QColor("#333333"))
        p.setPen(QColor("#1a1a1a"))
        p.drawLine(r.bottomLeft(), r.bottomRight())
        font = p.font()
        font.setPointSizeF(7.5)
        p.setFont(font)
        p.setPen(QColor("#c9c9c9") if selected else QColor("#9a9a9a"))
        p.drawText(QRect(r.left() + 4, r.top(), 28, r.height() - 12),
                   Qt.AlignVCenter | Qt.AlignRight, str(int(brush["size"])))
        image = self.panel.preview(brush, r.width() - 44)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(QRectF(r.left() + 38, r.top() + 2, image.width(), image.height()), image)
        p.setPen(QColor("#ffffff") if selected else QColor("#e0e0e0"))
        p.drawText(QRect(r.left() + 38, r.bottom() - 15, r.width() - 42, 14),
                   Qt.AlignLeft | Qt.AlignVCenter, brush["name"])
        p.restore()


class BrushesPanel(QWidget):
    """Search, a category menu, and the brushes."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.cache = {}
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(5)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search")
        self.search.setClearButtonEnabled(True)
        v.addWidget(self.search)
        self.category = QComboBox()
        for name, _ in CATEGORIES:
            self.category.addItem(name)
        v.addWidget(self.category)
        self.list = QListWidget()
        self.list.setObjectName("brushList")
        self.list.setItemDelegate(BrushDelegate(self))
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list.setUniformItemSizes(True)
        self.list.setFrameShape(QListWidget.NoFrame)
        v.addWidget(self.list, 1)
        self.hint = QLabel()
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        v.addWidget(self.hint)
        self.category.activated.connect(lambda _: self.fill())
        self.search.textChanged.connect(lambda _: self.fill())
        self.list.itemClicked.connect(self.on_clicked)
        self.current = None
        saved = win.settings.value("brush_choice", "")
        if saved in BY_NAME:
            cat = next(c for c, b in ALL if b["name"] == saved)
            self.category.setCurrentIndex(max(0, self.category.findText(cat)))
            self.current = saved
        self.fill()

    def preview(self, brush, width):
        key = (brush["name"], int(width) // 12)
        image = self.cache.get(key)
        if image is None:
            image = render_preview(brush, width)
            self.cache[key] = image
        return image

    def fill(self):
        text = self.search.text().strip().lower()
        self.category.setEnabled(not text)
        if text:
            shown = [(c, b) for c, b in ALL
                     if all(w in (b["name"] + " " + c).lower() for w in text.split())]
        else:
            name = self.category.currentText()
            shown = [(c, b) for c, b in ALL if c == name]
        self.list.clear()
        for cat, b in shown:
            it = QListWidgetItem(b["name"])
            it.setData(Qt.UserRole, b)
            it.setToolTip(f"{b['name']} ({cat}): {int(b['size'])} px, "
                          f"{int(b['opacity'])} % strong, {int(b['hardness'] * 100)} % hard")
            self.list.addItem(it)
            if b["name"] == self.current:
                self.list.setCurrentItem(it)
        self.hint.setText("" if shown else "No brushes match.")
        self.hint.setVisible(not shown)

    def select(self, name):
        """Show a brush as chosen (used when one is restored or picked elsewhere)."""
        self.current = name
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.data(Qt.UserRole)["name"] == name:
                self.list.setCurrentItem(it)
                return

    def on_clicked(self, item):
        brush = item.data(Qt.UserRole)
        self.current = brush["name"]
        self.win.use_brush(brush)
