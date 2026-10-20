"""Image files placed in a document.

The original file bytes are kept, so saving never re-compresses a photo.
On screen Folio draws a smaller preview; exports use the full image.
"""

import hashlib
import uuid

from PyQt5.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt
from PyQt5.QtGui import QImage, QImageIOHandler, QImageReader, QPixmap

PREVIEW_MAX = 2048


class AssetStore:
    def __init__(self):
        self.data = {}      # id -> bytes
        self.ext = {}       # id -> file extension
        self.names = {}     # id -> original file name
        self._size = {}
        self._preview = {}
        self._levels = {}
        self._full = {}
        self.live = {}      # id -> QImage being painted on (pixel layers)
        self.dirty = set()  # live ids whose saved bytes are out of date

    def add(self, data, ext, name="", aid=None):
        """Add a picture's file bytes. ``aid`` keeps the id a saved file used
        (painted layers have their own kind of id)."""
        aid = aid or hashlib.sha1(data).hexdigest()[:16]
        if aid not in self.data:
            self.data[aid] = bytes(data)
            self.ext[aid] = (ext or "png").lower().lstrip(".")
            self.names[aid] = name
        return aid

    def add_qimage(self, image, name="pasted image"):
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        image.save(buf, "PNG")
        buf.close()
        return self.add(bytes(ba), "png", name)

    def has(self, aid):
        return aid in self.data

    # ---- pixel layers: pictures that can be painted on --------------------

    def new_live(self, image, name="Pixel"):
        """Add an editable picture; returns its id."""
        aid = "px" + uuid.uuid4().hex[:14]
        self.live[aid] = image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        self.data[aid] = b""
        self.ext[aid] = "png"
        self.names[aid] = name
        self.dirty.add(aid)
        return aid

    def live_copy(self, aid):
        """An editable copy of a picture, so painting never changes the original."""
        image = self.live[aid].copy() if aid in self.live else self.full(aid, keep=False)
        return self.new_live(image, self.names.get(aid, "Pixel"))

    def is_live(self, aid):
        return aid in self.live

    def touched(self, aid):
        """The pixels of a live picture changed: forget old previews."""
        self.dirty.add(aid)
        self._preview.pop(aid, None)
        self._levels.pop(aid, None)
        self._full.pop(aid, None)

    def bytes_of(self, aid):
        """The picture's file bytes (a live picture is saved as PNG first)."""
        if aid in self.live and (aid in self.dirty or not self.data.get(aid)):
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QIODevice.WriteOnly)
            self.live[aid].save(buf, "PNG")
            buf.close()
            self.data[aid] = bytes(ba)
            self.ext[aid] = "png"
            self.dirty.discard(aid)
        return self.data[aid]

    def flush(self):
        for aid in list(self.dirty):
            if aid in self.live:
                self.bytes_of(aid)

    def _reader(self, aid):
        buf = QBuffer()
        buf.setData(QByteArray(self.data[aid]))
        buf.open(QIODevice.ReadOnly)
        reader = QImageReader(buf)
        reader.setAutoTransform(True)
        return reader, buf

    def size(self, aid):
        """Pixel size of the full image, after EXIF rotation."""
        if aid in self.live:
            return self.live[aid].size()
        if aid not in self._size:
            if aid not in self.data:
                return QSize(1, 1)
            reader, buf = self._reader(aid)
            size = reader.size()
            if reader.transformation() & QImageIOHandler.TransformationRotate90:
                size = size.transposed()
            buf.close()
            if not size.isValid() or size.isEmpty():
                image = self.full(aid, keep=False)
                size = image.size() if not image.isNull() else QSize(1, 1)
            self._size[aid] = size
        return self._size[aid]

    def preview(self, aid):
        """A screen-sized pixmap, cached."""
        pix = self._preview.get(aid)
        if pix is None and aid in self.live:
            pix = QPixmap.fromImage(self.live[aid])
            self._preview[aid] = pix
        if pix is None:
            if aid not in self.data:
                return QPixmap()
            reader, buf = self._reader(aid)
            stored = reader.size()
            if stored.isValid() and max(stored.width(), stored.height()) > PREVIEW_MAX:
                reader.setScaledSize(stored.scaled(PREVIEW_MAX, PREVIEW_MAX,
                                                   Qt.KeepAspectRatio))
            image = reader.read()
            buf.close()
            pix = QPixmap.fromImage(image) if not image.isNull() else QPixmap()
            self._preview[aid] = pix
        return pix

    def preview_for(self, aid, needed):
        """The smallest cached preview that is at least ``needed`` pixels across.

        Drawing a big photo shrunk down looks grainy, so smaller copies are
        made once and reused while zoomed out.
        """
        levels = self._levels.get(aid)
        if levels is None:
            base = self.preview(aid)
            levels = [base]
            cur = base
            while not cur.isNull() and max(cur.width(), cur.height()) > 256:
                cur = cur.scaled(max(1, cur.width() // 2), max(1, cur.height() // 2),
                                 Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                levels.append(cur)
            self._levels[aid] = levels
        for pix in reversed(levels):
            if max(pix.width(), pix.height()) >= needed:
                return pix
        return levels[0]

    def full(self, aid, keep=True):
        """The full-resolution image. ``keep`` caches it (used while exporting)."""
        if aid in self.live:
            return self.live[aid]
        image = self._full.get(aid)
        if image is not None:
            return image
        if aid not in self.data:
            return QImage()
        reader, buf = self._reader(aid)
        image = reader.read()
        buf.close()
        if image.isNull():
            image = QImage()
        if keep:
            self._full[aid] = image
        return image

    def release_full(self):
        """Free full-resolution images after an export."""
        self._full.clear()

    def is_valid_image(self, aid):
        return not self.preview(aid).isNull()
