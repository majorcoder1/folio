"""Exporting to PDF, PNG and JPEG."""

import math
import re
from contextlib import contextmanager

from PyQt5.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PyQt5.QtGui import (QColor, QColorSpace, QImage, QPageLayout, QPageSize, QPainter,
                         QPdfWriter)

from .items import RENDER

MAX_PIXELS = 300_000_000


class ExportError(Exception):
    pass


@contextmanager
def export_mode(scene, outline_text=False):
    scene.exporting = True
    RENDER["export"] = True
    RENDER["outline_text"] = outline_text
    try:
        yield
    finally:
        scene.exporting = False
        RENDER["export"] = False
        RENDER["outline_text"] = False
        scene.assets.release_full()


def region_rect(scene, area, rect=None):
    if rect:
        return QRectF(*rect)
    regs = scene.doc.regions()
    return QRectF(regs.get(area, regs["page"]))


def render_image(scene, region, scale, transparent=False, smooth=True, matte=None):
    w = max(1, int(round(region.width() * scale)))
    h = max(1, int(round(region.height() * scale)))
    if w * h > MAX_PIXELS:
        raise ExportError("That is too many pixels to export. Choose a lower resolution.")
    image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    if image.isNull():
        raise ExportError("Not enough memory for an image this big. "
                          "Choose a lower resolution.")
    image.fill(QColor(matte) if matte else Qt.transparent if transparent else Qt.white)
    p = QPainter(image)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform, smooth)
    scene.render(p, QRectF(0, 0, w, h), region, Qt.IgnoreAspectRatio)
    p.end()
    return image


def export_image(scene, opts, path):
    fmt = opts["format"]
    dpi = float(opts.get("dpi", scene.doc.dpi))
    region = region_rect(scene, opts.get("area", "page"), opts.get("rect"))
    transparent = fmt == "png" and not scene.doc.background
    matte = opts.get("matte") or None
    with export_mode(scene):
        image = render_image(scene, region, dpi / scene.doc.dpi, transparent,
                             smooth=opts.get("resample", "bilinear") != "nearest", matte=matte)
    dpm = int(round(dpi / 0.0254))
    image.setDotsPerMeterX(dpm)
    image.setDotsPerMeterY(dpm)
    if fmt == "jpeg":
        flat = QImage(image.size(), QImage.Format_RGB32)
        flat.fill(QColor(matte) if matte else Qt.white)
        p = QPainter(flat)
        p.drawImage(0, 0, image)
        p.end()
        flat.setDotsPerMeterX(dpm)
        flat.setDotsPerMeterY(dpm)
        ok = finish(flat, opts).save(path, "JPEG", int(opts.get("quality", 92)))
    else:
        ok = finish(image, opts).save(path, "PNG")
    if not ok:
        raise ExportError("The file could not be written. Check the folder and try again.")


def finish(image, opts):
    """Pixel format and colour profile, as chosen in Export Options."""
    if opts.get("pixel_format") == "grey":
        dpm_x, dpm_y = image.dotsPerMeterX(), image.dotsPerMeterY()
        image = image.convertToFormat(QImage.Format_Grayscale8)
        image.setDotsPerMeterX(dpm_x)
        image.setDotsPerMeterY(dpm_y)
    elif opts.get("icc", True):
        image.setColorSpace(QColorSpace(QColorSpace.SRgb))
    return image


def export_pdf(scene, opts, path):
    doc = scene.doc
    area = opts.get("area", "page")
    region = region_rect(scene, area, opts.get("rect"))
    w_pt = region.width() / doc.dpi * 72.0
    h_pt = region.height() / doc.dpi * 72.0
    # Qt rounds page sizes to whole points, so ask for a page a little
    # bigger, draw at the exact size, then set the exact page box afterwards.
    page_w, page_h = math.ceil(w_pt - 1e-6), math.ceil(h_pt - 1e-6)
    writer = QPdfWriter(path)
    res = int(round(doc.dpi))
    writer.setResolution(res)
    layout = QPageLayout(QPageSize(QSizeF(page_w, page_h), QPageSize.Point, "Folio",
                                   QPageSize.ExactMatch),
                         QPageLayout.Portrait, QMarginsF(0, 0, 0, 0), QPageLayout.Point)
    writer.setPageLayout(layout)
    writer.setTitle(doc.title or "Folio document")
    writer.setCreator("Folio")
    target = QRectF(0, 0, w_pt / 72.0 * res, h_pt / 72.0 * res)
    with export_mode(scene, outline_text=bool(opts.get("outline_text", True))):
        p = QPainter()
        if not p.begin(writer):
            raise ExportError("The PDF could not be started. Check the folder and try again.")
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform
                         | QPainter.TextAntialiasing)
        if uses_blending(scene):
            # PDF cannot blend layers, so the page goes in as a sharp picture.
            image = render_image(scene, region, 1.0)
            p.drawImage(target, image)
        else:
            scene.render(p, target, region, Qt.IgnoreAspectRatio)
        p.end()
    bleed_pt = doc.bleed / doc.dpi * 72.0 if area == "page" else 0.0
    set_page_boxes(path, w_pt, h_pt, bleed_pt)


def uses_blending(scene):
    return any(getattr(i, "blend", "normal") != "normal" and i.isVisible()
               for i in scene.folio_items())


def _box(x0, y0, x1, y1):
    return f"[{x0:.4f} {y0:.4f} {x1:.4f} {y1:.4f}]"


def set_page_boxes(path, w_pt, h_pt, bleed_pt):
    """Give the PDF page its exact size, plus trim and bleed boxes.

    The page Qt wrote is whole points; our drawing starts at its top-left
    corner, so the exact page is the top-left w x h of it.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    m = re.search(rb"/MediaBox \[0 0 ([0-9.]+) ([0-9.]+)\]", data)
    if not m:
        return
    page_h = float(m.group(2))
    low = page_h - h_pt
    b = bleed_pt
    new = ("/MediaBox " + _box(0, low, w_pt, page_h)
           + "\n/BleedBox " + _box(0, low, w_pt, page_h)
           + "\n/TrimBox " + _box(b, low + b, w_pt - b, page_h - b)).encode("ascii")
    start, end = m.start(), m.end()
    delta = len(new) - (end - start)
    data = data[:start] + new + data[end:]
    xref_at = data.rfind(b"\nxref\n")
    if xref_at < 0:
        raise ExportError("The PDF was written in an unexpected way.")
    xref_at += 1
    head = re.match(rb"xref\n(\d+) (\d+)\n", data[xref_at:])
    count = int(head.group(2))
    pos = xref_at + head.end()
    entries = bytearray(data[pos:pos + 20 * count])
    for i in range(count):
        line = entries[i * 20:(i + 1) * 20]
        offset = int(line[:10])
        if line[17:18] == b"n" and offset > start:
            entries[i * 20:i * 20 + 10] = b"%010d" % (offset + delta)
    data = data[:pos] + bytes(entries) + data[pos + 20 * count:]
    sm = re.search(rb"startxref\n(\d+)", data[pos:])
    s_at = pos + sm.start(1)
    s_end = pos + sm.end(1)
    data = data[:s_at] + str(xref_at).encode("ascii") + data[s_end:]
    with open(path, "wb") as fh:
        fh.write(data)


def export(scene, opts, path):
    if opts["format"] == "pdf":
        export_pdf(scene, opts, path)
    else:
        export_image(scene, opts, path)


def thumbnail_png(scene, size=512):
    """A small PNG of the page, stored inside saved files."""
    from PyQt5.QtCore import QBuffer, QByteArray, QIODevice
    page = scene.doc.page_rect()
    scale = size / max(page.width(), page.height())
    scene.exporting = True
    try:
        image = render_image(scene, page, scale, transparent=not scene.doc.background)
    finally:
        scene.exporting = False
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    image.save(buf, "PNG")
    buf.close()
    return bytes(ba)
