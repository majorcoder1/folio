"""Units, paper sizes and book-cover math.

Everything inside a Folio document is measured in document pixels.
A document has a DPI, so pixels convert to inches, millimetres or points.
"""

UNITS = ["px", "in", "mm", "cm", "pt"]

UNIT_NAMES = {
    "px": "Pixels",
    "in": "Inches",
    "mm": "Millimetres",
    "cm": "Centimetres",
    "pt": "Points",
}


def to_px(value, unit, dpi):
    if unit == "px":
        return float(value)
    if unit == "in":
        return value * dpi
    if unit == "mm":
        return value * dpi / 25.4
    if unit == "cm":
        return value * dpi / 2.54
    if unit == "pt":
        return value * dpi / 72.0
    raise ValueError(unit)


def from_px(px, unit, dpi):
    if unit == "px":
        return float(px)
    if unit == "in":
        return px / dpi
    if unit == "mm":
        return px * 25.4 / dpi
    if unit == "cm":
        return px * 2.54 / dpi
    if unit == "pt":
        return px * 72.0 / dpi
    raise ValueError(unit)


def decimals(unit):
    return {"px": 1, "in": 3, "mm": 2, "cm": 3, "pt": 1}[unit]


def tidy(value, places):
    """``value`` with up to ``places`` decimals, dropping zeros at the end but
    keeping at least two: 24 -> 24.00, 0.125 -> 0.125, 0.45 -> 0.45."""
    text = f"{value:.{places}f}"
    keep = min(2, places) if places > 1 else 0
    if "." in text:
        whole, part = text.split(".")
        while len(part) > keep and part.endswith("0"):
            part = part[:-1]
        text = f"{whole}.{part}" if part else whole
    return text


def fmt(px, unit, dpi):
    """Format a pixel length in the given unit, e.g. '6.125 in'."""
    v = from_px(px, unit, dpi)
    text = f"{v:.{decimals(unit)}f}".rstrip("0").rstrip(".")
    return f"{text} {unit}"


def pt_to_px(pt, dpi):
    return pt * dpi / 72.0


def px_to_pt(px, dpi):
    return px * 72.0 / dpi


# Paper types for print-on-demand covers. The number is the spine
# thickness per page in inches, as published by Amazon KDP.
PAPER_TYPES = [
    ("white", "Black & white, white paper", 0.002252),
    ("cream", "Black & white, cream paper", 0.0025),
    ("color", "Standard color, white paper", 0.002252),
    ("premium", "Premium color, white paper", 0.002347),
]

PAPER_FACTOR = {key: factor for key, _, factor in PAPER_TYPES}

MM = 1 / 25.4

# Book sizes (width x height, inches), in groups for the size menu.
PAPERBACK_SIZE_GROUPS = [
    ("Amazon KDP paperback sizes", [
        ("5 x 8 in", 5.0, 8.0),
        ("5.06 x 7.81 in", 5.06, 7.81),
        ("5.25 x 8 in", 5.25, 8.0),
        ("5.5 x 8.5 in  (digest)", 5.5, 8.5),
        ("6 x 9 in  (US trade, most popular)", 6.0, 9.0),
        ("6.14 x 9.21 in  (royal)", 6.14, 9.21),
        ("6.69 x 9.61 in", 6.69, 9.61),
        ("7 x 10 in  (executive)", 7.0, 10.0),
        ("7.44 x 9.69 in  (crown quarto)", 7.44, 9.69),
        ("7.5 x 9.25 in", 7.5, 9.25),
        ("8 x 10 in", 8.0, 10.0),
        ("8.25 x 6 in  (landscape)", 8.25, 6.0),
        ("8.25 x 8.25 in  (square)", 8.25, 8.25),
        ("8.5 x 8.5 in  (square)", 8.5, 8.5),
        ("8.5 x 11 in  (letter: workbooks, journals)", 8.5, 11.0),
        ("8.27 x 11.69 in  (A4)", 8.27, 11.69),
    ]),
    ("Pocket and mass-market sizes", [
        ("4 x 6 in  (pocket)", 4.0, 6.0),
        ("4.25 x 6.87 in  (mass market)", 4.25, 6.87),
        ("4.37 x 7 in", 4.37, 7.0),
        ("4.72 x 7.48 in", 4.72, 7.48),
        ("5 x 7 in", 5.0, 7.0),
        ("5 x 7.5 in  (manga)", 5.0, 7.5),
    ]),
    ("UK and European sizes", [
        ("A-format  110 x 178 mm", 110 * MM, 178 * MM),
        ("B-format  129 x 198 mm", 129 * MM, 198 * MM),
        ("Demy  138 x 216 mm", 138 * MM, 216 * MM),
        ("A5  148 x 210 mm", 148 * MM, 210 * MM),
        ("Royal  156 x 234 mm", 156 * MM, 234 * MM),
        ("Crown quarto  189 x 246 mm", 189 * MM, 246 * MM),
        ("A4  210 x 297 mm", 210 * MM, 297 * MM),
    ]),
    ("Square books", [
        ("6 x 6 in", 6.0, 6.0),
        ("7 x 7 in", 7.0, 7.0),
        ("7.5 x 7.5 in", 7.5, 7.5),
        ("8 x 8 in", 8.0, 8.0),
        ("10 x 10 in", 10.0, 10.0),
        ("12 x 12 in  (photo book)", 12.0, 12.0),
    ]),
    ("Landscape books", [
        ("9 x 7 in", 9.0, 7.0),
        ("10 x 8 in", 10.0, 8.0),
        ("11 x 8.5 in", 11.0, 8.5),
        ("12 x 9 in", 12.0, 9.0),
    ]),
    ("Comics, magazines and large books", [
        ("6.625 x 10.25 in  (comic book, graphic novel)", 6.625, 10.25),
        ("8.375 x 10.875 in  (magazine)", 8.375, 10.875),
        ("9 x 12 in  (large picture book)", 9.0, 12.0),
    ]),
]

HARDCOVER_SIZE_GROUPS = [
    ("Amazon KDP hardcover sizes", [
        ("5.5 x 8.5 in", 5.5, 8.5),
        ("6 x 9 in  (most popular)", 6.0, 9.0),
        ("6.14 x 9.21 in", 6.14, 9.21),
        ("7 x 10 in", 7.0, 10.0),
        ("8.25 x 11 in", 8.25, 11.0),
    ]),
]

# Amazon KDP case-laminate hardcover allowances, in inches: the cover wraps
# round the boards, the boards stand a little proud of the pages, and the
# spine is thicker than the pages alone.
HARDCOVER = {"wrap": 0.591, "board_w": 0.197, "board_h": 0.236,
             "case": 0.189, "hinge": 0.394}

# Page counts Amazon KDP prints (black and white interiors).
PAGE_RANGE = {"paperback": (24, 828), "hardcover": (75, 550)}

# Older name, still used for "is this a standard size" checks.
TRIM_SIZES = [entry for _, entries in PAPERBACK_SIZE_GROUPS for entry in entries]


def all_book_sizes():
    return [entry for _, entries in PAPERBACK_SIZE_GROUPS for entry in entries]


# ---------------------------------------------------------------------------
# Printers. Sources: Amazon KDP help ("Create a paperback cover"), the
# IngramSpark File Creation Guide (8.24.26) and the Lulu Book Creation Guide.

PRINTERS = [("kdp", "Amazon KDP"), ("ingram", "IngramSpark"), ("lulu", "Lulu")]
PRINTER_NAMES = dict(PRINTERS)

INGRAM_PAPERBACK = [
    ("IngramSpark paperback sizes", [
        ("4 x 6 in", 4.0, 6.0), ("4 x 7 in", 4.0, 7.0), ("4.25 x 7 in", 4.25, 7.0),
        ("4.37 x 7 in", 4.37, 7.0), ("4.72 x 7.48 in", 4.72, 7.48), ("5 x 7 in", 5.0, 7.0),
        ("5 x 8 in", 5.0, 8.0), ("5.06 x 7.81 in", 5.06, 7.81), ("5.25 x 8 in", 5.25, 8.0),
        ("5.5 x 7.5 in", 5.5, 7.5), ("5.5 x 8.25 in", 5.5, 8.25), ("5.5 x 8.38 in", 5.5, 8.38),
        ("5.5 x 8.5 in  (demy 8vo)", 5.5, 8.5), ("5.83 x 8.27 in  (A5)", 5.83, 8.27),
        ("6 x 9 in  (most popular)", 6.0, 9.0), ("6.14 x 9.21 in  (royal 8vo)", 6.14, 9.21),
        ("6.5 x 6.5 in", 6.5, 6.5), ("6.625 x 10.25 in", 6.625, 10.25),
        ("6.69 x 9.61 in  (pinched crown)", 6.69, 9.61), ("7 x 10 in", 7.0, 10.0),
        ("7.44 x 9.69 in  (crown 4vo)", 7.44, 9.69), ("7.5 x 9.25 in", 7.5, 9.25),
        ("8 x 8 in", 8.0, 8.0), ("8 x 10 in", 8.0, 10.0), ("8 x 10.88 in", 8.0, 10.88),
        ("8.25 x 10.75 in", 8.25, 10.75), ("8.25 x 11 in", 8.25, 11.0),
        ("8.268 x 11.693 in  (A4)", 8.268, 11.693), ("8.5 x 8.5 in", 8.5, 8.5),
        ("8.5 x 9 in", 8.5, 9.0), ("8.5 x 11 in", 8.5, 11.0), ("11 x 8.5 in  (landscape)", 11.0, 8.5),
    ]),
]

INGRAM_HARDCOVER = [
    ("IngramSpark hardcover (case laminate) sizes", [
        ("5 x 8 in", 5.0, 8.0), ("5.5 x 8.5 in  (demy 8vo)", 5.5, 8.5),
        ("5.83 x 8.27 in  (A5)", 5.83, 8.27), ("6 x 9 in  (most popular)", 6.0, 9.0),
        ("6.14 x 9.21 in  (royal 8vo)", 6.14, 9.21), ("6.69 x 9.61 in  (pinched crown)", 6.69, 9.61),
        ("7 x 10 in", 7.0, 10.0), ("7.5 x 9.25 in", 7.5, 9.25), ("8 x 8 in", 8.0, 8.0),
        ("8 x 10 in", 8.0, 10.0), ("8 x 10.88 in", 8.0, 10.88), ("8.25 x 10.75 in", 8.25, 10.75),
        ("8.5 x 8.5 in", 8.5, 8.5), ("8.5 x 11 in", 8.5, 11.0), ("11 x 8.5 in  (landscape)", 11.0, 8.5),
    ]),
]

LULU_SIZES = [
    ("Lulu sizes", [
        ("Pocketbook  4.25 x 6.875 in", 4.25, 6.875), ("Novella  5 x 8 in", 5.0, 8.0),
        ("Digest  5.5 x 8.5 in", 5.5, 8.5), ("A5  5.83 x 8.27 in", 5.83, 8.27),
        ("US Trade  6 x 9 in  (most popular)", 6.0, 9.0), ("Royal  6.14 x 9.21 in", 6.14, 9.21),
        ("Comic Book  6.63 x 10.25 in", 6.63, 10.25), ("Executive  7 x 10 in", 7.0, 10.0),
        ("Crown Quarto  7.44 x 9.68 in", 7.44, 9.68), ("Small Square  7.5 x 7.5 in", 7.5, 7.5),
        ("A4  8.27 x 11.69 in", 8.27, 11.69), ("Square  8.5 x 8.5 in", 8.5, 8.5),
        ("US Letter  8.5 x 11 in", 8.5, 11.0), ("Small Landscape  9 x 7 in", 9.0, 7.0),
        ("US Letter Landscape  11 x 8.5 in", 11.0, 8.5), ("A4 Landscape  11.69 x 8.27 in", 11.69, 8.27),
    ]),
]

# Paper choices per printer: (key, title, inches of spine per page).
PRINTER_PAPERS = {
    "kdp": PAPER_TYPES,
    "ingram": [
        ("creme50", "Black & white, creme 50 lb", 0.0025),
        ("white50", "Black & white, white 50 lb", 0.002252),
        ("color50", "Color, white 50 lb", 0.002252),
        ("color70", "Color, white 70 lb", 0.0028),
    ],
    "lulu": [
        ("standard", "Black & white or color (any paper)", 1 / 444),
    ],
}

# Lulu hardcover spines come from a page-count table (Book Creation Guide).
LULU_HARDCOVER_SPINE = [
    (84, 0.25), (140, 0.5), (168, 0.625), (194, 0.688), (222, 0.75), (250, 0.813),
    (278, 0.875), (306, 0.938), (334, 1.0), (360, 1.063), (388, 1.125), (416, 1.188),
    (444, 1.25), (472, 1.313), (500, 1.375), (528, 1.438), (556, 1.5), (582, 1.563),
    (610, 1.625), (638, 1.688), (666, 1.75), (694, 1.813), (722, 1.875), (750, 1.938),
    (778, 2.0), (799, 2.063), (800, 2.125),
]


def cover_spec(printer, binding):
    """How a printer builds a cover, in inches.

    wrap      - bleed (paperback) or the art that folds round the boards
    board_dw  - board width minus book width (hardcover)
    board_dh  - board height minus book height (hardcover)
    gutter    - a hinge strip between each board and the spine (IngramSpark)
    hinge     - a bend zone just inside each board, beside the spine
    """
    hard = binding == "hardcover"
    spec = {"wrap": 0.125, "board_dw": 0.0, "board_dh": 0.0, "gutter": 0.0, "hinge": 0.0,
            "safe": 0.25, "spine_margin": 0.0625, "spine_text_pages": 80,
            "barcode": (2.0, 1.2), "pages": (24, 828), "exact": True, "note": ""}
    if printer == "kdp":
        if hard:
            spec.update(wrap=0.591, board_dw=0.197, board_dh=0.236, hinge=0.394,
                        pages=(75, 550), exact=False,
                        note="Amazon KDP hardcover sizes come from published guides. "
                             "Compare with KDP's cover calculator before you order.")
    elif printer == "ingram":
        spec.update(spine_text_pages=48, barcode=(1.75, 1.0), pages=(18, 1200), exact=False,
                    note="IngramSpark works out the exact spine in its free cover template. "
                         "Untick the box above and type its spine width in.")
        if hard:
            spec.update(wrap=0.625, board_dw=-0.185, board_dh=0.25, gutter=0.5, pages=(18, 840))
    elif printer == "lulu":
        spec.update(safe=0.5, spine_margin=0.125, spine_text_pages=81,
                    pages=(24, 800) if hard else (32, 800))
        if hard:
            spec.update(wrap=0.75, board_dw=0.125, board_dh=0.25, hinge=0.25)
    return spec


def size_groups(printer, binding):
    if printer == "ingram":
        return INGRAM_HARDCOVER if binding == "hardcover" else INGRAM_PAPERBACK
    if printer == "lulu":
        return LULU_SIZES
    return HARDCOVER_SIZE_GROUPS if binding == "hardcover" else PAPERBACK_SIZE_GROUPS


# KDP: books need more than this many pages before the spine can carry text.
SPINE_TEXT_MIN_PAGES = 80


def spine_width_in(pages, paper, binding="paperback", printer="kdp"):
    """Spine width in inches for a printer, binding, paper and page count."""
    if printer == "lulu":
        if binding == "hardcover":
            for top, width in LULU_HARDCOVER_SPINE:
                if pages <= top:
                    return width
            return LULU_HARDCOVER_SPINE[-1][1]
        return pages / 444 + 0.06
    papers = {key: factor for key, _, factor in PRINTER_PAPERS.get(printer, PAPER_TYPES)}
    factor = papers.get(paper, next(iter(papers.values())))
    if printer == "ingram":
        pages += pages % 2      # IngramSpark counts pages in pairs
    width = pages * factor
    if binding == "hardcover":
        width += HARDCOVER["case"]
    return width
