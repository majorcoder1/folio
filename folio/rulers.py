"""Rulers along the top and left of the page, guides dragged out of them,
and the page grid.

Measurements start at the top-left corner of the page (bleed included), the
same place the Transform panel measures from. Drag from a ruler onto the
page to make a guide; drag a guide back off the page to remove it.
"""

import math

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QGridLayout, QWidget

from . import units

RULER = 20
GUIDE_COLOUR = QColor("#00c8ff")
GRID_COLOUR = QColor(120, 160, 255, 50)
GRID_MAJOR = QColor(120, 160, 255, 95)
GRID_STEP = {"in": 0.25, "mm": 5.0, "cm": 0.5, "px": 50.0, "pt": 18.0}


def nice_step(unit_px, min_px=60.0):
    """A round step (in units) whose ticks are at least ``min_px`` apart."""
    for base in (1, 2, 5):
        for power in range(-3, 7):
            step = base * 10 ** power
            if step * unit_px >= min_px:
                yield step
                return
    yield 10 ** 7


class Ruler(QWidget):
    def __init__(self, win, horizontal):
        super().__init__()
        self.win = win
        self.horizontal = horizontal
        self.marker = None
        if horizontal:
            self.setFixedHeight(RULER)
        else:
            self.setFixedWidth(RULER)
        self.setCursor(Qt.SplitVCursor if horizontal else Qt.SplitHCursor)
        self.setToolTip("Drag onto the page to add a guide")

    # ---- drawing ------------------------------------------------------------

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#262626"))
        p.setPen(QColor("#3a3a3a"))
        if self.horizontal:
            p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        else:
            p.drawLine(self.width() - 1, 0, self.width() - 1, self.height())
        view = self.win.view
        doc = self.win.scene.doc
        u = doc.unit
        unit_px = units.to_px(1.0, u, doc.dpi) * view.zoom()
        if unit_px <= 0:
            return
        step = next(nice_step(unit_px))
        minor = step / (4 if step * unit_px >= 80 else 2)
        origin = doc.page_rect().topLeft()
        font = QFont(self.font())
        font.setPointSizeF(7)
        p.setFont(font)
        length = self.width() if self.horizontal else self.height()
        offset = self.view_offset()

        def to_screen(value_units):
            scene = units.to_px(value_units, u, doc.dpi)
            if self.horizontal:
                return view.mapFromScene(QPointF(origin.x() + scene, 0)).x() + offset
            return view.mapFromScene(QPointF(0, origin.y() + scene)).y() + offset

        def to_units(pos):
            pt = view.mapToScene(int(pos - offset), int(pos - offset))
            px = (pt.x() - origin.x()) if self.horizontal else (pt.y() - origin.y())
            return units.from_px(px, u, doc.dpi)

        lo, hi = sorted((to_units(0), to_units(length)))
        k = math.floor(lo / minor)
        p.setPen(QColor("#8a8a8a"))
        while k * minor <= hi:
            value = k * minor
            pos = to_screen(value)
            major = abs(value / step - round(value / step)) < 1e-6
            size = RULER if major else RULER * 0.3
            if self.horizontal:
                p.drawLine(int(pos), RULER - int(size), int(pos), RULER)
                if major:
                    p.drawText(int(pos) + 3, 10, f"{value:g}")
            else:
                p.drawLine(RULER - int(size), int(pos), RULER, int(pos))
                if major:
                    p.save()
                    p.translate(10, int(pos) + 3)
                    p.rotate(-90)
                    p.drawText(-p.fontMetrics().horizontalAdvance(f"{value:g}") - 3, 0,
                               f"{value:g}")
                    p.restore()
            k += 1
        if self.marker is not None:
            p.setPen(QPen(QColor("#4a8fe7"), 1))
            m = int(self.marker + offset)
            if self.horizontal:
                p.drawLine(m, 0, m, RULER)
            else:
                p.drawLine(0, m, RULER, m)
        p.end()

    def view_offset(self):
        """Where the canvas starts, measured along this ruler."""
        vp = self.win.view.viewport()
        here = self.mapFromGlobal(vp.mapToGlobal(vp.rect().topLeft()))
        return here.x() if self.horizontal else here.y()

    def show_cursor(self, scene_pt):
        vp = self.win.view.mapFromScene(scene_pt)
        self.marker = vp.x() if self.horizontal else vp.y()
        self.update()

    # ---- dragging out a guide --------------------------------------------------

    def _scene_point(self, e):
        vp = self.win.view.viewport()
        local = vp.mapFromGlobal(e.globalPos())
        return self.win.view.mapToScene(local), vp.rect().contains(local)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and not self.win.guides_locked():
            self.win.view.temp_guide = None

    def mouseMoveEvent(self, e):
        if not e.buttons() & Qt.LeftButton or self.win.guides_locked():
            return
        sp, inside = self._scene_point(e)
        axis = "y" if self.horizontal else "x"
        self.win.view.temp_guide = (axis, sp.y() if axis == "y" else sp.x()) if inside else None
        self.win.view.viewport().update()

    def mouseReleaseEvent(self, e):
        temp, self.win.view.temp_guide = self.win.view.temp_guide, None
        if temp is not None:
            self.win.add_guide(*temp)
        self.win.view.viewport().update()


def wrap_with_rulers(win, view):
    """The canvas with a ruler above and one to the left."""
    box = QWidget()
    grid = QGridLayout(box)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setSpacing(0)
    corner = QWidget()
    corner.setFixedSize(RULER, RULER)
    corner.setStyleSheet("background: #262626;")
    win.ruler_h = Ruler(win, True)
    win.ruler_v = Ruler(win, False)
    win.ruler_corner = corner
    grid.addWidget(corner, 0, 0)
    grid.addWidget(win.ruler_h, 0, 1)
    grid.addWidget(win.ruler_v, 1, 0)
    grid.addWidget(view, 1, 1)
    for bar in (view.horizontalScrollBar(), view.verticalScrollBar()):
        bar.valueChanged.connect(lambda _: (win.ruler_h.update(), win.ruler_v.update()))
    view.zoomChanged.connect(lambda _: (win.ruler_h.update(), win.ruler_v.update()))
    return box


def grid_lines(doc, visible):
    """(xs, ys) for the grid inside the visible part of the page."""
    step = units.to_px(GRID_STEP.get(doc.unit, 0.25), doc.unit, doc.dpi)
    page = doc.page_rect()
    area = visible.intersected(page)
    if step <= 0 or area.isEmpty():
        return [], []
    xs, ys = [], []
    k = math.ceil((area.left() - page.left()) / step)
    while page.left() + k * step <= area.right():
        xs.append((page.left() + k * step, k % 4 == 0))
        k += 1
    k = math.ceil((area.top() - page.top()) / step)
    while page.top() + k * step <= area.bottom():
        ys.append((page.top() + k * step, k % 4 == 0))
        k += 1
    return xs, ys


def draw_grid_and_guides(painter, view, scene):
    visible = view.mapToScene(view.viewport().rect()).boundingRect()
    doc = scene.doc
    if view.show_grid:
        xs, ys = grid_lines(doc, visible)
        page = doc.page_rect()
        if len(xs) + len(ys) < 1200:
            for x, major in xs:
                painter.setPen(QPen(GRID_MAJOR if major else GRID_COLOUR, 0))
                painter.drawLine(QPointF(x, page.top()), QPointF(x, page.bottom()))
            for y, major in ys:
                painter.setPen(QPen(GRID_MAJOR if major else GRID_COLOUR, 0))
                painter.drawLine(QPointF(page.left(), y), QPointF(page.right(), y))
    if view.show_guides:
        painter.setPen(QPen(GUIDE_COLOUR, 0))
        for x in scene.guides.get("x", []):
            painter.drawLine(QPointF(x, visible.top()), QPointF(x, visible.bottom()))
        for y in scene.guides.get("y", []):
            painter.drawLine(QPointF(visible.left(), y), QPointF(visible.right(), y))
    temp = view.temp_guide
    if temp is not None:
        painter.setPen(QPen(GUIDE_COLOUR, 0, Qt.DashLine))
        axis, value = temp
        if axis == "x":
            painter.drawLine(QPointF(value, visible.top()), QPointF(value, visible.bottom()))
        else:
            painter.drawLine(QPointF(visible.left(), value), QPointF(visible.right(), value))
