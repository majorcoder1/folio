"""Ready-made shapes for the shape tools: rounded rectangle, triangle,
diamond, star, polygon, arrow and heart. Each is drawn into the box the
user drags out."""

import math

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QPainterPath

from .items import build_path

# (tool name, title, keyboard key or None)
SHAPE_TOOLS = [
    ("rect", "Rectangle", "M"),
    ("ellipse", "Ellipse", "E"),
    ("rounded", "Rounded rectangle", "U"),
    ("triangle", "Triangle", None),
    ("diamond", "Diamond", None),
    ("star", "Star", None),
    ("polygon", "Polygon", None),
    ("arrow", "Arrow", None),
    ("heart", "Heart", None),
]
NAMES = {key: title for key, title, _ in SHAPE_TOOLS}
CURVE_SHAPES = ("triangle", "diamond", "star", "polygon", "arrow", "heart")


def _corner(x, y):
    return {"p": [x, y], "i": None, "o": None, "t": "corner"}


def _node(p, i=None, o=None, t="smooth"):
    return {"p": list(p), "i": list(i) if i else None, "o": list(o) if o else None, "t": t}


def _fit(points):
    """Stretch points so they fill the 0..1 box exactly."""
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    w = max(xs) - min(xs) or 1.0
    h = max(ys) - min(ys) or 1.0
    return [((x - min(xs)) / w, (y - min(ys)) / h) for x, y in points]


def _around(count, inner=None, start=-90.0):
    pts = []
    steps = count * 2 if inner else count
    for k in range(steps):
        r = inner if inner and k % 2 else 1.0
        a = math.radians(start + 360.0 * k / steps)
        pts.append((r * math.cos(a), r * math.sin(a)))
    return _fit(pts)


def unit_nodes(kind):
    """The shape's nodes in a 0..1 box."""
    if kind == "triangle":
        return [_corner(*p) for p in ((0.5, 0), (1, 1), (0, 1))]
    if kind == "diamond":
        return [_corner(*p) for p in ((0.5, 0), (1, 0.5), (0.5, 1), (0, 0.5))]
    if kind == "star":
        return [_corner(*p) for p in _around(5, inner=0.42)]
    if kind == "polygon":
        return [_corner(*p) for p in _around(6, start=-90.0)]
    if kind == "arrow":
        return [_corner(*p) for p in ((0, 0.3), (0.6, 0.3), (0.6, 0), (1, 0.5),
                                      (0.6, 1), (0.6, 0.7), (0, 0.7))]
    if kind == "heart":
        return [_node((0.5, 1), (0.8, 0.78), (0.2, 0.78), "corner"),
                _node((0, 0.3), (0, 0.55), (0, 0.1)),
                _node((0.27, 0), (0.12, 0), (0.4, 0)),
                _node((0.5, 0.22), (0.5, 0.1), (0.5, 0.1), "corner"),
                _node((0.73, 0), (0.6, 0), (0.88, 0)),
                _node((1, 0.3), (1, 0.1), (1, 0.55))]
    raise ValueError(kind)


def scene_nodes(kind, rect):
    """The shape's nodes stretched into ``rect`` (page coordinates)."""
    def place(v):
        return None if v is None else [rect.left() + v[0] * rect.width(),
                                       rect.top() + v[1] * rect.height()]
    return [{**n, "p": place(n["p"]), "i": place(n["i"]), "o": place(n["o"])}
            for n in unit_nodes(kind)]


def rounded_radius(w, h):
    return min(w, h) * 0.15


def preview_path(kind, rect):
    """The outline to show while the shape is being dragged out."""
    path = QPainterPath()
    if kind == "ellipse":
        path.addEllipse(rect)
    elif kind == "rounded":
        r = rounded_radius(rect.width(), rect.height())
        path.addRoundedRect(rect, r, r)
    elif kind in CURVE_SHAPES:
        path = build_path(scene_nodes(kind, rect), True)
    else:
        path.addRect(rect)
    return path


def icon_path(kind, box=QRectF(4, 4, 16, 16)):
    """The outline used for the tool's icon."""
    return preview_path(kind, box)
