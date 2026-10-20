"""Tools: what a mouse click does on the canvas."""

import math

from PyQt5.QtCore import QPoint, QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainterPath, QPen

from .canvas import (ACCENT, CORNERS, HANDLES, OPPOSITE, angle_cursor)
from .items import ImageItem, PathItem, TextItem, build_path
from . import shapes, snapping, units

HANDLE_PX = 8.0


def _norm_angle(a):
    a = math.fmod(a, 360.0)
    if a > 180:
        a -= 360
    if a <= -180:
        a += 360
    return a


def _rotate(v, degrees):
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    return QPointF(v.x() * c - v.y() * s, v.x() * s + v.y() * c)


def _dist(a, b):
    return math.hypot(a.x() - b.x(), a.y() - b.y())


def _constrain45(origin, p):
    d = p - origin
    length = math.hypot(d.x(), d.y())
    if length == 0:
        return p
    a = round(math.atan2(d.y(), d.x()) / (math.pi / 4)) * (math.pi / 4)
    return origin + QPointF(math.cos(a), math.sin(a)) * length


def draw_handle(painter, p, size, round_handle=False):
    r = QRectF(p.x() - size / 2, p.y() - size / 2, size, size)
    painter.setPen(QPen(ACCENT, 0))
    painter.setBrush(QColor("#ffffff"))
    if round_handle:
        painter.drawEllipse(r)
    else:
        painter.drawRect(r)


class Tool:
    name = ""
    cursor = Qt.ArrowCursor

    def __init__(self, view):
        self.view = view

    @property
    def win(self):
        return self.view.win

    @property
    def scene(self):
        return self.view.scene()

    def activate(self):
        pass

    def deactivate(self):
        pass

    def press(self, e, sp):
        pass

    def move(self, e, sp):
        pass

    def release(self, e, sp):
        pass

    def double_click(self, e, sp):
        pass

    def key_press(self, e):
        return False

    def wants_key(self, e):
        """True if this tool should get a key before the menu shortcuts."""
        return False

    def cursor_at(self, sp):
        return self.cursor

    def draw_overlay(self, painter):
        pass

    def draw_selection(self, painter, handles=True):
        frame = self.view.selection_frame()
        if frame is None:
            return
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(ACCENT, 0))
        for item in frame["items"]:
            painter.drawPolygon(item.scene_polygon())
        if not handles or frame["locked"]:
            return
        if not frame["single"]:
            painter.setPen(QPen(ACCENT, 0, Qt.DashLine))
            painter.drawPolygon(frame["outline"])
        size = self.view.tol(HANDLE_PX)
        painter.setPen(QPen(ACCENT, 0))
        painter.drawLine(frame["top"], frame["rot"])
        draw_handle(painter, frame["rot"], size, round_handle=True)
        for p in frame["points"].values():
            draw_handle(painter, p, size)


class MoveTool(Tool):
    """Select, move, resize and rotate (V)."""

    name = "move"

    def __init__(self, view):
        super().__init__(view)
        self.mode = None

    def handle_at(self, sp):
        frame = self.view.selection_frame()
        if frame is None or frame["locked"]:
            return None, frame
        t = self.view.tol(HANDLE_PX / 2 + 3)
        if _dist(sp, frame["rot"]) <= t:
            return "rot", frame
        for key, p in frame["points"].items():
            if abs(sp.x() - p.x()) <= t and abs(sp.y() - p.y()) <= t:
                return key, frame
        return None, frame

    def cursor_at(self, sp):
        key, frame = self.handle_at(sp)
        if key is None:
            guide = self.win.guide_at(sp)
            if guide is not None:
                return Qt.SplitHCursor if guide[0] == "x" else Qt.SplitVCursor
        if key == "rot":
            return Qt.CrossCursor
        if key:
            items = frame["items"]
            centre = (items[0].center_scene() if frame["single"]
                      else self.scene.items_rect(items).center())
            return angle_cursor(frame["points"][key] - centre)
        return Qt.ArrowCursor

    # ---- press --------------------------------------------------------------

    def press(self, e, sp):
        self.mode = None
        key, frame = self.handle_at(sp)
        if key == "rot":
            self.begin_rotate(frame, sp)
            return
        if key:
            self.begin_resize(frame, key, sp)
            return
        guide = self.win.guide_at(sp)
        if guide is not None:
            self.win.begin_change()
            self.mode = "guide"
            self.guide = guide
            self.moved = False
            return
        item = self.view.item_at(sp)
        mods = e.modifiers()
        if item is not None:
            single = mods & Qt.ControlModifier or self.win.auto_select == "object"
            unit = [item] if single else self.scene.unit_of(item)
            if mods & Qt.ShiftModifier:
                if all(i.isSelected() for i in unit):
                    for i in unit:
                        i.setSelected(False)
                    return
                for i in unit:
                    i.setSelected(True)
            elif not item.isSelected():
                self.scene.select_only(unit)
            self.begin_move(sp)
        else:
            self.keep = set(self.scene.selected_folio()) if mods & Qt.ShiftModifier else set()
            if not mods & Qt.ShiftModifier:
                self.scene.select_only([])
            self.mode = "rubber"
            self.start = sp
            self.rubber = QRectF(sp, sp)

    def begin_move(self, sp):
        moving = [i for i in self.scene.selected_folio() if not i.locked]
        if not moving:
            return
        self.win.begin_change()
        self.mode = "move"
        self.start = sp
        self.moving = moving
        self.orig = {id(i): i.pos() for i in moving}
        self.box0 = self.scene.items_rect(moving)
        self.lines = self.view.snap_lines(moving)
        self.moved = False

    def begin_resize(self, frame, key, sp):
        self.win.begin_change()
        self.mode = "resize"
        self.key = key
        self.moved = False
        self.single = frame["single"]
        items = frame["items"]
        self.lines = self.view.snap_lines(items)
        if self.single:
            it = items[0]
            self.item = it
            self.orig_state = it.to_dict()
            ox, oy = HANDLES[OPPOSITE[key]]
            if isinstance(it, TextItem) and key in ("l", "r"):
                oy = 0.0   # wrapping text grows downwards; keep its top still
            self.anchor_frac = (ox, oy)
            self.anchor_scene = it.mapToScene(QPointF(ox * it.w, oy * it.h))
            self.inv = it.sceneTransform().inverted()[0]
            self.w0, self.h0 = it.w, it.h
        else:
            self.items = items
            self.states = [i.to_dict() for i in items]
            self.centres = [i.center_scene() for i in items]
            box = self.scene.items_rect(items)
            corner = {"tl": box.topLeft(), "tr": box.topRight(),
                      "br": box.bottomRight(), "bl": box.bottomLeft()}
            self.anchor_scene = corner[OPPOSITE[key]]
            self.handle0 = corner[key]

    def begin_rotate(self, frame, sp):
        self.win.begin_change()
        self.mode = "rotate"
        self.moved = False
        items = frame["items"]
        self.items = items
        self.single = frame["single"]
        self.centre = (items[0].center_scene() if self.single
                       else self.scene.items_rect(items).center())
        d = sp - self.centre
        self.a0 = math.degrees(math.atan2(d.y(), d.x()))
        self.rot0 = [i.rotation() for i in items]
        self.centres = [i.center_scene() for i in items]

    # ---- drag ---------------------------------------------------------------

    def move(self, e, sp):
        if not e.buttons() & Qt.LeftButton or self.mode is None:
            return
        if self.mode == "guide":
            axis, index = self.guide
            self.scene.guides[axis][index] = sp.x() if axis == "x" else sp.y()
            self.moved = True
        elif self.mode == "rubber":
            self.drag_rubber(sp)
        elif self.mode == "move":
            self.drag_move(e, sp)
        elif self.mode == "resize":
            self.drag_resize(e, sp)
        elif self.mode == "rotate":
            self.drag_rotate(e, sp)
        self.view.viewport().update()

    def drag_rubber(self, sp):
        self.rubber = QRectF(self.start, sp).normalized()
        area = QPainterPath()
        area.addRect(self.rubber)
        chosen = set(self.keep)
        for item in self.scene.folio_items():
            if not item.isVisible() or item.locked:
                continue
            outline = QPainterPath()
            outline.addPolygon(item.scene_polygon())
            if area.intersects(outline):
                chosen.update(self.scene.unit_of(item))
        self.scene.select_only(chosen)

    def drag_move(self, e, sp):
        d = sp - self.start
        if not self.moved and math.hypot(d.x(), d.y()) * self.view.zoom() < 3:
            return
        self.moved = True
        if e.modifiers() & Qt.ShiftModifier:
            if abs(d.x()) > abs(d.y()):
                d.setY(0)
            else:
                d.setX(0)
        self.view.smart_x = self.view.smart_y = None
        if self.view.snap_enabled and not e.modifiers() & Qt.ControlModifier:
            xs, ys = self.lines
            off, gx, gy = snapping.snap_rect(self.box0.translated(d), xs, ys,
                                             self.view.snap_tol())
            if e.modifiers() & Qt.ShiftModifier:
                off = QPointF(off.x() if d.y() == 0 else 0, off.y() if d.x() == 0 else 0)
                gx = gx if d.y() == 0 else None
                gy = gy if d.x() == 0 else None
            d += off
            self.view.smart_x, self.view.smart_y = gx, gy
        for item in self.moving:
            item.setPos(self.orig[id(item)] + d)

    def snapped(self, e, sp):
        self.view.smart_x = self.view.smart_y = None
        if not self.view.snap_enabled or e.modifiers() & Qt.ControlModifier:
            return sp
        xs, ys = self.lines
        out, gx, gy = snapping.snap_point(sp, xs, ys, self.view.snap_tol())
        self.view.smart_x, self.view.smart_y = gx, gy
        return out

    def drag_resize(self, e, sp):
        self.moved = True
        sp = self.snapped(e, sp)
        shift = bool(e.modifiers() & Qt.ShiftModifier)
        if not self.single:
            self.drag_resize_many(sp)
            return
        it = self.item
        key = self.key
        fx, fy = HANDLES[key]
        ox, oy = self.anchor_frac
        local = self.inv.map(sp)
        ax, ay = ox * self.w0, oy * self.h0
        minimum = self.view.tol(1)
        new_w, new_h = self.w0, self.h0
        if fx != 0.5:
            new_w = (local.x() - ax) * (1 if fx > ox else -1)
        if fy != 0.5:
            new_h = (local.y() - ay) * (1 if fy > oy else -1)
        new_w = max(new_w, minimum)
        new_h = max(new_h, minimum)
        corner = key in CORNERS
        it.apply_dict(self.orig_state)
        if isinstance(it, TextItem):
            if corner:
                s = new_w / max(self.w0, 1e-6)
                it.scale_content(max(s, 0.01))
            else:
                it.set_frame_width(new_w)
        else:
            keep = corner and (shift != isinstance(it, ImageItem))
            if keep and self.w0 > 0 and self.h0 > 0:
                s = max(new_w / self.w0, new_h / self.h0)
                new_w, new_h = self.w0 * s, self.h0 * s
            elif not corner and shift and self.w0 > 0 and self.h0 > 0:
                s = new_w / self.w0 if fx != 0.5 else new_h / self.h0
                new_w, new_h = self.w0 * s, self.h0 * s
            it.resize_content(new_w, new_h)
        it.place_local_at(QPointF(ox * it.w, oy * it.h), self.anchor_scene)

    def drag_resize_many(self, sp):
        a, h0 = self.anchor_scene, self.handle0
        dx, dy = h0.x() - a.x(), h0.y() - a.y()
        sx = (sp.x() - a.x()) / dx if abs(dx) > 1e-6 else 1.0
        sy = (sp.y() - a.y()) / dy if abs(dy) > 1e-6 else 1.0
        s = max(min(max(sx, sy), 100.0), 0.01)
        for item, state, c0 in zip(self.items, self.states, self.centres):
            item.apply_dict(state)
            item.scale_content(s)
            item.set_center_scene(a + (c0 - a) * s)

    def drag_rotate(self, e, sp):
        self.moved = True
        d = sp - self.centre
        delta = math.degrees(math.atan2(d.y(), d.x())) - self.a0
        shift = bool(e.modifiers() & Qt.ShiftModifier)
        if self.single:
            r = self.rot0[0] + delta
            if shift:
                r = round(r / 15.0) * 15.0
            self.items[0].setRotation(_norm_angle(r))
            return
        if shift:
            delta = round(delta / 15.0) * 15.0
        for item, r0, c0 in zip(self.items, self.rot0, self.centres):
            item.setRotation(_norm_angle(r0 + delta))
            item.set_center_scene(self.centre + _rotate(c0 - self.centre, delta))

    def release(self, e, sp):
        mode, self.mode = self.mode, None
        self.view.clear_smart()
        if mode == "rubber":
            self.rubber = None
            self.view.viewport().update()
            return
        if mode == "guide":
            axis, index = self.guide
            if not self.view.viewport().rect().contains(e.pos()):
                del self.scene.guides[axis][index]       # dragged off: remove it
                self.win.end_change("Remove guide")
            elif self.moved:
                self.win.end_change("Move guide")
            else:
                self.win.cancel_change()
            self.view.viewport().update()
            return
        if mode in ("move", "resize", "rotate"):
            if self.moved:
                label = {"move": "Move", "resize": "Resize", "rotate": "Rotate"}[mode]
                self.win.end_change(label)
            else:
                self.win.cancel_change()

    def double_click(self, e, sp):
        item = self.view.item_at(sp)
        if isinstance(item, TextItem):
            self.win.start_text_editing(item, sp)
        elif isinstance(item, PathItem):
            self.scene.select_only([item])
            self.win.set_tool("node")

    def key_press(self, e):
        key = e.key()
        step = self.win.nudge_step * (10.0 if e.modifiers() & Qt.ShiftModifier else 1.0)
        moves = {Qt.Key_Left: (-step, 0), Qt.Key_Right: (step, 0),
                 Qt.Key_Up: (0, -step), Qt.Key_Down: (0, step)}
        if key in moves:
            self.win.nudge(*moves[key])
            return True
        if key == Qt.Key_Escape:
            self.scene.select_only([])
            return True
        if key in (Qt.Key_Return, Qt.Key_Enter):
            sel = self.scene.selected_folio()
            if len(sel) == 1 and isinstance(sel[0], TextItem):
                self.win.start_text_editing(sel[0], None)
                return True
        return False

    def draw_overlay(self, painter):
        self.draw_selection(painter, handles=self.mode not in ("move",))
        if self.mode == "rubber" and getattr(self, "rubber", None) is not None:
            painter.setPen(QPen(ACCENT, 0, Qt.DashLine))
            fill = QColor(ACCENT)
            fill.setAlpha(40)
            painter.setBrush(fill)
            painter.drawRect(self.rubber)


class ShapeTool(Tool):
    """Rectangle (M), Ellipse (E), Rounded rectangle (U) and the other
    ready-made shapes. Shift keeps the shape even, Ctrl draws from the centre."""

    cursor = Qt.CrossCursor

    def __init__(self, view, kind):
        super().__init__(view)
        self.kind = kind
        self.name = kind
        self.start = None
        self.rect = None

    def press(self, e, sp):
        self.start = self.view.snap(sp)
        self.rect = None

    def move(self, e, sp):
        if self.start is None or not e.buttons() & Qt.LeftButton:
            return
        p = self.view.snap(sp)
        d = p - self.start
        if e.modifiers() & Qt.ShiftModifier:
            side = max(abs(d.x()), abs(d.y()))
            d = QPointF(math.copysign(side, d.x() or 1), math.copysign(side, d.y() or 1))
        if e.modifiers() & Qt.ControlModifier:
            self.rect = QRectF(self.start - d, self.start + d).normalized()
        else:
            self.rect = QRectF(self.start, self.start + d).normalized()
        self.view.viewport().update()

    def release(self, e, sp):
        rect, self.rect, self.start = self.rect, None, None
        self.view.clear_smart()
        z = self.view.zoom()
        if rect is not None and rect.width() * z >= 3 and rect.height() * z >= 3:
            self.win.create_shape(self.kind, rect)

    def deactivate(self):
        self.start = self.rect = None

    def draw_overlay(self, painter):
        self.draw_selection(painter, handles=False)
        if self.rect is None:
            return
        painter.setPen(QPen(ACCENT, 0))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(shapes.preview_path(self.kind, self.rect))


class LineTool(Tool):
    """Straight lines (L). Shift keeps to 45 degree steps."""

    name = "line"
    cursor = Qt.CrossCursor

    def __init__(self, view):
        super().__init__(view)
        self.start = None
        self.end = None

    def press(self, e, sp):
        self.start = self.view.snap(sp)
        self.end = None

    def move(self, e, sp):
        if self.start is None or not e.buttons() & Qt.LeftButton:
            return
        p = sp if e.modifiers() & Qt.ShiftModifier else self.view.snap(sp)
        if e.modifiers() & Qt.ShiftModifier:
            p = _constrain45(self.start, p)
        self.end = p
        self.view.viewport().update()

    def release(self, e, sp):
        start, end = self.start, self.end
        self.start = self.end = None
        self.view.clear_smart()
        if start is not None and end is not None and _dist(start, end) * self.view.zoom() >= 3:
            self.win.create_path([{"p": [start.x(), start.y()], "i": None, "o": None, "t": "corner"},
                                  {"p": [end.x(), end.y()], "i": None, "o": None, "t": "corner"}],
                                 closed=False, line=True)

    def draw_overlay(self, painter):
        self.draw_selection(painter, handles=False)
        if self.start is not None and self.end is not None:
            painter.setPen(QPen(ACCENT, 0))
            painter.drawLine(self.start, self.end)


class PenTool(Tool):
    """Draw curves (P). Click for a corner, drag for a smooth curve, click
    the first point to close the shape, Enter or Esc to finish."""

    name = "pen"
    cursor = Qt.CrossCursor

    def __init__(self, view):
        super().__init__(view)
        self.nodes = []
        self.dragging = False
        self.hover = None

    def press(self, e, sp):
        p = self.view.snap(sp)
        if len(self.nodes) >= 2 and _dist(sp, QPointF(*self.nodes[0]["p"])) <= self.view.tol(8):
            self.finish(closed=True)
            return
        if self.nodes and e.modifiers() & Qt.ShiftModifier:
            p = _constrain45(QPointF(*self.nodes[-1]["p"]), sp)
        self.nodes.append({"p": [p.x(), p.y()], "i": None, "o": None, "t": "corner"})
        self.dragging = True
        self.view.viewport().update()

    def move(self, e, sp):
        if self.dragging and e.buttons() & Qt.LeftButton and self.nodes:
            node = self.nodes[-1]
            p = QPointF(*node["p"])
            if _dist(sp, p) * self.view.zoom() > 2:
                node["o"] = [sp.x(), sp.y()]
                node["i"] = [2 * p.x() - sp.x(), 2 * p.y() - sp.y()]
                node["t"] = "smooth"
        else:
            self.hover = self.view.snap(sp) if self.nodes else None
        self.view.viewport().update()

    def release(self, e, sp):
        self.dragging = False

    def double_click(self, e, sp):
        self.finish(closed=False)

    def wants_key(self, e):
        return bool(self.nodes) and e.key() in (Qt.Key_Backspace, Qt.Key_Delete,
                                                Qt.Key_Return, Qt.Key_Enter)

    def key_press(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape):
            if self.nodes:
                self.finish(closed=False)
            else:
                self.win.set_tool("move")
            return True
        if e.key() in (Qt.Key_Backspace, Qt.Key_Delete) and self.nodes:
            self.nodes.pop()
            self.view.viewport().update()
            return True
        return False

    def deactivate(self):
        if self.nodes:
            self.finish(closed=False, switch=False)

    def finish(self, closed, switch=True):
        nodes, self.nodes = self.nodes, []
        self.dragging = False
        self.hover = None
        self.view.clear_smart()
        if len(nodes) >= 2:
            self.win.create_path(nodes, closed=closed, switch=switch)
        self.view.viewport().update()

    def draw_overlay(self, painter):
        self.draw_selection(painter, handles=False)
        if not self.nodes:
            return
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(ACCENT, 0))
        painter.drawPath(build_path(self.nodes, False))
        last = self.nodes[-1]
        if self.hover is not None and not self.dragging:
            preview = QPainterPath()
            preview.moveTo(QPointF(*last["p"]))
            c1 = QPointF(*(last["o"] or last["p"]))
            preview.cubicTo(c1, self.hover, self.hover)
            painter.setPen(QPen(ACCENT, 0, Qt.DashLine))
            painter.drawPath(preview)
        size = self.view.tol(HANDLE_PX - 1)
        if last.get("o") is not None:
            painter.setPen(QPen(ACCENT, 0))
            painter.drawLine(QPointF(*last["i"]), QPointF(*last["o"]))
            draw_handle(painter, QPointF(*last["i"]), size * 0.8, True)
            draw_handle(painter, QPointF(*last["o"]), size * 0.8, True)
        for n in self.nodes:
            draw_handle(painter, QPointF(*n["p"]), size)


class NodeTool(Tool):
    """Edit the points of a curve (A). Drag points or handles, click a line
    to add a point, double-click a point to make it smooth or sharp,
    Delete removes the chosen point."""

    name = "node"

    def __init__(self, view):
        super().__init__(view)
        self.drag = None
        self.chosen = None

    def path_item(self):
        sel = self.scene.selected_folio()
        if len(sel) == 1 and isinstance(sel[0], PathItem) and not sel[0].locked:
            return sel[0]
        return None

    def activate(self):
        self.chosen = None
        sel = self.scene.selected_folio()
        if len(sel) > 1:
            paths = [i for i in sel if isinstance(i, PathItem)]
            self.scene.select_only(paths[-1:])

    def hit_part(self, item, sp):
        t = self.view.tol(HANDLE_PX / 2 + 3)
        for k in reversed(range(len(item.nodes))):
            n = item.nodes[k]
            for part in ("i", "o"):
                if n.get(part) is not None and _dist(item.mapToScene(QPointF(*n[part])), sp) <= t:
                    return (part, k)
            if _dist(item.mapToScene(QPointF(*n["p"])), sp) <= t:
                return ("p", k)
        return None

    def press(self, e, sp):
        item = self.path_item()
        if item is not None:
            part = self.hit_part(item, sp)
            if part is not None:
                self.win.begin_change()
                self.drag = (item, part[0], part[1], e.modifiers() & Qt.AltModifier)
                self.chosen = part[1]
                self.moved = False
                self.view.viewport().update()
                return
            seg = self.segment_at(item, sp)
            if seg is not None:
                self.win.begin_change()
                self.insert_node(item, *seg)
                item.normalize()
                self.win.end_change("Add point")
                return
        target = self.view.item_at(sp)
        if isinstance(target, PathItem):
            self.scene.select_only([target])
        elif target is not None:
            self.scene.select_only(self.scene.unit_of(target))
            self.win.set_tool("move")
        else:
            self.scene.select_only([])
        self.chosen = None
        self.view.viewport().update()

    def move(self, e, sp):
        if self.drag is None or not e.buttons() & Qt.LeftButton:
            return
        item, part, k, alt = self.drag
        self.moved = True
        if part == "p":
            sp = self.view.snap(sp, exclude=[item])
        local = item.mapFromScene(sp)
        node = item.nodes[k]
        if part == "p":
            old = QPointF(*node["p"])
            dx, dy = local.x() - old.x(), local.y() - old.y()
            for key in ("p", "i", "o"):
                if node.get(key) is not None:
                    node[key] = [node[key][0] + dx, node[key][1] + dy]
        else:
            node[part] = [local.x(), local.y()]
            other = "o" if part == "i" else "i"
            if alt:
                node["t"] = "corner"
            elif node.get("t") == "smooth" and node.get(other) is not None:
                p = QPointF(*node["p"])
                v = local - p
                length = math.hypot(v.x(), v.y())
                o = QPointF(*node[other]) - p
                olen = math.hypot(o.x(), o.y())
                if length > 1e-6:
                    node[other] = [p.x() - v.x() / length * olen, p.y() - v.y() / length * olen]
        item.prepareGeometryChange()
        item.changed()
        self.view.viewport().update()

    def release(self, e, sp):
        if self.drag is None:
            return
        item = self.drag[0]
        self.drag = None
        self.view.clear_smart()
        if self.moved:
            item.normalize()
            self.win.end_change("Edit points")
        else:
            self.win.cancel_change()

    def double_click(self, e, sp):
        item = self.path_item()
        if item is None:
            target = self.view.item_at(sp)
            if isinstance(target, TextItem):
                self.win.set_tool("move")
                self.win.start_text_editing(target, sp)
            return
        part = self.hit_part(item, sp)
        if part is None or part[0] != "p":
            return
        k = part[1]
        self.win.begin_change()
        node = item.nodes[k]
        if node.get("t") == "smooth":
            node.update({"i": None, "o": None, "t": "corner"})
        else:
            n = len(item.nodes)
            p = QPointF(*node["p"])
            prev = item.nodes[(k - 1) % n] if (item.closed or k > 0) else None
            nxt = item.nodes[(k + 1) % n] if (item.closed or k < n - 1) else None
            a = QPointF(*prev["p"]) if prev else p
            b = QPointF(*nxt["p"]) if nxt else p
            d = b - a
            length = math.hypot(d.x(), d.y())
            if length > 1e-6:
                u = d / length
                li = _dist(p, a) / 3 if prev else 0
                lo = _dist(p, b) / 3 if nxt else 0
                node["i"] = [p.x() - u.x() * li, p.y() - u.y() * li] if prev else None
                node["o"] = [p.x() + u.x() * lo, p.y() + u.y() * lo] if nxt else None
                node["t"] = "smooth"
        item.normalize()
        self.win.end_change("Change point")

    def wants_key(self, e):
        return (e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.chosen is not None
                and self.path_item() is not None)

    def key_press(self, e):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            item = self.path_item()
            if item is not None and self.chosen is not None:
                if len(item.nodes) > 2 and self.chosen < len(item.nodes):
                    self.win.begin_change()
                    del item.nodes[self.chosen]
                    if len(item.nodes) < 3:
                        item.closed = False
                    item.normalize()
                    self.win.end_change("Delete point")
                    self.chosen = None
                    self.view.viewport().update()
                return True
            return False
        if e.key() in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter):
            self.win.set_tool("move")
            return True
        return False

    @staticmethod
    def _cubic(item, k):
        n = len(item.nodes)
        a, b = item.nodes[k], item.nodes[(k + 1) % n]
        p0 = QPointF(*a["p"])
        p3 = QPointF(*b["p"])
        p1 = QPointF(*(a.get("o") or a["p"]))
        p2 = QPointF(*(b.get("i") or b["p"]))
        straight = a.get("o") is None and b.get("i") is None
        return p0, p1, p2, p3, straight

    @staticmethod
    def _at(p0, p1, p2, p3, t):
        u = 1 - t
        return (p0 * (u * u * u) + p1 * (3 * u * u * t) + p2 * (3 * u * t * t)
                + p3 * (t * t * t))

    def segment_at(self, item, sp):
        local = item.mapFromScene(sp)
        tol = self.view.tol(6)
        n = len(item.nodes)
        best = None
        for k in range(n if item.closed else n - 1):
            p0, p1, p2, p3, _ = self._cubic(item, k)
            for step in range(41):
                t = step / 40.0
                d = _dist(self._at(p0, p1, p2, p3, t), local)
                if best is None or d < best[0]:
                    best = (d, k, t)
        if best is None or best[0] > tol or best[2] in (0.0, 1.0):
            return None
        return best[1], best[2]

    def insert_node(self, item, k, t):
        p0, p1, p2, p3, straight = self._cubic(item, k)
        n = len(item.nodes)
        a, b = item.nodes[k], item.nodes[(k + 1) % n]
        mid = self._at(p0, p1, p2, p3, t)
        if straight:
            new = {"p": [mid.x(), mid.y()], "i": None, "o": None, "t": "corner"}
        else:
            lerp = lambda u, v: u + (v - u) * t
            p01, p12, p23 = lerp(p0, p1), lerp(p1, p2), lerp(p2, p3)
            p012, p123 = lerp(p01, p12), lerp(p12, p23)
            a["o"] = [p01.x(), p01.y()]
            b["i"] = [p23.x(), p23.y()]
            new = {"p": [mid.x(), mid.y()], "i": [p012.x(), p012.y()],
                   "o": [p123.x(), p123.y()], "t": "smooth"}
        item.nodes.insert(k + 1, new)
        self.chosen = k + 1

    def draw_overlay(self, painter):
        item = self.path_item()
        if item is None:
            self.draw_selection(painter, handles=False)
            return
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(ACCENT, 0))
        painter.drawPath(item.mapToScene(item.shape_path()))
        size = self.view.tol(HANDLE_PX - 1)
        for k, n in enumerate(item.nodes):
            p = item.mapToScene(QPointF(*n["p"]))
            for part in ("i", "o"):
                if n.get(part) is not None:
                    h = item.mapToScene(QPointF(*n[part]))
                    painter.setPen(QPen(ACCENT, 0))
                    painter.drawLine(p, h)
                    draw_handle(painter, h, size * 0.8, True)
        for k, n in enumerate(item.nodes):
            p = item.mapToScene(QPointF(*n["p"]))
            draw_handle(painter, p, size)
            if k == self.chosen:
                r = QRectF(p.x() - size / 2, p.y() - size / 2, size, size)
                painter.fillRect(r, ACCENT)


class TextTool(Tool):
    """Click to type, or drag a box for text that wraps (T)."""

    name = "text"
    cursor = Qt.IBeamCursor

    def __init__(self, view):
        super().__init__(view)
        self.start = None
        self.rect = None

    def press(self, e, sp):
        item = self.view.item_at(sp)
        if isinstance(item, TextItem):
            self.win.start_text_editing(item, sp)
            self.start = None
            return
        self.start = sp
        self.rect = None

    def move(self, e, sp):
        if self.start is None or not e.buttons() & Qt.LeftButton:
            return
        self.rect = QRectF(self.start, sp).normalized()
        self.view.viewport().update()

    def release(self, e, sp):
        start, rect = self.start, self.rect
        self.start = self.rect = None
        if start is None:
            return
        if rect is not None and rect.width() * self.view.zoom() > 12:
            self.win.create_text(rect.topLeft(), rect.width())
        else:
            self.win.create_text(start, None, centre_on_click=True)
        self.view.viewport().update()

    def draw_overlay(self, painter):
        if self.rect is not None:
            painter.setPen(QPen(ACCENT, 0, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.rect)


class PencilTool(Tool):
    """Draw freehand (N). The line is smoothed when you let go; end where
    you started to make a closed shape."""

    name = "pencil"
    cursor = Qt.CrossCursor

    def __init__(self, view):
        super().__init__(view)
        self.points = []

    def press(self, e, sp):
        self.points = [sp]

    def move(self, e, sp):
        if not self.points or not e.buttons() & Qt.LeftButton:
            return
        if _dist(sp, self.points[-1]) * self.view.zoom() >= 2:
            self.points.append(sp)
            self.view.viewport().update()

    def release(self, e, sp):
        points, self.points = self.points, []
        self.view.viewport().update()
        if len(points) < 3:
            return
        tol = self.view.tol(1.6)
        closed = _dist(points[0], points[-1]) <= self.view.tol(10) and len(points) > 8
        kept = simplify(points, tol)
        if closed and len(kept) > 3 and _dist(kept[0], kept[-1]) <= self.view.tol(10):
            kept = kept[:-1]
        if len(kept) < 2:
            return
        self.win.create_path(smooth_nodes(kept, closed), closed=closed, switch=False)

    def deactivate(self):
        self.points = []

    def draw_overlay(self, painter):
        self.draw_selection(painter, handles=False)
        if len(self.points) > 1:
            painter.setPen(QPen(ACCENT, 0))
            for a, b in zip(self.points, self.points[1:]):
                painter.drawLine(a, b)


def simplify(points, tol):
    """Fewer points, same line (Ramer-Douglas-Peucker)."""
    if len(points) < 3:
        return list(points)
    a, b = points[0], points[-1]
    dx, dy = b.x() - a.x(), b.y() - a.y()
    length = math.hypot(dx, dy)
    worst, at = -1.0, 0
    for k in range(1, len(points) - 1):
        p = points[k]
        if length < 1e-9:
            d = _dist(p, a)
        else:
            d = abs(dy * p.x() - dx * p.y() + b.x() * a.y() - b.y() * a.x()) / length
        if d > worst:
            worst, at = d, k
    if worst <= tol:
        return [a, b]
    return simplify(points[:at + 1], tol)[:-1] + simplify(points[at:], tol)


def smooth_nodes(points, closed):
    """Smooth curve nodes through the points (Catmull-Rom style handles)."""
    n = len(points)
    nodes = []
    for k, p in enumerate(points):
        prev = points[k - 1] if (k > 0 or closed) else p
        nxt = points[(k + 1) % n] if (k < n - 1 or closed) else p
        d = (nxt - prev) / 6.0
        node = {"p": [p.x(), p.y()], "i": None, "o": None, "t": "smooth"}
        if n > 2 and (closed or 0 < k < n - 1):
            node["i"] = [p.x() - d.x(), p.y() - d.y()]
            node["o"] = [p.x() + d.x(), p.y() + d.y()]
        elif n > 2 and k == 0:
            node["o"] = [p.x() + d.x(), p.y() + d.y()]
        elif n > 2:
            node["i"] = [p.x() - d.x(), p.y() - d.y()]
        nodes.append(node)
    return nodes


class FillTool(Tool):
    """Gradient fill (G): drag across a shape to fill it with a gradient
    running that way. Hold Shift for a round gradient."""

    name = "fill"
    cursor = Qt.CrossCursor

    def __init__(self, view):
        super().__init__(view)
        self.start = self.end = None
        self.item = None

    def target(self, sp):
        sel = [i for i in self.scene.selected_folio() if i.has_fill and i.gradient_fill]
        if len(sel) == 1:
            return sel[0]
        hit = self.view.item_at(sp)
        return hit if hit is not None and hit.has_fill and hit.gradient_fill else None

    def press(self, e, sp):
        self.item = self.target(sp)
        if self.item is None:
            self.win.statusBar().showMessage(
                "Drag across a shape to give it a gradient (text and pictures cannot have one).",
                5000)
            return
        self.scene.select_only([self.item])
        self.start = self.end = sp
        self.win.begin_change()

    def move(self, e, sp):
        if self.item is None or not e.buttons() & Qt.LeftButton:
            return
        self.end = sp
        d = self.end - self.start
        if math.hypot(d.x(), d.y()) * self.view.zoom() < 3:
            return
        it = self.item
        local = it.mapFromScene(self.end) - it.mapFromScene(self.start)
        fill = it.fill
        if fill.get("type") not in ("linear", "radial"):
            base = fill.get("color", "#ff3d7bd9")
            fill["color2"] = fill.get("color2") if fill.get("color2") not in (None, base) \
                else "#ffffffff"
            fill["color"] = base
        fill["type"] = "radial" if e.modifiers() & Qt.ShiftModifier else "linear"
        fill["angle"] = math.degrees(math.atan2(local.y(), local.x())) % 360.0
        it.changed()
        self.view.viewport().update()

    def release(self, e, sp):
        if self.item is None:
            return
        moved = self.start is not None and self.end is not None and \
            _dist(self.start, self.end) * self.view.zoom() >= 3
        self.item = None
        self.start = self.end = None
        if moved:
            self.win.end_change("Gradient")
        else:
            self.win.cancel_change()
        self.view.viewport().update()

    def draw_overlay(self, painter):
        self.draw_selection(painter, handles=False)
        if self.start is not None and self.end is not None and self.item is not None:
            painter.setPen(QPen(ACCENT, 0))
            painter.drawLine(self.start, self.end)
            size = self.view.tol(HANDLE_PX)
            draw_handle(painter, self.start, size, True)
            draw_handle(painter, self.end, size, True)


class PickerTool(Tool):
    """Colour picker (I): click anything on the page to pick up its colour
    for the selection's fill (or outline, if the outline circle is chosen)."""

    name = "picker"
    cursor = Qt.CrossCursor

    def press(self, e, sp):
        image = self.view.viewport().grab().toImage()
        ratio = image.devicePixelRatio() or 1.0
        c = image.pixelColor(int(e.pos().x() * ratio), int(e.pos().y() * ratio))
        self.win.apply_colour(c, merge=False)
        self.win.remember_colour(c)
        self.win.statusBar().showMessage(f"Picked #{c.name()[1:].upper()}", 4000)


class MeasureTool(Tool):
    """Measure (no key): drag to see a distance and its angle."""

    name = "measure"
    cursor = Qt.CrossCursor

    def __init__(self, view):
        super().__init__(view)
        self.start = self.end = None

    def press(self, e, sp):
        self.start = self.end = self.view.snap(sp)

    def move(self, e, sp):
        if self.start is None or not e.buttons() & Qt.LeftButton:
            return
        p = self.view.snap(sp)
        if e.modifiers() & Qt.ShiftModifier:
            p = _constrain45(self.start, sp)
        self.end = p
        self.win.statusBar().showMessage(self.text())
        self.view.viewport().update()

    def release(self, e, sp):
        self.view.clear_smart()

    def key_press(self, e):
        if e.key() == Qt.Key_Escape:
            self.start = self.end = None
            self.view.viewport().update()
            return True
        return False

    def deactivate(self):
        self.start = self.end = None

    def text(self):
        if self.start is None or self.end is None:
            return ""
        doc = self.scene.doc
        d = self.end - self.start
        length = math.hypot(d.x(), d.y())
        angle = (-math.degrees(math.atan2(d.y(), d.x()))) % 360.0
        u = doc.unit
        text = f"{units.tidy(units.from_px(length, u, doc.dpi), units.decimals(u))} {u}"
        if u == "px":
            text += f" ({units.tidy(length / doc.dpi, 3)} in)"
        return f"{text}   at {angle:.1f}°"

    def draw_overlay(self, painter):
        if self.start is None or self.end is None:
            return
        painter.setPen(QPen(QColor("#ff9800"), 0))
        painter.drawLine(self.start, self.end)
        size = self.view.tol(6)
        for p in (self.start, self.end):
            painter.drawLine(p - QPointF(size, 0), p + QPointF(size, 0))
            painter.drawLine(p - QPointF(0, size), p + QPointF(0, size))
        text = self.text()
        if text:
            painter.save()
            vp = self.view.mapFromScene((self.start + self.end) / 2)
            painter.resetTransform()
            font = painter.font()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            r = painter.fontMetrics().boundingRect(text).adjusted(-6, -3, 6, 3)
            r.moveCenter(vp + QPoint(0, -16))
            painter.fillRect(r, QColor(30, 30, 34, 220))
            painter.setPen(QColor("#ffcc80"))
            painter.drawText(r, Qt.AlignCenter, text)
            painter.restore()


class HandTool(Tool):
    """Drag to move around the page (H, or hold Space)."""

    name = "hand"
    cursor = Qt.OpenHandCursor

    def __init__(self, view):
        super().__init__(view)
        self.last = None

    def press(self, e, sp):
        self.last = e.pos()
        self.view.viewport().setCursor(Qt.ClosedHandCursor)

    def move(self, e, sp):
        if self.last is None or not e.buttons() & Qt.LeftButton:
            return
        d = e.pos() - self.last
        self.last = e.pos()
        h, v = self.view.horizontalScrollBar(), self.view.verticalScrollBar()
        h.setValue(h.value() - d.x())
        v.setValue(v.value() - d.y())

    def release(self, e, sp):
        self.last = None
        self.view.viewport().setCursor(self.cursor)


class ZoomTool(Tool):
    """Click to zoom in, Ctrl-click to zoom out, drag a box to zoom to it (Z)."""

    name = "zoom"
    cursor = Qt.CrossCursor

    def __init__(self, view):
        super().__init__(view)
        self.start = None
        self.rect = None

    def press(self, e, sp):
        self.start = sp
        self.rect = None

    def move(self, e, sp):
        if self.start is None or not e.buttons() & Qt.LeftButton:
            return
        self.rect = QRectF(self.start, sp).normalized()
        self.view.viewport().update()

    def release(self, e, sp):
        rect, self.rect, self.start = self.rect, None, None
        if rect is not None and rect.width() * self.view.zoom() > 8:
            self.view.fit_rect(rect)
        elif e.modifiers() & (Qt.ControlModifier | Qt.AltModifier):
            self.view.zoom_by(1 / 1.5, e.pos())
        else:
            self.view.zoom_by(1.5, e.pos())
        self.view.viewport().update()

    def draw_overlay(self, painter):
        self.draw_selection(painter, handles=False)
        if self.rect is not None:
            painter.setPen(QPen(ACCENT, 0, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.rect)


def make_tools(view):
    tools = {
        "move": MoveTool(view),
        "node": NodeTool(view),
        "pen": PenTool(view),
        "line": LineTool(view),
        "pencil": PencilTool(view),
        "fill": FillTool(view),
        "text": TextTool(view),
        "picker": PickerTool(view),
        "measure": MeasureTool(view),
        "hand": HandTool(view),
        "zoom": ZoomTool(view),
    }
    for key, _, _ in shapes.SHAPE_TOOLS:
        tools[key] = ShapeTool(view, key)
    return tools
