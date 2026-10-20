"""The start-up screen shown while Folio loads."""

import time

from PyQt5.QtCore import (QEasingCurve, QEventLoop, QPointF,
                          QPropertyAnimation, QRectF, Qt)
from PyQt5.QtGui import (QColor, QFont, QGuiApplication, QLinearGradient,
                         QPainter, QPainterPath, QPen, QPixmap,
                         QRadialGradient)
from PyQt5.QtWidgets import QApplication, QSplashScreen

from . import __version__
from .icons import app_pixmap

MAKER = "4ThePeople Media"
W, H = 640, 380
ACCENT = QColor("#4a8fe7")


def _font(size, bold=False, family=None):
    font = QFont(family) if family else QFont(QApplication.font())
    font.setPixelSize(size)
    font.setBold(bold)
    return font


def _card(dpr):
    """Everything that does not change while loading."""
    pix = QPixmap(int(W * dpr), int(H * dpr))
    pix.setDevicePixelRatio(dpr)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)

    card = QPainterPath()
    card.addRoundedRect(QRectF(0.5, 0.5, W - 1, H - 1), 18, 18)
    bg = QLinearGradient(0, 0, W, H)
    bg.setColorAt(0, QColor("#262b40"))
    bg.setColorAt(1, QColor("#131419"))
    p.fillPath(card, bg)
    glow = QRadialGradient(QPointF(W * 0.85, H * 0.05), W * 0.65)
    glow.setColorAt(0, QColor(74, 143, 231, 95))
    glow.setColorAt(1, QColor(74, 143, 231, 0))
    p.fillPath(card, glow)

    icon = app_pixmap(int(140 * dpr))
    p.drawPixmap(QRectF(44, 74, 140, 140), icon, QRectF(icon.rect()))

    p.setPen(QColor("#ffffff"))
    p.setFont(_font(84, True, "Noto Serif"))
    p.drawText(QRectF(206, 74, W - 230, 104), Qt.AlignLeft | Qt.AlignVCenter, "Folio")
    p.setPen(QColor("#aab3c2"))
    p.setFont(_font(22))
    p.drawText(QRectF(210, 176, W - 230, 32), Qt.AlignLeft | Qt.AlignVCenter,
               "Graphic design")

    # The maker's name, small, in the bottom-left corner.
    p.setFont(_font(11))
    p.setPen(QColor("#7d8796"))
    p.drawText(QRectF(22, H - 30, W - 44, 18), Qt.AlignLeft | Qt.AlignVCenter,
               f"Made by {MAKER}")

    p.setPen(QPen(QColor(255, 255, 255, 40), 1))
    p.setBrush(Qt.NoBrush)
    p.drawPath(card)
    p.end()
    return pix


class Splash(QSplashScreen):
    """Shows the name, the maker, and how far loading has got."""

    def __init__(self):
        screen = QGuiApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen is not None else 1.0
        super().__init__(_card(dpr))
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint
                            | Qt.WindowStaysOnTopHint)
        self.step_text = "Starting up…"
        self.progress = 0.0
        self.started = time.monotonic()
        self._fade = None

    def step(self, text, progress):
        self.step_text = text
        self.progress = max(0.0, min(1.0, progress))
        self.repaint()
        QApplication.processEvents()

    def drawContents(self, p):
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        track = QRectF(44, H - 100, W - 88, 5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 30))
        p.drawRoundedRect(track, 2.5, 2.5)
        done = QRectF(track)
        done.setWidth(max(track.height(), track.width() * self.progress))
        p.setBrush(ACCENT)
        p.drawRoundedRect(done, 2.5, 2.5)
        p.setFont(_font(15))
        p.setPen(QColor("#8f99a8"))
        row = QRectF(44, H - 88, W - 88, 30)
        p.drawText(row, Qt.AlignLeft | Qt.AlignVCenter, self.step_text)
        p.drawText(row, Qt.AlignRight | Qt.AlignVCenter, f"Version {__version__}")

    def mousePressEvent(self, e):
        pass   # stay up until loading is finished

    def wait(self, seconds):
        """Keep showing for at least ``seconds`` since it appeared."""
        while time.monotonic() - self.started < seconds:
            QApplication.processEvents(QEventLoop.AllEvents, 30)
            time.sleep(0.015)

    def fade_out(self, then=None):
        """Fade away (where the desktop allows it), then run ``then``."""
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(320)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.InQuad)

        def finished():
            self.close()
            if then is not None:
                then()

        anim.finished.connect(finished)
        self._fade = anim
        anim.start()
