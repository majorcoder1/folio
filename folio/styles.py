"""Saved styles: a look (colours, outline, shadow, lettering) that goes on
any object with one click, and the Styles panel that shows them.

Lengths in a style are kept in points, so a style looks the same on a
72 dpi web banner and on a 300 dpi book cover. A style only changes the
parts it has: "Soft shadow" changes the shadow and leaves the colours.
"""

import copy
import json

from PyQt5.QtCore import QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import (QGraphicsScene, QHBoxLayout, QInputDialog, QLabel,
                             QListView, QListWidget, QListWidgetItem, QMenu,
                             QToolButton, QVBoxLayout, QWidget)

from .icons import icon
from .items import RectItem, TextItem

# Lettering that a style carries over to text. Size and alignment stay
# as they are, so a style never moves or resizes a title.
TEXT_KEYS = ("family", "bold", "italic", "tracking", "line", "caps")

STARTER_STYLES = [
    {"name": "Gold lettering",
     "fill": {"type": "solid", "color": "#ffd4a82f"},
     "stroke": {"color": "#ff5c3a00", "width": 0.75, "dash": "solid"},
     "shadow": {"on": True, "color": "#99000000", "blur": 3.0, "dx": 1.5, "dy": 1.5}},
    {"name": "White, dark outline",
     "fill": {"type": "solid", "color": "#ffffffff"},
     "stroke": {"color": "#ff111111", "width": 1.5, "dash": "solid"}},
    {"name": "Outline only",
     "fill": {"type": "none"},
     "stroke": {"color": "#ff1a1a1a", "width": 2.0, "dash": "solid"}},
    {"name": "Soft shadow",
     "shadow": {"on": True, "color": "#8c000000", "blur": 8.0, "dx": 3.0, "dy": 4.0}},
    {"name": "Glow",
     "shadow": {"on": True, "color": "#e6ffe082", "blur": 12.0, "dx": 0.0, "dy": 0.0}},
    {"name": "Night sky",
     "fill": {"type": "linear", "color": "#ff07122b", "color2": "#ff2c5596", "angle": 90.0}},
    {"name": "Sunset",
     "fill": {"type": "linear", "color": "#ff5b2a86", "color2": "#ffffa64d", "angle": 90.0}},
    {"name": "No effects",
     "shadow": {"on": False}, "opacity": 1.0},
]


def _scale_lengths(style, factor):
    out = copy.deepcopy(style)
    if "width" in out.get("stroke", {}):
        out["stroke"]["width"] = float(out["stroke"]["width"]) * factor
    for key in ("blur", "dx", "dy"):
        if key in out.get("shadow", {}):
            out["shadow"][key] = float(out["shadow"][key]) * factor
    return out


def style_from_dict(d, dpi, name="", parts=("fill", "stroke", "shadow", "opacity", "text")):
    """A style (in points) from a saved object (in pixels at ``dpi``)."""
    s = {"name": name}
    if "fill" in parts and d.get("kind") != "image" and "fill" in d:
        s["fill"] = dict(d["fill"])
    if "stroke" in parts and "stroke" in d:
        s["stroke"] = {k: v for k, v in d["stroke"].items() if k != "join"}
    if "shadow" in parts and "shadow" in d:
        s["shadow"] = dict(d["shadow"])
    if "opacity" in parts:
        s["opacity"] = float(d.get("opacity", 1.0))
    if "text" in parts and d.get("kind") == "text":
        s["text"] = {k: d.get("style", {})[k] for k in TEXT_KEYS if k in d.get("style", {})}
    return _scale_lengths(s, 72.0 / dpi)


def style_from_item(item, dpi, name=""):
    return style_from_dict(item.to_dict(), dpi, name)


def apply_style(item, style, dpi):
    """Put a style on an object. The caller redraws it (and makes the undo step)."""
    s = _scale_lengths(style, dpi / 72.0)
    if "fill" in s and item.has_fill:
        fill = {**item.fill, **s["fill"]}
        if isinstance(item, TextItem):
            if fill.get("type") == "none":
                # letters with no fill: only their outline shows
                fill.update(type="solid", color="#00000000")
            else:
                fill["type"] = "solid"
        item.fill = fill
    if "stroke" in s and item.has_stroke:
        item.stroke = {**item.stroke, **s["stroke"]}
    if "shadow" in s:
        item.shadow = {**item.shadow, **s["shadow"]}
    if "opacity" in s:
        item.setOpacity(float(s["opacity"]))
    if "text" in s and isinstance(item, TextItem):
        item.style.update(s["text"])


def describe(style):
    bits = []
    if "fill" in style:
        bits.append({"none": "no fill", "solid": "colour", "linear": "gradient",
                     "radial": "round gradient"}.get(style["fill"].get("type"), "fill"))
    if "stroke" in style:
        w = float(style["stroke"].get("width", 0))
        bits.append(f"{w:g} pt outline" if w > 0 else "no outline")
    if "shadow" in style:
        bits.append("shadow" if style["shadow"].get("on") else "no shadow")
    if "text" in style:
        bits.append(style["text"].get("family", "lettering"))
    return style.get("name", "Style") + ": " + ", ".join(bits)


def thumbnail(style, size=56):
    """A small picture of the style, on a light tile so every style shows."""
    scene = QGraphicsScene()
    if "text" in style:
        item = TextItem("Aa")
        item.style["size"] = size * 0.5
        item.fill = {**item.fill, "color": "#ff1a1a1a"}
    else:
        item = RectItem()
        item.radius = size * 0.1
        item.set_size(size * 0.6, size * 0.6)
        item.fill = {"type": "solid", "color": "#ff8f9aa6", "color2": "#ff10233f", "angle": 90.0}
        item.stroke = {"color": "#ff000000", "width": 0.0, "dash": "solid"}
    apply_style(item, style, 72.0)
    if isinstance(item, TextItem):
        item.apply_style()
    else:
        item.changed()
    scene.addItem(item)
    item.setPos((size - item.w) / 2, (size - item.h) / 2)
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#dcdde1"))
    p.drawRoundedRect(QRectF(0.5, 0.5, size - 1, size - 1), 6, 6)
    scene.render(p, QRectF(0, 0, size, size), QRectF(0, 0, size, size))
    p.end()
    return image


class StylesPanel(QWidget):
    """Saved looks. Click one to put it on what is selected."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        hint = QLabel("Click a style to put it on what you selected.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        v.addWidget(hint)
        self.list = QListWidget()
        self.list.setViewMode(QListView.IconMode)
        self.list.setIconSize(QSize(56, 56))
        self.list.setGridSize(QSize(88, 96))
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setWordWrap(True)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        v.addWidget(self.list, 1)
        bar = QHBoxLayout()
        for name, tip, fn in (("plus", "Make a style from the selected object", win.create_style),
                              ("trash", "Delete the chosen style", self.delete_current)):
            b = QToolButton()
            b.setIcon(icon(name))
            b.setToolTip(tip)
            b.clicked.connect(fn)
            bar.addWidget(b)
        bar.addStretch(1)
        v.addLayout(bar)
        self.list.itemClicked.connect(self.on_clicked)
        self.list.customContextMenuRequested.connect(self.on_menu)
        self.styles = self.load()
        self.refill()

    # ---- keeping the list ------------------------------------------------

    def load(self):
        raw = self.win.settings.value("styles", "")
        if raw:
            try:
                styles = json.loads(raw)
                if isinstance(styles, list):
                    return [s for s in styles if isinstance(s, dict)]
            except ValueError:
                pass
        return copy.deepcopy(STARTER_STYLES)

    def save(self):
        self.win.settings.setValue("styles", json.dumps(self.styles))

    def refill(self):
        self.list.clear()
        for index, style in enumerate(self.styles):
            it = QListWidgetItem(QIcon(QPixmap.fromImage(thumbnail(style))),
                                 style.get("name", "Style"))
            it.setData(Qt.UserRole, index)
            it.setToolTip(describe(style))
            self.list.addItem(it)

    def add(self, style):
        self.styles.append(style)
        self.save()
        self.refill()
        self.list.setCurrentRow(len(self.styles) - 1)

    def current_index(self):
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it is not None else None

    # ---- actions ---------------------------------------------------------

    def on_clicked(self, it):
        self.win.apply_saved_style(self.styles[it.data(Qt.UserRole)])

    def delete_current(self):
        index = self.current_index()
        if index is None:
            return
        del self.styles[index]
        self.save()
        self.refill()

    def rename_current(self):
        index = self.current_index()
        if index is None:
            return
        name, ok = QInputDialog.getText(self, "Rename style", "Name:",
                                        text=self.styles[index].get("name", ""))
        if ok and name.strip():
            self.styles[index]["name"] = name.strip()
            self.save()
            self.refill()
            self.list.setCurrentRow(index)

    def restore_starters(self):
        have = {s.get("name") for s in self.styles}
        self.styles.extend(copy.deepcopy(s) for s in STARTER_STYLES if s["name"] not in have)
        self.save()
        self.refill()

    def on_menu(self, pos):
        it = self.list.itemAt(pos)
        if it is not None:
            self.list.setCurrentItem(it)
        m = QMenu(self)
        if it is not None:
            m.addAction("Put On Selection", lambda: self.on_clicked(it))
            m.addAction("Rename…", self.rename_current)
            m.addAction("Delete", self.delete_current)
            m.addSeparator()
        m.addAction("New Style from Selection…", self.win.create_style)
        m.addAction("Put Back the Starter Styles", self.restore_starters)
        m.exec_(self.list.viewport().mapToGlobal(pos))
