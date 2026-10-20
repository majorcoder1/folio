"""The Export persona: slices, the Export Options and Slices panels, and
the slice tools.

A slice is a named area of the page to export, with its own file type and
resolution. Every document has a "Page" slice, and a cover also has its
front cover, back cover and spine. Draw more with the Slice tool.
"""

import os
import re
import uuid

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QPen
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QGridLayout, QHBoxLayout,
                             QLabel, QMessageBox, QPushButton, QSlider, QSpinBox,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import exporter
from .tools import Tool

FORMATS = [("png", "PNG"), ("jpeg", "JPEG"), ("pdf", "PDF")]
EXT = {"png": "png", "jpeg": "jpg", "pdf": "pdf"}
PRESETS = [
    ("PNG", {"format": "png"}),
    ("JPEG", {"format": "jpeg", "quality": 92}),
    ("JPEG, best quality", {"format": "jpeg", "quality": 95}),
    ("JPEG, smaller file", {"format": "jpeg", "quality": 80}),
    ("PDF for printing", {"format": "pdf", "outline_text": True}),
    ("PDF, text kept as text", {"format": "pdf", "outline_text": False}),
]
SLICE_COLOUR = QColor("#ff8a3d")


def new_slice(name, dpi, region=None, rect=None, fmt="png", bleed=False, export=True):
    return {"id": uuid.uuid4().hex[:10], "name": name, "region": region, "rect": rect,
            "format": fmt, "dpi": float(dpi), "quality": 92, "bleed": bleed,
            "outline_text": True, "export": export}


def default_slices(doc):
    """The slices every document starts with."""
    if doc.kind == "cover":
        return [new_slice("Whole cover", doc.dpi, "page", fmt="pdf", bleed=True),
                new_slice("Front cover", doc.dpi, "front", fmt="jpeg"),
                new_slice("Back cover", doc.dpi, "back", export=False),
                new_slice("Spine", doc.dpi, "spine", export=False)]
    return [new_slice("Page", doc.dpi, "page", bleed=doc.bleed > 0)]


def slice_rect(doc, s):
    """Where a slice is on the page."""
    if s.get("rect"):
        return QRectF(*s["rect"])
    regs = doc.regions()
    key = s.get("region") or "page"
    if key == "page":
        return QRectF(regs["page"] if s.get("bleed", True) else regs["trim"])
    r = QRectF(regs.get(key, regs["page"]))
    if s.get("bleed") and doc.bleed > 0:
        b = doc.bleed
        grow = {"front": (0, -b, b, b), "back": (-b, -b, 0, b), "spine": (0, -b, 0, b)}
        r = r.adjusted(*grow.get(key, (0, 0, 0, 0)))
    return r


def pixel_size(doc, s):
    r = slice_rect(doc, s)
    k = s.get("dpi", doc.dpi) / doc.dpi
    return round(r.width() * k), round(r.height() * k)


def file_name(s):
    name = re.sub(r'[/\\:*?"<>|]+', "-", s.get("name") or "slice").strip(" .") or "slice"
    return f"{name}.{EXT[s.get('format', 'png')]}"


def export_slice(scene, s, folder):
    """Write one slice into ``folder``; returns the file path."""
    r = slice_rect(scene.doc, s)
    opts = {"format": s.get("format", "png"), "dpi": s.get("dpi", scene.doc.dpi),
            "quality": s.get("quality", 92), "outline_text": s.get("outline_text", True),
            "rect": [r.x(), r.y(), r.width(), r.height()],
            "area": "page" if s.get("region") == "page" and s.get("bleed") else "custom",
            "pixel_format": s.get("pixel_format", "document"),
            "resample": s.get("resample", "bilinear"), "matte": s.get("matte", ""),
            "icc": s.get("icc", True)}
    path = os.path.join(folder, file_name(s))
    exporter.export(scene, opts, path)
    return path


# ---- tools -------------------------------------------------------------------------

class SliceTool(Tool):
    """Slice tool: drag out an area of the page to export on its own."""

    name = "slice"
    cursor = Qt.CrossCursor

    def __init__(self, view):
        super().__init__(view)
        self.start = self.rect = None

    def press(self, e, sp):
        self.start = self.view.snap(sp)
        self.rect = None

    def move(self, e, sp):
        if self.start is None or not e.buttons() & Qt.LeftButton:
            return
        self.rect = QRectF(self.start, self.view.snap(sp)).normalized()
        self.view.viewport().update()

    def release(self, e, sp):
        rect, self.rect, self.start = self.rect, None, None
        self.view.clear_smart()
        if rect is None or rect.width() * self.view.zoom() < 4 or rect.height() * self.view.zoom() < 4:
            return
        self.win.add_slice(rect)

    def draw_overlay(self, painter):
        if self.rect is not None:
            painter.setPen(QPen(SLICE_COLOUR, 0, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.rect)


class SliceSelectTool(Tool):
    """Slice selection tool: click a slice to choose it, drag to move one you drew."""

    name = "slice-select"
    cursor = Qt.ArrowCursor

    def __init__(self, view):
        super().__init__(view)
        self.drag = None

    def press(self, e, sp):
        doc = self.scene.doc
        hit = None
        for s in reversed(self.scene.slices):
            r = slice_rect(doc, s)
            if r.contains(sp):
                if hit is None or r.width() * r.height() < slice_rect(doc, hit).width() * \
                        slice_rect(doc, hit).height():
                    hit = s
        if hit is None:
            return
        self.win.choose_slice(hit["id"])
        if hit.get("rect"):
            self.win.begin_change()
            self.drag = (hit, sp, list(hit["rect"]), False)

    def move(self, e, sp):
        if self.drag is None or not e.buttons() & Qt.LeftButton:
            return
        s, start, rect, _ = self.drag
        d = sp - start
        s["rect"] = [rect[0] + d.x(), rect[1] + d.y(), rect[2], rect[3]]
        self.drag = (s, start, rect, True)
        self.view.viewport().update()

    def release(self, e, sp):
        if self.drag is None:
            return
        moved = self.drag[3]
        self.drag = None
        if moved:
            self.win.end_change("Move slice")
        else:
            self.win.cancel_change()
        self.win.refresh_slices()


def draw_slices(painter, view, scene, chosen):
    """Outline every slice; the chosen one is solid and named."""
    doc = scene.doc
    for s in scene.slices:
        r = slice_rect(doc, s)
        on = s["id"] == chosen
        painter.setPen(QPen(SLICE_COLOUR if on else QColor(255, 138, 61, 140), 0,
                            Qt.SolidLine if on else Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(r)
        if not on and not s.get("rect"):
            continue
        painter.save()
        top_left = view.mapFromScene(r.topLeft())
        painter.resetTransform()
        font = QFont(painter.font())
        font.setPointSizeF(8)
        font.setBold(on)
        painter.setFont(font)
        label = f"{s['name']}  {s['format'].upper()}"
        width = painter.fontMetrics().horizontalAdvance(label) + 10
        y = top_left.y() - 17 if on else top_left.y() + 1
        box = QRectF(top_left.x(), y, width, 16)
        painter.fillRect(box, SLICE_COLOUR if on else QColor(60, 60, 60, 220))
        painter.setPen(QColor("#ffffff"))
        painter.drawText(box, Qt.AlignCenter, label)
        painter.restore()


# ---- panels ------------------------------------------------------------------------

EXPORT_KEYS = ("format", "dpi", "quality", "outline_text", "pixel_format", "resample",
               "matte", "icc", "bleed")


class MatteButton(QWidget):
    """The matte swatch: white with a red slash means no matte. Click it to
    choose a colour or take the matte away."""

    def __init__(self, on_change):
        super().__init__()
        self.colour = ""
        self.on_change = on_change
        self.setFixedSize(52, 22)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Matte: the colour behind see-through areas")

    def set_colour(self, colour):
        self.colour = colour or ""
        self.update()

    def paintEvent(self, e):
        from PyQt5.QtGui import QPainter
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.fillRect(r, QColor(self.colour or "#ffffff"))
        if not self.colour:
            p.setPen(QPen(QColor("#e03030"), 1.6))
            p.drawLine(r.bottomLeft() + QPointF(6, -2), r.topRight() + QPointF(-6, 2))
        p.setPen(QPen(QColor("#5a5a5a"), 1))
        p.drawRect(r)
        p.end()

    def mousePressEvent(self, e):
        from PyQt5.QtWidgets import QColorDialog, QMenu
        m = QMenu(self)
        none = m.addAction("None")
        pick = m.addAction("Choose colour\u2026")
        chosen = m.exec_(self.mapToGlobal(self.rect().bottomLeft()))
        if chosen is none:
            self.on_change("")
        elif chosen is pick:
            c = QColorDialog.getColor(QColor(self.colour or "#ffffff"), self, "Matte colour")
            if c.isValid():
                self.on_change(c.name())


class ExportOptionsPanel(QWidget):
    """Export Options, laid out like the pro apps: Mode (the chosen slice or
    the defaults for new slices), preset, file format, pixel format,
    resample, matte, colour profile and bleed."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.updating = False
        self.mode = "selection"
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)
        g = QGridLayout()
        g.setHorizontalSpacing(6)
        g.setVerticalSpacing(5)
        g.setColumnStretch(1, 1)
        self.grid = g
        self.rows = {}

        def label(text):
            lab = QLabel(text)
            lab.setObjectName("hint")
            lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            return lab

        def add(key, text, widget, gap=False):
            r = g.rowCount()
            if gap:
                g.setRowMinimumHeight(r, 8)
                r += 1
            lab = label(text) if text else QLabel()
            g.addWidget(lab, r, 0)
            g.addWidget(widget, r, 1)
            self.rows[key] = (lab, widget)

        mode = QWidget()
        mh = QHBoxLayout(mode)
        mh.setContentsMargins(0, 0, 0, 0)
        mh.setSpacing(0)
        self.mode_buttons = {}
        for key, text in (("selection", "Selection"), ("defaults", "Defaults")):
            b = QPushButton(text)
            b.setCheckable(True)
            b.setToolTip("Change the chosen slice" if key == "selection"
                         else "Change the settings new slices start with")
            b.clicked.connect(lambda _=False, k=key: self.set_mode(k))
            mh.addWidget(b)
            self.mode_buttons[key] = b
        mh.addStretch(1)
        add("mode", "Mode:", mode)
        self.preset = QComboBox()
        for title, _ in PRESETS:
            self.preset.addItem(title)
        self.preset.addItem("Custom")
        add("preset", "Preset:", self.preset)
        self.format = QComboBox()
        for key, title in FORMATS:
            self.format.addItem(title, key)
        add("format", "File format:", self.format, gap=True)
        self.pixel_format = QComboBox()
        self.pixel_format.addItem("Use document format", "document")
        self.pixel_format.addItem("Greyscale 8-bit", "grey")
        add("pixel_format", "Pixel format:", self.pixel_format)
        self.resample = QComboBox()
        for key, title in (("bilinear", "Bilinear"), ("bicubic", "Bicubic"),
                           ("nearest", "Nearest Neighbour")):
            self.resample.addItem(title, key)
        add("resample", "Resample:", self.resample)
        self.quality = QSlider(Qt.Horizontal)
        self.quality.setRange(40, 100)
        qrow = QWidget()
        qh = QHBoxLayout(qrow)
        qh.setContentsMargins(0, 0, 0, 0)
        self.quality_val = QLabel()
        self.quality_val.setMinimumWidth(24)
        qh.addWidget(self.quality, 1)
        qh.addWidget(self.quality_val)
        add("quality", "Quality:", qrow)
        self.dpi = QSpinBox()
        self.dpi.setRange(36, 1200)
        self.dpi.setSuffix(" dpi")
        add("dpi", "Resolution:", self.dpi)
        self.matte = MatteButton(lambda c: self.set_key("matte", c))
        mrow = QWidget()
        mrh = QHBoxLayout(mrow)
        mrh.setContentsMargins(0, 0, 0, 0)
        mrh.addWidget(self.matte)
        mrh.addStretch(1)
        add("matte", "Matte:", mrow)
        self.icc_profile = QComboBox()
        self.icc_profile.addItem("sRGB IEC61966-2.1")
        add("icc_profile", "ICC profile:", self.icc_profile, gap=True)
        self.icc = QCheckBox("Embed ICC profiles")
        add("icc", "", self.icc)
        self.outline = QCheckBox("Text as curves (safest for printers)")
        add("outline", "", self.outline)
        outer.addLayout(g)
        self.bleed = QCheckBox("Include bleed")
        outer.addSpacing(8)
        outer.addWidget(self.bleed)
        self.size = QLabel()
        self.size.setObjectName("hint")
        self.size.setWordWrap(True)
        outer.addWidget(self.size)
        outer.addStretch(1)

        self.preset.activated.connect(self.on_preset)
        self.format.activated.connect(lambda _: self.set_key("format", self.format.currentData()))
        self.pixel_format.activated.connect(
            lambda _: self.set_key("pixel_format", self.pixel_format.currentData()))
        self.resample.activated.connect(lambda _: self.set_key("resample", self.resample.currentData()))
        self.quality.valueChanged.connect(lambda v: self.set_key("quality", int(v)))
        self.dpi.valueChanged.connect(lambda v: self.set_key("dpi", float(v)))
        self.icc.toggled.connect(lambda v: self.set_key("icc", bool(v)))
        self.outline.toggled.connect(lambda v: self.set_key("outline_text", bool(v)))
        self.bleed.toggled.connect(lambda v: self.set_key("bleed", bool(v)))

    def show_row(self, key, on):
        for w in self.rows[key]:
            w.setVisible(on)

    def set_mode(self, mode):
        self.mode = mode
        self.refresh()

    def target(self):
        if self.mode == "defaults":
            return self.win.slice_defaults
        return self.win.current_slice()

    def refresh(self):
        self.updating = True
        try:
            for key, b in self.mode_buttons.items():
                b.setChecked(key == self.mode)
            s = self.target()
            for key in self.rows:
                if key != "mode":
                    self.rows[key][1].setEnabled(s is not None)
            self.bleed.setEnabled(s is not None)
            if s is None:
                self.size.setText("Choose a slice in the Slices panel, or draw one with the "
                                  "Slice tool.")
                return
            fmt = s.get("format", "png")
            match = next((i for i, (_, v) in enumerate(PRESETS)
                          if all(s.get(k, v[k]) == v[k] for k in v)), len(PRESETS))
            self.preset.setCurrentIndex(match)
            self.format.setCurrentIndex(max(0, self.format.findData(fmt)))
            self.pixel_format.setCurrentIndex(
                max(0, self.pixel_format.findData(s.get("pixel_format", "document"))))
            self.resample.setCurrentIndex(max(0, self.resample.findData(s.get("resample", "bilinear"))))
            self.quality.setValue(int(s.get("quality", 92)))
            self.quality_val.setText(str(int(s.get("quality", 92))))
            self.dpi.setValue(int(round(s.get("dpi", self.win.scene.doc.dpi))))
            self.matte.set_colour(s.get("matte", ""))
            self.icc.setChecked(bool(s.get("icc", True)))
            self.outline.setChecked(bool(s.get("outline_text", True)))
            self.bleed.setChecked(bool(s.get("bleed")))
            raster = fmt != "pdf"
            for key in ("pixel_format", "resample", "matte", "icc_profile", "icc", "dpi"):
                self.show_row(key, raster)
            self.show_row("quality", fmt == "jpeg")
            self.show_row("outline", fmt == "pdf")
            if self.mode == "defaults":
                self.bleed.setVisible(True)
                self.size.setText("New slices start with these settings.")
                return
            self.bleed.setVisible(not s.get("rect") and self.win.scene.doc.bleed > 0)
            w, h = pixel_size(self.win.scene.doc, s)
            r = slice_rect(self.win.scene.doc, s)
            dpi = self.win.scene.doc.dpi
            self.size.setText(f"{s['name']}: {w} \u00d7 {h} pixels "
                              f"({r.width() / dpi:.2f} \u00d7 {r.height() / dpi:.2f} in)")
        finally:
            self.updating = False

    def set_key(self, key, value):
        if self.updating:
            return
        s = self.target()
        if s is None or s.get(key) == value:
            return
        if self.mode == "defaults":
            s[key] = value
            self.win.save_slice_defaults()
            self.refresh()
            return
        with self.win.change("Export options", merge="slice-" + key):
            s[key] = value
        self.win.refresh_slices()

    def on_preset(self, index):
        if index >= len(PRESETS):
            return
        s = self.target()
        if s is None:
            return
        if self.mode == "defaults":
            s.update(PRESETS[index][1])
            self.win.save_slice_defaults()
            self.refresh()
            return
        with self.win.change("Export preset"):
            s.update(PRESETS[index][1])
        self.win.refresh_slices()


class SlicesPanel(QWidget):
    """Slices, laid out like the pro apps: each slice has a tick (export it or
    not), a small picture, its name, its file type and its own export button.
    Open a slice with its arrow to see its size and settings."""

    THUMB = 40

    def __init__(self, win):
        super().__init__()
        from PyQt5.QtCore import QSize, QTimer
        from PyQt5.QtWidgets import QAbstractItemView, QHeaderView, QToolButton
        from .icons import icon
        self.win = win
        self.updating = False
        self.thumbs = {}
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(4)
        self.tree = QTreeWidget()
        self.tree.setObjectName("slicesTree")
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(3)
        self.tree.setIconSize(QSize(self.THUMB, self.THUMB))
        self.tree.setIndentation(14)
        self.tree.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.resizeSection(2, 30)
        v.addWidget(self.tree, 1)
        bar = QHBoxLayout()
        bar.setSpacing(2)

        def tool(name, tip, fn, text=None):
            b = QToolButton()
            b.setIcon(icon(name))
            b.setToolTip(tip)
            b.setAutoRaise(True)
            if text:
                b.setText(text)
                b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.clicked.connect(fn)
            bar.addWidget(b)
            return b
        self.export_btn = QPushButton("Export Slices\u2026")
        self.export_btn.setToolTip("Save every ticked slice into a folder you choose")
        self.export_btn.clicked.connect(self.export_all)
        bar.addWidget(self.export_btn)
        bar.addStretch(1)
        self.delete_btn = tool("trash", "Delete the chosen slice (only ones you drew)",
                               win.delete_slice)
        self.create_btn = tool("slice", "Make a slice the size of the selected objects",
                               win.slice_from_selection, "Create Slice")
        v.addLayout(bar)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.make_thumbs)
        self.tree.itemChanged.connect(self.on_changed)
        self.tree.currentItemChanged.connect(self.on_current)

    def refresh(self):
        from PyQt5.QtWidgets import QToolButton
        from .icons import icon
        self.updating = True
        try:
            open_ids = {self.tree.topLevelItem(i).data(0, Qt.UserRole)
                        for i in range(self.tree.topLevelItemCount())
                        if self.tree.topLevelItem(i).isExpanded()}
            self.tree.clear()
            doc = self.win.scene.doc
            chosen = None
            for s in self.win.scene.slices:
                w, h = pixel_size(doc, s)
                it = QTreeWidgetItem([s["name"], s["format"].upper(), ""])
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
                            | Qt.ItemIsUserCheckable)
                it.setCheckState(0, Qt.Checked if s.get("export", True) else Qt.Unchecked)
                it.setData(0, Qt.UserRole, s["id"])
                it.setForeground(1, QColor("#9a9a9a"))
                it.setToolTip(0, "Tick to export this slice. Double-click the name to rename it.")
                if s["id"] in self.thumbs:
                    it.setIcon(0, self.thumbs[s["id"]])
                fmt = s["format"]
                detail = f"{w} \u00d7 {h} px" if fmt != "pdf" else \
                    f"{slice_rect(doc, s).width() / doc.dpi:.2f} \u00d7 " \
                    f"{slice_rect(doc, s).height() / doc.dpi:.2f} in"
                bits = [detail]
                if fmt != "pdf":
                    bits.append(f"{s.get('dpi', doc.dpi):g} dpi")
                if fmt == "jpeg":
                    bits.append(f"quality {s.get('quality', 92)}")
                if s.get("bleed"):
                    bits.append("with bleed")
                child = QTreeWidgetItem([", ".join(bits) + "  \u2192  " + file_name(s), "", ""])
                child.setFlags(Qt.ItemIsEnabled)
                child.setForeground(0, QColor("#8a8a8a"))
                child.setToolTip(0, child.text(0))
                it.addChild(child)
                child.setFirstColumnSpanned(True)
                self.tree.addTopLevelItem(it)
                it.setExpanded(s["id"] in open_ids)
                b = QToolButton()
                b.setIcon(icon("export"))
                b.setAutoRaise(True)
                b.setToolTip("Export just this slice now")
                b.clicked.connect(lambda _=False, sid=s["id"]: self.export_one(sid))
                self.tree.setItemWidget(it, 2, b)
                if s["id"] == self.win.chosen_slice:
                    chosen = it
            if chosen is not None:
                self.tree.setCurrentItem(chosen)
            current = self.win.current_slice()
            self.delete_btn.setEnabled(bool(current and current.get("rect")))
        finally:
            self.updating = False
        self.timer.start(300)

    def make_thumbs(self):
        """Small pictures of each slice's area (made a moment after changes)."""
        from PyQt5.QtGui import QIcon, QImage, QPainter, QPixmap
        if not self.isVisible():
            return
        scene = self.win.scene
        size = self.THUMB
        for s in scene.slices:
            r = slice_rect(scene.doc, s)
            if r.isEmpty():
                continue
            k = min(size / r.width(), size / r.height())
            image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
            image.fill(Qt.transparent)
            p = QPainter(image)
            p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
            target = QRectF((size - r.width() * k) / 2, (size - r.height() * k) / 2,
                            r.width() * k, r.height() * k)
            p.fillRect(target, QColor(scene.doc.background or "#ffffff"))
            scene.exporting = True
            try:
                scene.render(p, target, r)
            finally:
                scene.exporting = False
            p.setPen(QPen(QColor("#5a5a5a"), 1))
            p.drawRect(target)
            p.end()
            self.thumbs[s["id"]] = QIcon(QPixmap.fromImage(image))
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            sid = it.data(0, Qt.UserRole)
            if sid in self.thumbs:
                self.updating = True
                it.setIcon(0, self.thumbs[sid])
                self.updating = False

    def showEvent(self, e):
        super().showEvent(e)
        self.timer.start(100)

    def on_current(self, item, _old=None):
        if self.updating or item is None:
            return
        if item.parent() is not None:
            item = item.parent()
        self.win.choose_slice(item.data(0, Qt.UserRole))

    def on_changed(self, item, column):
        if self.updating or item.parent() is not None:
            return
        sid = item.data(0, Qt.UserRole)
        s = next((x for x in self.win.scene.slices if x["id"] == sid), None)
        if s is None:
            return
        export = item.checkState(0) == Qt.Checked
        name = item.text(0).strip() or s["name"]
        if export != s.get("export", True) or name != s["name"]:
            with self.win.change("Slice"):
                s["export"] = export
                s["name"] = name
            self.win.refresh_slices()

    def ask_folder(self):
        start = self.win.settings.value("export_dir", os.path.expanduser("~/Documents"))
        folder = QFileDialog.getExistingDirectory(self, "Export slices into", start)
        if folder:
            self.win.settings.setValue("export_dir", folder)
        return folder

    def export_one(self, sid):
        s = next((x for x in self.win.scene.slices if x["id"] == sid), None)
        folder = self.ask_folder() if s is not None else None
        if folder and self.win.export_slices([s], folder):
            self.win.statusBar().showMessage(f"Exported {file_name(s)} to {folder}", 8000)

    def export_all(self):
        chosen = [s for s in self.win.scene.slices if s.get("export", True)]
        if not chosen:
            QMessageBox.information(self, "Export Slices", "Tick at least one slice first.")
            return
        folder = self.ask_folder()
        if not folder:
            return
        done = self.win.export_slices(chosen, folder)
        if done:
            self.win.statusBar().showMessage(
                f"Exported {len(done)} slice{'s' if len(done) != 1 else ''} to {folder}", 8000)
