"""Icons, drawn in code so Folio needs no image files."""

from functools import lru_cache

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QBrush, QColor, QIcon, QLinearGradient, QPainter,
                         QPainterPath, QPen, QPixmap, QPolygonF)

FG = QColor("#d8dbe0")
DIM = QColor("#8c939d")
ACCENT = QColor("#4a8fe7")


def _pen(color=FG, width=1.6):
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _poly(*pts):
    return QPolygonF([QPointF(x, y) for x, y in pts])


def _draw(name, p):
    """Draw icon ``name`` on a 24 x 24 grid."""
    p.setPen(_pen())
    p.setBrush(Qt.NoBrush)

    def line(x1, y1, x2, y2):
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    if name == "move":
        p.setBrush(FG)
        p.drawPolygon(_poly((6, 3), (6, 19), (10, 15.2), (12.8, 21), (15.2, 20),
                            (12.4, 14.2), (17.6, 14.2)))
    elif name == "node":
        p.drawPolygon(_poly((5, 3), (5, 17), (8.6, 13.6), (11, 19), (13, 18.2),
                            (10.6, 12.8), (15.4, 12.8)))
        p.setBrush(ACCENT)
        p.setPen(_pen(ACCENT, 1.2))
        p.drawRect(QRectF(15, 15, 5, 5))
    elif name == "pen":
        path = QPainterPath()
        path.moveTo(12, 3)
        path.lineTo(18, 12)
        path.lineTo(14, 20)
        path.lineTo(10, 20)
        path.lineTo(6, 12)
        path.closeSubpath()
        p.setBrush(QColor(FG.red(), FG.green(), FG.blue(), 70))
        p.drawPath(path)
        p.setBrush(Qt.NoBrush)
        line(12, 3, 12, 11)
        p.drawEllipse(QPointF(12, 12.5), 1.4, 1.4)
        line(9, 22, 15, 22)
    elif name == "line":
        line(5, 19, 19, 5)
        p.setBrush(FG)
        p.drawRect(QRectF(3, 17, 4, 4))
        p.drawRect(QRectF(17, 3, 4, 4))
    elif name == "rect":
        p.setBrush(QColor(FG.red(), FG.green(), FG.blue(), 150))
        p.setPen(_pen(FG, 1.2))
        p.drawRect(QRectF(4, 4, 16, 16))
    elif name == "ellipse":
        p.setBrush(QColor(FG.red(), FG.green(), FG.blue(), 150))
        p.setPen(_pen(FG, 1.2))
        p.drawEllipse(QRectF(4, 4, 16, 16))
    elif name == "text":
        p.setPen(_pen(FG, 2.2))
        line(5.5, 5, 18.5, 5)
        line(12, 5, 12, 19.5)
        p.setPen(_pen(FG, 1.6))
        line(9, 19.5, 15, 19.5)
        line(5.5, 5, 5.5, 7.5)
        line(18.5, 5, 18.5, 7.5)
    elif name == "image":
        sky = QLinearGradient(0, 5, 0, 19)
        sky.setColorAt(0, QColor("#4fa3f7"))
        sky.setColorAt(1, QColor("#b9dcff"))
        frame = QRectF(3, 5, 18, 14)
        p.setBrush(QBrush(sky))
        p.setPen(_pen(FG, 1.2))
        p.drawRoundedRect(frame, 2, 2)
        hill = QPainterPath()
        hill.moveTo(3.5, 18.5)
        hill.lineTo(9, 11.5)
        hill.lineTo(13, 15.5)
        hill.lineTo(15.5, 13)
        hill.lineTo(20.5, 18.5)
        hill.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#3fae5a"))
        p.drawPath(hill)
        p.setBrush(QColor("#ffd54f"))
        p.drawEllipse(QPointF(16.5, 8.8), 1.8, 1.8)
    elif name == "hand":
        path = QPainterPath()
        path.moveTo(8, 12)
        path.lineTo(8, 5.5)
        path.moveTo(10.7, 11.5)
        path.lineTo(10.7, 4)
        path.moveTo(13.4, 11.5)
        path.lineTo(13.4, 4.5)
        path.moveTo(16, 12)
        path.lineTo(16, 7)
        p.setPen(_pen(FG, 2.0))
        p.drawPath(path)
        p.setPen(_pen())
        body = QPainterPath()
        body.moveTo(6.6, 12)
        body.lineTo(17.4, 11)
        body.cubicTo(17.6, 16, 16.5, 20.5, 12.5, 20.5)
        body.cubicTo(9.5, 20.5, 8, 18.5, 5, 14.5)
        body.lineTo(4, 12.6)
        body.cubicTo(4.6, 11.6, 5.8, 11.8, 6.6, 12)
        p.drawPath(body)
    elif name == "zoom":
        p.setBrush(QColor(110, 180, 255, 110))
        p.drawEllipse(QPointF(10, 10), 6, 6)
        p.setPen(_pen(QColor("#c99a5b"), 3))
        line(14.6, 14.6, 20, 20)
    elif name == "new":
        p.drawPolygon(_poly((6, 3), (14, 3), (19, 8), (19, 21), (6, 21)))
        p.drawPolyline(_poly((14, 3), (14, 8), (19, 8)))
        p.setPen(_pen(ACCENT, 2))
        line(12.5, 11, 12.5, 18)
        line(9, 14.5, 16, 14.5)
    elif name == "open":
        p.drawPolygon(_poly((3, 6), (9, 6), (11, 8), (20, 8), (20, 19), (3, 19)))
        p.drawPolyline(_poly((3, 19), (6, 11), (22, 11), (20, 19)))
    elif name == "save":
        p.drawPolygon(_poly((4, 4), (17, 4), (20, 7), (20, 20), (4, 20)))
        p.drawRect(QRectF(8, 4, 7, 5))
        p.drawRect(QRectF(7, 13, 10, 7))
    elif name == "export":
        p.drawPolyline(_poly((10, 5), (5, 5), (5, 19), (19, 19), (19, 14)))
        line(11, 13, 20, 4)
        p.drawPolyline(_poly((14, 4), (20, 4), (20, 10)))
    elif name in ("undo", "redo"):
        path = QPainterPath()
        if name == "undo":
            path.moveTo(5, 10)
            path.lineTo(15, 10)
            path.cubicTo(22, 10, 22, 20, 15, 20)
            path.lineTo(9, 20)
            p.drawPath(path)
            p.drawPolyline(_poly((9, 6), (5, 10), (9, 14)))
        else:
            path.moveTo(19, 10)
            path.lineTo(9, 10)
            path.cubicTo(2, 10, 2, 20, 9, 20)
            path.lineTo(15, 20)
            p.drawPath(path)
            p.drawPolyline(_poly((15, 6), (19, 10), (15, 14)))
    elif name == "snap":
        path = QPainterPath()
        path.moveTo(6, 4)
        path.lineTo(6, 12)
        path.cubicTo(6, 21.5, 18, 21.5, 18, 12)
        path.lineTo(18, 4)
        p.setPen(_pen(FG, 3.2))
        p.drawPath(path)
        p.setPen(_pen(QColor("#e05555"), 3.2))
        line(6, 4, 6, 7)
        line(18, 4, 18, 7)
    elif name == "guides":
        pen = _pen(QColor("#29b6f6"), 1.4)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        line(8, 3, 8, 21)
        line(16, 3, 16, 21)
        line(3, 8, 21, 8)
        line(3, 16, 21, 16)
        p.setPen(_pen(DIM, 1.2))
        p.drawRect(QRectF(3, 3, 18, 18))
    elif name in ("preview", "eye"):
        path = QPainterPath()
        path.moveTo(2.5, 12)
        path.cubicTo(7, 5, 17, 5, 21.5, 12)
        path.cubicTo(17, 19, 7, 19, 2.5, 12)
        p.drawPath(path)
        p.setBrush(FG)
        p.drawEllipse(QPointF(12, 12), 2.8, 2.8)
    elif name == "eye-off":
        p.setPen(_pen(DIM))
        path = QPainterPath()
        path.moveTo(2.5, 12)
        path.cubicTo(7, 5, 17, 5, 21.5, 12)
        path.cubicTo(17, 19, 7, 19, 2.5, 12)
        p.drawPath(path)
        line(4, 20, 20, 4)
    elif name in ("lock", "unlock"):
        p.drawRoundedRect(QRectF(5, 11, 14, 10), 2, 2)
        path = QPainterPath()
        if name == "lock":
            path.moveTo(8, 11)
            path.lineTo(8, 8)
            path.cubicTo(8, 2.5, 16, 2.5, 16, 8)
            path.lineTo(16, 11)
        else:
            p.setPen(_pen(DIM))
            path.moveTo(8, 11)
            path.lineTo(8, 8)
            path.cubicTo(8, 2.5, 16, 2.5, 16, 6)
        p.drawPath(path)
    elif name.startswith("align-"):
        kind = name[6:]
        p.setBrush(QColor(FG.red(), FG.green(), FG.blue(), 70))
        if kind in ("left", "hcenter", "right"):
            x = {"left": 4, "hcenter": 12, "right": 20}[kind]
            p.setPen(_pen(ACCENT, 1.8))
            line(x, 3, x, 21)
            p.setPen(_pen())
            if kind == "left":
                p.drawRect(QRectF(4, 6, 14, 4))
                p.drawRect(QRectF(4, 14, 9, 4))
            elif kind == "right":
                p.drawRect(QRectF(6, 6, 14, 4))
                p.drawRect(QRectF(11, 14, 9, 4))
            else:
                p.drawRect(QRectF(5, 6, 14, 4))
                p.drawRect(QRectF(7.5, 14, 9, 4))
        else:
            y = {"top": 4, "vcenter": 12, "bottom": 20}[kind]
            p.setPen(_pen(ACCENT, 1.8))
            line(3, y, 21, y)
            p.setPen(_pen())
            if kind == "top":
                p.drawRect(QRectF(6, 4, 4, 14))
                p.drawRect(QRectF(14, 4, 4, 9))
            elif kind == "bottom":
                p.drawRect(QRectF(6, 6, 4, 14))
                p.drawRect(QRectF(14, 11, 4, 9))
            else:
                p.drawRect(QRectF(6, 5, 4, 14))
                p.drawRect(QRectF(14, 7.5, 4, 9))
    elif name == "dist-h":
        p.setBrush(QColor(FG.red(), FG.green(), FG.blue(), 70))
        for x in (3, 10, 17):
            p.drawRect(QRectF(x, 7, 4, 10))
    elif name == "dist-v":
        p.setBrush(QColor(FG.red(), FG.green(), FG.blue(), 70))
        for y in (3, 10, 17):
            p.drawRect(QRectF(7, y, 10, 4))
    elif name in ("front", "back", "forward", "backward"):
        top_filled = name in ("front", "forward")
        back_rect, front_rect = QRectF(4, 4, 11, 11), QRectF(9, 9, 11, 11)
        p.setBrush(Qt.NoBrush)
        p.drawRect(back_rect)
        p.setBrush(QColor("#2b2b2e"))
        p.drawRect(front_rect)
        p.setBrush(ACCENT)
        p.setPen(_pen(ACCENT, 1.2))
        if top_filled:
            p.drawRect(front_rect.adjusted(1.5, 1.5, -1.5, -1.5))
        else:
            p.drawRect(QRectF(5.5, 5.5, 3.5, 3.5))
        if name in ("front", "back"):
            p.setPen(_pen(FG, 1.4))
            if name == "back":
                line(2, 22, 22, 22)
            else:
                line(2, 2, 22, 2)
    elif name in ("group", "ungroup"):
        pen = _pen(DIM if name == "ungroup" else ACCENT, 1.3)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.drawRect(QRectF(2.5, 2.5, 19, 19))
        p.setPen(_pen())
        p.drawRect(QRectF(5.5, 5.5, 7, 7))
        p.drawEllipse(QRectF(11.5, 11.5, 7, 7))
    elif name == "flip-h":
        line(12, 3, 12, 21)
        p.setBrush(FG)
        p.drawPolygon(_poly((10, 6), (10, 18), (3, 18)))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(_poly((14, 6), (14, 18), (21, 18)))
    elif name == "flip-v":
        line(3, 12, 21, 12)
        p.setBrush(FG)
        p.drawPolygon(_poly((6, 10), (18, 10), (18, 3)))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(_poly((6, 14), (18, 14), (18, 21)))
    elif name in ("rotate-cw", "rotate-ccw"):
        path = QPainterPath()
        path.arcMoveTo(QRectF(4, 4, 16, 16), 90)
        path.arcTo(QRectF(4, 4, 16, 16), 90, -270 if name == "rotate-cw" else 270)
        p.drawPath(path)
        if name == "rotate-cw":
            p.drawPolyline(_poly((8, 1.5), (12, 4), (8, 7)))
        else:
            p.drawPolyline(_poly((16, 1.5), (12, 4), (16, 7)))
    elif name == "trash":
        line(4, 6, 20, 6)
        p.drawPolyline(_poly((9, 6), (9, 3.5), (15, 3.5), (15, 6)))
        p.drawPolygon(_poly((6, 6), (7.5, 21), (16.5, 21), (18, 6)))
        line(10.5, 10, 10.5, 17)
        line(13.5, 10, 13.5, 17)
    elif name.startswith("text-"):
        kind = name[5:]
        lines = [(3, 21), (3, 15), (3, 21), (3, 13)]
        for i, (x0, x1) in enumerate(lines):
            y = 5 + i * 4.7
            width = x1 - x0
            if kind == "justify":
                a, b = 3, 21
            elif kind == "left":
                a, b = 3, 3 + width
            elif kind == "right":
                a, b = 21 - width, 21
            else:
                a, b = 12 - width / 2, 12 + width / 2
            line(a, y, b, y)
    elif name == "print":
        p.drawRect(QRectF(7, 3, 10, 6))
        p.drawRoundedRect(QRectF(3, 9, 18, 8), 2, 2)
        p.setBrush(QColor("#2b2b2e"))
        p.drawRect(QRectF(7, 14, 10, 7))
        p.setPen(_pen(ACCENT, 1.4))
        line(9, 17, 15, 17)
        line(9, 19, 13, 19)
    elif name == "spine":
        p.drawRect(QRectF(2.5, 4, 19, 16))
        p.setBrush(ACCENT)
        p.setPen(_pen(ACCENT, 1))
        p.drawRect(QRectF(10.5, 4, 3, 16))
    elif name == "cover":
        p.drawRect(QRectF(4, 3, 16, 18))
        p.setPen(_pen(ACCENT, 2))
        line(7, 8, 17, 8)
        p.setPen(_pen(DIM, 1.4))
        line(8, 11, 16, 11)
    elif name == "persona-pixel":
        colours = ["#e05555", "#f2c94c", "#3fae5a", "#4a8fe7", "#b06ad8", "#ff9800",
                   "#d8dbe0", "#38c172", "#e0566b"]
        for k, c in enumerate(colours):
            x, y = 4 + (k % 3) * 5.6, 4 + (k // 3) * 5.6
            p.fillRect(QRectF(x, y, 4.6, 4.6), QColor(c))
    elif name == "persona-export":
        p.setBrush(QColor("#5b5bd6"))
        p.setPen(_pen(QColor("#a5a5ff"), 1.2))
        p.drawRoundedRect(QRectF(3, 5, 15, 15), 2, 2)
        p.setPen(_pen(QColor("#38c172"), 2))
        line(11, 13, 20, 4)
        p.drawPolyline(_poly((14, 4), (20, 4), (20, 10)))
    elif name in ("px-rect", "px-ellipse", "px-row", "px-column"):
        pen = _pen(FG, 1.3)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        if name == "px-rect":
            p.drawRect(QRectF(4, 5, 16, 14))
        elif name == "px-ellipse":
            p.drawEllipse(QRectF(4, 4, 16, 16))
        elif name == "px-row":
            p.drawRect(QRectF(2, 9.5, 20, 5))
        else:
            p.drawRect(QRectF(9.5, 2, 5, 20))
    elif name == "px-lasso":
        p.setPen(_pen(QColor("#f2a33a"), 1.8))
        path = QPainterPath()
        path.moveTo(9, 18)
        path.cubicTo(2, 16, 3, 6, 12, 5)
        path.cubicTo(21, 4, 22, 13, 14, 15)
        path.cubicTo(10, 16, 8, 19, 11, 21)
        p.drawPath(path)
    elif name == "px-wand":
        p.setPen(_pen(QColor("#9a7bd8"), 2.4))
        line(5, 19, 14, 10)
        p.setPen(_pen(QColor("#f2c94c"), 1.4))
        for x1, y1, x2, y2 in ((17, 3, 17, 9), (14, 6, 20, 6), (15, 4, 19, 8), (19, 4, 15, 8)):
            line(x1, y1, x2, y2)
    elif name == "px-brush":
        p.save()
        p.translate(12, 12)
        p.rotate(45)
        p.setPen(_pen(QColor("#5c3a1a"), 1))
        p.setBrush(QColor("#c99a5b"))
        p.drawRoundedRect(QRectF(-1.6, -1, 3.2, 11), 1.5, 1.5)
        p.setBrush(QColor("#9aa1ab"))
        p.drawRect(QRectF(-2.2, -4, 4.4, 3))
        p.setBrush(QColor("#e05555"))
        p.setPen(Qt.NoPen)
        tip = QPainterPath()
        tip.moveTo(-2.2, -4)
        tip.cubicTo(-2.4, -8, 0, -11, 0, -11)
        tip.cubicTo(0, -11, 2.4, -8, 2.2, -4)
        tip.closeSubpath()
        p.drawPath(tip)
        p.restore()
    elif name == "px-erase":
        p.save()
        p.translate(12, 12)
        p.rotate(-45)
        p.setPen(_pen(QColor("#6b3a4a"), 1))
        p.setBrush(QColor("#f4a6b8"))
        p.drawRoundedRect(QRectF(-8, -4, 9, 8), 1.5, 1.5)
        p.setBrush(QColor("#d8dbe0"))
        p.drawRoundedRect(QRectF(1, -4, 7, 8), 1.5, 1.5)
        p.restore()
    elif name == "px-fill":
        p.save()
        p.translate(11, 12)
        p.rotate(-30)
        p.setPen(_pen(FG, 1.2))
        p.setBrush(QColor(FG.red(), FG.green(), FG.blue(), 60))
        p.drawRect(QRectF(-6, -5, 11, 11))
        p.restore()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#4a8fe7"))
        drop = QPainterPath()
        drop.moveTo(19, 12)
        drop.cubicTo(21.5, 16, 21.5, 19, 19, 19.5)
        drop.cubicTo(16.5, 19, 16.5, 16, 19, 12)
        p.drawPath(drop)
    elif name in ("px-blur", "px-dodge", "px-burn"):
        if name == "px-blur":
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#4a8fe7"))
            drop = QPainterPath()
            drop.moveTo(12, 3)
            drop.cubicTo(18, 11, 19, 15, 16, 19)
            drop.cubicTo(13.5, 21.5, 10.5, 21.5, 8, 19)
            drop.cubicTo(5, 15, 6, 11, 12, 3)
            p.drawPath(drop)
        else:
            dark = name == "px-burn"
            p.setPen(_pen(QColor("#9aa1ab"), 2))
            line(12, 12, 12, 21)
            p.setBrush(QColor("#3a3a3a") if dark else QColor("#f2f2f2"))
            p.setPen(_pen(QColor("#9aa1ab"), 1))
            p.drawEllipse(QPointF(12, 8), 5, 5)
    elif name == "slice":
        p.setPen(_pen(QColor("#b38cff"), 1.3))
        pen = _pen(QColor("#b38cff"), 1.3)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.drawRect(QRectF(3, 3, 13, 13))
        p.setPen(_pen(QColor("#d8dbe0"), 1.4))
        p.setBrush(QColor("#d8dbe0"))
        p.drawPolygon(_poly((10, 21), (21, 10), (19, 8), (8, 19)))
    elif name == "slice-select":
        pen = _pen(QColor("#b38cff"), 1.2)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.drawRect(QRectF(9, 9, 12, 12))
        p.setPen(_pen())
        p.setBrush(FG)
        p.drawPolygon(_poly((4, 3), (4, 15), (7, 12), (9, 17), (11, 16), (9, 11), (13, 11)))
    elif name == "pencil":
        p.save()
        p.translate(12, 12)
        p.rotate(-45)
        p.setPen(_pen(QColor("#5b4a2a"), 1))
        p.setBrush(QColor("#f2c94c"))
        p.drawRect(QRectF(-6, -2.6, 11, 5.2))
        p.setBrush(QColor("#f28b82"))
        p.drawRect(QRectF(5, -2.6, 3.4, 5.2))
        p.setBrush(QColor("#e8c39e"))
        p.drawPolygon(_poly((-6, -2.6), (-6, 2.6), (-10.5, 0)))
        p.setBrush(QColor("#333333"))
        p.drawPolygon(_poly((-9, -0.9), (-9, 0.9), (-10.5, 0)))
        p.restore()
    elif name == "fill":
        grad = QLinearGradient(4, 4, 20, 20)
        grad.setColorAt(0, QColor("#2f6fe0"))
        grad.setColorAt(1, QColor("#e9f1ff"))
        p.setBrush(QBrush(grad))
        p.setPen(_pen(DIM, 1))
        p.drawRoundedRect(QRectF(3.5, 3.5, 17, 17), 2.5, 2.5)
        p.setPen(_pen(QColor("#ffffff"), 1.4))
        line(7, 7, 17, 17)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QPointF(7, 7), 1.8, 1.8)
        p.drawEllipse(QPointF(17, 17), 1.8, 1.8)
    elif name == "picker":
        p.save()
        p.translate(12, 12)
        p.rotate(45)
        p.setPen(_pen(QColor("#5c5c66"), 1))
        p.setBrush(QColor("#d8dbe0"))
        p.drawRect(QRectF(-1.6, -3, 3.2, 11))
        p.drawPolygon(_poly((-1.6, 8), (1.6, 8), (0, 11)))
        p.setBrush(QColor("#ff9800"))
        p.drawRoundedRect(QRectF(-3.2, -10.5, 6.4, 7), 2.5, 2.5)
        p.setBrush(QColor("#9aa1ab"))
        p.drawRect(QRectF(-4, -4, 8, 1.8))
        p.restore()
    elif name == "measure":
        p.save()
        p.translate(12, 12)
        p.rotate(-45)
        p.setPen(_pen(QColor("#6a4b00"), 1))
        p.setBrush(QColor("#f2b84b"))
        p.drawRect(QRectF(-10, -3.5, 20, 7))
        for k in range(-8, 9, 2):
            line(k, -3.5, k, -3.5 + (3 if k % 4 == 0 else 1.8))
        p.restore()
    elif name in ("rounded", "triangle", "diamond", "star", "polygon", "arrow-shape",
                  "heart-shape"):
        from .shapes import icon_path
        kind = {"arrow-shape": "arrow", "heart-shape": "heart"}.get(name, name)
        colour = {"star": QColor("#f2c94c"), "heart": QColor("#e0566b")}.get(
            kind, QColor(FG.red(), FG.green(), FG.blue(), 150))
        p.setBrush(colour)
        p.setPen(_pen(FG, 1.2))
        box = QRectF(3.5, 3.5, 17, 17) if kind != "arrow" else QRectF(3, 6, 18, 12)
        p.drawPath(icon_path(kind, box))
    elif name == "settings":
        p.setBrush(QColor(FG.red(), FG.green(), FG.blue(), 60))
        path = QPainterPath()
        import math as _m
        for k in range(16):
            r = 9.5 if k % 2 == 0 else 7
            a = _m.radians(k * 22.5)
            pt = QPointF(12 + r * _m.cos(a), 12 + r * _m.sin(a))
            if k == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
        path.closeSubpath()
        p.drawPath(path)
        p.setBrush(QColor("#e05555"))
        p.setPen(_pen(QColor("#e05555"), 1.2))
        p.drawEllipse(QPointF(12, 12), 3, 3)
    elif name in ("fit-page", "fit-selection", "actual-size"):
        p.setPen(_pen(ACCENT, 1.6))
        for (x, y, dx, dy) in ((3, 3, 1, 1), (21, 3, -1, 1), (3, 21, 1, -1), (21, 21, -1, -1)):
            line(x, y, x + 4 * dx, y)
            line(x, y, x, y + 4 * dy)
        p.setPen(_pen(FG, 1.2))
        if name == "fit-page":
            p.drawRect(QRectF(7, 6, 10, 12))
        elif name == "fit-selection":
            p.setBrush(QColor(FG.red(), FG.green(), FG.blue(), 90))
            p.drawRect(QRectF(8.5, 8.5, 7, 7))
        else:
            f = p.font()
            f.setPixelSize(8)
            f.setBold(True)
            p.setFont(f)
            p.drawText(QRectF(4, 4, 16, 16), Qt.AlignCenter, "1:1")
    elif name.startswith("geo-"):
        kind = name[4:]
        a, b = QPainterPath(), QPainterPath()
        a.addRect(QRectF(3, 3, 12, 12))
        b.addEllipse(QRectF(9, 9, 12, 12))
        fill = QColor("#3d8bfd")
        dim = QColor(FG.red(), FG.green(), FG.blue(), 40)
        p.setPen(Qt.NoPen)
        if kind == "add":
            p.fillPath(a.united(b), fill)
        elif kind == "subtract":
            p.fillPath(b, dim)
            p.fillPath(a.subtracted(b), fill)
        elif kind == "intersect":
            p.fillPath(a.united(b), dim)
            p.fillPath(a.intersected(b), fill)
        elif kind == "xor":
            p.fillPath(a.united(b).subtracted(a.intersected(b)), fill)
        else:
            p.fillPath(a.subtracted(b), fill)
            p.fillPath(a.intersected(b), QColor("#7fb3ff"))
            p.fillPath(b.subtracted(a), QColor("#2a62b8"))
        p.setPen(_pen(FG, 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(a)
        p.drawPath(b)
    elif name.startswith("insert-"):
        kind = name[7:]
        green = QColor("#38c172")
        p.setPen(_pen(FG, 1.2))
        if kind == "inside":
            p.drawRoundedRect(QRectF(3, 3, 18, 18), 3, 3)
            p.setBrush(green)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(8, 8, 8, 8))
        else:
            back, front = QRectF(3, 3, 12, 12), QRectF(9, 9, 12, 12)
            if kind == "behind":
                p.setBrush(green)
                p.drawRect(back)
                p.setBrush(QColor("#3a3a40"))
                p.drawRect(front)
            else:
                p.setBrush(QColor("#3a3a40"))
                p.drawRect(back)
                p.setBrush(green)
                p.drawRect(front)
    elif name == "help":
        p.drawEllipse(QRectF(3, 3, 18, 18))
        f = p.font()
        f.setPixelSize(13)
        f.setBold(True)
        p.setFont(f)
        p.setPen(_pen(ACCENT, 1))
        p.drawText(QRectF(3, 3, 18, 18), Qt.AlignCenter, "?")
    elif name == "artistic-text":
        pen = _pen(DIM, 1)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.drawRect(QRectF(3, 3, 18, 18))
        f = p.font()
        f.setPixelSize(15)
        f.setBold(True)
        p.setFont(f)
        p.setPen(_pen(FG, 1))
        p.drawText(QRectF(3, 2.5, 18, 18), Qt.AlignCenter, "A")
    elif name == "eyedropper":
        p.drawPolygon(_poly((14.5, 6.5), (17.5, 9.5), (8, 19), (5, 20), (5, 19), (6, 16)))
        p.setBrush(FG)
        p.drawPolygon(_poly((13, 5), (16, 2.5), (21.5, 8), (19, 11)))
    elif name.startswith("stroke-"):
        kind = name[7:]
        if kind == "none":
            p.drawEllipse(QRectF(5, 5, 14, 14))
            p.setPen(_pen(QColor("#e05555"), 1.8))
            line(6.5, 17.5, 17.5, 6.5)
        elif kind in ("solid", "dash", "dot", "dashdot"):
            pen = _pen(FG, 2.4 if kind != "dot" else 2.6)
            pen.setStyle({"solid": Qt.SolidLine, "dash": Qt.DashLine, "dot": Qt.DotLine,
                          "dashdot": Qt.DashDotLine}[kind])
            pen.setCapStyle(Qt.RoundCap if kind == "dot" else Qt.FlatCap)
            p.setPen(pen)
            line(3, 12, 21, 12)
        else:   # centre, inside, outside: where the outline sits on the edge
            p.setPen(_pen(DIM, 1))
            p.setBrush(QColor(FG.red(), FG.green(), FG.blue(), 40))
            p.drawRect(QRectF(6, 6, 12, 12))
            p.setBrush(Qt.NoBrush)
            p.setPen(_pen(ACCENT, 2.6))
            grow = {"center": 0, "inside": -1.8, "outside": 1.8}.get(kind, 0)
            p.drawRect(QRectF(6 - grow, 6 - grow, 12 + 2 * grow, 12 + 2 * grow))
    elif name.startswith("cap-"):
        pen = _pen(FG, 6)
        pen.setCapStyle({"cap-butt": Qt.FlatCap, "cap-round": Qt.RoundCap,
                         "cap-square": Qt.SquareCap}[name])
        p.setPen(pen)
        line(4, 12, 14, 12)
        p.setPen(_pen(ACCENT, 1))
        line(14, 6, 14, 18)
    elif name.startswith("join-"):
        pen = _pen(FG, 5)
        pen.setJoinStyle({"join-miter": Qt.MiterJoin, "join-round": Qt.RoundJoin,
                          "join-bevel": Qt.BevelJoin}[name])
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)
        p.drawPolyline(_poly((5, 20), (5, 6), (20, 6)))
    elif name in ("zoom-in", "zoom-out"):
        p.drawEllipse(QPointF(10, 10), 6, 6)
        line(14.6, 14.6, 20, 20)
        line(7, 10, 13, 10)
        if name == "zoom-in":
            line(10, 7, 10, 13)
    elif name in ("heart", "heart-on"):
        path = QPainterPath()
        path.moveTo(12, 20)
        path.cubicTo(4, 14.5, 2.5, 10.5, 4.2, 7.2)
        path.cubicTo(6, 4, 10.5, 4.2, 12, 7.6)
        path.cubicTo(13.5, 4.2, 18, 4, 19.8, 7.2)
        path.cubicTo(21.5, 10.5, 20, 14.5, 12, 20)
        if name == "heart-on":
            p.setBrush(QColor("#e0566b"))
            p.setPen(_pen(QColor("#e0566b"), 1.4))
        p.drawPath(path)
    elif name in ("portrait", "landscape"):
        r = QRectF(7, 3, 11, 18) if name == "portrait" else QRectF(3, 6.5, 18, 11)
        fold = 4
        p.drawPolygon(_poly((r.left(), r.top()), (r.right() - fold, r.top()),
                            (r.right(), r.top() + fold), (r.right(), r.bottom()),
                            (r.left(), r.bottom())))
        p.drawPolyline(_poly((r.right() - fold, r.top()), (r.right() - fold, r.top() + fold),
                             (r.right(), r.top() + fold)))
    elif name == "swap":
        p.drawPolyline(_poly((5, 9), (19, 9)))
        p.drawPolyline(_poly((15, 5), (19, 9), (15, 13)))
        p.drawPolyline(_poly((19, 15), (5, 15)))
        p.drawPolyline(_poly((9, 11), (5, 15), (9, 19)))
    elif name == "save-preset":
        p.drawRoundedRect(QRectF(4, 4, 16, 16), 2, 2)
        p.setPen(_pen(ACCENT, 2))
        line(12, 8, 12, 16)
        line(8, 12, 16, 12)
    elif name == "plus":
        p.setPen(_pen(FG, 2.2))
        line(12, 5, 12, 19)
        line(5, 12, 19, 12)
    elif name == "style":
        p.setBrush(QColor("#e8b04a"))
        p.drawEllipse(QRectF(3, 3, 11, 11))
        p.setBrush(ACCENT)
        p.drawRoundedRect(QRectF(10, 10, 11, 11), 2, 2)
    elif name == "history":
        p.drawEllipse(QRectF(4, 4, 16, 16))
        line(12, 12, 12, 7.5)
        line(12, 12, 15.5, 14)
    elif name == "paste-inside":
        p.drawEllipse(QRectF(3, 3, 18, 18))
        p.save()
        clip = QPainterPath()
        clip.addEllipse(QRectF(3.8, 3.8, 16.4, 16.4))
        p.setClipPath(clip)
        p.setPen(_pen(ACCENT, 1.4))
        p.drawPolyline(_poly((2, 18), (9, 10.5), (13, 14.5), (16, 11.5), (22, 17)))
        p.restore()
    else:
        p.drawRect(QRectF(4, 4, 16, 16))


@lru_cache(maxsize=None)
def icon(name):
    ic = QIcon()
    for size in (24, 48):
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(size / 24.0, size / 24.0)
        _draw(name, p)
        p.end()
        ic.addPixmap(pix)
        # A faded copy for when the button cannot be used right now.
        faded = QPixmap(size, size)
        faded.fill(Qt.transparent)
        p = QPainter(faded)
        p.setOpacity(0.28)
        p.drawPixmap(0, 0, pix)
        p.end()
        ic.addPixmap(faded, QIcon.Disabled)
    return ic


def _slant(points, k=0.20, base=206.0):
    """Lean shapes to the right, like italic type."""
    return QPolygonF([QPointF(x + (base - y) * k, y) for x, y in points])


def _tile_gradient(x0, y0, x1, y1):
    bg = QLinearGradient(x0, y0, x1, y1)
    bg.setColorAt(0.0, QColor("#23695f"))
    bg.setColorAt(0.5, QColor("#154a6e"))
    bg.setColorAt(1.0, QColor("#0a1b45"))
    return QBrush(bg)


FACET_COLOURS = (("#2a5bd7", "#64c4ff"),    # upright stroke
                 ("#72e6ff", "#3a7ff0"),    # top arm
                 ("#80f8c8", "#3fb6ee"))    # middle arm
OUTLINE = QColor("#05102c")


def _app_pixmap_small(size):
    """16 and 24 pixel icons: an upright F lined up with the pixel grid."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    tile = QPainterPath()
    tile.addRoundedRect(QRectF(0, 0, size, size), size * 0.2, size * 0.2)
    p.fillPath(tile, _tile_gradient(0, 0, size, size))
    p.setRenderHint(QPainter.Antialiasing, False)
    u = size / 16.0
    sx, sy = round(4 * u), round(3 * u)
    sw, sh = max(2, round(3 * u)), size - 2 * round(3 * u)
    gap = 1
    aw = max(2, round(2.5 * u))
    stem = QRectF(sx, sy, sw, sh)
    top = QRectF(sx + sw + gap, sy, round(6 * u), aw)
    mid = QRectF(sx + sw + gap, sy + round(4.5 * u), round(4 * u), aw)
    for rect, (c1, c2) in zip((stem, top, mid), FACET_COLOURS):
        grad = QLinearGradient(rect.bottomLeft(), rect.topRight())
        grad.setColorAt(0, QColor(c1))
        grad.setColorAt(1, QColor(c2))
        p.fillRect(rect, QBrush(grad))
    p.end()
    return pix


def app_pixmap(size=256):
    """The Folio app icon: a faceted, leaning letter F on a teal-to-navy tile."""
    if size <= 24:
        return _app_pixmap_small(size)
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 256.0, size / 256.0)
    p.setPen(Qt.NoPen)

    tile = QPainterPath()
    tile.addRoundedRect(QRectF(6, 6, 244, 244), 46, 46)
    p.fillPath(tile, _tile_gradient(30, 6, 226, 250))
    p.save()
    p.setClipPath(tile)
    p.setBrush(QColor(255, 255, 255, 22))
    p.drawPolygon(_poly((92, 262), (172, 262), (300, -12), (220, -12)))
    p.setBrush(QColor(255, 255, 255, 11))
    p.drawPolygon(_poly((-34, 262), (36, 262), (146, -12), (76, -12)))
    p.setBrush(QColor(2, 10, 32, 80))
    p.drawPolygon(_poly((-20, 170), (276, 140), (276, 270), (-20, 270)))
    p.restore()

    # The F: an upright stroke and two arms with sharp, angled ends.
    stem = _slant([(54, 206), (96, 206), (96, 50), (54, 50)])
    top = _slant([(104, 50), (176, 50), (160, 92), (104, 92)])
    mid = _slant([(104, 112), (160, 112), (148, 148), (104, 148)])
    ends = [((54, 206), (102, 50)), ((120, 92), (190, 50)), ((112, 148), (165, 112))]

    # A dark edge round every piece keeps the shapes crisp at any size.
    edge = QPen(OUTLINE, 9)
    edge.setJoinStyle(Qt.MiterJoin)
    p.setPen(edge)
    p.setBrush(OUTLINE)
    for poly in (stem, top, mid):
        p.drawPolygon(poly)
    p.setPen(Qt.NoPen)
    for poly, ((ax, ay), (bx, by)), (c1, c2) in zip((stem, top, mid), ends, FACET_COLOURS):
        grad = QLinearGradient(ax, ay, bx, by)
        grad.setColorAt(0, QColor(c1))
        grad.setColorAt(1, QColor(c2))
        p.setBrush(QBrush(grad))
        p.drawPolygon(poly)
        # a thin bright line along the top edge, like light catching it
        shine = QPen(QColor(255, 255, 255, 150), 2.4)
        shine.setCapStyle(Qt.FlatCap)
        p.setPen(shine)
        if poly is stem:
            p.drawLine(poly[3], poly[2])
        else:
            p.drawLine(poly[0], poly[1])
        p.setPen(Qt.NoPen)

    p.setPen(QPen(QColor(255, 255, 255, 26), 1.5))
    p.setBrush(Qt.NoBrush)
    p.drawPath(tile)
    p.end()
    return pix


def app_icon():
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(app_pixmap(s))
    return ic


def save_app_icons(hicolor_dir):
    """Write the app icon into an icon theme folder (used by install.sh)."""
    import os
    for size in (16, 24, 32, 48, 64, 128, 256):
        folder = os.path.join(hicolor_dir, f"{size}x{size}", "apps")
        os.makedirs(folder, exist_ok=True)
        app_pixmap(size).save(os.path.join(folder, "folio.png"))
        mime_folder = os.path.join(hicolor_dir, f"{size}x{size}", "mimetypes")
        os.makedirs(mime_folder, exist_ok=True)
        app_pixmap(size).save(os.path.join(mime_folder, "application-x-folio.png"))
