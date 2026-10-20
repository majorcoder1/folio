"""The start window: New, Open, Recent and Templates down the side, a
searchable list of ready-made sizes, a picture of the page, and tabs for
the details. Without the side bar and the list it is Document Setup.
"""

import json
import os
import uuid

from PyQt5.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSettings, QSize, Qt
from PyQt5.QtGui import (QColor, QPolygonF, QDoubleValidator, QFont, QIcon, QPainter,
                         QPainterPath, QPen, QPixmap)
from PyQt5.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox,
                             QDialog, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
                             QLineEdit, QListView, QListWidget, QListWidgetItem,
                             QMessageBox, QPushButton, QSpinBox, QStackedWidget, QStyle,
                             QStyledItemDelegate, QTabWidget, QToolButton, QVBoxLayout,
                             QWidget)

from . import fileio, units
from .dialogs import CATEGORIES, dspin, fill_grouped, select_matching
from .document import DocSettings, cover_settings, page_settings
from .icons import icon
from .items import color_str
from .panels import ColorButton

KIND_ROLE = Qt.UserRole
ROW_ROLE = Qt.UserRole + 1
DPI_CHOICES = ["72", "96", "150", "200", "300", "400", "600"]
TEXT = QColor("#e3e5e8")
MUTED = QColor("#9aa1ab")
HEART = QColor("#e0566b")
DEFAULT_PRESET = "cover:kdp:paperback"


BOOK_SECTIONS = ("Paperback book cover", "Hardcover book cover", "eBook cover",
                 "Audiobook and podcast cover", "Book page (inside the book)")


def _size_text(w, h, unit):
    return f"{w:g} {unit} × {h:g} {unit}"


def builtin_sections():
    """[(category, [rows])]; a row is a dict describing one ready-made size."""
    out = []
    for title, form, extra, _ in CATEGORIES:
        rows = []
        if form == "cover":
            binding = extra
            for key, printer in units.PRINTERS:
                rows.append({"id": f"cover:{key}:{binding}", "name": printer, "note": "",
                             "size": "6 in × 9 in", "kind": "cover", "printer": key,
                             "binding": binding, "icon": "cover", "wide": True})
        elif extra:
            generic = "Book page" if title.startswith("Book page") else None
            for group, entries in extra:
                rows.append({"kind": "sub", "name": group})
                for entry in entries:
                    label, w, h, unit = entry[:4]
                    parts = [p.strip() for p in label.split("  ") if p.strip()]
                    name = generic or parts[0]
                    note = " ".join(p for p in parts[1:] if p.startswith("(")).strip("()")
                    rows.append({"id": "page:" + label, "name": name, "note": note,
                                 "size": _size_text(w, h, unit), "kind": "page",
                                 "entry": list(entry),
                                 "icon": "screen" if unit == "px" else
                                 "device" if unit == "pt" else "page",
                                 "wide": w > h})
        if rows:
            out.append((title, rows))
    return out


def draw_doc_icon(p, r, row):
    p.setPen(QPen(QColor("#c9ccd2"), 1.2))
    p.setBrush(Qt.NoBrush)
    kind = row.get("icon")
    if kind == "cover":
        h = r.height() * 0.8
        top = r.center().y() - h / 2
        pw = r.width() * 0.4
        p.drawRect(QRectF(r.left(), top, pw, h))
        p.drawRect(QRectF(r.right() - pw, top, pw, h))
        p.fillRect(QRectF(r.left() + pw + 1.5, top, r.width() - 2 * pw - 3, h), QColor("#4a8fe7"))
    elif kind == "device":
        body = QRectF(r.center().x() - r.width() * 0.26, r.top(), r.width() * 0.52, r.height())
        p.drawRoundedRect(body, 2.5, 2.5)
        p.drawLine(QPointF(body.center().x() - 1.5, body.bottom() - 2.5),
                   QPointF(body.center().x() + 1.5, body.bottom() - 2.5))
    elif kind == "screen":
        if row.get("wide"):
            body = QRectF(r.left(), r.top() + 2, r.width(), r.height() * 0.62)
        else:
            body = QRectF(r.center().x() - r.width() * 0.32, r.top(), r.width() * 0.64,
                          r.height() * 0.86)
        p.drawRoundedRect(body, 1.5, 1.5)
        if row.get("wide"):
            cx, bottom = body.center().x(), body.bottom()
            p.drawLine(QPointF(cx, bottom), QPointF(cx, bottom + 3))
            p.drawLine(QPointF(cx - 4, bottom + 3.5), QPointF(cx + 4, bottom + 3.5))
    else:
        if row.get("wide"):
            body = QRectF(r.left(), r.top() + r.height() * 0.2, r.width(), r.height() * 0.62)
        else:
            body = QRectF(r.center().x() - r.width() * 0.34, r.top(), r.width() * 0.68, r.height())
        fold = 4.0
        path = QPainterPath()
        path.moveTo(body.left(), body.top())
        path.lineTo(body.right() - fold, body.top())
        path.lineTo(body.right(), body.top() + fold)
        path.lineTo(body.right(), body.bottom())
        path.lineTo(body.left(), body.bottom())
        path.closeSubpath()
        p.drawPath(path)


def heart_path(r):
    path = QPainterPath()
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    path.moveTo(x + w / 2, y + h)
    path.cubicTo(x - w * 0.15, y + h * 0.5, x, y - h * 0.1, x + w / 2, y + h * 0.28)
    path.cubicTo(x + w, y - h * 0.1, x + w * 1.15, y + h * 0.5, x + w / 2, y + h)
    return path


class PresetDelegate(QStyledItemDelegate):
    """Draws the size list: headings, and rows with an icon, the name, the
    size and a heart for favourites."""

    def __init__(self, dlg):
        super().__init__(dlg)
        self.dlg = dlg

    def sizeHint(self, option, index):
        kind = index.data(KIND_ROLE)
        return QSize(260, {"header": 34, "sub": 26, "part": 30}.get(kind, 36))

    @staticmethod
    def heart_rect(rect):
        return QRect(rect.right() - 28, rect.center().y() - 7, 16, 14)

    def paint(self, p, option, index):
        kind = index.data(KIND_ROLE)
        r = option.rect
        text = index.data(Qt.DisplayRole) or ""
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        font = QFont(option.font)
        if kind == "part":
            p.fillRect(r, QColor("#1f1f1f"))
            f = QFont(font)
            f.setBold(True)
            f.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)
            p.setFont(f)
            p.setPen(QColor("#4a8fe7"))
            p.drawText(r.adjusted(12, 0, -10, 0), Qt.AlignVCenter | Qt.AlignLeft, text)
        elif kind == "header":
            p.fillRect(r, QColor("#26262a"))
            # an arrow: down when the section is open, right when it is closed
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#c3c8cf"))
            cx, cy = r.left() + 15, r.center().y()
            if text in self.dlg.collapsed:
                arrow = [QPointF(cx - 3, cy - 5), QPointF(cx + 3, cy), QPointF(cx - 3, cy + 5)]
            else:
                arrow = [QPointF(cx - 5, cy - 3), QPointF(cx + 5, cy - 3), QPointF(cx, cy + 3)]
            p.drawPolygon(QPolygonF(arrow))
            font.setBold(True)
            font.setPointSizeF(font.pointSizeF() + 0.5)
            p.setFont(font)
            p.setPen(TEXT)
            p.drawText(r.adjusted(30, 0, -10, 0), Qt.AlignVCenter | Qt.AlignLeft, text)
        elif kind == "sub":
            font.setPointSizeF(max(7.5, font.pointSizeF() - 1))
            p.setFont(font)
            p.setPen(MUTED)
            p.drawText(r.adjusted(14, 0, -10, 0), Qt.AlignVCenter | Qt.AlignLeft, text.upper())
        else:
            row = index.data(ROW_ROLE)
            font.setPointSizeF(max(7.5, font.pointSizeF() - 0.5))
            selected = bool(option.state & QStyle.State_Selected)
            hover = bool(option.state & QStyle.State_MouseOver)
            bg = QColor("#4a6b98") if selected else QColor("#3a3a3a") if hover else QColor("#333333")
            p.fillRect(QRectF(r).adjusted(2, 1, -2, -1), bg)
            draw_doc_icon(p, QRectF(r.left() + 13, r.center().y() - 9, 18, 18), row)
            heart = self.heart_rect(r)
            p.setFont(font)
            size_w = p.fontMetrics().horizontalAdvance(row.get("size", "")) + 2
            size_rect = QRect(heart.left() - size_w - 8, r.top(), size_w, r.height())
            name_rect = QRect(r.left() + 42, r.top(), size_rect.left() - r.left() - 46, r.height())
            bold = QFont(font)
            bold.setBold(True)
            p.setFont(bold)
            p.setPen(QColor("#ffffff") if selected else TEXT)
            name = p.fontMetrics().elidedText(row["name"], Qt.ElideRight, name_rect.width())
            p.drawText(name_rect, Qt.AlignVCenter | Qt.AlignLeft, name)
            used = p.fontMetrics().horizontalAdvance(name)
            if row.get("note") and used + 30 < name_rect.width():
                p.setFont(font)
                p.setPen(QColor("#c5cbd3") if selected else MUTED)
                note_rect = name_rect.adjusted(used + 8, 0, 0, 0)
                p.drawText(note_rect, Qt.AlignVCenter | Qt.AlignLeft,
                           p.fontMetrics().elidedText(row["note"], Qt.ElideRight, note_rect.width()))
            p.setFont(font)
            p.setPen(QColor("#e9edf2") if selected else QColor("#c3c8cf"))
            p.drawText(size_rect, Qt.AlignVCenter | Qt.AlignRight, row.get("size", ""))
            line_y = r.bottom() - 4
            p.setPen(QPen(QColor("#9aa4b0") if selected else QColor("#141414"), 1))
            p.drawLine(r.left() + r.width() // 2 - 10, line_y, heart.left() - 4, line_y)
            fav = row.get("id") in self.dlg.favourites
            p.setPen(QPen(HEART if fav else QColor("#8a9099"), 1.2))
            p.setBrush(HEART if fav else Qt.NoBrush)
            p.drawPath(heart_path(QRectF(heart)))
        p.restore()

    def editorEvent(self, event, model, option, index):
        if (index.data(KIND_ROLE) == "row" and event.type() == QEvent.MouseButtonRelease
                and self.heart_rect(option.rect).contains(event.pos())):
            self.dlg.toggle_favourite(index.data(ROW_ROLE)["id"])
            return True
        return super().editorEvent(event, model, option, index)


class PagePreview(QWidget):
    """A picture of the page: bleed in red, safe area in blue, and for a
    cover the back, spine and front."""

    def __init__(self):
        super().__init__()
        self.doc = None
        self.setMinimumHeight(240)

    def set_doc(self, doc):
        self.doc = doc
        self.update()

    def paintEvent(self, e):
        doc = self.doc
        if doc is None or doc.page_width <= 0 or doc.page_height <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        page = doc.page_rect()
        avail = QRectF(self.rect()).adjusted(30, 14, -30, -14)
        s = min(avail.width() / page.width(), avail.height() / page.height())
        ox = avail.center().x() - page.width() * s / 2
        oy = avail.center().y() - page.height() * s / 2

        def m(rect):
            return QRectF(ox + rect.left() * s, oy + rect.top() * s,
                          rect.width() * s, rect.height() * s)

        whole = m(page)
        p.fillRect(whole.translated(3, 4), QColor(0, 0, 0, 90))
        if doc.background:
            p.fillRect(whole, QColor(doc.background))
        else:
            cell = 8
            p.fillRect(whole, QColor("#ffffff"))
            p.save()
            p.setClipRect(whole)
            y = whole.top()
            j = 0
            while y < whole.bottom():
                x = whole.left() + (cell if j % 2 else 0)
                while x < whole.right():
                    p.fillRect(QRectF(x, y, cell, cell), QColor("#dcdcdc"))
                    x += 2 * cell
                y += cell
                j += 1
            p.restore()
        trim = m(doc.trim_rect())
        if doc.bleed > 0:
            outer = QPainterPath()
            outer.addRect(whole)
            inner = QPainterPath()
            inner.addRect(trim)
            p.fillPath(outer.subtracted(inner), QColor(225, 70, 70, 50))
            p.setPen(QPen(QColor("#d04848"), 1, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(trim)
        small = QFont(self.font())
        small.setPointSizeF(max(7.0, small.pointSizeF() - 1.5))
        small.setBold(True)
        p.setFont(small)
        if doc.kind == "cover":
            regs = doc.regions()
            spine = m(regs["spine"])
            p.fillRect(spine, QColor(74, 143, 231, 55))
            for r in doc.hinge_rects():
                p.fillRect(m(r), QColor(255, 202, 40, 50))
            p.setPen(QPen(QColor("#4a8fe7"), 1))
            p.drawLine(spine.topLeft(), spine.bottomLeft())
            p.drawLine(spine.topRight(), spine.bottomRight())
            barcode = doc.barcode_rect()
            if barcode is not None:
                p.setPen(QPen(QColor("#e0a800"), 1))
                p.drawRect(m(barcode))
            p.setPen(QColor("#9aa3ad"))
            for key, label in (("back", "BACK"), ("front", "FRONT")):
                p.drawText(m(regs[key]), Qt.AlignCenter, label)
        p.setPen(QPen(QColor("#2f6fe0"), 1.2))
        p.setBrush(Qt.NoBrush)
        for r in doc.safe_rects():
            p.drawRect(m(r))
        p.setPen(QPen(QColor(0, 0, 0, 70), 1))
        p.drawRect(whole)
        p.end()


class NewDocumentDialog(QDialog):
    """New Document (and Open, Recent, Templates). With ``current`` it is
    Document Setup for the open document."""

    def __init__(self, parent=None, current=None, templates=None, recent=None,
                 show_on_start=True):
        super().__init__(parent)
        self.setup_mode = current is not None
        self.current = current
        self.store = QSettings("Folio", "Folio")
        self.wants_open = False
        self.kind = "cover"
        self.binding = "paperback"
        self._unit = "in"
        self._loading = False
        self.base = None
        self.base_name = ""
        self.row_id = None
        try:
            self.favourites = set(json.loads(self.store.value("favourite_presets", "[]") or "[]"))
            self.collapsed = set(json.loads(self.store.value("closed_sections", "[]") or "[]"))
            self.user_presets = json.loads(self.store.value("user_presets", "[]") or "[]")
        except ValueError:
            self.favourites, self.user_presets = set(), []
            self.collapsed = set()
        self.setWindowTitle("Document Setup" if self.setup_mode else "New Document")
        self.setMinimumSize(1180, 700)
        self.resize(1320, 800)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, 1)

        self.sidebar = QWidget()
        self.sidebar.setObjectName("startSidebar")
        self.sidebar.setFixedWidth(92)
        sv = QVBoxLayout(self.sidebar)
        sv.setContentsMargins(6, 10, 6, 10)
        sv.setSpacing(6)
        self.side = {}
        group = QButtonGroup(self)
        for key, title, ic in (("new", "New", "new"), ("open", "Open", "open"),
                               ("recent", "Recent", "history"),
                               ("templates", "Templates", "cover")):
            b = QToolButton()
            b.setObjectName("sideButton")
            b.setText(title)
            b.setIcon(icon(ic))
            b.setIconSize(QSize(28, 28))
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setFixedSize(80, 66)
            if key != "open":
                b.setCheckable(True)
                group.addButton(b)
            b.clicked.connect(lambda _=False, k=key: self.show_page(k))
            sv.addWidget(b)
            self.side[key] = b
        sv.addStretch(1)
        body.addWidget(self.sidebar)

        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        self.pages.addWidget(self.build_new_page())
        self.recent_page, self.recent_grid = self.build_grid_page(recent or [], "recent")
        self.template_page, self.template_grid = self.build_grid_page(templates or [], "templates")
        self.pages.addWidget(self.recent_page)
        self.pages.addWidget(self.template_page)

        bar = QWidget()
        bar.setObjectName("startBar")
        bh = QHBoxLayout(bar)
        bh.setContentsMargins(14, 8, 14, 8)
        self.show_start = QCheckBox("Show on startup")
        self.show_start.setChecked(bool(show_on_start))
        self.show_start.setToolTip("Show this window every time Folio starts")
        bh.addWidget(self.show_start)
        bh.addStretch(1)
        self.primary = QPushButton("Apply" if self.setup_mode else "Create")
        self.primary.setDefault(True)
        self.primary.setMinimumWidth(110)
        cancel = QPushButton("Cancel")
        cancel.setMinimumWidth(110)
        self.primary.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        bh.addWidget(self.primary)
        bh.addWidget(cancel)
        outer.addWidget(bar)

        self.fill_presets()
        if self.setup_mode:
            self.sidebar.hide()
            self.left.hide()
            self.show_start.hide()
            self.load_doc(current)
            self.base = self.settings()
            self.base_name = current.title or "This document"
            self.make_setup_layout(current)
            self.update_all()
        else:
            self.side["new"].setChecked(True)
            wanted = self.store.value("last_preset_id", DEFAULT_PRESET) or DEFAULT_PRESET
            if not self.select_preset(wanted):
                self.select_preset(DEFAULT_PRESET)

    # ---- Document Setup -------------------------------------------------------

    def make_setup_layout(self, current):
        """Document Setup: a compact window like the pro apps' one, with the
        type, preset and units on top, the tabs, and what objects do."""
        from .panels import AnchorGrid
        for w in (self.title, self.save_btn, self.swap_btn, self.preview, self.summary_pane):
            w.hide()
        self.right_area.setObjectName("")
        top = QWidget()
        form = QGridLayout(top)
        form.setContentsMargins(40, 14, 40, 6)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        kind = ("Hardcover book cover" if current.hardcover else "Paperback book cover"
                if current.kind == "cover" else "Page")
        form.addWidget(self._label("Type:"), 0, 0)
        type_label = QLabel(kind)
        form.addWidget(type_label, 0, 1)
        self.page_preset = QComboBox()
        self.page_preset.addItem("Custom")
        for title, rows in builtin_sections():
            for row in rows:
                if row.get("kind") == "page":
                    self.page_preset.addItem(f"{row['name']}  {row['size']}", row["entry"])
        self.page_preset.setMaxVisibleItems(24)
        if current.kind == "page":
            u = current.unit
            w = units.from_px(current.width, u, current.dpi)
            h = units.from_px(current.height, u, current.dpi)
            for i in range(1, self.page_preset.count()):
                e = self.page_preset.itemData(i)
                if e[3] == u and abs(e[1] - w) < 1e-3 and abs(e[2] - h) < 1e-3:
                    self.page_preset.setCurrentIndex(i)
                    break
        self.tabs.setTabText(0, "Dimensions")
        if current.kind == "page":
            form.addWidget(self._label("Page Preset:"), 1, 0)
            form.addWidget(self.page_preset, 1, 1)
        form.setColumnStretch(1, 1)
        self.right_box.insertWidget(0, top)
        objects = QWidget()
        og = QGridLayout(objects)
        og.setContentsMargins(40, 6, 40, 10)
        og.setHorizontalSpacing(10)
        og.addWidget(self._label("Objects will:"), 0, 0)
        choices = QHBoxLayout()
        choices.setSpacing(0)
        self.objects_group = QButtonGroup(self)
        modes = [("anchor", "Anchor to Page"), ("rescale", "Rescale")]
        if current.kind == "cover":
            modes.insert(0, ("keep", "Stay with Cover Parts"))
        for key, text in modes:
            b = QPushButton(text)
            b.setCheckable(True)
            b.setProperty("mode", key)
            self.objects_group.addButton(b)
            choices.addWidget(b)
        self.objects_group.buttons()[0].setChecked(True)
        choices.addStretch(1)
        og.addLayout(choices, 0, 1)
        og.addWidget(self._label("Anchor:"), 1, 0)
        self.anchor = AnchorGrid()
        og.addWidget(self.anchor, 1, 1)
        note = QLabel("Objects keep their real size when the DPI changes.")
        note.setObjectName("hint")
        og.addWidget(note, 2, 1)
        self.right_box.addWidget(objects)
        self.page_preset.activated.connect(self.on_page_preset)
        self.objects_group.buttonClicked.connect(lambda _: self.anchor.setEnabled(
            self.objects_mode() == "anchor"))
        self.anchor.setEnabled(self.objects_mode() == "anchor")
        self.setMinimumSize(560, 470)
        self.resize(600, 520)

    def on_page_preset(self, index):
        entry = self.page_preset.itemData(index)
        if entry:
            _, w, h, unit, dpi, bleed, margin = entry
            self.set_page_values(w, h, unit, dpi, bleed, margin)
            self.update_all()

    def objects_mode(self):
        group = getattr(self, "objects_group", None)
        b = group.checkedButton() if group is not None else None
        return b.property("mode") if b is not None else "keep"

    def anchor_point(self):
        a = getattr(self, "anchor", None)
        return (a.fx, a.fy) if a is not None else (0.0, 0.0)

    # ---- the New page ------------------------------------------------------

    def build_new_page(self):
        page = QWidget()
        h = QHBoxLayout(page)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self.left = QWidget()
        self.left.setObjectName("presetColumn")
        self.left.setFixedWidth(380)
        lv = QVBoxLayout(self.left)
        lv.setContentsMargins(8, 8, 8, 6)
        lv.setSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search sizes")
        self.search.setClearButtonEnabled(True)
        lv.addWidget(self.search)
        top = QHBoxLayout()
        top.setSpacing(1)
        self.category = QComboBox()
        self.category.setToolTip("Jump to a kind of document")
        top.addWidget(self.category, 1)
        self.fav_only = QToolButton()
        self.fav_only.setCheckable(True)
        self.fav_only.setIcon(icon("heart"))
        self.fav_only.setToolTip("Show only your favourite sizes (click a heart to add one)")
        top.addWidget(self.fav_only)
        self.portrait = QToolButton()
        self.portrait.setIcon(icon("portrait"))
        self.portrait.setToolTip("Portrait (tall)")
        self.landscape = QToolButton()
        self.landscape.setIcon(icon("landscape"))
        self.landscape.setToolTip("Landscape (wide)")
        for b in (self.portrait, self.landscape):
            b.setCheckable(True)
            top.addWidget(b)
        lv.addLayout(top)
        self.presets = QListWidget()
        self.presets.setObjectName("presetList")
        self.presets.setItemDelegate(PresetDelegate(self))
        self.presets.setMouseTracking(True)
        self.presets.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.presets.setUniformItemSizes(False)
        self.presets.setSpacing(0)
        lv.addWidget(self.presets, 1)
        bottom = QHBoxLayout()
        self.add_preset_btn = QToolButton()
        self.add_preset_btn.setIcon(icon("save-preset"))
        self.add_preset_btn.setToolTip("Save these settings as your own preset")
        self.del_preset_btn = QToolButton()
        self.del_preset_btn.setIcon(icon("trash"))
        self.del_preset_btn.setToolTip("Delete the chosen preset (only your own)")
        bottom.addWidget(self.add_preset_btn)
        bottom.addStretch(1)
        bottom.addWidget(self.del_preset_btn)
        lv.addLayout(bottom)
        h.addWidget(self.left)

        right = QWidget()
        right.setObjectName("previewArea")
        self.right_area = right
        rv = QVBoxLayout(right)
        self.right_box = rv
        rv.setContentsMargins(0, 10, 0, 0)
        rv.setSpacing(4)
        title_row = QHBoxLayout()
        self.title_row = title_row
        title_row.addStretch(1)
        self.title = QLabel()
        self.title.setObjectName("startTitle")
        title_row.addWidget(self.title)
        title_row.addSpacing(8)
        self.save_btn = QToolButton()
        self.save_btn.setIcon(icon("save-preset"))
        self.save_btn.setToolTip("Save these settings as your own preset")
        self.swap_btn = QToolButton()
        self.swap_btn.setIcon(icon("swap"))
        self.swap_btn.setToolTip("Swap width and height")
        title_row.addWidget(self.save_btn)
        title_row.addWidget(self.swap_btn)
        title_row.addStretch(1)
        rv.addLayout(title_row)
        self.preview = PagePreview()
        rv.addWidget(self.preview, 1)

        details = QWidget()
        details.setObjectName("detailsPane")
        dh = QHBoxLayout(details)
        dh.setContentsMargins(0, 0, 0, 0)
        dh.setSpacing(0)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("detailTabs")
        self.tabs.addTab(self.build_layout_tab(), "Layout")
        self.tabs.addTab(self.build_colour_tab(), "Colour")
        self.tabs.addTab(self.build_margin_tab(), "Margins")
        self.tabs.addTab(self.build_bleed_tab(), "Bleed")
        self.tabs.setMinimumHeight(220)
        dh.addWidget(self.tabs, 1)
        summary = QWidget()
        self.summary_pane = summary
        summary.setObjectName("summaryPane")
        summary.setFixedWidth(236)
        sv = QVBoxLayout(summary)
        sv.setContentsMargins(0, 0, 0, 0)
        head = QLabel("Document Summary")
        head.setObjectName("summaryTitle")
        head.setAlignment(Qt.AlignCenter)
        sv.addWidget(head)
        self.summary = QLabel()
        self.summary.setObjectName("summaryText")
        self.summary.setTextFormat(Qt.RichText)
        self.summary.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.summary.setWordWrap(True)
        sv.addWidget(self.summary, 1)
        dh.addWidget(summary)
        rv.addWidget(details)
        h.addWidget(right, 1)

        self.search.textChanged.connect(self.apply_filter)
        self.fav_only.toggled.connect(self.apply_filter)
        self.category.activated.connect(self.jump_to_category)
        self.presets.currentItemChanged.connect(self.on_preset_row)
        self.presets.itemClicked.connect(self.on_heading_clicked)
        self.portrait.clicked.connect(lambda: self.set_orientation(False))
        self.landscape.clicked.connect(lambda: self.set_orientation(True))
        self.swap_btn.clicked.connect(self.swap_sides)
        self.add_preset_btn.clicked.connect(self.save_preset)
        self.save_btn.clicked.connect(self.save_preset)
        self.del_preset_btn.clicked.connect(self.delete_preset)
        return page

    @staticmethod
    def _grid():
        g = QGridLayout()
        g.setContentsMargins(24, 18, 24, 12)
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(8)
        g.setColumnStretch(1, 1)
        g.setColumnStretch(3, 1)
        return g

    @staticmethod
    def _label(text):
        lab = QLabel(text)
        lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return lab

    @staticmethod
    def _dpi_combo():
        c = QComboBox()
        c.setEditable(True)
        c.addItems(DPI_CHOICES)
        c.setCurrentText("300")
        c.lineEdit().setValidator(QDoubleValidator(36, 1200, 1))
        c.setToolTip("Dots per inch. 300 is right for printing.")
        return c

    def build_layout_tab(self):
        self.layout_stack = QStackedWidget()
        # a single page
        pw = QWidget()
        g = self._grid()
        pw.setLayout(g)
        self.w = dspin(0.01, 100000, 3, 1)
        self.h = dspin(0.01, 100000, 3, 1)
        self.unit = QComboBox()
        for u in units.UNITS:
            self.unit.addItem(units.UNIT_NAMES[u], u)
        self.page_dpi = self._dpi_combo()
        g.addWidget(self._label("Page width:"), 0, 0)
        g.addWidget(self.w, 0, 1)
        g.addWidget(self._label("Document units:"), 0, 2)
        g.addWidget(self.unit, 0, 3)
        g.addWidget(self._label("Page height:"), 1, 0)
        g.addWidget(self.h, 1, 1)
        g.addWidget(self._label("DPI:"), 2, 0)
        g.addWidget(self.page_dpi, 2, 1)
        g.setRowStretch(3, 1)
        self.layout_stack.addWidget(pw)
        # a book cover
        cw = QWidget()
        g = self._grid()
        cw.setLayout(g)
        self.printer = QComboBox()
        for key, title in units.PRINTERS:
            self.printer.addItem(title, key)
        self.printer.setToolTip("Each printer measures covers a little differently")
        self.trim = QComboBox()
        self.trim.setMaxVisibleItems(26)
        self.tw = dspin(2, 30, 3, 0.125, " in")
        self.th = dspin(2, 30, 3, 0.125, " in")
        self.pages_box = QSpinBox()
        self.pages_box.setRange(4, 1200)
        self.pages_box.setValue(200)
        self.paper = QComboBox()
        self.spine_auto = QCheckBox("Spine from page count")
        self.spine_auto.setChecked(True)
        self.spine = dspin(0, 5, 3, 0.01, " in")
        self.cover_dpi = self._dpi_combo()
        rows = [("Printer:", self.printer, "Book size:", self.trim),
                ("Width:", self.tw, "Height:", self.th),
                ("Pages:", self.pages_box, "Paper:", self.paper),
                ("", self.spine_auto, "Spine width:", self.spine),
                ("DPI:", self.cover_dpi, None, None)]
        for r, (a, wa, b, wb) in enumerate(rows):
            g.addWidget(self._label(a), r, 0)
            g.addWidget(wa, r, 1)
            if b is not None:
                g.addWidget(self._label(b), r, 2)
                g.addWidget(wb, r, 3)
        g.setRowStretch(len(rows), 1)
        self.layout_stack.addWidget(cw)

        self.unit.currentIndexChanged.connect(self.on_unit)
        for box in (self.w, self.h, self.tw, self.th, self.spine):
            box.valueChanged.connect(self.on_changed)
        for combo in (self.page_dpi, self.cover_dpi):
            combo.currentTextChanged.connect(self.on_changed)
        self.pages_box.valueChanged.connect(self.on_changed)
        self.paper.currentIndexChanged.connect(self.on_changed)
        self.spine_auto.toggled.connect(self.on_changed)
        self.printer.currentIndexChanged.connect(lambda _: self.refill_cover())
        self.trim.currentIndexChanged.connect(self.on_trim)
        return self.layout_stack

    def build_colour_tab(self):
        w = QWidget()
        g = self._grid()
        w.setLayout(g)
        fmt = QLabel("RGB, 8 bits per colour")
        self.page_colour = ColorButton("Page colour")
        self.page_colour.setColor(QColor("#ffffff"))
        self.transparent = QCheckBox("Transparent background")
        self.transparent.setToolTip("For logos and artwork that go on top of other things")
        note = QLabel("KDP, IngramSpark and Lulu all take RGB files and turn them into "
                      "printing colours themselves.")
        note.setObjectName("hint")
        note.setWordWrap(True)
        g.addWidget(self._label("Colour format:"), 0, 0)
        g.addWidget(fmt, 0, 1)
        g.addWidget(self._label("Page colour:"), 1, 0)
        g.addWidget(self.page_colour, 1, 1)
        g.addWidget(self.transparent, 2, 1, 1, 3)
        g.addWidget(note, 3, 0, 1, 4)
        g.setRowStretch(4, 1)
        self.page_colour.colorChanged.connect(self.on_changed)
        self.transparent.toggled.connect(self.on_changed)
        return w

    def build_margin_tab(self):
        w = QWidget()
        g = self._grid()
        w.setLayout(g)
        self.use_margin = QCheckBox("Include safe margin")
        self.use_margin.setChecked(True)
        self.margin = dspin(0, 10000, 3, 0.125)
        note = QLabel("Keep words and faces inside the blue line, so the printer's "
                      "trimming cannot cut them off.")
        note.setObjectName("hint")
        note.setWordWrap(True)
        g.addWidget(self.use_margin, 0, 1, 1, 3)
        g.addWidget(self._label("All sides:"), 1, 0)
        g.addWidget(self.margin, 1, 1)
        g.addWidget(note, 2, 0, 1, 4)
        g.setRowStretch(3, 1)
        self.use_margin.toggled.connect(self.on_changed)
        self.margin.valueChanged.connect(self.on_changed)
        return w

    def build_bleed_tab(self):
        w = QWidget()
        g = self._grid()
        w.setLayout(g)
        self.bleed_label = self._label("All sides:")
        self.bleed = dspin(0, 10000, 3, 0.0625)
        self.bleed_note = QLabel()
        self.bleed_note.setObjectName("hint")
        self.bleed_note.setWordWrap(True)
        g.addWidget(self.bleed_label, 0, 0)
        g.addWidget(self.bleed, 0, 1)
        g.addWidget(self.bleed_note, 1, 0, 1, 4)
        g.setRowStretch(2, 1)
        self.bleed.valueChanged.connect(self.on_changed)
        return w

    # ---- Recent and Templates ---------------------------------------------

    def build_grid_page(self, paths, which):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(10, 10, 10, 6)
        search = QLineEdit()
        search.setPlaceholderText("Search")
        search.setClearButtonEnabled(True)
        search.setMaximumWidth(320)
        v.addWidget(search)
        grid = QListWidget()
        grid.setObjectName("thumbGrid")
        grid.setViewMode(QListView.IconMode)
        grid.setIconSize(QSize(170, 170))
        grid.setGridSize(QSize(200, 226))
        grid.setResizeMode(QListView.Adjust)
        grid.setMovement(QListView.Static)
        grid.setWordWrap(True)
        empty = QLabel("Nothing here yet. Files you open or save show up here."
                       if which == "recent" else
                       "No templates yet.\n\nMake a design you want to use again, then choose "
                       "File, Export as Template. It will show up here.")
        empty.setObjectName("hint")
        empty.setWordWrap(True)
        empty.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        v.addWidget(empty)
        v.addWidget(grid, 1)
        for path in paths:
            it = QListWidgetItem(os.path.splitext(os.path.basename(path))[0])
            png = fileio.read_thumbnail(path)
            pix = QPixmap()
            if png and pix.loadFromData(png):
                it.setIcon(QIcon(pix))
            else:
                it.setIcon(icon("cover"))
            it.setData(Qt.UserRole, path)
            it.setToolTip(path)
            grid.addItem(it)
        if which == "templates":
            row = QHBoxLayout()
            row.addStretch(1)
            delete = QPushButton("Delete template")
            delete.clicked.connect(self.delete_template)
            row.addWidget(delete)
            v.addLayout(row)
            self.delete_template_btn = delete

        def refresh():
            text = search.text().strip().lower()
            for i in range(grid.count()):
                it = grid.item(i)
                it.setHidden(bool(text) and text not in it.text().lower())
            has = grid.count() > 0
            grid.setVisible(has)
            empty.setVisible(not has)
            if which == "templates":
                self.delete_template_btn.setVisible(has)

        search.textChanged.connect(refresh)
        grid.itemDoubleClicked.connect(lambda _: self.accept())
        grid.currentItemChanged.connect(lambda *_: self.update_primary())
        if grid.count():
            grid.setCurrentRow(0)
        refresh()
        w.refresh = refresh
        return w, grid

    def delete_template(self):
        it = self.template_grid.currentItem()
        if it is None:
            return
        answer = QMessageBox.question(self, "Delete template",
                                      f"Delete the template “{it.text()}”?")
        if answer != QMessageBox.Yes:
            return
        try:
            os.remove(it.data(Qt.UserRole))
        except OSError:
            pass
        self.template_grid.takeItem(self.template_grid.row(it))
        self.template_page.refresh()
        self.update_primary()

    def show_page(self, key):
        if key == "open":
            self.wants_open = True
            self.reject()
            return
        page = {"new": 0, "recent": 1, "templates": 2}[key]
        self.pages.setCurrentIndex(page)
        self.side[key].setChecked(True)
        self.update_primary()

    def update_primary(self):
        if not hasattr(self, "primary"):
            return      # still being built
        page = self.pages.currentIndex()
        if page == 0:
            self.primary.setText("Apply" if self.setup_mode else "Create")
            self.primary.setEnabled(True)
        elif page == 1:
            self.primary.setText("Open")
            self.primary.setEnabled(self.recent_grid.currentItem() is not None)
        else:
            self.primary.setText("Create")
            self.primary.setEnabled(self.template_grid.currentItem() is not None)

    def recent_path(self):
        if self.pages.currentIndex() == 1 and self.recent_grid.currentItem() is not None:
            return self.recent_grid.currentItem().data(Qt.UserRole)
        return None

    def template_path(self):
        if self.pages.currentIndex() == 2 and self.template_grid.currentItem() is not None:
            return self.template_grid.currentItem().data(Qt.UserRole)
        return None

    def accept(self):
        if self.pages.currentIndex() == 1 and not self.recent_path():
            return
        if self.pages.currentIndex() == 2 and not self.template_path():
            return
        super().accept()

    # ---- the size list ----------------------------------------------------

    def sections(self):
        out = []
        if self.user_presets:
            rows = []
            for preset in self.user_presets:
                try:
                    s = DocSettings.from_dict(preset["doc"])
                except (KeyError, TypeError):
                    continue
                if s.kind == "cover":
                    size = f"{s.trim_w_in:g} × {s.trim_h_in:g} in"
                else:
                    u = s.unit
                    size = _size_text(round(units.from_px(s.width, u, s.dpi), 3),
                                      round(units.from_px(s.height, u, s.dpi), 3), u)
                rows.append({"id": preset["id"], "name": preset["name"], "note": "",
                             "size": size, "kind": "user", "doc": preset["doc"],
                             "icon": "cover" if s.kind == "cover" else "page",
                             "wide": s.page_width > s.page_height})
            if rows:
                out.append(("My presets", rows))
        return out + builtin_sections()

    def fill_presets(self):
        self.presets.blockSignals(True)
        self.presets.clear()
        self.category.clear()
        self.headers = {}
        part = None
        for title, rows in self.sections():
            wanted = ("My presets" if title == "My presets" else
                      "Books" if title in BOOK_SECTIONS else "Other sizes")
            if wanted != part and wanted != "My presets":
                part = wanted
                divider = QListWidgetItem(part.upper())
                divider.setData(KIND_ROLE, "part")
                divider.setFlags(Qt.ItemIsEnabled)
                self.presets.addItem(divider)
                self.headers[part] = divider
                self.category.addItem(part)
                self.category.setItemData(self.category.count() - 1,
                                          QFont("", -1, QFont.Bold), Qt.FontRole)
            head = QListWidgetItem(title)
            head.setData(KIND_ROLE, "header")
            head.setFlags(Qt.ItemIsEnabled)
            self.presets.addItem(head)
            self.headers[title] = head
            self.category.addItem(title)
            for row in rows:
                if row["kind"] == "sub":
                    it = QListWidgetItem(row["name"])
                    it.setData(KIND_ROLE, "sub")
                    it.setFlags(Qt.ItemIsEnabled)
                else:
                    it = QListWidgetItem(row["name"])
                    it.setData(KIND_ROLE, "row")
                    it.setData(ROW_ROLE, row)
                    tip = row["name"] + (f" ({row['note']})" if row.get("note") else "")
                    it.setToolTip(f"{tip}: {row['size']}")
                self.presets.addItem(it)
        self.presets.blockSignals(False)
        self.apply_filter()

    def row_items(self):
        for i in range(self.presets.count()):
            it = self.presets.item(i)
            if it.data(KIND_ROLE) == "row":
                yield it

    def select_preset(self, preset_id):
        for it in self.row_items():
            if it.data(ROW_ROLE)["id"] == preset_id:
                if it.isHidden():
                    self.search.clear()
                    self.fav_only.setChecked(False)
                    for i in range(self.presets.row(it), -1, -1):
                        h = self.presets.item(i)
                        if h.data(KIND_ROLE) == "header":
                            self.collapsed.discard(h.text())
                            break
                    self.apply_filter()
                self.presets.scrollToItem(it, QAbstractItemView.PositionAtCenter)
                self.presets.setCurrentItem(it)
                return True
        return False

    def apply_filter(self):
        text = self.search.text().strip().lower()
        favs = self.fav_only.isChecked()
        visible_under = {}
        current_head = None
        sub = None
        for i in range(self.presets.count()):
            it = self.presets.item(i)
            kind = it.data(KIND_ROLE)
            if kind == "header":
                current_head = it
                visible_under[id(it)] = 0
                sub = None
                continue
            if kind == "sub":
                sub = it
                visible_under[id(it)] = 0
                continue
            if kind == "part":
                continue
            row = it.data(ROW_ROLE)
            words = " ".join([row["name"], row.get("note", ""), row.get("size", ""),
                              current_head.text() if current_head else "",
                              sub.text() if sub else ""]).lower()
            show = (not text or all(w in words for w in text.split())) and \
                (not favs or row["id"] in self.favourites)
            closed = not text and not favs and current_head is not None \
                and current_head.text() in self.collapsed
            it.setHidden(not show or closed)
            if show:
                visible_under[id(current_head)] = visible_under.get(id(current_head), 0) + 1
                if sub is not None:
                    visible_under[id(sub)] += 1
        head = None
        for i in range(self.presets.count()):
            it = self.presets.item(i)
            kind = it.data(KIND_ROLE)
            if kind == "header":
                head = it
                it.setHidden(visible_under.get(id(it), 0) == 0)
            elif kind == "sub":
                closed = not text and not favs and head is not None and head.text() in self.collapsed
                it.setHidden(closed or visible_under.get(id(it), 0) == 0)

    def on_heading_clicked(self, item):
        """Click a section heading to close it, click again to open it."""
        if item is None or item.data(KIND_ROLE) != "header":
            return
        self.collapsed ^= {item.text()}
        self.store.setValue("closed_sections", json.dumps(sorted(self.collapsed)))
        self.apply_filter()
        self.presets.viewport().update()

    def jump_to_category(self, index):
        head = self.headers.get(self.category.itemText(index))
        if head is not None and not head.isHidden():
            self.presets.scrollToItem(head, QAbstractItemView.PositionAtTop)

    def show_category(self, item):
        """Show the chosen size's section in the menu above the list."""
        for i in range(self.presets.row(item), -1, -1):
            it = self.presets.item(i)
            if it.data(KIND_ROLE) == "header":
                self.category.blockSignals(True)
                self.category.setCurrentIndex(max(0, self.category.findText(it.text())))
                self.category.blockSignals(False)
                return

    def follow_category(self, *_):
        """Show the section at the top of the list in the menu, as it scrolls."""
        top = self.presets.indexAt(self.presets.viewport().rect().topLeft() + QPoint(4, 4))
        title = None
        for i in range(top.row() if top.isValid() else 0, -1, -1):
            it = self.presets.item(i)
            if it is not None and it.data(KIND_ROLE) == "header":
                title = it.text()
                break
        if title is not None and self.category.currentText() != title:
            self.category.blockSignals(True)
            self.category.setCurrentIndex(max(0, self.category.findText(title)))
            self.category.blockSignals(False)

    def toggle_favourite(self, preset_id):
        if preset_id in self.favourites:
            self.favourites.discard(preset_id)
        else:
            self.favourites.add(preset_id)
        self.store.setValue("favourite_presets", json.dumps(sorted(self.favourites)))
        self.apply_filter()
        self.presets.viewport().update()

    def on_preset_row(self, item, _previous=None):
        if item is None or item.data(KIND_ROLE) != "row":
            return
        row = item.data(ROW_ROLE)
        self._loading = True
        try:
            if row["kind"] == "cover":
                self.set_kind("cover")
                self.binding = row["binding"]
                self.printer.blockSignals(True)
                self.printer.setCurrentIndex(max(0, self.printer.findData(row["printer"])))
                self.printer.blockSignals(False)
                self.tw.setValue(6.0)
                self.th.setValue(9.0)
                self.refill_cover()
            elif row["kind"] == "user":
                self.load_doc(DocSettings.from_dict(row["doc"]))
            else:
                self.set_kind("page")
                _, w, h, unit, dpi, bleed, margin = row["entry"]
                self.set_page_values(w, h, unit, dpi, bleed, margin)
        finally:
            self._loading = False
        self.row_id = row["id"]
        self.show_category(item)
        if row["kind"] == "cover":
            self.base_name = f"{row['name']} {row['binding']}"
        else:
            self.base_name = row["name"] + (f" {row['size']}" if row["kind"] == "page"
                                            and row["name"] == "Book page" else "")
        self.base = self.settings()
        self.store.setValue("last_preset_id", row["id"])
        self.update_all()

    def save_preset(self):
        name, ok = QInputDialog.getText(self, "Save preset", "Name for these settings:",
                                        text=self.base_name.rstrip("*"))
        name = name.strip()
        if not ok or not name:
            return
        preset = {"id": "user:" + uuid.uuid4().hex[:10], "name": name,
                  "doc": self.settings().to_dict()}
        self.user_presets.append(preset)
        self.store.setValue("user_presets", json.dumps(self.user_presets))
        self.fill_presets()
        self.select_preset(preset["id"])

    def delete_preset(self):
        it = self.presets.currentItem()
        if it is None or it.data(KIND_ROLE) != "row" or it.data(ROW_ROLE)["kind"] != "user":
            QMessageBox.information(self, "Delete preset",
                                    "Only presets you saved yourself can be deleted.")
            return
        pid = it.data(ROW_ROLE)["id"]
        self.user_presets = [p for p in self.user_presets if p["id"] != pid]
        self.store.setValue("user_presets", json.dumps(self.user_presets))
        self.fill_presets()
        self.select_preset(DEFAULT_PRESET)

    # ---- fields -------------------------------------------------------------

    def set_kind(self, kind):
        self.kind = kind
        self.layout_stack.setCurrentIndex(1 if kind == "cover" else 0)
        for b in (self.portrait, self.landscape, self.swap_btn):
            b.setEnabled(kind == "page")
        self.set_length_unit("in" if kind == "cover" else self._unit)

    def set_length_unit(self, unit):
        dec = units.decimals(unit)
        for s in (self.bleed, self.margin):
            s.blockSignals(True)
            s.setDecimals(dec)
            s.setSuffix(" " + unit)
            s.blockSignals(False)
        if self.kind == "page":
            for s in (self.w, self.h):
                s.blockSignals(True)
                s.setDecimals(dec)
                s.setSuffix(" " + unit)
                s.blockSignals(False)

    def set_page_values(self, w, h, unit, dpi, bleed=0.0, margin=0.0):
        self._unit = unit
        self.unit.blockSignals(True)
        self.unit.setCurrentIndex(max(0, self.unit.findData(unit)))
        self.unit.blockSignals(False)
        self.set_length_unit(unit)
        self.page_dpi.setCurrentText(f"{float(dpi):g}")
        for box, value in ((self.w, w), (self.h, h), (self.bleed, bleed), (self.margin, margin)):
            box.blockSignals(True)
            box.setValue(value)
            box.blockSignals(False)
        self.use_margin.setChecked(margin > 0)
        self.on_changed()

    def on_unit(self):
        new = self.unit.currentData()
        dpi = self.dpi_value(self.page_dpi)
        boxes = (self.w, self.h, self.bleed, self.margin)
        vals = [units.to_px(b.value(), self._unit, dpi) for b in boxes]
        self._unit = new
        self.set_length_unit(new)
        for b, px in zip(boxes, vals):
            b.blockSignals(True)
            b.setValue(units.from_px(px, new, dpi))
            b.blockSignals(False)
        self.on_changed()

    def refill_cover(self):
        """Sizes, papers, bleed and margin for the chosen printer and binding."""
        printer = self.printer.currentData() or "kdp"
        spec = units.cover_spec(printer, self.binding)
        w, h = self.tw.value() or 6.0, self.th.value() or 9.0
        was_loading, self._loading = self._loading, True
        fill_grouped(self.trim, units.size_groups(printer, self.binding), other="Other size…")
        if not select_matching(self.trim, lambda d: abs(d[1] - w) < 1e-6 and abs(d[2] - h) < 1e-6):
            select_matching(self.trim, lambda d: d[1] == 6.0 and d[2] == 9.0)
        paper = self.paper.currentData()
        self.paper.blockSignals(True)
        self.paper.clear()
        for key, title, _ in units.PRINTER_PAPERS[printer]:
            self.paper.addItem(title, key)
        self.paper.setCurrentIndex(max(0, self.paper.findData(paper)))
        self.paper.blockSignals(False)
        for box, value in ((self.bleed, spec["wrap"]), (self.margin, spec["safe"])):
            box.blockSignals(True)
            box.setValue(value)
            box.blockSignals(False)
        self.use_margin.setChecked(True)
        self._loading = was_loading
        self.on_trim()

    def on_trim(self):
        data = self.trim.currentData()
        custom = not isinstance(data, tuple)
        self.tw.setEnabled(custom)
        self.th.setEnabled(custom)
        if not custom:
            for box, value in ((self.tw, data[1]), (self.th, data[2])):
                box.blockSignals(True)
                box.setValue(value)
                box.blockSignals(False)
        self.on_changed()

    def trim_size(self):
        data = self.trim.currentData()
        if isinstance(data, tuple):
            return data[1], data[2]
        return self.tw.value(), self.th.value()

    @staticmethod
    def dpi_value(combo):
        try:
            return min(max(float(combo.currentText()), 36.0), 1200.0)
        except ValueError:
            return 300.0

    def background(self):
        return "" if self.transparent.isChecked() else color_str(self.page_colour.color())

    def settings(self):
        margin = self.margin.value() if self.use_margin.isChecked() else 0.0
        if self.kind == "cover":
            w, h = self.trim_size()
            s = cover_settings(w, h, self.pages_box.value(), self.paper.currentData(),
                               self.bleed.value(), margin, self.dpi_value(self.cover_dpi),
                               self.binding, self.printer.currentData() or "kdp")
            s.spine_override_in = 0.0 if self.spine_auto.isChecked() else self.spine.value()
            s.background = self.background()
        else:
            s = page_settings(self.w.value(), self.h.value(), self._unit,
                              self.dpi_value(self.page_dpi), self.bleed.value(), margin,
                              self.background())
        if self.current is not None:
            s.title = self.current.title
            s.barcode = self.current.barcode
            if s.kind == "cover":
                s.unit = self.current.unit
        return s

    def load_doc(self, s):
        self._loading = True
        try:
            self.page_colour.setColor(QColor(s.background or "#ffffffff"))
            self.transparent.setChecked(not s.background)
            if s.kind == "cover":
                self.set_kind("cover")
                self.binding = s.binding
                self.printer.blockSignals(True)
                self.printer.setCurrentIndex(max(0, self.printer.findData(s.printer)))
                self.printer.blockSignals(False)
                self.tw.setValue(s.trim_w_in)
                self.th.setValue(s.trim_h_in)
                self.refill_cover()
                if not select_matching(self.trim, lambda d: abs(d[1] - s.trim_w_in) < 1e-6
                                       and abs(d[2] - s.trim_h_in) < 1e-6):
                    self.trim.setCurrentIndex(self.trim.count() - 1)
                self.tw.setValue(s.trim_w_in)
                self.th.setValue(s.trim_h_in)
                self.pages_box.setValue(s.pages)
                self.paper.setCurrentIndex(max(0, self.paper.findData(s.paper)))
                self.spine_auto.setChecked(s.spine_override_in <= 0)
                self.spine.setValue(s.spine_in)
                self.bleed.setValue(s.bleed / s.dpi)
                self.margin.setValue(s.margin / s.dpi)
                self.use_margin.setChecked(s.margin > 0)
                self.cover_dpi.setCurrentText(f"{s.dpi:g}")
            else:
                self.set_kind("page")
                u = s.unit
                self.set_page_values(units.from_px(s.width, u, s.dpi),
                                     units.from_px(s.height, u, s.dpi), u, s.dpi,
                                     units.from_px(s.bleed, u, s.dpi),
                                     units.from_px(s.margin, u, s.dpi))
                self.use_margin.setChecked(s.margin > 0)
        finally:
            self._loading = False
        self.update_all()

    def set_orientation(self, wide):
        if self.kind != "page":
            return
        w, h = self.w.value(), self.h.value()
        if (wide and w < h) or (not wide and w > h):
            self.swap_sides()
        else:
            self.update_all()

    def swap_sides(self):
        if self.kind != "page":
            return
        w, h = self.w.value(), self.h.value()
        for box, value in ((self.w, h), (self.h, w)):
            box.blockSignals(True)
            box.setValue(value)
            box.blockSignals(False)
        self.on_changed()

    def on_changed(self, *_):
        if not self._loading:
            self.update_all()

    def update_all(self):
        s = self.settings()
        if self.kind == "cover":
            auto = self.spine_auto.isChecked()
            self.spine.setEnabled(not auto)
            if auto:
                self.spine.blockSignals(True)
                self.spine.setValue(s.spine_in)
                self.spine.blockSignals(False)
        self.margin.setEnabled(self.use_margin.isChecked())
        self.page_colour.setEnabled(not self.transparent.isChecked())
        hard = s.kind == "cover" and s.binding == "hardcover"
        self.bleed_label.setText("Wrap, all sides:" if hard else "All sides:")
        self.bleed_note.setText(
            "The wrap is the part of the cover that folds round the boards." if hard else
            "Bleed is extra picture past the edge, trimmed off after printing. "
            "Book printers ask for 0.125 in (3 mm).")
        wide = s.trim_width > s.trim_height
        self.portrait.setChecked(not wide)
        self.landscape.setChecked(wide)
        self.preview.set_doc(s)
        star = "*" if self.base is not None and s != self.base else ""
        self.title.setText((self.base_name or "Custom") + star)
        self.summary.setText(self.summary_html(s))

    def summary_html(self, s):
        u = "in" if s.kind == "cover" else s.unit

        def size(px_w, px_h):
            dec = units.decimals(u)
            return (f"{units.tidy(units.from_px(px_w, u, s.dpi), dec)} × "
                    f"{units.tidy(units.from_px(px_h, u, s.dpi), dec)} {u}")

        rows = [("Size", size(s.trim_width, s.trim_height))]
        if s.bleed > 0:
            rows.append(("With bleed" if not s.hardcover else "With wrap",
                         size(s.page_width, s.page_height)))
        rows.append(("DPI", f"{s.dpi:g}"))
        rows.append(("Pixels", f"{s.page_width:.0f} × {s.page_height:.0f}"))
        swatch = ("<span style='color:#ff4040'>■</span><span style='color:#40d040'>■"
                  "</span><span style='color:#4080ff'>■</span>")
        rows.append(("Colour", f"RGB 8-bit {swatch}"))
        rows.append(("Background", "transparent" if not s.background else "solid"))
        if s.kind == "cover":
            rows.append(("Printer", units.PRINTER_NAMES.get(s.printer, "")))
            rows.append(("Pages", f"{s.pages}"))
            rows.append(("Spine", f"{units.tidy(s.spine_in, 3)} in"))
            lo, hi = s.spec["pages"]
            if not lo <= s.pages <= hi:
                rows.append(("Note", f"{units.PRINTER_NAMES[s.printer]} prints "
                                     f"{s.binding}s with {lo} to {hi} pages."))
            elif s.pages < s.spec["spine_text_pages"]:
                rows.append(("Note", f"Under {s.spec['spine_text_pages']} pages: no text "
                                     f"on the spine."))
        cells = "".join(f"<tr><td style='color:#9aa1ab;padding:2px 10px 2px 0'>{a}:</td>"
                        f"<td style='padding:2px 0'>{b}</td></tr>" for a, b in rows)
        name = (self.title.text() or "").replace("&", "&amp;").replace("<", "&lt;")
        return f"<div style='margin:8px 10px'><b>{name}</b><table>{cells}</table></div>"
