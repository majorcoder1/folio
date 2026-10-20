"""The canvas: shows the page, handles zoom and pan, and passes mouse
events to the active tool."""

import math

from PyQt5.QtCore import QEvent, QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import (QBrush, QColor, QFont, QPainter, QPainterPath, QPen,
                         QPolygonF, QTransform)
from PyQt5.QtWidgets import QFrame, QGraphicsView

from .items import FolioItem, TextItem
from .scene import PASTEBOARD
from . import snapping
from .rulers import draw_grid_and_guides

ACCENT = QColor("#4a8fe7")
SMART = QColor("#ff3df2")
TRIM_COLOR = QColor("#29b6f6")
SAFE_COLOR = QColor("#66bb6a")
BARCODE_COLOR = QColor("#ffca28")

HANDLES = {"tl": (0.0, 0.0), "t": (0.5, 0.0), "tr": (1.0, 0.0), "r": (1.0, 0.5),
           "br": (1.0, 1.0), "b": (0.5, 1.0), "bl": (0.0, 1.0), "l": (0.0, 0.5)}
OPPOSITE = {"tl": "br", "t": "b", "tr": "bl", "r": "l", "br": "tl", "b": "t",
            "bl": "tr", "l": "r"}
CORNERS = ("tl", "tr", "br", "bl")
TEXT_HANDLES = ("tl", "tr", "br", "bl", "l", "r")

EDIT_KEYS = {Qt.Key_Z, Qt.Key_Y, Qt.Key_C, Qt.Key_V, Qt.Key_X, Qt.Key_A,
             Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down, Qt.Key_Home,
             Qt.Key_End, Qt.Key_Backspace, Qt.Key_Delete, Qt.Key_Return, Qt.Key_Enter}


class CanvasView(QGraphicsView):
    zoomChanged = pyqtSignal(float)
    cursorMoved = pyqtSignal(QPointF)

    def __init__(self, scene, win):
        super().__init__(scene)
        self.win = win
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform
                            | QPainter.TextAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setFocusPolicy(Qt.StrongFocus)
        self.tool = None
        self.show_guides = True
        self.preview = False
        self.snap_enabled = True
        self.snap_page = True       # page edges, cover parts and guides
        self.show_grid = False
        self.show_margins = True
        self.temp_guide = None      # a guide being dragged out of a ruler
        self.snap_objects = True    # other objects
        self.smart_x = None
        self.smart_y = None
        self.editing_text = None
        self._pan = None
        self._space = False
        self._forward = False

    # ---- zoom ----------------------------------------------------------------

    def zoom(self):
        return self.transform().m11()

    def set_zoom(self, z, anchor=None):
        z = min(max(z, 0.01), 64.0)
        if anchor is None:
            anchor = self.viewport().rect().center()
        scene_pt = self.mapToScene(anchor)
        self.setTransform(QTransform.fromScale(z, z))
        moved = self.mapFromScene(scene_pt) - anchor
        h, v = self.horizontalScrollBar(), self.verticalScrollBar()
        h.setValue(h.value() + moved.x())
        v.setValue(v.value() + moved.y())
        self.zoomChanged.emit(z)
        self.viewport().update()

    def zoom_by(self, factor, anchor=None):
        self.set_zoom(self.zoom() * factor, anchor)

    def fit_rect(self, rect):
        if rect.isEmpty():
            return
        view = self.viewport().rect()
        z = min(view.width() / rect.width(), view.height() / rect.height())
        self.setTransform(QTransform.fromScale(z, z))
        self.centerOn(rect.center())
        self.zoomChanged.emit(z)
        self.viewport().update()

    def fit_page(self):
        page = self.scene().doc.page_rect()
        pad = max(page.width(), page.height()) * 0.05
        self.fit_rect(page.adjusted(-pad, -pad, pad, pad))

    def tol(self, px=5.0):
        return px / max(self.zoom(), 1e-6)

    # ---- snapping helpers ----------------------------------------------------

    def snap_lines(self, exclude=()):
        if not self.snap_enabled:
            return [], []
        xs, ys = snapping.guide_lines(self.scene(), exclude, self.snap_page, self.snap_objects)
        if self.show_guides:
            xs = xs + list(self.scene().guides.get("x", []))
            ys = ys + list(self.scene().guides.get("y", []))
        if self.show_grid:
            from .rulers import grid_lines
            gx, gy = grid_lines(self.scene().doc, self.scene().doc.page_rect())
            xs = xs + [x for x, _ in gx]
            ys = ys + [y for y, _ in gy]
        return xs, ys

    def snap_tol(self):
        return 7.0 / max(self.zoom(), 1e-6)

    def snap(self, p, exclude=()):
        """Snap a single point and show the guide lines it hit."""
        if not self.snap_enabled:
            self.smart_x = self.smart_y = None
            return p
        xs, ys = self.snap_lines(exclude)
        out, gx, gy = snapping.snap_point(p, xs, ys, self.snap_tol())
        self.smart_x, self.smart_y = gx, gy
        return out

    def clear_smart(self):
        self.smart_x = self.smart_y = None
        self.viewport().update()

    # ---- finding objects -----------------------------------------------------

    def item_at(self, sp, include_locked=False):
        t = self.tol(4)
        area = QRectF(sp.x() - t, sp.y() - t, 2 * t, 2 * t)
        for item in self.scene().items(area):
            if not isinstance(item, FolioItem) or not item.isVisible():
                continue
            if item.locked and not include_locked:
                continue
            if item.hit(sp, t):
                return item
        return None

    def selection_frame(self):
        """Outline and handle positions for what is selected, or None."""
        sel = self.scene().selected_folio()
        if not sel:
            return None
        locked = any(i.locked for i in sel)
        if len(sel) == 1:
            it = sel[0]
            keys = TEXT_HANDLES if isinstance(it, TextItem) else tuple(HANDLES)
            points = {k: it.mapToScene(QPointF(fx * it.w, fy * it.h))
                      for k, (fx, fy) in HANDLES.items() if k in keys}
            top = it.mapToScene(QPointF(it.w / 2, 0))
            centre = it.center_scene()
            d = top - centre
            length = math.hypot(d.x(), d.y())
            if length < 1e-6:
                a = math.radians(it.rotation() - 90)
                unit = QPointF(math.cos(a), math.sin(a))
            else:
                unit = d / length
            rot = top + unit * self.tol(26)
            outline = it.scene_polygon()
            single = True
        else:
            box = self.scene().items_rect(sel)
            points = {"tl": box.topLeft(), "tr": box.topRight(),
                      "br": box.bottomRight(), "bl": box.bottomLeft()}
            top = QPointF(box.center().x(), box.top())
            rot = QPointF(top.x(), top.y() - self.tol(26))
            outline = QPolygonF(box)
            single = False
        return {"items": sel, "points": points, "rot": rot, "top": top,
                "outline": outline, "single": single, "locked": locked}

    # ---- events --------------------------------------------------------------

    def event(self, e):
        if e.type() == QEvent.ShortcutOverride:
            if self.editing_text is not None:
                mods = e.modifiers()
                if not mods & (Qt.ControlModifier | Qt.AltModifier) or e.key() in EDIT_KEYS:
                    e.accept()
                    return True
            elif self.tool is not None and self.tool.wants_key(e):
                # e.g. Delete removes one point of a curve, not the whole curve
                e.accept()
                return True
        return super().event(e)

    def scene_pos(self, e):
        return self.mapToScene(e.pos())

    def mousePressEvent(self, e):
        self.setFocus(Qt.MouseFocusReason)
        if e.button() == Qt.MiddleButton or (e.button() == Qt.LeftButton and self._space):
            self._pan = e.pos()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            return
        sp = self.scene_pos(e)
        if self.editing_text is not None:
            if e.button() == Qt.LeftButton and self.editing_text.hit(sp, self.tol(2)):
                self._forward = True
                super().mousePressEvent(e)
                return
            self.win.stop_text_editing()
        if e.button() == Qt.LeftButton and self.tool is not None:
            self.tool.press(e, sp)

    def mouseMoveEvent(self, e):
        sp = self.scene_pos(e)
        self.cursorMoved.emit(sp)
        if self._pan is not None:
            d = e.pos() - self._pan
            self._pan = e.pos()
            h, v = self.horizontalScrollBar(), self.verticalScrollBar()
            h.setValue(h.value() - d.x())
            v.setValue(v.value() - d.y())
            return
        if self._forward:
            super().mouseMoveEvent(e)
            return
        if self.tool is not None:
            self.tool.move(e, sp)
            if not e.buttons() and not self._space:
                self.viewport().setCursor(self.tool.cursor_at(sp))

    def mouseReleaseEvent(self, e):
        if self._pan is not None and e.button() in (Qt.MiddleButton, Qt.LeftButton):
            self._pan = None
            self.update_cursor()
            return
        if self._forward:
            self._forward = False
            super().mouseReleaseEvent(e)
            return
        if e.button() == Qt.LeftButton and self.tool is not None:
            self.tool.release(e, self.scene_pos(e))

    def mouseDoubleClickEvent(self, e):
        sp = self.scene_pos(e)
        if self.editing_text is not None and self.editing_text.hit(sp, self.tol(2)):
            self._forward = True
            super().mouseDoubleClickEvent(e)
            return
        if e.button() == Qt.LeftButton and self.tool is not None:
            self.tool.double_click(e, sp)

    def wheelEvent(self, e):
        dy = e.angleDelta().y()
        if e.modifiers() & Qt.ControlModifier:
            self.zoom_by(1.2 ** (dy / 120.0), e.position().toPoint())
            return
        if e.modifiers() & Qt.ShiftModifier:
            h = self.horizontalScrollBar()
            h.setValue(h.value() - dy)
            return
        super().wheelEvent(e)

    def keyPressEvent(self, e):
        if self.editing_text is not None:
            if e.key() == Qt.Key_Escape:
                self.win.stop_text_editing(select=True)
                return
            super().keyPressEvent(e)
            return
        if e.key() == Qt.Key_Space:
            if not e.isAutoRepeat():
                self._space = True
                self.update_cursor()
            return
        if self.tool is not None and self.tool.key_press(e):
            return
        if e.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            return
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key_Space and not e.isAutoRepeat():
            self._space = False
            self.update_cursor()
            return
        super().keyReleaseEvent(e)

    def focusOutEvent(self, e):
        self._space = False
        super().focusOutEvent(e)

    def update_cursor(self):
        if self._space:
            self.viewport().setCursor(Qt.OpenHandCursor)
        elif self.tool is not None:
            self.viewport().setCursor(self.tool.cursor)
        else:
            self.viewport().unsetCursor()

    def contextMenuEvent(self, e):
        if self.editing_text is not None:
            super().contextMenuEvent(e)
            return
        self.win.show_context_menu(e.globalPos(), self.mapToScene(e.pos()))

    def dragEnterEvent(self, e):
        md = e.mimeData()
        if md.hasUrls() or md.hasImage():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        md = e.mimeData()
        if md.hasUrls() or md.hasImage():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):
        self.win.handle_drop(e.mimeData(), self.mapToScene(e.pos()))
        e.acceptProposedAction()

    # ---- drawing on top of the page ------------------------------------------

    def drawForeground(self, painter, rect):
        scene = self.scene()
        doc = scene.doc
        page = doc.page_rect()
        hole = doc.trim_rect() if self.preview else page
        veil = QColor(PASTEBOARD)
        veil.setAlpha(255 if self.preview else 215)
        outside = QPainterPath()
        outside.addRect(rect.united(page).adjusted(-10, -10, 10, 10))
        outside.addRect(hole)
        outside.setFillRule(Qt.OddEvenFill)
        painter.save()
        painter.fillPath(outside, veil)
        if self.show_guides and not self.preview:
            self.draw_guides(painter)
        if self.editing_text is not None:
            pen = QPen(ACCENT, 0, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPolygon(self.editing_text.scene_polygon())
        if not self.preview:
            draw_grid_and_guides(painter, self, scene)
        self.win.draw_persona_overlay(painter)
        if self.tool is not None:
            self.tool.draw_overlay(painter)
        self.draw_smart(painter, page)
        if not scene.folio_items():
            self.draw_tip(painter)
        painter.restore()

    def draw_tip(self, painter):
        """A hint on an empty page, so it is clear how to start."""
        painter.save()
        painter.resetTransform()
        font = QFont(self.font())
        font.setPointSizeF(10.5)
        painter.setFont(font)
        text = ("Start here:  T  add text    •    Ctrl+Shift+I  place a photo    "
                "•    M  rectangle    •    E  ellipse")
        fm = painter.fontMetrics()
        w = fm.horizontalAdvance(text) + 32
        vp = self.viewport().rect()
        box = QRectF((vp.width() - w) / 2, vp.height() - 52, w, 34)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(20, 20, 24, 220))
        painter.drawRoundedRect(box, 8, 8)
        painter.setPen(QColor("#d8dbe0"))
        painter.drawText(box, Qt.AlignCenter, text)
        painter.restore()

    def draw_smart(self, painter, page):
        if self.smart_x is None and self.smart_y is None:
            return
        pen = QPen(SMART, 0)
        painter.setPen(pen)
        big = page.adjusted(-page.width(), -page.height(), page.width(), page.height())
        if self.smart_x is not None:
            painter.drawLine(QPointF(self.smart_x, big.top()), QPointF(self.smart_x, big.bottom()))
        if self.smart_y is not None:
            painter.drawLine(QPointF(big.left(), self.smart_y), QPointF(big.right(), self.smart_y))

    def draw_guides(self, painter):
        doc = self.scene().doc
        regs = doc.regions()
        page, trim = regs["page"], regs["trim"]
        if doc.bleed > 0:
            bleed = QPainterPath()
            bleed.addRect(page)
            bleed.addRect(trim)
            bleed.setFillRule(Qt.OddEvenFill)
            painter.fillPath(bleed, QColor(255, 82, 82, 40))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(TRIM_COLOR, 0))
        painter.drawRect(trim)
        if doc.kind == "cover":
            spine = regs["spine"]
            pen = QPen(TRIM_COLOR, 0, Qt.DashLine)
            painter.setPen(pen)
            for x in (spine.left(), spine.right()):
                painter.drawLine(QPointF(x, page.top()), QPointF(x, page.bottom()))
        for r in doc.hinge_rects():
            # hardcover hinges: the cover bends here, so keep words out
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(255, 167, 38, 90), Qt.BDiagPattern))
            painter.drawRect(r)
            painter.setBrush(Qt.NoBrush)
        pen = QPen(SAFE_COLOR, 0, Qt.DashLine)
        painter.setPen(pen)
        for r in (doc.safe_rects() if self.show_margins else ()):
            painter.drawRect(r)
        barcode = doc.barcode_rect()
        if barcode is not None:
            fill = QColor(BARCODE_COLOR)
            fill.setAlpha(55)
            painter.fillRect(barcode, fill)
            painter.setPen(QPen(BARCODE_COLOR, 0))
            painter.drawRect(barcode)
        self.draw_labels(painter, doc, regs, barcode)

    def draw_labels(self, painter, doc, regs, barcode):
        painter.save()
        painter.resetTransform()
        font = QFont(self.font())
        font.setPointSizeF(8.5)
        font.setBold(True)
        painter.setFont(font)
        page = regs["page"]
        labels = []
        if doc.kind == "cover":
            labels = [("BACK COVER", regs["back"]), ("SPINE", regs["spine"]),
                      ("FRONT COVER", regs["front"])]
        for text, r in labels:
            left = self.mapFromScene(QPointF(r.left(), page.top()))
            right = self.mapFromScene(QPointF(r.right(), page.top()))
            width = right.x() - left.x()
            if width < painter.fontMetrics().horizontalAdvance(text) + 6:
                if text == "SPINE" and width > 0:
                    text = "S"
                else:
                    continue
            painter.setPen(QColor("#9aa4b1"))
            box = QRectF(left.x(), left.y() - 22, width, 18)
            painter.drawText(box, Qt.AlignCenter, text)
        if barcode is not None:
            tl = self.mapFromScene(barcode.topLeft())
            br = self.mapFromScene(barcode.bottomRight())
            box = QRectF(QPointF(tl), QPointF(br))
            if box.width() > 60:
                painter.setPen(QColor("#b38f00"))
                painter.drawText(box, Qt.AlignCenter, "Barcode")
        painter.restore()


def angle_cursor(vec):
    """Pick a resize cursor that matches a handle's direction on screen."""
    a = math.degrees(math.atan2(vec.y(), vec.x())) % 180
    if a < 22.5 or a >= 157.5:
        return Qt.SizeHorCursor
    if a < 67.5:
        return Qt.SizeFDiagCursor
    if a < 112.5:
        return Qt.SizeVerCursor
    return Qt.SizeBDiagCursor
