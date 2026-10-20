"""The document: page settings, objects, groups and placed images."""

import copy

from PyQt5.QtCore import QRectF, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QPainter, QPixmap
from PyQt5.QtWidgets import QGraphicsScene

from .assets import AssetStore
from .document import DocSettings
from .items import FolioItem, item_from_dict, new_uid

PASTEBOARD = QColor("#252525")


def checker_brush():
    pix = QPixmap(32, 32)
    pix.fill(QColor("#ffffff"))
    p = QPainter(pix)
    p.fillRect(0, 0, 16, 16, QColor("#d9d9d9"))
    p.fillRect(16, 16, 16, 16, QColor("#d9d9d9"))
    p.end()
    return QBrush(pix)


class DocScene(QGraphicsScene):
    docChanged = pyqtSignal()        # page size or guides changed
    contentChanged = pyqtSignal()    # objects added, removed or rebuilt

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.doc = settings or DocSettings()
        self.assets = AssetStore()
        self.groups = {}             # group id -> name
        from .slices import default_slices
        self.slices = default_slices(self.doc)    # areas to export (Export persona)
        self.guides = {"x": [], "y": []}          # guides dragged out of the rulers
        self.exporting = False
        self._checker = checker_brush()
        self.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.update_scene_rect()

    # ---- page ----------------------------------------------------------------

    def update_scene_rect(self):
        page = self.doc.page_rect()
        pad = max(page.width(), page.height()) * 0.8
        self.setSceneRect(page.adjusted(-pad, -pad, pad, pad))

    def set_settings(self, settings):
        self.doc = settings
        self.update_scene_rect()
        self.update()
        self.docChanged.emit()

    def regions(self):
        return self.doc.regions()

    def drawBackground(self, painter, rect):
        page = self.doc.page_rect()
        if not self.exporting:
            painter.fillRect(rect, PASTEBOARD)
            # a soft edge so the page lifts off the pasteboard
            for i, alpha in enumerate((60, 35, 18)):
                d = (i + 1) * 0.004 * max(page.width(), page.height())
                painter.fillRect(page.translated(d * 0.5, d), QColor(0, 0, 0, alpha))
        bg = self.doc.background
        if bg:
            painter.fillRect(page, QColor(bg))
        elif not self.exporting:
            painter.fillRect(page, self._checker)

    # ---- objects -------------------------------------------------------------

    def folio_items(self):
        """All objects, bottom to top."""
        found = [i for i in self.items() if isinstance(i, FolioItem)]
        found.sort(key=lambda i: i.zValue())
        return found

    def find(self, uid):
        for item in self.items():
            if isinstance(item, FolioItem) and item.uid == uid:
                return item
        return None

    def next_z(self):
        found = self.folio_items()
        return found[-1].zValue() + 1 if found else 0.0

    def add_folio_item(self, item, z=None):
        item.setZValue(self.next_z() if z is None else z)
        self.addItem(item)
        self.contentChanged.emit()
        return item

    def remove_folio_items(self, victims):
        for item in victims:
            self.removeItem(item)
        self.prune_groups()
        self.normalize_z()
        self.contentChanged.emit()

    def set_order(self, ordered):
        """Restack objects; ``ordered`` runs bottom to top."""
        for z, item in enumerate(ordered):
            item.setZValue(float(z))
        self.contentChanged.emit()

    def normalize_z(self):
        for z, item in enumerate(self.folio_items()):
            item.setZValue(float(z))

    def selected_folio(self):
        found = [i for i in self.selectedItems() if isinstance(i, FolioItem)]
        found.sort(key=lambda i: i.zValue())
        return found

    def select_only(self, chosen):
        chosen = set(chosen)
        self.blockSignals(True)
        for item in self.folio_items():
            item.setSelected(item in chosen)
        self.blockSignals(False)
        self.selectionChanged.emit()

    # ---- groups --------------------------------------------------------------

    def group_members(self, gid):
        return [i for i in self.folio_items() if i.group == gid]

    def unit_of(self, item):
        """The object, or every object in its group."""
        if item.group:
            return self.group_members(item.group)
        return [item]

    def prune_groups(self):
        used = {i.group for i in self.folio_items() if i.group}
        for gid in list(self.groups):
            if gid not in used:
                del self.groups[gid]
        for item in self.folio_items():
            if item.group and item.group not in self.groups:
                self.groups[item.group] = "Group"

    def new_group(self, name="Group"):
        gid = new_uid()
        self.groups[gid] = name
        return gid

    # ---- snapshots (undo, clipboard, saving) ---------------------------------

    def snapshot(self):
        return {
            "doc": self.doc.to_dict(),
            "items": [i.to_dict() for i in self.folio_items()],
            "groups": dict(self.groups),
            "slices": copy.deepcopy(self.slices),
            "guides": copy.deepcopy(self.guides),
        }

    def restore(self, snap, selected_uids=()):
        """Rebuild the page from a snapshot."""
        settings = DocSettings.from_dict(snap["doc"])
        if settings != self.doc:
            self.doc = settings
            self.update_scene_rect()
            self.docChanged.emit()
        self.blockSignals(True)
        for item in self.folio_items():
            self.removeItem(item)
        self.groups = dict(snap.get("groups", {}))
        from .slices import default_slices
        self.slices = copy.deepcopy(snap.get("slices") or default_slices(self.doc))
        self.guides = copy.deepcopy(snap.get("guides") or {"x": [], "y": []})
        wanted = set(selected_uids)
        for z, data in enumerate(snap["items"]):
            item = item_from_dict(copy.deepcopy(data), self.assets)
            if item is None:
                continue
            item.setZValue(float(z))
            self.addItem(item)
            if item.uid in wanted:
                item.setSelected(True)
        self.blockSignals(False)
        self.update()
        self.contentChanged.emit()
        self.selectionChanged.emit()

    def items_rect(self, chosen):
        rect = QRectF()
        for item in chosen:
            rect = rect.united(item.scene_bounds())
        return rect
