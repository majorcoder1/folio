"""The Pixel persona: painting on pictures ("pixel layers") and selecting
pixels, as in the pixel side of pro design apps.

A pixel layer is a picture whose pixels can be changed. Painting on a
placed photo first makes an editable copy, so the original file is never
touched. Each brush stroke is one undo step that remembers only the part
of the picture it changed.

The pixel selection is an outline on the page (page coordinates). Brushes,
fills and Delete only work inside it while it exists.
"""

import math
import random

from PyQt5.QtCore import QPointF, QRect, QRectF, Qt
from PyQt5.QtGui import (QBitmap, QBrush, QColor, QImage, QPainter, QPainterPath, QPen,
                         QRadialGradient, QRegion, QTransform)
from PyQt5.QtWidgets import QUndoCommand

from . import shapes
from .items import blur_image
from .tools import Tool, _dist

DEFAULT_BRUSH = {"size": 60.0, "hardness": 0.7, "opacity": 100.0, "flow": 100.0,
                 "tolerance": 32, "sample": "page"}


# ---- undo ---------------------------------------------------------------------------

class PixelCommand(QUndoCommand):
    """One brush stroke (or fill, or clear): the changed area before and after."""

    def __init__(self, win, aid, rect, before, after, label):
        super().__init__(label)
        self.win = win
        self.aid = aid
        self.rect = QRect(rect)
        self.before, self.after = before, after
        self.first = True

    def _paste(self, patch):
        image = self.win.scene.assets.live.get(self.aid)
        if image is None:
            return
        p = QPainter(image)
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.drawImage(self.rect.topLeft(), patch)
        p.end()
        self.win.pixels_changed(self.aid)

    def redo(self):
        if self.first:
            self.first = False
            return
        self._paste(self.after)

    def undo(self):
        self._paste(self.before)


# ---- layers -------------------------------------------------------------------------

def to_layer(item):
    """Page coordinates -> pixel coordinates of an image layer."""
    image_size = item.assets.size(item.aid)
    inv, _ = item.sceneTransform().inverted()
    return inv * QTransform.fromScale(image_size.width() / max(item.w, 1e-9),
                                      image_size.height() / max(item.h, 1e-9))


def layer_scale(item):
    size = item.assets.size(item.aid)
    return (size.width() / max(item.w, 1e-9) + size.height() / max(item.h, 1e-9)) / 2


class Stroke:
    """Changes to one layer, kept as a single undo step."""

    def __init__(self, win, item, label):
        self.win = win
        self.item = item
        self.label = label
        self.aid = item.aid
        self.image = win.scene.assets.live[self.aid]
        self.start = self.image.copy()
        self.dirty = QRect()
        self.to_layer = to_layer(item)
        self.scale = layer_scale(item)
        sel = win.pixel_selection
        self.clip = self.to_layer.map(sel) if sel is not None and not sel.isEmpty() else None

    def painter(self):
        p = QPainter(self.image)
        p.setRenderHint(QPainter.Antialiasing)
        if self.clip is not None:
            p.setClipPath(self.clip)
        return p

    def touch(self, rect):
        self.dirty = self.dirty.united(rect.toAlignedRect().intersected(self.image.rect()))
        self.win.pixels_changed(self.aid)

    def finish(self):
        if self.dirty.isEmpty():
            return False
        r = self.dirty
        self.win.undo.push(PixelCommand(self.win, self.aid, r, self.start.copy(r),
                                        self.image.copy(r), self.label))
        self.start = None
        self.win.update_title()
        return True


# ---- brushes ------------------------------------------------------------------------

def dab_brush(colour, centre, radius, hardness, alpha):
    c = QColor(colour)
    c.setAlphaF(max(0.0, min(1.0, c.alphaF() * alpha)))
    g = QRadialGradient(centre, max(radius, 0.5))
    edge = QColor(c)
    edge.setAlpha(0)
    g.setColorAt(0.0, c)
    g.setColorAt(max(0.0, min(0.99, hardness)), c)
    g.setColorAt(1.0, edge)
    return QBrush(g)


BRUSH_SHAPE_DEFAULTS = {"shape": "round", "squash": 1.0, "angle": 0.0, "grain": 0.0,
                        "scatter": 0.0, "spacing": 0.3}


def shape_dab(p, centre, radius, s, colour, alpha):
    """One touch of a shaped brush: round or flat (chisel), speckled for dry
    media, scattered, or a stamp (star, heart, dot, line ...)."""
    shape = s.get("shape", "round")
    hardness = s.get("hardness", 0.7)
    grain = s.get("grain", 0.0)
    scatter = s.get("scatter", 0.0)
    if scatter > 0:
        reach = radius * scatter
        centre = QPointF(centre.x() + random.uniform(-reach, reach),
                         centre.y() + random.uniform(-reach, reach))
    c = QColor(colour)
    c.setAlphaF(max(0.0, min(1.0, c.alphaF() * alpha)))
    p.save()
    p.translate(centre)
    p.rotate(s.get("angle", 0.0))
    p.scale(1.0, max(0.05, s.get("squash", 1.0)))
    if grain > 0 and shape in ("round", "square"):
        # the speckle is the same at any brush size: dots are a fixed fraction
        # of the brush, and each touch covers a fixed share of its disc
        dot = max(0.5, radius * 0.07)
        share = 0.04 + 0.15 * grain
        count = int(min(160, max(8, share * (radius / dot) ** 2)))
        p.setPen(Qt.NoPen)
        for _ in range(count):
            a = random.uniform(0, 2 * math.pi)
            d = radius * math.sqrt(random.random())
            fade = 1.0 - (1.0 - hardness) * (d / max(radius, 1e-6)) ** 2
            dc = QColor(c)
            dc.setAlphaF(max(0.0, min(1.0, c.alphaF() * random.uniform(0.35, 1.0) * fade)))
            p.setBrush(dc)
            r = dot * random.uniform(0.6, 1.4)
            p.drawEllipse(QPointF(d * math.cos(a), d * math.sin(a)), r, r)
    elif shape == "round":
        p.setPen(Qt.NoPen)
        p.setBrush(dab_brush(colour, QPointF(0, 0), radius, hardness, alpha))
        p.drawEllipse(QRectF(-radius, -radius, 2 * radius, 2 * radius))
    elif shape == "line":
        p.setPen(QPen(c, max(1.0, radius * 0.12), Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(-radius, 0), QPointF(radius, 0))
    elif shape == "cross":
        p.setPen(QPen(c, max(1.0, radius * 0.22), Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(-radius, 0), QPointF(radius, 0))
        p.drawLine(QPointF(0, -radius), QPointF(0, radius))
    elif shape == "square":
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawRect(QRectF(-radius, -radius, 2 * radius, 2 * radius))
    else:
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        if shape == "dot":
            p.drawEllipse(QRectF(-radius * 0.5, -radius * 0.5, radius, radius))
        else:
            p.drawPath(shapes.preview_path(shape, QRectF(-radius, -radius, 2 * radius, 2 * radius)))
    p.restore()


def paint_dab(stroke, kind, centre, radius, settings, colour):
    """One touch of the brush at ``centre`` (layer pixels)."""
    hardness = settings["hardness"]
    alpha = settings["flow"] / 100.0 * settings["opacity"] / 100.0
    reach = 1.0 + (settings.get("scatter", 0.0) if kind == "brush" else 0.0)
    box = QRectF(centre.x() - radius * reach, centre.y() - radius * reach,
                 2 * radius * reach, 2 * radius * reach)
    p = stroke.painter()
    p.setPen(Qt.NoPen)
    if kind == "brush":
        shape_dab(p, centre, radius, settings, colour, alpha)
    elif kind == "erase":
        p.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        p.setBrush(dab_brush(QColor(0, 0, 0), centre, radius, hardness, alpha))
        p.drawEllipse(box)
    elif kind in ("dodge", "burn"):
        p.setCompositionMode(QPainter.CompositionMode_SourceAtop)
        tone = QColor(255, 255, 255) if kind == "dodge" else QColor(0, 0, 0)
        p.setBrush(dab_brush(tone, centre, radius, hardness, alpha * 0.25))
        p.drawEllipse(box)
    elif kind == "blur":
        area = box.toAlignedRect().intersected(stroke.image.rect())
        if not area.isEmpty():
            patch = stroke.image.copy(area)
            soft = blur_image(patch, max(1.5, radius * 0.25))
            mask = QPainter(soft)
            mask.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            local = centre - QPointF(area.topLeft())
            mask.setBrush(dab_brush(QColor(0, 0, 0), local, radius, hardness * 0.5, alpha))
            mask.setPen(Qt.NoPen)
            mask.drawRect(QRectF(soft.rect()))
            mask.end()
            p.drawImage(area.topLeft(), soft)
    p.end()
    stroke.touch(box.adjusted(-1, -1, 1, 1))


# ---- selecting by colour (magic wand, flood fill) ----------------------------------

def _rows(image, fmt):
    img = image.convertToFormat(fmt)
    data = bytes(img.constBits().asstring(img.byteCount()))
    return data, img.bytesPerLine()


def similar_mask(small, seed, tol):
    """bytearray, 1 where a pixel is close to the seed pixel's colour."""
    w, h = small.width(), small.height()
    rgb = small.convertToFormat(QImage.Format_RGB32)
    seed_rgb = rgb.pixelColor(seed)
    seed_a = small.pixelColor(seed).alpha()
    p = QPainter(rgb)
    p.setCompositionMode(QPainter.CompositionMode_Difference)
    p.fillRect(rgb.rect(), seed_rgb)
    p.end()
    grey, bpl_g = _rows(rgb, QImage.Format_Grayscale8)
    alpha, bpl_a = _rows(small, QImage.Format_Alpha8)
    near = bytes(1 if v <= tol else 0 for v in range(256))
    near_a = bytes(1 if abs(v - seed_a) <= tol else 0 for v in range(256))
    ok = bytearray(w * h)
    for y in range(h):
        g = grey[y * bpl_g:y * bpl_g + w].translate(near)
        a = alpha[y * bpl_a:y * bpl_a + w].translate(near_a)
        ok[y * w:(y + 1) * w] = (int.from_bytes(g, "big") & int.from_bytes(a, "big")).to_bytes(w, "big")
    return ok


def flood(ok, w, h, sx, sy):
    """Mark the pixels joined to (sx, sy) with 2 (scanline fill)."""
    state = ok
    if not state[sy * w + sx] == 1:
        return state
    stack = [(sx, sy)]
    while stack:
        x, y = stack.pop()
        row = y * w
        if state[row + x] != 1:
            continue
        left = max(state.rfind(b"\x00", row, row + x), state.rfind(b"\x02", row, row + x)) + 1
        left = max(left, row)
        stops = [i for i in (state.find(b"\x00", row + x, row + w),
                             state.find(b"\x02", row + x, row + w)) if i >= 0]
        right = min(stops) if stops else row + w
        state[left:right] = b"\x02" * (right - left)
        for ny in (y - 1, y + 1):
            if 0 <= ny < h:
                nrow = ny * w
                i = left - row
                end = right - row
                while i < end:
                    j = state.find(b"\x01", nrow + i, nrow + end)
                    if j < 0:
                        break
                    stack.append((j - nrow, ny))
                    stops = [k for k in (state.find(b"\x00", j, nrow + end),
                                         state.find(b"\x02", j, nrow + end)) if k >= 0]
                    i = (min(stops) if stops else nrow + end) - nrow
    return state


def mask_path(state, w, h):
    """The marked (2) pixels as an outline, in the small image's pixels."""
    grey = bytes(state).translate(bytes(0 if v == 2 else 255 for v in range(256)))
    image = QImage(grey, w, h, w, QImage.Format_Grayscale8).copy()
    bitmap = QBitmap.fromImage(image.convertToFormat(QImage.Format_Mono, Qt.ThresholdDither))
    path = QPainterPath()
    path.addRegion(QRegion(bitmap))
    return path.simplified()


def colour_region(source, point, tol, max_side=1400):
    """The area around ``point`` (in ``source`` pixels) that has nearly the
    same colour, as an outline in ``source`` pixels; or None."""
    if source.isNull():
        return None
    scale = min(1.0, max_side / max(source.width(), source.height()))
    small = source if scale >= 1.0 else source.scaled(
        max(1, round(source.width() * scale)), max(1, round(source.height() * scale)),
        Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    small = small.convertToFormat(QImage.Format_ARGB32_Premultiplied)
    sx = min(small.width() - 1, max(0, int(point.x() * scale)))
    sy = min(small.height() - 1, max(0, int(point.y() * scale)))
    w, h = small.width(), small.height()
    state = flood(similar_mask(small, QRect(sx, sy, 1, 1).topLeft(), tol), w, h, sx, sy)
    path = mask_path(state, w, h)
    if path.isEmpty():
        return None
    return QTransform.fromScale(1 / scale, 1 / scale).map(path)


def page_picture(scene, max_side=1400):
    """The whole page drawn small, and the page -> picture scale."""
    from .exporter import export_mode
    page = scene.doc.page_rect()
    s = min(1.0, max_side / max(page.width(), page.height()))
    image = QImage(max(1, round(page.width() * s)), max(1, round(page.height() * s)),
                   QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    with export_mode(scene):
        scene.render(p, QRectF(image.rect()), page)
    p.end()
    return image, s


def region_on_page(win, scene_pt):
    """Area of nearly the same colour around a page point, in page coordinates,
    sampled from the chosen layer or from the whole page."""
    tol = win.brush["tolerance"]
    layer = win.pixel_layer(create=False)
    if win.brush["sample"] == "layer" and layer is not None:
        t = to_layer(layer)
        image = win.scene.assets.full(layer.aid)
        path = colour_region(image, t.map(scene_pt), tol)
        if path is None:
            return None
        back, _ = t.inverted()
        return back.map(path)
    picture, s = page_picture(win.scene)
    page = win.scene.doc.page_rect()
    local = QPointF((scene_pt.x() - page.left()) * s, (scene_pt.y() - page.top()) * s)
    path = colour_region(picture, local, tol, max_side=max(picture.width(), picture.height()))
    if path is None:
        return None
    return QTransform(1 / s, 0, 0, 1 / s, page.left(), page.top()).map(path)


def combine(old, new, mods):
    """Shift adds to the selection, Alt takes away, both keep the overlap."""
    if old is None or old.isEmpty() or not mods & (Qt.ShiftModifier | Qt.AltModifier):
        return new
    if mods & Qt.ShiftModifier and mods & Qt.AltModifier:
        return old.intersected(new)
    if mods & Qt.AltModifier:
        return old.subtracted(new)
    return old.united(new)


# ---- tools --------------------------------------------------------------------------

class BrushTool(Tool):
    """Paint brush (B), Erase brush (E), Blur brush (U), Dodge and Burn (O)."""

    cursor = Qt.CrossCursor

    def __init__(self, view, kind):
        super().__init__(view)
        self.kind = kind
        self.name = "px-" + kind
        self.stroke = None
        self.last = None
        self.hover = None

    def radius_px(self):
        return max(0.5, self.win.brush["size"] / 2.0)

    def press(self, e, sp):
        layer = self.win.pixel_layer(create=True)
        if layer is None:
            return
        labels = {"brush": "Paint", "erase": "Erase", "blur": "Blur", "dodge": "Dodge",
                  "burn": "Burn"}
        self.stroke = Stroke(self.win, layer, labels[self.kind])
        self.last = self.stroke.to_layer.map(sp)
        self.dab(self.last)

    def dab(self, centre):
        s = self.stroke
        paint_dab(s, self.kind, centre, self.radius_px() * s.scale, self.win.brush,
                  self.win.paint_colour())

    def move(self, e, sp):
        self.hover = sp
        if self.stroke is None or not e.buttons() & Qt.LeftButton:
            self.view.viewport().update()
            return
        p = self.stroke.to_layer.map(sp)
        spacing = max(0.05, float(self.win.brush.get("spacing", 0.3)))
        step = max(1.0, self.radius_px() * self.stroke.scale * spacing)
        d = _dist(p, self.last)
        if d < step:
            return
        n = int(d // step)
        for k in range(1, n + 1):
            self.dab(self.last + (p - self.last) * (k / n))
        self.last = p

    def release(self, e, sp):
        if self.stroke is not None:
            self.stroke.finish()
        self.stroke = None
        self.last = None

    def deactivate(self):
        if self.stroke is not None:
            self.stroke.finish()
        self.stroke = None

    def draw_overlay(self, painter):
        if self.hover is None:
            return
        r = self.radius_px()
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(0, 0, 0, 160), 0))
        painter.drawEllipse(self.hover, r, r)
        painter.setPen(QPen(QColor(255, 255, 255, 200), 0, Qt.DashLine))
        painter.drawEllipse(self.hover, r, r)


class MarqueeTool(Tool):
    """Rectangle (M), ellipse, single row and single column selections.
    Shift adds, Alt takes away."""

    cursor = Qt.CrossCursor

    def __init__(self, view, shape):
        super().__init__(view)
        self.shape = shape
        self.name = "px-" + shape
        self.start = self.rect = None

    def press(self, e, sp):
        self.start = sp
        self.rect = None
        if self.shape in ("row", "column"):
            page = self.scene.doc.page_rect()
            unit = 1.0
            r = (QRectF(page.left(), math.floor(sp.y()), page.width(), unit) if self.shape == "row"
                 else QRectF(math.floor(sp.x()), page.top(), unit, page.height()))
            path = QPainterPath()
            path.addRect(r)
            self.win.set_pixel_selection(combine(self.win.pixel_selection, path, e.modifiers()))
            self.start = None

    def move(self, e, sp):
        if self.start is None or not e.buttons() & Qt.LeftButton:
            return
        d = sp - self.start
        if e.modifiers() & Qt.ControlModifier:
            side = max(abs(d.x()), abs(d.y()))
            d = QPointF(math.copysign(side, d.x() or 1), math.copysign(side, d.y() or 1))
        self.rect = QRectF(self.start, self.start + d).normalized()
        self.view.viewport().update()

    def release(self, e, sp):
        rect, self.rect, self.start = self.rect, None, None
        if rect is None or rect.width() * self.view.zoom() < 2:
            if self.shape in ("rect", "ellipse") and not e.modifiers():
                self.win.set_pixel_selection(None)
            return
        path = QPainterPath()
        if self.shape == "ellipse":
            path.addEllipse(rect)
        else:
            path.addRect(rect)
        self.win.set_pixel_selection(combine(self.win.pixel_selection, path, e.modifiers()))

    def draw_overlay(self, painter):
        if self.rect is not None:
            painter.setPen(QPen(QColor("#ffffff"), 0, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            if self.shape == "ellipse":
                painter.drawEllipse(self.rect)
            else:
                painter.drawRect(self.rect)


class LassoTool(Tool):
    """Freehand selection (L): draw round what you want."""

    name = "px-lasso"
    cursor = Qt.CrossCursor

    def __init__(self, view):
        super().__init__(view)
        self.points = []

    def press(self, e, sp):
        self.points = [sp]

    def move(self, e, sp):
        if self.points and e.buttons() & Qt.LeftButton:
            if _dist(sp, self.points[-1]) * self.view.zoom() >= 2:
                self.points.append(sp)
                self.view.viewport().update()

    def release(self, e, sp):
        points, self.points = self.points, []
        if len(points) < 3:
            self.win.set_pixel_selection(None)
            return
        path = QPainterPath(points[0])
        for p in points[1:]:
            path.lineTo(p)
        path.closeSubpath()
        self.win.set_pixel_selection(combine(self.win.pixel_selection, path.simplified(),
                                             e.modifiers()))

    def draw_overlay(self, painter):
        if len(self.points) > 1:
            painter.setPen(QPen(QColor("#ffffff"), 0, Qt.DashLine))
            for a, b in zip(self.points, self.points[1:]):
                painter.drawLine(a, b)


class WandTool(Tool):
    """Flood select / magic wand (W): click to select the area of nearly the
    same colour. Tolerance is in the bar at the top."""

    name = "px-wand"
    cursor = Qt.PointingHandCursor

    def press(self, e, sp):
        path = region_on_page(self.win, sp)
        if path is None:
            self.win.statusBar().showMessage("Click on the page.", 4000)
            return
        self.win.set_pixel_selection(combine(self.win.pixel_selection, path, e.modifiers()))


class FloodFillTool(Tool):
    """Flood fill (G): fill the area of nearly the same colour with the fill colour."""

    name = "px-fill"
    cursor = Qt.PointingHandCursor

    def press(self, e, sp):
        area = region_on_page(self.win, sp)
        if area is None:
            return
        layer = self.win.pixel_layer(create=True)
        if layer is None:
            return
        stroke = Stroke(self.win, layer, "Flood fill")
        shape = stroke.to_layer.map(area)
        p = stroke.painter()
        p.fillPath(shape, self.win.paint_colour())
        p.end()
        stroke.touch(shape.boundingRect().adjusted(-2, -2, 2, 2))
        stroke.finish()


PIXEL_TOOL_CLASSES = {
    "px-brush": lambda v: BrushTool(v, "brush"),
    "px-erase": lambda v: BrushTool(v, "erase"),
    "px-blur": lambda v: BrushTool(v, "blur"),
    "px-dodge": lambda v: BrushTool(v, "dodge"),
    "px-burn": lambda v: BrushTool(v, "burn"),
    "px-rect": lambda v: MarqueeTool(v, "rect"),
    "px-ellipse": lambda v: MarqueeTool(v, "ellipse"),
    "px-row": lambda v: MarqueeTool(v, "row"),
    "px-column": lambda v: MarqueeTool(v, "column"),
    "px-lasso": LassoTool,
    "px-wand": WandTool,
    "px-fill": FloodFillTool,
}


DEFAULT_BRUSH.update(BRUSH_SHAPE_DEFAULTS)


def new_layer_image(width, height):
    image = QImage(max(1, int(round(width))), max(1, int(round(height))),
                   QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    return image
