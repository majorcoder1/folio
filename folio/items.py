"""Objects on the canvas: shapes, curves, text and images.

Every object has a frame of ``w`` x ``h`` in its own coordinates, starting
at (0, 0). It rotates and flips around the middle of that frame, so the
frame's centre on the page is always ``pos + (w/2, h/2)``.
"""

import math
import uuid

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QBrush, QColor, QFont, QImage, QLinearGradient,
                         QPainter, QPainterPath, QPainterPathStroker, QPen,
                         QPixmap, QRadialGradient, QTextBlockFormat,
                         QTextCharFormat, QTextCursor, QTransform)
from PyQt5.QtWidgets import (QGraphicsBlurEffect, QGraphicsItem,
                             QGraphicsPixmapItem, QGraphicsScene,
                             QGraphicsTextItem, QStyle,
                             QStyleOptionGraphicsItem)

# Shared drawing switches, set while exporting.
RENDER = {"export": False, "outline_text": False}

DEFAULT_FILL = {"type": "solid", "color": "#ff3d7bd9", "color2": "#ff10233f",
                "angle": 90.0}
DEFAULT_STROKE = {"color": "#ff000000", "width": 0.0, "dash": "solid"}
DEFAULT_SHADOW = {"on": False, "color": "#99000000", "blur": 20.0,
                  "dx": 10.0, "dy": 10.0}
DEFAULT_TEXT_STYLE = {"family": "Noto Serif", "size": 200.0, "bold": False,
                      "italic": False, "tracking": 0.0, "line": 100.0,
                      "align": "left", "caps": False}

ALIGN = {"left": Qt.AlignLeft, "center": Qt.AlignHCenter,
         "right": Qt.AlignRight, "justify": Qt.AlignJustify}
DASH = {"solid": Qt.SolidLine, "dash": Qt.DashLine, "dot": Qt.DotLine,
        "dashdot": Qt.DashDotLine}
CAPS = {"butt": Qt.FlatCap, "round": Qt.RoundCap, "square": Qt.SquareCap}
# How an object mixes with what is under it (the Layers panel's blend mode).
BLENDS = [("normal", "Normal", QPainter.CompositionMode_SourceOver),
          ("multiply", "Multiply", QPainter.CompositionMode_Multiply),
          ("screen", "Screen", QPainter.CompositionMode_Screen),
          ("overlay", "Overlay", QPainter.CompositionMode_Overlay),
          ("darken", "Darken", QPainter.CompositionMode_Darken),
          ("lighten", "Lighten", QPainter.CompositionMode_Lighten),
          ("dodge", "Colour Dodge", QPainter.CompositionMode_ColorDodge),
          ("burn", "Colour Burn", QPainter.CompositionMode_ColorBurn),
          ("hardlight", "Hard Light", QPainter.CompositionMode_HardLight),
          ("softlight", "Soft Light", QPainter.CompositionMode_SoftLight),
          ("difference", "Difference", QPainter.CompositionMode_Difference),
          ("exclusion", "Exclusion", QPainter.CompositionMode_Exclusion)]
BLEND_MODE = {key: mode for key, _, mode in BLENDS}
JOINS = {"miter": Qt.MiterJoin, "round": Qt.RoundJoin, "bevel": Qt.BevelJoin}


def new_uid():
    return uuid.uuid4().hex[:12]


def qcolor(text):
    c = QColor(text or "#ff000000")
    return c if c.isValid() else QColor(0, 0, 0)


def color_str(color):
    return color.name(QColor.HexArgb)


def make_brush(fill, rect):
    kind = fill.get("type", "solid")
    if kind == "none":
        return QBrush(Qt.NoBrush)
    c1 = qcolor(fill.get("color"))
    if kind == "solid":
        return QBrush(c1)
    c2 = qcolor(fill.get("color2"))
    if kind == "linear":
        a = math.radians(fill.get("angle", 90.0))
        d = QPointF(math.cos(a), math.sin(a))
        half = abs(rect.width() / 2 * d.x()) + abs(rect.height() / 2 * d.y())
        c = rect.center()
        grad = QLinearGradient(c - d * half, c + d * half)
    else:
        radius = max(math.hypot(rect.width(), rect.height()) / 2, 0.5)
        grad = QRadialGradient(rect.center(), radius)
    grad.setColorAt(0.0, c1)
    grad.setColorAt(1.0, c2)
    return QBrush(grad)


def make_pen(stroke):
    width = float(stroke.get("width", 0.0))
    if width <= 0:
        return QPen(Qt.NoPen)
    pen = QPen(qcolor(stroke.get("color")), width)
    dash = stroke.get("dash", "solid")
    pen.setStyle(DASH.get(dash, Qt.SolidLine))
    cap = stroke.get("cap") or ("round" if dash == "dot" else "butt")
    pen.setCapStyle(CAPS.get(cap, Qt.FlatCap))
    pen.setJoinStyle(JOINS.get(stroke.get("join"), Qt.MiterJoin))
    pen.setMiterLimit(float(stroke.get("miter", 2.0)))
    return pen


def draw_stroked(painter, path, stroke, closed):
    """Draw the outline of ``path``: centred on the edge, or (for closed
    shapes) just inside or just outside it."""
    pen = make_pen(stroke)
    if pen.style() == Qt.NoPen:
        return
    align = stroke.get("align", "center") if closed else "center"
    painter.setBrush(Qt.NoBrush)
    if align == "center":
        painter.setPen(pen)
        painter.drawPath(path)
        return
    pen.setWidthF(pen.widthF() * 2)
    painter.save()
    if align == "inside":
        painter.setClipPath(path, Qt.IntersectClip)
        painter.setPen(pen)
        painter.drawPath(path)
    else:
        outline = QPainterPathStroker(pen).createStroke(path).subtracted(path)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(pen.color()))
        painter.drawPath(outline)
    painter.restore()


def blur_image(image, radius):
    """Soften an image with Qt's own blur (fast, done in C++)."""
    if radius < 0.5:
        return image
    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(QPixmap.fromImage(image))
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(radius)
    effect.setBlurHints(QGraphicsBlurEffect.QualityHint)
    item.setGraphicsEffect(effect)
    scene.addItem(item)
    out = QImage(image.size(), QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    painter = QPainter(out)
    scene.render(painter, QRectF(out.rect()),
                 QRectF(0, 0, image.width(), image.height()))
    painter.end()
    return out


def pt(v):
    return QPointF(v[0], v[1])


def build_path(nodes, closed):
    path = QPainterPath()
    if not nodes:
        return path
    path.moveTo(pt(nodes[0]["p"]))
    n = len(nodes)
    for k in range(n if closed else n - 1):
        a, b = nodes[k], nodes[(k + 1) % n]
        if a.get("o") is None and b.get("i") is None:
            path.lineTo(pt(b["p"]))
        else:
            path.cubicTo(pt(a.get("o") or a["p"]), pt(b.get("i") or b["p"]), pt(b["p"]))
    if closed:
        path.closeSubpath()
    return path


class FolioItem:
    """Shared behaviour, mixed into each Qt item class."""

    kind = "item"
    label = "Item"
    has_fill = True
    has_stroke = True
    gradient_fill = True

    def init_common(self):
        self.uid = new_uid()
        self.name = ""
        self.locked = False
        self.group = None
        self.clip = None        # uid of the shape this object only shows inside
        self.blend = "normal"
        self.w = 100.0
        self.h = 100.0
        self.flip_h = False
        self.flip_v = False
        self.fill = dict(DEFAULT_FILL)
        self.stroke = dict(DEFAULT_STROKE)
        self.shadow = dict(DEFAULT_SHADOW)
        self._version = 0
        self._shadow_cache = None
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)

    # ---- frame and placement ---------------------------------------------

    def frame_rect(self):
        return QRectF(0, 0, self.w, self.h)

    def _update_frame(self):
        cx, cy = self.w / 2, self.h / 2
        self.setTransformOriginPoint(cx, cy)
        sx = -1.0 if self.flip_h else 1.0
        sy = -1.0 if self.flip_v else 1.0
        self.setTransform(QTransform(sx, 0, 0, sy, cx * (1 - sx), cy * (1 - sy)))

    def set_size(self, w, h):
        self.prepareGeometryChange()
        self.w = max(float(w), 0.01)
        self.h = max(float(h), 0.01)
        self._update_frame()
        self.changed()

    def changed(self):
        self._version += 1
        self._shadow_cache = None
        self.update()

    def center_scene(self):
        return self.mapToScene(QPointF(self.w / 2, self.h / 2))

    def set_center_scene(self, c):
        self.setPos(self.pos() + (c - self.center_scene()))

    def place_local_at(self, local_pt, scene_pt):
        """Move the object so ``local_pt`` lands on ``scene_pt``."""
        self.setPos(self.pos() + (scene_pt - self.mapToScene(local_pt)))

    def scene_polygon(self):
        return self.mapToScene(self.frame_rect())

    def scene_bounds(self):
        """The area the object covers; for an object inside a shape, only
        the part that shows."""
        r = self.scene_polygon().boundingRect()
        owner = self.clip_owner()
        if owner is not None:
            shown = r.intersected(owner.scene_polygon().boundingRect())
            if not shown.isEmpty():
                return shown
        return r

    # ---- showing only inside another shape (Paste Inside) ---------------

    def clip_area(self):
        """The outline other objects are cut to when pasted inside this one."""
        path = QPainterPath()
        path.addRect(self.frame_rect())
        return path

    def clip_owner(self):
        scene = self.scene()
        if not self.clip or scene is None:
            return None
        owner = scene.find(self.clip)
        return owner if owner is not None and owner is not self else None

    def apply_blend(self, painter):
        if self.blend != "normal":
            painter.setCompositionMode(BLEND_MODE.get(self.blend, QPainter.CompositionMode_SourceOver))

    def apply_clip(self, painter):
        self.apply_blend(painter)
        owner = self.clip_owner()
        if owner is None:
            return
        to_self = owner.sceneTransform() * self.sceneTransform().inverted()[0]
        painter.setClipPath(to_self.map(owner.clip_area()), Qt.IntersectClip)

    def clip_contains(self, scene_pt):
        owner = self.clip_owner()
        if owner is None:
            return True
        return owner.clip_area().contains(owner.mapFromScene(scene_pt))

    def set_flip(self, horizontal=None, vertical=None):
        anchor = self.center_scene()
        if horizontal is not None:
            self.flip_h = horizontal
        if vertical is not None:
            self.flip_v = vertical
        self._update_frame()
        self.set_center_scene(anchor)
        self.changed()

    def display_name(self):
        return self.name or self.default_name()

    def default_name(self):
        return self.label

    # ---- resizing --------------------------------------------------------

    def resize_content(self, w, h):
        """Change the frame size, stretching the content (stays at (0, 0))."""
        self.set_size(w, h)

    def scale_content(self, s):
        """Uniform scale, used when several objects are resized together."""
        self.stroke["width"] = self.stroke.get("width", 0.0) * s
        for key in ("blur", "dx", "dy"):
            self.shadow[key] = self.shadow.get(key, 0.0) * s
        self.resize_content(self.w * s, self.h * s)

    # ---- painting helpers ------------------------------------------------

    def stroke_width(self):
        return float(self.stroke.get("width", 0.0)) if self.has_stroke else 0.0

    def paint_margin(self):
        m = max(self.stroke_width(), 1.0)
        sh = self.shadow
        if sh.get("on"):
            m += sh.get("blur", 0.0) * 2 + math.hypot(sh.get("dx", 0.0), sh.get("dy", 0.0)) + 2
        return m

    def content_bounds(self):
        sw = self.stroke_width()
        return self.frame_rect().adjusted(-sw, -sw, sw, sw)

    def paint_shadow(self, painter):
        sh = self.shadow
        if not sh.get("on"):
            return
        color = qcolor(sh.get("color"))
        if color.alpha() == 0:
            return
        t = painter.worldTransform()
        scale = math.sqrt(abs(t.m11() * t.m22() - t.m12() * t.m21())) or 1.0
        blur = max(float(sh.get("blur", 0.0)), 0.0)
        m = blur * 2 + 2
        src = self.content_bounds().adjusted(-m, -m, m, m)
        limit = 2.4e7 if RENDER["export"] else 4.0e6
        area = src.width() * src.height() * scale * scale
        if area > limit:
            scale *= math.sqrt(limit / area)
        scale = max(scale, 0.01)
        key = (self._version, round(scale, 3), RENDER["export"])
        cache = self._shadow_cache
        if cache and cache[0] == key:
            image = cache[1]
        else:
            image = self._render_shadow(src, scale, blur, color)
            self._shadow_cache = (key, image)
        # The offset points the same way on the page however the object turns.
        st = self.sceneTransform()
        lin, ok = QTransform(st.m11(), st.m12(), st.m21(), st.m22(), 0, 0).inverted()
        off = lin.map(QPointF(sh.get("dx", 0.0), sh.get("dy", 0.0)))
        painter.drawImage(src.translated(off), image)

    def _render_shadow(self, src, scale, blur, color):
        w = max(1, int(math.ceil(src.width() * scale)))
        h = max(1, int(math.ceil(src.height() * scale)))
        image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        p = QPainter(image)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.scale(scale, scale)
        p.translate(-src.left(), -src.top())
        self.draw_content(p, for_shadow=True)
        p.resetTransform()
        p.setCompositionMode(QPainter.CompositionMode_SourceIn)
        p.fillRect(image.rect(), color)
        p.end()
        return blur_image(image, blur * scale)

    # ---- hit testing -----------------------------------------------------

    def hit(self, scene_pt, tol):
        if not self.clip_contains(scene_pt):
            return False
        return self.hit_local(self.mapFromScene(scene_pt), tol)

    def hit_local(self, p, tol):
        return self.frame_rect().adjusted(-tol, -tol, tol, tol).contains(p)

    # ---- saving ----------------------------------------------------------

    def base_dict(self):
        return {
            "kind": self.kind, "uid": self.uid, "name": self.name,
            "x": self.pos().x(), "y": self.pos().y(), "w": self.w, "h": self.h,
            "rot": self.rotation(), "flip_h": self.flip_h, "flip_v": self.flip_v,
            "opacity": self.opacity(), "visible": self.isVisible(),
            "locked": self.locked, "group": self.group, "clip": self.clip,
            "blend": self.blend,
            "fill": dict(self.fill), "stroke": dict(self.stroke),
            "shadow": dict(self.shadow),
        }

    def apply_base(self, d, size=True):
        self.uid = d.get("uid") or new_uid()
        self.name = d.get("name", "")
        self.locked = bool(d.get("locked", False))
        self.group = d.get("group")
        self.clip = d.get("clip")
        self.blend = d.get("blend", "normal")
        self.fill = {**DEFAULT_FILL, **d.get("fill", {})}
        self.stroke = {**DEFAULT_STROKE, **d.get("stroke", {})}
        self.shadow = {**DEFAULT_SHADOW, **d.get("shadow", {})}
        self.flip_h = bool(d.get("flip_h", False))
        self.flip_v = bool(d.get("flip_v", False))
        self.setRotation(float(d.get("rot", 0.0)))
        self.setOpacity(float(d.get("opacity", 1.0)))
        self.setVisible(bool(d.get("visible", True)))
        if size:
            self.set_size(d.get("w", 100.0), d.get("h", 100.0))
        else:
            self._update_frame()
            self.changed()
        self.setPos(float(d.get("x", 0.0)), float(d.get("y", 0.0)))

    def to_dict(self):
        return self.base_dict()

    def apply_dict(self, d):
        self.apply_base(d)


class ShapeItem(QGraphicsItem, FolioItem):
    """Base for rectangles, ellipses and curves."""

    def __init__(self):
        QGraphicsItem.__init__(self)
        self.init_common()
        self._update_frame()

    def shape_path(self):
        raise NotImplementedError

    def is_closed(self):
        return True

    def boundingRect(self):
        m = self.paint_margin()
        r = self.shape_path().boundingRect().united(self.frame_rect())
        return r.adjusted(-m, -m, m, m)

    def content_bounds(self):
        sw = self.stroke_width()
        r = self.shape_path().boundingRect().united(self.frame_rect())
        return r.adjusted(-sw, -sw, sw, sw)

    def shape(self):
        path = self.shape_path()
        stroker = QPainterPathStroker()
        stroker.setWidth(max(self.stroke_width(), 1.0))
        outline = stroker.createStroke(path)
        if self.fill.get("type") != "none" and self.is_closed():
            return path.united(outline)
        return outline

    def clip_area(self):
        return self.shape_path()

    def paint(self, painter, option, widget=None):
        painter.save()
        self.apply_clip(painter)
        self.paint_shadow(painter)
        self.draw_content(painter)
        painter.restore()

    def draw_content(self, painter, for_shadow=False):
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = self.shape_path()
        painter.setPen(Qt.NoPen)
        painter.setBrush(make_brush(self.fill, self.frame_rect()))
        painter.drawPath(path)
        draw_stroked(painter, path, self.stroke, self.is_closed())

    def hit_local(self, p, tol):
        path = self.shape_path()
        if self.fill.get("type") != "none" and self.is_closed() and path.contains(p):
            return True
        stroker = QPainterPathStroker()
        stroker.setWidth(self.stroke_width() + 2 * tol)
        return stroker.createStroke(path).contains(p)


class RectItem(ShapeItem):
    kind = "rect"
    label = "Rectangle"

    def __init__(self):
        ShapeItem.__init__(self)
        self.radius = 0.0

    def shape_path(self):
        path = QPainterPath()
        r = min(self.radius, self.w / 2, self.h / 2)
        if r > 0:
            path.addRoundedRect(self.frame_rect(), r, r)
        else:
            path.addRect(self.frame_rect())
        return path

    def scale_content(self, s):
        self.radius *= s
        ShapeItem.scale_content(self, s)

    def to_dict(self):
        d = self.base_dict()
        d["radius"] = self.radius
        return d

    def apply_dict(self, d):
        self.radius = float(d.get("radius", 0.0))
        self.apply_base(d)


class EllipseItem(ShapeItem):
    kind = "ellipse"
    label = "Ellipse"

    def shape_path(self):
        path = QPainterPath()
        path.addEllipse(self.frame_rect())
        return path


class PathItem(ShapeItem):
    """A curve made of nodes, drawn with the Pen, Pencil or Line tool, or
    made by combining shapes or turning text into curves.

    Each node is a dict: ``p`` point, ``i`` handle coming in, ``o`` handle
    going out (``None`` for a sharp corner), ``t`` 'smooth' or 'corner'.
    ``nodes``/``closed`` is the first part; ``extra`` holds any more parts
    (the holes in an O, or the letters of a word), each {"nodes", "closed"}.
    """

    kind = "path"
    label = "Curve"

    def __init__(self):
        ShapeItem.__init__(self)
        self.nodes = []
        self.closed = False
        self.extra = []
        self.fill_rule = "winding"

    def is_closed(self):
        return self.closed

    def is_line(self):
        return (len(self.nodes) == 2 and not self.closed and not self.extra
                and all(n.get("i") is None and n.get("o") is None for n in self.nodes))

    def default_name(self):
        if self.extra:
            return "Curves"
        return "Line" if self.is_line() else "Curve"

    def parts(self):
        """Every part as (nodes, closed), the first part first."""
        return [(self.nodes, self.closed)] + [(e["nodes"], e["closed"]) for e in self.extra]

    def shape_path(self):
        path = build_path(self.nodes, self.closed)
        for e in self.extra:
            path.addPath(build_path(e["nodes"], e["closed"]))
        path.setFillRule(Qt.OddEvenFill if self.fill_rule == "evenodd" else Qt.WindingFill)
        return path

    def set_nodes_from_scene(self, scene_nodes, closed):
        """Create the curve from nodes given in page coordinates."""
        self.set_parts_from_scene([(scene_nodes, closed)])

    def set_parts_from_scene(self, parts, fill_rule="winding"):
        """Create the curve from several parts given in page coordinates."""
        path = QPainterPath()
        for nodes, closed in parts:
            path.addPath(build_path(nodes, closed))
        b = path.boundingRect()
        shifted = [([self._shift_node(n, -b.left(), -b.top()) for n in nodes], closed)
                   for nodes, closed in parts]
        self.nodes, self.closed = shifted[0]
        self.extra = [{"nodes": n, "closed": c} for n, c in shifted[1:]]
        self.fill_rule = fill_rule
        self.setRotation(0)
        self.set_size(max(b.width(), 0.01), max(b.height(), 0.01))
        self.setPos(b.topLeft())

    @staticmethod
    def _shift_node(n, dx, dy):
        out = dict(n)
        for key in ("p", "i", "o"):
            if out.get(key) is not None:
                out[key] = [out[key][0] + dx, out[key][1] + dy]
        return out

    def _map_nodes(self, fn):
        self.nodes = [fn(n) for n in self.nodes]
        for e in self.extra:
            e["nodes"] = [fn(n) for n in e["nodes"]]

    def normalize(self):
        """Fit the frame to the curve again without moving it on the page."""
        b = self.shape_path().boundingRect()
        anchor = self.mapToScene(b.topLeft())
        self._map_nodes(lambda n: self._shift_node(n, -b.left(), -b.top()))
        self.set_size(max(b.width(), 0.01), max(b.height(), 0.01))
        self.place_local_at(QPointF(0, 0), anchor)

    def resize_content(self, w, h):
        sx = w / self.w if self.w > 0.5 else 1.0
        sy = h / self.h if self.h > 0.5 else 1.0

        def scale(n):
            m = dict(n)
            for key in ("p", "i", "o"):
                if m.get(key) is not None:
                    m[key] = [m[key][0] * sx, m[key][1] * sy]
            return m
        self._map_nodes(scale)
        b = self.shape_path().boundingRect()
        self.set_size(b.width() if self.w > 0.5 else self.w,
                      b.height() if self.h > 0.5 else self.h)

    def to_dict(self):
        d = self.base_dict()
        d["nodes"] = [dict(n) for n in self.nodes]
        d["closed"] = self.closed
        if self.extra:
            d["extra"] = [{"nodes": [dict(n) for n in e["nodes"]], "closed": e["closed"]}
                          for e in self.extra]
        if self.fill_rule != "winding":
            d["fill_rule"] = self.fill_rule
        return d

    def apply_dict(self, d):
        self.nodes = [dict(n) for n in d.get("nodes", [])]
        self.closed = bool(d.get("closed", False))
        self.extra = [{"nodes": [dict(n) for n in e.get("nodes", [])],
                       "closed": bool(e.get("closed", True))} for e in d.get("extra", [])]
        self.fill_rule = d.get("fill_rule", "winding")
        self.apply_base(d)


def parts_from_path(path, closed=True, tol=0.01):
    """Turn a QPainterPath into [(nodes, closed)], one entry per part.
    Areas (text, combined shapes) are closed; their last point, when it
    repeats the first, is folded into the first."""
    parts = []
    nodes = None
    i, count = 0, path.elementCount()
    while i < count:
        e = path.elementAt(i)
        if e.isMoveTo():
            nodes = [{"p": [e.x, e.y], "i": None, "o": None, "t": "corner"}]
            parts.append(nodes)
            i += 1
        elif e.isLineTo():
            nodes.append({"p": [e.x, e.y], "i": None, "o": None, "t": "corner"})
            i += 1
        elif e.isCurveTo() and i + 2 < count:
            c2, end = path.elementAt(i + 1), path.elementAt(i + 2)
            nodes[-1]["o"] = [e.x, e.y]
            nodes.append({"p": [end.x, end.y], "i": [c2.x, c2.y], "o": None, "t": "corner"})
            i += 3
        else:
            i += 1
    out = []
    for nodes in parts:
        if len(nodes) > 2:
            a, b = nodes[0]["p"], nodes[-1]["p"]
            if abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol:
                last = nodes.pop()
                nodes[0]["i"] = last.get("i")
        for n in nodes:
            if n.get("i") is not None and n.get("o") is not None:
                n["t"] = "smooth" if _lined_up(n) else "corner"
        if len(nodes) >= 2:
            out.append((nodes, closed))
    return out


def _lined_up(n):
    """True if a node's two handles point straight away from each other."""
    px, py = n["p"]
    ax, ay = n["i"][0] - px, n["i"][1] - py
    bx, by = n["o"][0] - px, n["o"][1] - py
    la, lb = math.hypot(ax, ay), math.hypot(bx, by)
    if la < 1e-9 or lb < 1e-9:
        return False
    return (ax * bx + ay * by) / (la * lb) < -0.999


def path_item_from_scene_path(path):
    """A PathItem drawing ``path`` (given in page coordinates), or None."""
    parts = parts_from_path(path)
    if not parts:
        return None
    item = PathItem()
    rule = "evenodd" if path.fillRule() == Qt.OddEvenFill else "winding"
    item.set_parts_from_scene(parts, rule)
    return item


class ImageItem(QGraphicsItem, FolioItem):
    kind = "image"
    label = "Image"
    has_fill = False

    def __init__(self, assets, aid):
        QGraphicsItem.__init__(self)
        self.init_common()
        self.assets = assets
        self.aid = aid
        size = assets.size(aid)
        self.set_size(size.width(), size.height())

    def default_name(self):
        name = self.assets.names.get(self.aid, "")
        return f"Image: {name}" if name else "Image"

    def pixel_size(self):
        return self.assets.size(self.aid)

    def boundingRect(self):
        m = self.paint_margin()
        return self.frame_rect().adjusted(-m, -m, m, m)

    def paint(self, painter, option, widget=None):
        painter.save()
        self.apply_clip(painter)
        self.paint_shadow(painter)
        self.draw_content(painter)
        painter.restore()

    def draw_content(self, painter, for_shadow=False):
        r = self.frame_rect()
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.Antialiasing, True)
        if self.assets.is_live(self.aid):
            image = self.assets.live[self.aid]
            painter.drawImage(r, image, QRectF(image.rect()))
        elif RENDER["export"] and not for_shadow:
            image = self.assets.full(self.aid)
            if not image.isNull():
                painter.drawImage(r, image, QRectF(image.rect()))
            else:
                self._draw_missing(painter, r)
        else:
            t = painter.worldTransform()
            scale = math.sqrt(abs(t.m11() * t.m22() - t.m12() * t.m21())) or 1.0
            pix = self.assets.preview_for(self.aid, max(self.w, self.h) * scale)
            if not pix.isNull():
                painter.drawPixmap(r, pix, QRectF(pix.rect()))
            else:
                self._draw_missing(painter, r)
        if self.stroke_width() > 0:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(make_pen(self.stroke))
            painter.drawRect(r)

    @staticmethod
    def _draw_missing(painter, r):
        painter.fillRect(r, QColor(128, 128, 128, 120))
        painter.setPen(QPen(QColor(200, 60, 60), 0))
        painter.drawLine(r.topLeft(), r.bottomRight())
        painter.drawLine(r.topRight(), r.bottomLeft())

    def to_dict(self):
        d = self.base_dict()
        d["asset"] = self.aid
        return d


class TextItem(QGraphicsTextItem, FolioItem):
    """Text you can type straight onto the page.

    The whole object shares one style. Its fill is the text colour and its
    stroke is an outline around the letters. ``frame_width`` is None for
    text that grows as you type, or a width in px for text that wraps.
    """

    kind = "text"
    label = "Text"
    gradient_fill = False

    def __init__(self, text=""):
        QGraphicsTextItem.__init__(self)
        self.init_common()
        self.style = dict(DEFAULT_TEXT_STYLE)
        self.fill = {**DEFAULT_FILL, "type": "solid", "color": "#ff1a1a1a"}
        self.stroke = {**DEFAULT_STROKE, "join": "round"}
        self.frame_width = None
        self._applying = False
        self.editing = False
        doc = self.document()
        doc.setDocumentMargin(0)
        doc.setUseDesignMetrics(True)
        doc.contentsChanged.connect(self._on_contents_changed)
        self.setPlainText(text)
        self.apply_style()

    def default_name(self):
        text = self.toPlainText().strip().replace("\n", " ")
        if len(text) > 24:
            text = text[:23] + "…"
        return f"Text: {text}" if text else "Text"

    # ---- style -------------------------------------------------------------

    def make_font(self):
        s = self.style
        font = QFont(s["family"])
        size = max(1.0, float(s["size"]))
        font.setPixelSize(max(1, int(round(size))))
        font.setWeight(QFont.Bold if s["bold"] else QFont.Normal)
        font.setItalic(bool(s["italic"]))
        font.setLetterSpacing(QFont.AbsoluteSpacing, s["tracking"] / 100.0 * size)
        font.setCapitalization(QFont.AllUppercase if s["caps"] else QFont.MixedCase)
        font.setHintingPreference(QFont.PreferNoHinting)
        font.setKerning(True)
        return font

    def char_format(self):
        fmt = QTextCharFormat()
        fmt.setFont(self.make_font())
        fmt.setForeground(QBrush(qcolor(self.fill.get("color"))))
        fmt.setTextOutline(make_pen(self.stroke))
        return fmt

    def apply_style(self):
        """Apply the shared style to every letter."""
        if self._applying:
            return
        self._applying = True
        try:
            doc = self.document()
            font = self.make_font()
            doc.setDefaultFont(font)
            option = doc.defaultTextOption()
            option.setAlignment(ALIGN.get(self.style["align"], Qt.AlignLeft))
            doc.setDefaultTextOption(option)
            fmt = self.char_format()
            block_fmt = QTextBlockFormat()
            block_fmt.setAlignment(ALIGN.get(self.style["align"], Qt.AlignLeft))
            block_fmt.setLineHeight(float(self.style["line"]),
                                    QTextBlockFormat.ProportionalHeight)
            cursor = QTextCursor(doc)
            cursor.select(QTextCursor.Document)
            cursor.setBlockFormat(block_fmt)
            cursor.setCharFormat(fmt)
            edit = self.textCursor()
            edit.setCharFormat(fmt)
            self.setTextCursor(edit)
        finally:
            self._applying = False
        self.sync_size()

    def _on_contents_changed(self):
        if not self._applying:
            self.sync_size()

    def anchor_fraction(self):
        return {"left": 0.0, "center": 0.5, "right": 1.0}.get(self.style["align"], 0.0)

    def sync_size(self):
        """Fit the frame to the text, keeping the aligned edge in place."""
        fx = self.anchor_fraction() if self.frame_width is None else 0.0
        anchor = self.mapToScene(QPointF(self.w * fx, 0))
        doc = self.document()
        if self.frame_width is None:
            doc.setTextWidth(-1)
            doc.setTextWidth(math.ceil(doc.idealWidth()) + 1)
        else:
            doc.setTextWidth(max(1.0, self.frame_width))
        size = doc.size()
        self.prepareGeometryChange()
        self.w = max(size.width(), 1.0)
        self.h = max(size.height(), 1.0)
        self._update_frame()
        self.place_local_at(QPointF(self.w * fx, 0), anchor)
        self.changed()

    def set_frame_width(self, width):
        self.frame_width = None if width is None else max(1.0, float(width))
        self.sync_size()

    def resize_content(self, w, h):
        self.set_frame_width(w)

    def scale_content(self, s):
        self.style["size"] = max(1.0, self.style["size"] * s)
        self.stroke["width"] = self.stroke.get("width", 0.0) * s
        for key in ("blur", "dx", "dy"):
            self.shadow[key] = self.shadow.get(key, 0.0) * s
        if self.frame_width is not None:
            self.frame_width *= s
        self.apply_style()

    # ---- drawing -----------------------------------------------------------

    def boundingRect(self):
        m = self.paint_margin() + self.style["size"] * 0.25
        return self.frame_rect().adjusted(-m, -m, m, m)

    def content_bounds(self):
        m = self.stroke_width() + self.style["size"] * 0.25
        return self.frame_rect().adjusted(-m, -m, m, m)

    def text_path(self):
        """The letters as outlines, positioned exactly as on screen."""
        doc = self.document()
        layout = doc.documentLayout()
        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        block = doc.begin()
        while block.isValid():
            text_layout = block.layout()
            origin = layout.blockBoundingRect(block).topLeft()
            for line_no in range(text_layout.lineCount()):
                for run in text_layout.lineAt(line_no).glyphRuns():
                    raw = run.rawFont()
                    for index, pos in zip(run.glyphIndexes(), run.positions()):
                        glyph = raw.pathForGlyph(index)
                        glyph.translate(origin + pos)
                        path.addPath(glyph)
            block = block.next()
        return path

    def draw_content(self, painter, for_shadow=False):
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = self.text_path()
        painter.fillPath(path, QBrush(qcolor(self.fill.get("color"))))
        pen = make_pen(self.stroke)
        if pen.style() != Qt.NoPen:
            painter.strokePath(path, pen)

    def clip_area(self):
        return self.text_path()

    def paint(self, painter, option, widget=None):
        painter.save()
        self.apply_clip(painter)
        self.paint_shadow(painter)
        if RENDER["outline_text"] and not self.editing:
            self.draw_content(painter)
        else:
            opt = QStyleOptionGraphicsItem(option)
            opt.state = opt.state & ~QStyle.State_Selected & ~QStyle.State_HasFocus
            opt.exposedRect = QRectF(self.frame_rect())
            QGraphicsTextItem.paint(self, painter, opt, widget)
        painter.restore()

    # ---- editing -----------------------------------------------------------

    def start_editing(self, scene_pos=None):
        self.editing = True
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.document().clearUndoRedoStacks()
        self.setFocus(Qt.MouseFocusReason)
        cursor = self.textCursor()
        if scene_pos is not None:
            local = self.mapFromScene(scene_pos)
            pos = self.document().documentLayout().hitTest(local, Qt.FuzzyHit)
            if pos >= 0:
                cursor.setPosition(pos)
        else:
            cursor.select(QTextCursor.Document)
        self.setTextCursor(cursor)
        self.update()

    def stop_editing(self):
        self.editing = False
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.clearFocus()
        self.apply_style()

    # ---- saving ------------------------------------------------------------

    def to_dict(self):
        d = self.base_dict()
        d["text"] = self.toPlainText()
        d["style"] = dict(self.style)
        d["frame_width"] = self.frame_width
        return d

    def apply_dict(self, d):
        self.style = {**DEFAULT_TEXT_STYLE, **d.get("style", {})}
        self.frame_width = d.get("frame_width")
        self.apply_base(d, size=False)
        self._applying = True
        self.setPlainText(d.get("text", ""))
        self._applying = False
        self.apply_style()
        self.setPos(float(d.get("x", 0.0)), float(d.get("y", 0.0)))


def item_from_dict(d, assets):
    kind = d.get("kind")
    if kind == "rect":
        item = RectItem()
    elif kind == "ellipse":
        item = EllipseItem()
    elif kind == "path":
        item = PathItem()
    elif kind == "text":
        item = TextItem()
    elif kind == "image":
        item = ImageItem(assets, d.get("asset", ""))
    else:
        return None
    item.apply_dict(d)
    return item
