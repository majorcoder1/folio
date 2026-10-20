"""Bringing in PDF files, Word documents and Affinity files.

* PDF pages come in as sharp pictures, drawn by poppler's pdftocairo.
* Word (.docx) text comes in as an editable text box (plus the document's
  pictures); or, through LibreOffice, whole pages as pictures.
* Affinity files are a private format nobody has documented, so only the
  small preview picture saved inside them can be read.
"""

import os
import re
import shutil
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET

MAX_PIXELS = 60_000_000
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class ImportProblem(Exception):
    """Something the person needs to be told in plain words."""


# ---- PDF ---------------------------------------------------------------------

def _run(args, timeout=120):
    try:
        out = subprocess.run(args, capture_output=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise ImportProblem(f"The helper program {args[0]} is not installed.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ImportProblem("That took too long and was stopped.") from exc
    return out


def pdf_info(path, page=None):
    """{'pages': n, 'width_pt': w, 'height_pt': h} for a page (default the first)."""
    args = ["pdfinfo"]
    if page:
        args += ["-f", str(page), "-l", str(page)]
    out = _run(args + [path], timeout=30)
    text = out.stdout.decode("utf-8", "replace")
    if out.returncode != 0:
        if "ncrypt" in text + out.stderr.decode("utf-8", "replace"):
            raise ImportProblem("This PDF is locked with a password.")
        raise ImportProblem("This file could not be read as a PDF.")
    pages = int(re.search(r"^Pages:\s+(\d+)", text, re.M).group(1))
    size = re.search(r"Page\s+(?:\d+\s+)?size:\s+([\d.]+) x ([\d.]+) pts", text)
    if not size:
        raise ImportProblem("The page size of this PDF could not be read.")
    return {"pages": pages, "width_pt": float(size.group(1)), "height_pt": float(size.group(2))}


def render_pdf_page(path, page, dpi, transparent=True):
    """One page as PNG bytes, at ``dpi`` (lowered for very large pages)."""
    info = pdf_info(path, page)
    w_in, h_in = info["width_pt"] / 72.0, info["height_pt"] / 72.0
    while dpi > 36 and (w_in * dpi) * (h_in * dpi) > MAX_PIXELS:
        dpi = int(dpi * 0.8)
    work = tempfile.mkdtemp(prefix="folio-pdf-")
    try:
        base = os.path.join(work, "page")
        args = ["pdftocairo", "-png", "-singlefile", "-r", str(int(dpi)),
                "-f", str(page), "-l", str(page)]
        if transparent:
            args.append("-transp")
        out = _run(args + [path, base], timeout=180)
        result = base + ".png"
        if out.returncode != 0 or not os.path.exists(result):
            raise ImportProblem("This PDF page could not be drawn.")
        with open(result, "rb") as fh:
            return fh.read()
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ---- Word ----------------------------------------------------------------------

def docx_contents(path):
    """Return (paragraphs, title, pictures) from a .docx file.

    ``title`` is the first paragraph styled as a title or heading, if any.
    ``pictures`` is a list of (bytes, extension, name).
    """
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml")
            pictures = []
            for name in z.namelist():
                if name.startswith("word/media/"):
                    ext = os.path.splitext(name)[1].lower().lstrip(".")
                    if ext in ("png", "jpg", "jpeg", "gif", "bmp", "webp", "tif", "tiff"):
                        pictures.append((z.read(name), ext, os.path.basename(name)))
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ImportProblem("This file is not a Word document Folio can read "
                            "(only .docx files work, not old .doc files).") from exc
    root = ET.fromstring(xml)
    paragraphs = []
    title = None
    for p in root.iter(W_NS + "p"):
        style = p.find(f"{W_NS}pPr/{W_NS}pStyle")
        style_id = style.get(W_NS + "val", "") if style is not None else ""
        parts = []
        for node in p.iter():
            if node.tag == W_NS + "t":
                parts.append(node.text or "")
            elif node.tag == W_NS + "tab":
                parts.append("\t")
            elif node.tag in (W_NS + "br", W_NS + "cr"):
                parts.append("\n")
        text = "".join(parts)
        if title is None and text.strip() and re.match(r"(Title|Heading1|Heading 1)$", style_id):
            title = text.strip()
            continue
        paragraphs.append(text)
    while paragraphs and not paragraphs[-1].strip():
        paragraphs.pop()
    while paragraphs and not paragraphs[0].strip():
        paragraphs.pop(0)
    return paragraphs, title, pictures


def office_to_pdf(path):
    """Convert a Word (or other office) file to PDF with LibreOffice; returns the PDF path."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise ImportProblem("LibreOffice is needed for this and is not installed.")
    out_dir = tempfile.mkdtemp(prefix="folio-office-")
    profile = os.path.join(tempfile.gettempdir(), "folio-libreoffice-profile")
    args = [soffice, f"-env:UserInstallation=file://{profile}", "--headless",
            "--convert-to", "pdf", "--outdir", out_dir, path]
    _run(args, timeout=240)
    pdf = os.path.join(out_dir, os.path.splitext(os.path.basename(path))[0] + ".pdf")
    if not os.path.exists(pdf):
        raise ImportProblem("LibreOffice could not turn this document into pages.")
    return pdf


# ---- Affinity -----------------------------------------------------------------

AFFINITY_MAGIC = b"\x00\xffKA"


def affinity_preview(path):
    """The biggest picture saved inside an Affinity file, as PNG bytes.

    Every Affinity file carries a preview; some also keep placed pictures as
    PNG. Of those that can be read, the largest is the most useful.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    if not data.startswith(AFFINITY_MAGIC):
        raise ImportProblem("This does not look like an Affinity file.")
    best = None
    start = data.find(b"\x89PNG\r\n\x1a\n")
    while start >= 0:
        end = data.find(b"IEND", start)
        if end < 0:
            break
        png = data[start:end + 8]
        w = int.from_bytes(png[16:20], "big")
        h = int.from_bytes(png[20:24], "big")
        if best is None or w * h > best[0]:
            best = (w * h, png)
        start = data.find(b"\x89PNG\r\n\x1a\n", end)
    if best is None:
        raise ImportProblem("This Affinity file has no preview picture saved in it.")
    return best[1]
