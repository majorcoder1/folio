"""Checks for importing PDF, Word and Affinity files.

    QT_QPA_PLATFORM=offscreen python3 -m tests.test_import
"""

import os
import shutil
import sys
import tempfile
import zipfile

_HOME = tempfile.mkdtemp(prefix="folio-home-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_HOME, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_HOME, "data")

from PyQt5.QtCore import QPointF  # noqa: E402
from PyQt5.QtGui import QColor, QImage  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import QApplication, QMessageBox  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app = QApplication.instance() or QApplication(sys.argv)
app.setProperty("quiet_errors", True)

from folio import exporter, importers, theme  # noqa: E402
from folio.dialogs import PdfImportDialog, WordImportDialog  # noqa: E402
from folio.document import cover_settings, page_settings  # noqa: E402
from folio.items import ImageItem, RectItem, TextItem  # noqa: E402
from folio.scene import DocScene  # noqa: E402
from folio.window import MainWindow  # noqa: E402
from tests.test_smoke import check  # noqa: E402

ERRORS = []
sys.excepthook = lambda *a: ERRORS.append(a)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.warning = staticmethod(lambda *a, **k: ERRORS.append(("warning", a)) or QMessageBox.Ok)


def make_docx(path, png_bytes):
    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        '<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr><w:r><w:t>The Almighty God</w:t></w:r></w:p>'
        "<w:p><w:r><w:t>In the beginning was the Word,</w:t></w:r>"
        '<w:r><w:t xml:space="preserve"> and the Word was with God.</w:t></w:r></w:p>'
        "<w:p/>"
        "<w:p><w:r><w:t>Second paragraph</w:t><w:tab/><w:t>with a tab.</w:t></w:r></w:p>"
        "</w:body></w:document>")
    types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>")
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)
        z.writestr("word/media/image1.png", png_bytes)


def png_bytes(w=320, h=200, colour="#3366cc"):
    from PyQt5.QtCore import QBuffer, QByteArray, QIODevice
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor(colour))
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def main():
    theme.apply(app)
    win = MainWindow()
    win.resize(1300, 850)
    win.show()
    QTest.qWait(30)

    # a PDF made by Folio itself: a 6 x 9 in page with a blue box
    src = DocScene(page_settings(6, 9, "in", 300))
    box = RectItem()
    box.set_size(900, 900)
    box.setPos(450, 900)
    src.add_folio_item(box)
    pdf = os.path.join(_HOME, "sample.pdf")
    exporter.export(src, {"format": "pdf", "area": "page", "outline_text": True}, pdf)
    info = importers.pdf_info(pdf)
    check(info["pages"] == 1 and abs(info["width_pt"] - 432) < 0.5, "PDF size read (6 x 9 in)")

    win.set_scene(DocScene(cover_settings(6, 9, 200, "white")))
    QTest.qWait(20)
    win.import_pdf(pdf, pages=[1])
    sel = win.scene.selected_folio()
    check(len(sel) == 1 and isinstance(sel[0], ImageItem), "PDF page placed as a picture")
    page_item = sel[0]
    check(abs(page_item.w - 6 * 300) < 2 and abs(page_item.h - 9 * 300) < 2,
          "the PDF page keeps its real size (6 x 9 in)")
    front = win.scene.doc.regions()["front"]
    check(abs(page_item.center_scene().x() - front.center().x()) < 1,
          "a book-sized PDF page lands on the front cover")
    pix = win.scene.assets.size(page_item.aid)
    check(pix.width() >= 1700, f"PDF drawn sharp ({pix.width()} pixels wide)")

    win.import_pdf(pdf, new_document=True, pages=[1])
    doc = win.scene.doc
    check(abs(doc.page_width - 1800) < 1 and abs(doc.page_height - 2700) < 1,
          "Open PDF makes a document the same size")
    check(len(win.scene.folio_items()) == 1, "the page fills the new document")

    dlg = PdfImportDialog(win, "sample.pdf", 5)
    dlg.first.setValue(2)
    dlg.last.setValue(4)
    check(dlg.choice()["pages"] == [2, 3, 4], "PDF page range chosen")

    # Word
    docx = os.path.join(_HOME, "manuscript.docx")
    make_docx(docx, png_bytes())
    paragraphs, title, pictures = importers.docx_contents(docx)
    check(title == "The Almighty God", "Word title found")
    check(paragraphs[0] == "In the beginning was the Word, and the Word was with God.",
          "Word paragraph joined across pieces")
    check(paragraphs[-1] == "Second paragraph\twith a tab.", "Word tab kept")
    check(len(pictures) == 1, "Word picture found")
    win.set_scene(DocScene(cover_settings(6, 9, 200, "white")))
    QTest.qWait(20)
    win.place_word_text("manuscript.docx", paragraphs, title, pictures)
    texts = [i for i in win.scene.folio_items() if isinstance(i, TextItem)]
    images = [i for i in win.scene.folio_items() if isinstance(i, ImageItem)]
    check(len(texts) == 2 and texts[0].toPlainText() == "The Almighty God", "title and text boxes made")
    back = win.scene.doc.regions()["back"]
    check(back.contains(texts[1].scene_bounds().topLeft()), "text lands on the back cover")
    check(len(images) == 1, "Word picture placed")
    wd = WordImportDialog(win, "manuscript.docx", 20, 1)
    check(not wd.choice()["as_pages"], "Word comes in as text by default")

    if shutil.which("soffice"):
        pdf2 = importers.office_to_pdf(docx)
        check(importers.pdf_info(pdf2)["pages"] >= 1, "LibreOffice turns Word into pages")

    # Affinity: a file with the Affinity signature and a saved preview
    fake = os.path.join(_HOME, "cover.afdesign")
    with open(fake, "wb") as fh:
        fh.write(importers.AFFINITY_MAGIC + b"\x0b\x00\x00\x00nsrP" + os.urandom(5000)
                 + png_bytes(341, 512, "#884422") + os.urandom(300))
    preview = importers.affinity_preview(fake)
    check(preview.startswith(b"\x89PNG"), "Affinity preview found")
    win.import_affinity(fake)
    sel = win.scene.selected_folio()
    check(len(sel) == 1 and win.scene.assets.size(sel[0].aid).width() == 341, "Affinity preview placed")
    bad = os.path.join(_HOME, "not.afdesign")
    with open(bad, "wb") as fh:
        fh.write(b"hello")
    try:
        importers.affinity_preview(bad)
        check(False, "a non-Affinity file is refused")
    except importers.ImportProblem:
        check(True, "a non-Affinity file is refused politely")

    # a damaged file with impossible numbers still opens (no division by zero)
    from folio.document import DocSettings
    odd = DocSettings.from_dict({"kind": "page", "dpi": 0, "width": -5, "height": 0, "pages": -3,
                                 "unit": "furlongs", "paper": "??"})
    check(odd.dpi >= 10 and odd.width >= 1 and odd.height >= 1 and odd.pages >= 1
          and odd.describe(), "impossible numbers in a file are repaired")

    win.undo.setClean()
    win.close()
    if ERRORS:
        import traceback
        for e in ERRORS:
            if e and e[0] == "warning":
                print("warning shown:", e[1][2:])
            else:
                traceback.print_exception(*e)
        raise SystemExit("problems")
    print("ALL GOOD")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(1)
