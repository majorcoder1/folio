"""Dialogs: export, importing, settings and keyboard shortcuts, plus the
ready-made sizes the New Document window offers."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                             QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
                             QRadioButton, QSlider, QSpinBox, QTextBrowser,
                             QVBoxLayout, QWidget)

from . import units
from .numberbox import NumberBox
from .document import DocSettings

IN, MM, PX = "in", "mm", "px"

# A size preset: (title, width, height, unit, dpi, bleed, safe margin);
# bleed and margin are in the same unit as the size.
BOOK_PAGE_PRESETS = [
    (title, [(label, w, h, IN, 300, 0.125, 0.5) for label, w, h in entries])
    for title, entries in units.PAPERBACK_SIZE_GROUPS
]

EBOOK_PRESETS = [
    ("eBook cover sizes", [
        ("eBook cover  1600 x 2560 px  (most stores)", 1600, 2560, PX, 300, 0, 0),
        ("eBook cover  1600 x 2400 px", 1600, 2400, PX, 300, 0, 0),
        ("eBook cover  2000 x 3000 px  (extra sharp)", 2000, 3000, PX, 300, 0, 0),
        ("eBook cover  2560 x 4096 px  (extra sharp)", 2560, 4096, PX, 300, 0, 0),
        ("eBook cover, square  2400 x 2400 px", 2400, 2400, PX, 300, 0, 0),
    ]),
]

AUDIO_PRESETS = [
    ("Square covers", [
        ("Audiobook cover  3000 x 3000 px", 3000, 3000, PX, 300, 0, 0),
        ("Audiobook cover, smallest allowed  2400 x 2400 px", 2400, 2400, PX, 300, 0, 0),
        ("Podcast cover  3000 x 3000 px", 3000, 3000, PX, 300, 0, 0),
        ("Album or single cover  3000 x 3000 px", 3000, 3000, PX, 300, 0, 0),
    ]),
]

US_PAPER_PRESETS = [
    ("US paper sizes, smallest to largest", [
        ("Half letter  5.5 x 8.5 in", 5.5, 8.5, IN, 300, 0, 0.5),
        ("Executive  7.25 x 10.5 in", 7.25, 10.5, IN, 300, 0, 0.5),
        ("Letter  8.5 x 11 in  (most popular)", 8.5, 11, IN, 300, 0, 0.5),
        ("Legal  8.5 x 14 in", 8.5, 14, IN, 300, 0, 0.5),
        ("Tabloid  11 x 17 in", 11, 17, IN, 300, 0, 0.5),
    ]),
    ("Large US sizes (posters and plans)", [
        ("Arch A  9 x 12 in", 9, 12, IN, 300, 0, 0.5),
        ("Arch B  12 x 18 in", 12, 18, IN, 200, 0, 0.5),
        ("Arch C  18 x 24 in", 18, 24, IN, 150, 0, 0.75),
        ("Arch D  24 x 36 in", 24, 36, IN, 150, 0, 1),
    ]),
]

A4_PRESETS = [
    ("A sizes, largest to smallest", [
        ("A0  841 x 1189 mm", 841, 1189, MM, 150, 0, 20),
        ("A1  594 x 841 mm", 594, 841, MM, 150, 0, 20),
        ("A2  420 x 594 mm", 420, 594, MM, 200, 0, 15),
        ("A3  297 x 420 mm", 297, 420, MM, 300, 0, 12),
        ("A4  210 x 297 mm  (most popular)", 210, 297, MM, 300, 0, 12),
        ("A5  148 x 210 mm", 148, 210, MM, 300, 0, 12),
        ("A6  105 x 148 mm", 105, 148, MM, 300, 0, 10),
        ("A7  74 x 105 mm", 74, 105, MM, 300, 0, 6),
    ]),
    ("Other international sizes", [
        ("B4  250 x 353 mm", 250, 353, MM, 300, 0, 15),
        ("B5  176 x 250 mm", 176, 250, MM, 300, 0, 12),
        ("DL  99 x 210 mm  (one-third A4 flyer)", 99, 210, MM, 300, 0, 6),
    ]),
]

BANNER_PRESETS = [
    ("Website and social media banners", [
        ("Website banner  1920 x 1080 px  (most popular)", 1920, 1080, PX, 72, 0, 0),
        ("Website header  1920 x 600 px", 1920, 600, PX, 72, 0, 0),
        ("YouTube channel banner  2560 x 1440 px", 2560, 1440, PX, 72, 0, 0),
        ("Facebook page cover  1640 x 624 px", 1640, 624, PX, 72, 0, 0),
        ("Facebook event cover  1920 x 1005 px", 1920, 1005, PX, 72, 0, 0),
        ("X (Twitter) header  1500 x 500 px", 1500, 500, PX, 72, 0, 0),
        ("LinkedIn banner  1584 x 396 px", 1584, 396, PX, 72, 0, 0),
        ("Email header  600 x 200 px", 600, 200, PX, 72, 0, 0),
    ]),
    ("Printed banners", [
        ("Banner  2 x 6 feet", 72, 24, IN, 100, 0.5, 1),
        ("Banner  3 x 6 feet", 72, 36, IN, 100, 0.5, 1.5),
        ("Banner  3 x 8 feet", 96, 36, IN, 80, 0.5, 1.5),
        ("Banner  4 x 8 feet", 96, 48, IN, 75, 0.5, 2),
        ("Roll-up stand  33 x 81 in", 33, 81, IN, 100, 0.5, 1.5),
    ]),
]

PRINT_PRESETS = [
    ("Cards", [
        ("Business card  3.5 x 2 in", 3.5, 2, IN, 300, 0.125, 0.125),
        ("Business card (Europe)  85 x 55 mm", 85, 55, MM, 300, 3, 3),
        ("Postcard  6 x 4 in", 6, 4, IN, 300, 0.125, 0.25),
        ("Postcard, upright  4 x 6 in", 4, 6, IN, 300, 0.125, 0.25),
        ("Card or invitation  5 x 7 in", 5, 7, IN, 300, 0.125, 0.25),
        ("Large postcard  9 x 6 in", 9, 6, IN, 300, 0.125, 0.25),
    ]),
    ("For promoting your book", [
        ("Bookmark  2 x 6 in", 2, 6, IN, 300, 0.125, 0.125),
        ("Bookmark  2 x 8 in", 2, 8, IN, 300, 0.125, 0.125),
        ("Rack card  4 x 9 in", 4, 9, IN, 300, 0.125, 0.25),
        ("Sticker  3 x 3 in", 3, 3, IN, 300, 0.125, 0.125),
        ("CD or DVD insert  4.75 x 4.75 in", 4.75, 4.75, IN, 300, 0.125, 0.125),
    ]),
    ("Flyers and posters", [
        ("Flyer  8.5 x 11 in", 8.5, 11, IN, 300, 0.125, 0.25),
        ("Half-page flyer  5.5 x 8.5 in", 5.5, 8.5, IN, 300, 0.125, 0.25),
        ("Door hanger  4.25 x 11 in", 4.25, 11, IN, 300, 0.125, 0.25),
        ("Poster  11 x 17 in", 11, 17, IN, 300, 0.125, 0.5),
        ("Poster  18 x 24 in", 18, 24, IN, 150, 0.125, 0.5),
        ("Poster  24 x 36 in", 24, 36, IN, 150, 0.125, 0.75),
    ]),
]

SOCIAL_PRESETS = [
    ("Instagram and Facebook", [
        ("Square post  1080 x 1080", 1080, 1080, PX, 72, 0, 0),
        ("Portrait post  1080 x 1350", 1080, 1350, PX, 72, 0, 0),
        ("Story or Reel  1080 x 1920", 1080, 1920, PX, 72, 0, 0),
        ("Facebook post  1200 x 630", 1200, 630, PX, 72, 0, 0),
    ]),
    ("Other sites", [
        ("YouTube video thumbnail  1280 x 720", 1280, 720, PX, 72, 0, 0),
        ("Pinterest pin  1000 x 1500", 1000, 1500, PX, 72, 0, 0),
        ("X (Twitter) post  1600 x 900", 1600, 900, PX, 72, 0, 0),
        ("LinkedIn post  1200 x 627", 1200, 627, PX, 72, 0, 0),
        ("TikTok video cover  1080 x 1920", 1080, 1920, PX, 72, 0, 0),
    ]),
]

def _paper(bleed_mm, bleed_in):
    """The standard print sheets, with or without bleed (press ready)."""
    mm = [("A3", 297, 420), ("A4", 210, 297), ("A5", 148, 210), ("A6", 105, 148)]
    inch = [("Letter", 8.5, 11), ("Legal", 8.5, 14), ("Ledger", 11, 17)]
    b = [("B3", 353, 500), ("B4", 250, 353), ("B5", 176, 250)]
    out = [(f"{n}  {w} x {h} mm", w, h, MM, 300, bleed_mm, 0) for n, w, h in mm]
    out += [(f"{n}  {w:g} x {h:g} in", w, h, IN, 300, bleed_in, 0) for n, w, h in inch]
    out += [(f"{n}  {w} x {h} mm", w, h, MM, 300, bleed_mm, 0) for n, w, h in b]
    out.append(("Business Card  55 x 88 mm", 55, 88, MM, 300, bleed_mm, 0))
    return out


AFFINITY_PRINT = [("Standard sheets", _paper(0, 0))]
AFFINITY_PRESS = [("With 3 mm (0.125 in) bleed for the printer", _paper(3, 0.125))]
AFFINITY_PHOTO = [("Photo prints", [
    ("4R  4 x 6 in", 4, 6, IN, 300, 0, 0),
    ("4D  4.5 x 6 in", 4.5, 6, IN, 300, 0, 0),
    ("5R  5 x 7 in", 5, 7, IN, 300, 0, 0),
    ("6R  6 x 8 in", 6, 8, IN, 300, 0, 0),
    ("8R  8 x 10 in", 8, 10, IN, 300, 0, 0)])]
AFFINITY_WEB = [("Screens", [
    ("XGA  768 x 1024", 768, 1024, PX, 72, 0, 0),
    ("WXGA  800 x 1280", 800, 1280, PX, 72, 0, 0),
    ("WXGA+  900 x 1440", 900, 1440, PX, 72, 0, 0),
    ("FHD 1080p  1080 x 1920", 1080, 1920, PX, 72, 0, 0),
    ("WQHD  1440 x 2560", 1440, 2560, PX, 72, 0, 0),
    ("QFHD  2160 x 3840", 2160, 3840, PX, 72, 0, 0),
    ("Social Media Square Post  1080 x 1080", 1080, 1080, PX, 72, 0, 0),
    ("Social Media Story Post  1080 x 1920", 1080, 1920, PX, 72, 0, 0),
    ("Social Media Portrait Post  1080 x 1350", 1080, 1350, PX, 72, 0, 0)])]
AFFINITY_DEVICES = [("Tablets, phones and watches", [
    ("iPad Mini  768 x 1024 pt", 768, 1024, "pt", 72, 0, 0),
    ('iPad 9.7"  768 x 1024 pt', 768, 1024, "pt", 72, 0, 0),
    ('iPad 10.5"  834 x 1112 pt', 834, 1112, "pt", 72, 0, 0),
    ('iPad 11"  834 x 1194 pt', 834, 1194, "pt", 72, 0, 0),
    ('iPad 12.9"  1024 x 1366 pt', 1024, 1366, "pt", 72, 0, 0),
    ("iPhone 6/7/8  375 x 667 pt", 375, 667, "pt", 72, 0, 0),
    ("iPhone 6/7/8 Plus  414 x 736 pt", 414, 736, "pt", 72, 0, 0),
    ("iPhone X/XS  375 x 812 pt", 375, 812, "pt", 72, 0, 0),
    ("Apple Watch 38mm  136 x 170 pt", 136, 170, "pt", 72, 0, 0),
    ("Apple Watch 42mm  156 x 195 pt", 156, 195, "pt", 72, 0, 0),
    ("Android 1080p  1080 x 1920 px", 1080, 1920, PX, 72, 0, 0)])]
AFFINITY_ARCH = [("Architectural sheets", [
    ("Arch A  9 x 12 in", 9, 12, IN, 300, 0, 0),
    ("Arch B  12 x 18 in", 12, 18, IN, 200, 0, 0),
    ("Arch C  18 x 24 in", 18, 24, IN, 150, 0, 0),
    ("Arch D  24 x 36 in", 24, 36, IN, 150, 0, 0),
    ("Arch E  36 x 48 in", 36, 48, IN, 100, 0, 0),
    ("Arch E1  30 x 42 in", 30, 42, IN, 100, 0, 0)])]

# The list on the left of New Document: (title, form, extra, icon).
CATEGORIES = [
    ("Paperback book cover", "cover", "paperback", "cover"),
    ("Hardcover book cover", "cover", "hardcover", "cover"),
    ("eBook cover", "page", EBOOK_PRESETS, "image"),
    ("Audiobook and podcast cover", "page", AUDIO_PRESETS, "image"),
    ("Book page (inside the book)", "page", BOOK_PAGE_PRESETS, "new"),
    ("Print", "page", AFFINITY_PRINT, "new"),
    ("Press Ready", "page", AFFINITY_PRESS, "new"),
    ("Photo", "page", AFFINITY_PHOTO, "image"),
    ("Web", "page", AFFINITY_WEB, "image"),
    ("Devices", "page", AFFINITY_DEVICES, "image"),
    ("Architectural", "page", AFFINITY_ARCH, "new"),
    ("US Letter page", "page", US_PAPER_PRESETS, "new"),
    ("A4 page", "page", A4_PRESETS, "new"),
    ("Wide banner", "page", BANNER_PRESETS, "image"),
    ("Social media post", "page", SOCIAL_PRESETS, "image"),
    ("Cards, bookmarks and posters", "page", PRINT_PRESETS, "new"),
    ("Custom size", "page", None, "new"),
]


def dspin(lo, hi, dec, step, suffix=""):
    s = NumberBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setSingleStep(step)
    s.setSuffix(suffix)
    s.setMinimumWidth(110)
    return s


def fill_grouped(combo, groups, other=None):
    """Fill a menu with headed groups; headers cannot be picked."""
    combo.blockSignals(True)
    combo.clear()
    model = combo.model()
    for title, entries in groups:
        combo.addItem(title)
        header = model.item(combo.count() - 1)
        header.setFlags(Qt.NoItemFlags)
        font = header.font()
        font.setBold(True)
        header.setFont(font)
        for entry in entries:
            combo.addItem("     " + entry[0], entry)
    if other:
        combo.addItem(other, "other")
    combo.blockSignals(False)


def select_matching(combo, test):
    for i in range(combo.count()):
        data = combo.itemData(i)
        if isinstance(data, tuple) and test(data):
            combo.setCurrentIndex(i)
            return True
    return False


class PdfImportDialog(QDialog):
    """How to bring in a PDF: which pages, and onto this page or a new document."""

    def __init__(self, parent, name, pages, new_document=False):
        super().__init__(parent)
        self.setWindowTitle("Import PDF")
        self.setMinimumWidth(480)
        f = QFormLayout(self)
        f.setVerticalSpacing(8)
        head = QLabel(f"<b>{name}</b> has {pages} page{'s' if pages != 1 else ''}.")
        head.setWordWrap(True)
        f.addRow(head)
        self.here = QRadioButton("Put it on this page, as a picture")
        self.new = QRadioButton("Start a new document the same size as the PDF page")
        (self.new if new_document else self.here).setChecked(True)
        f.addRow(self.here)
        f.addRow(self.new)
        self.first = QSpinBox()
        self.first.setRange(1, pages)
        self.last = QSpinBox()
        self.last.setRange(1, pages)
        self.last.setValue(1)
        self.first_label = QLabel("From page")
        f.addRow(self.first_label, self.first)
        self.last_label = QLabel("To page")
        f.addRow(self.last_label, self.last)
        self.transparent = QCheckBox("See-through background (for logos and artwork)")
        self.transparent.setChecked(not new_document)
        f.addRow("", self.transparent)
        note = QLabel("Pages come in as sharp pictures at this document's resolution. "
                      "Their words cannot be edited; type new text on top instead.")
        note.setObjectName("hint")
        note.setWordWrap(True)
        f.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Import")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        f.addRow(buttons)
        self.first.valueChanged.connect(lambda v: self.last.setValue(max(v, self.last.value())))
        self.new.toggled.connect(self.update_ui)
        self.update_ui()

    def update_ui(self):
        new = self.new.isChecked()
        self.first_label.setText("Page" if new else "From page")
        self.last.setVisible(not new)
        self.last_label.setVisible(not new)
        if new:
            self.transparent.setChecked(False)

    def choice(self):
        first = self.first.value()
        last = first if self.new.isChecked() else max(first, self.last.value())
        return {"new_document": self.new.isChecked(), "pages": list(range(first, last + 1)),
                "transparent": self.transparent.isChecked()}


class WordImportDialog(QDialog):
    """Bring in a Word document as editable text, or as page pictures."""

    def __init__(self, parent, name, words, pictures):
        super().__init__(parent)
        self.setWindowTitle("Import Word document")
        self.setMinimumWidth(480)
        f = QFormLayout(self)
        f.setVerticalSpacing(8)
        bits = [f"{words:,} words"]
        if pictures:
            bits.append(f"{pictures} picture{'s' if pictures != 1 else ''}")
        head = QLabel(f"<b>{name}</b>: {', '.join(bits)}.")
        head.setWordWrap(True)
        f.addRow(head)
        self.text = QRadioButton("Text I can edit, in a text box (pictures come too)")
        self.pages = QRadioButton("Pages as pictures, laid out like in Word")
        self.text.setChecked(True)
        f.addRow(self.text)
        f.addRow(self.pages)
        self.first = QSpinBox()
        self.first.setRange(1, 9999)
        self.last = QSpinBox()
        self.last.setRange(1, 9999)
        self.first_label = QLabel("From page")
        self.last_label = QLabel("To page")
        f.addRow(self.first_label, self.first)
        f.addRow(self.last_label, self.last)
        note = QLabel("Long documents: only the start comes in as text, so it stays easy to "
                      "work with. Use pages as pictures for whole chapters.")
        note.setObjectName("hint")
        note.setWordWrap(True)
        f.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Import")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        f.addRow(buttons)
        self.first.valueChanged.connect(lambda v: self.last.setValue(max(v, self.last.value())))
        self.pages.toggled.connect(self.update_ui)
        self.update_ui()

    def update_ui(self):
        on = self.pages.isChecked()
        for w in (self.first, self.last, self.first_label, self.last_label):
            w.setVisible(on)

    def choice(self):
        return {"as_pages": self.pages.isChecked(),
                "pages": list(range(self.first.value(), max(self.first.value(), self.last.value()) + 1))}


class ExportDialog(QDialog):
    FORMATS = [("PDF for printing", "pdf"), ("PNG picture", "png"),
               ("JPEG picture (smaller file)", "jpeg")]

    def __init__(self, parent, doc: DocSettings, last=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle("Export")
        self.setMinimumWidth(460)
        last = last or {}
        f = QFormLayout(self)
        f.setVerticalSpacing(8)
        self.fmt = QComboBox()
        for title, key in self.FORMATS:
            self.fmt.addItem(title, key)
        self.area = QComboBox()
        self.area.addItem("Whole document, with bleed", "page")
        if doc.bleed > 0:
            self.area.addItem("Trimmed, without bleed", "trim")
        if doc.kind == "cover":
            self.area.addItem("Front cover only (for ebooks and adverts)", "front")
            self.area.addItem("Back cover only", "back")
            self.area.addItem("Spine only", "spine")
        self.dpi = QSpinBox()
        self.dpi.setRange(36, 1200)
        self.dpi.setSuffix(" dpi")
        self.size_label = QLabel()
        self.size_label.setObjectName("hint")
        self.quality = QSlider(Qt.Horizontal)
        self.quality.setRange(40, 100)
        self.quality_val = QLabel()
        self.outline = QCheckBox("Turn text into shapes (safest for printers)")
        self.outline.setChecked(True)
        self.note = QLabel()
        self.note.setObjectName("hint")
        self.note.setWordWrap(True)
        f.addRow("Format", self.fmt)
        f.addRow("Area", self.area)
        f.addRow("Resolution", self.dpi)
        f.addRow("", self.size_label)
        q = QWidget()
        qh = QHBoxLayout(q)
        qh.setContentsMargins(0, 0, 0, 0)
        qh.addWidget(self.quality)
        qh.addWidget(self.quality_val)
        f.addRow("Quality", q)
        f.addRow("", self.outline)
        f.addRow(self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Export…")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        f.addRow(buttons)
        self.fmt.setCurrentIndex(max(0, self.fmt.findData(last.get("format", "pdf"))))
        self.area.setCurrentIndex(max(0, self.area.findData(last.get("area", "page"))))
        self.dpi.setValue(int(last.get("dpi", doc.dpi)))
        self.quality.setValue(int(last.get("quality", 92)))
        self.outline.setChecked(bool(last.get("outline_text", True)))
        self.quality_row = q
        self.form = f
        self.fmt.currentIndexChanged.connect(self.update_ui)
        self.area.currentIndexChanged.connect(self.update_ui)
        self.dpi.valueChanged.connect(self.update_ui)
        self.quality.valueChanged.connect(self.update_ui)
        self.update_ui()

    def region(self):
        regs = self.doc.regions()
        return regs.get(self.area.currentData(), regs["page"])

    def show_row(self, field, visible):
        field.setVisible(visible)
        label = self.form.labelForField(field)
        if label is not None:
            label.setVisible(visible)

    def update_ui(self):
        fmt = self.fmt.currentData()
        raster = fmt in ("png", "jpeg")
        self.show_row(self.dpi, raster)
        self.show_row(self.quality_row, fmt == "jpeg")
        self.show_row(self.outline, fmt == "pdf")
        self.quality_val.setText(f"{self.quality.value()}")
        r = self.region()
        if raster:
            scale = self.dpi.value() / self.doc.dpi
            self.size_label.setText(f"{r.width() * scale:.0f} x {r.height() * scale:.0f} pixels")
        else:
            self.size_label.setText(f"{r.width() / self.doc.dpi:.3f} x "
                                    f"{r.height() / self.doc.dpi:.3f} in")
        notes = []
        if fmt == "pdf" and self.doc.kind == "cover" and self.area.currentData() == "page":
            notes.append("This is the file to upload for a paperback cover.")
        if fmt == "jpeg" and self.area.currentData() == "front":
            notes.append("Good for an ebook cover or an online advert.")
        if fmt == "png" and not self.doc.background:
            notes.append("The background stays see-through.")
        self.note.setText(" ".join(notes))
        self.note.setVisible(bool(notes))

    def options(self):
        return {"format": self.fmt.currentData(), "area": self.area.currentData(),
                "dpi": self.dpi.value(), "quality": self.quality.value(),
                "outline_text": self.outline.isChecked()}


class SettingsDialog(QDialog):
    """Edit > Settings: how Folio behaves."""

    def __init__(self, parent, values):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(460)
        f = QFormLayout(self)
        f.setVerticalSpacing(10)
        self.nudge = QDoubleSpinBox()
        self.nudge.setRange(0.1, 500)
        self.nudge.setDecimals(1)
        self.nudge.setSuffix(" pixels")
        self.nudge.setValue(float(values["nudge"]))
        f.addRow("Arrow keys move things by", self.nudge)
        hint = QLabel("Hold Shift with an arrow key to move ten times as far.")
        hint.setObjectName("hint")
        f.addRow("", hint)
        self.autosave = QSpinBox()
        self.autosave.setRange(1, 60)
        self.autosave.setSuffix(" minutes")
        self.autosave.setValue(int(values["autosave_min"]))
        f.addRow("Save a rescue copy every", self.autosave)
        self.undo = QSpinBox()
        self.undo.setRange(20, 2000)
        self.undo.setSingleStep(50)
        self.undo.setValue(int(values["undo_steps"]))
        f.addRow("Undo steps to keep", self.undo)
        self.reset_layout = QCheckBox("Put the panels back where they started")
        f.addRow("", self.reset_layout)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        f.addRow(buttons)

    def values(self):
        return {"nudge": self.nudge.value(), "autosave_min": self.autosave.value(),
                "undo_steps": self.undo.value(), "reset_layout": self.reset_layout.isChecked()}


SHORTCUTS = [
    ("Tools", [("V", "Move and resize"), ("A", "Edit points of a curve"),
               ("P", "Pen (curves)"), ("L", "Line"), ("M", "Rectangle"),
               ("E", "Ellipse"), ("T", "Text"), ("H", "Hand (or hold Space)"),
               ("Z", "Zoom")]),
    ("While dragging", [("Shift", "Keep proportions, or move straight"),
                        ("Ctrl", "Draw shapes from the centre; turn off snapping when moving"),
                        ("Ctrl + click", "Pick one object inside a group")]),
    ("Edit", [("Ctrl+Z / Ctrl+Shift+Z", "Undo / Redo"), ("Ctrl+C, Ctrl+X, Ctrl+V", "Copy, cut, paste"),
              ("Ctrl+Shift+V", "Paste style (colours, outline, shadow, lettering)"),
              ("Ctrl+Alt+V", "Paste inside the selected shape or text"),
              ("Ctrl+Alt+Shift+V", "Paste without format (plain text)"),
              ("Ctrl+J", "Duplicate"), ("Delete", "Delete"), ("Arrow keys", "Nudge (Shift = 10x)"),
              ("Ctrl+G / Ctrl+Shift+G", "Group / Ungroup"),
              ("Ctrl+] / Ctrl+[", "Bring forward / Send backward"),
              ("Ctrl+Shift+] / [", "Bring to front / Send to back")]),
    ("View", [("Ctrl+0", "Fit the page"), ("Ctrl+1", "Actual pixels"),
              ("Ctrl + mouse wheel", "Zoom"), ("Ctrl+=, Ctrl+-", "Zoom in, out"),
              ("W", "Preview the trimmed cover"), ("Ctrl+;", "Show or hide guides")]),
    ("File", [("Ctrl+N", "New"), ("Ctrl+Alt+Shift+N", "New from clipboard"),
              ("Ctrl+O", "Open"), ("Ctrl+S", "Save"),
              ("Ctrl+Shift+E or Ctrl+Alt+Shift+S", "Export"), ("Ctrl+P", "Print"),
              ("Ctrl+Shift+I", "Place image"), ("Ctrl+I", "Import"),
              ("Ctrl+Shift+P", "Document setup"), ("Ctrl+,", "Settings")]),
]


class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard shortcuts")
        self.resize(560, 640)
        v = QVBoxLayout(self)
        view = QTextBrowser()
        html = ["<style>td{padding:3px 12px 3px 0} h3{margin:14px 0 4px 0}</style>"]
        for title, rows in SHORTCUTS:
            html.append(f"<h3>{title}</h3><table>")
            for key, what in rows:
                html.append(f"<tr><td><b>{key}</b></td><td>{what}</td></tr>")
            html.append("</table>")
        view.setHtml("".join(html))
        v.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        v.addWidget(buttons)
