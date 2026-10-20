"""Document settings and the page geometry derived from them.

Two kinds of document exist:

* ``page``  - a single page (ebook cover, flyer, poster, social post ...)
* ``cover`` - a full paperback wrap: back cover, spine and front cover
  side by side, with bleed all round.

All lengths are stored in document pixels.
"""

from dataclasses import dataclass, asdict

from PyQt5.QtCore import QRectF

from . import units


@dataclass
class DocSettings:
    kind: str = "page"          # "page" or "cover"
    dpi: float = 300.0
    unit: str = "in"            # unit shown in the interface
    width: float = 2550.0       # trim width in px (page documents)
    height: float = 3300.0      # trim height in px (page documents)
    bleed: float = 0.0          # px, added on every side
    margin: float = 0.0         # safe margin inside the trim, px
    background: str = "#ffffffff"   # "" means transparent
    # Cover documents only (inches).
    trim_w_in: float = 6.0
    trim_h_in: float = 9.0
    pages: int = 200
    paper: str = "white"
    spine_override_in: float = 0.0   # 0 = calculate from pages
    spine_margin_in: float = 0.0625
    barcode: bool = True
    title: str = ""
    binding: str = "paperback"       # covers: "paperback" or "hardcover"
    printer: str = "kdp"             # covers: "kdp", "ingram" or "lulu"

    def __post_init__(self):
        """Repair impossible values (a damaged or hand-edited file), so the
        program can always open it: no zero resolution, no negative size."""
        def num(value, default):
            try:
                value = float(value)
            except (TypeError, ValueError):
                return default
            return value if value == value and abs(value) != float("inf") else default
        self.dpi = min(max(num(self.dpi, 300.0), 10.0), 4800.0)
        self.width = max(num(self.width, 2550.0), 1.0)
        self.height = max(num(self.height, 3300.0), 1.0)
        self.bleed = max(num(self.bleed, 0.0), 0.0)
        self.margin = max(num(self.margin, 0.0), 0.0)
        self.trim_w_in = min(max(num(self.trim_w_in, 6.0), 0.5), 60.0)
        self.trim_h_in = min(max(num(self.trim_h_in, 9.0), 0.5), 60.0)
        self.pages = int(min(max(num(self.pages, 200), 1), 5000))
        self.spine_override_in = max(num(self.spine_override_in, 0.0), 0.0)
        self.spine_margin_in = max(num(self.spine_margin_in, 0.0625), 0.0)
        if self.unit not in units.UNITS:
            self.unit = "in"
        if self.kind not in ("page", "cover"):
            self.kind = "page"
        if self.binding not in ("paperback", "hardcover"):
            self.binding = "paperback"
        if self.printer not in dict(units.PRINTERS):
            self.printer = "kdp"
        if self.paper not in {p[0] for plist in units.PRINTER_PAPERS.values() for p in plist}:
            self.paper = "white"

    # ---- derived geometry -------------------------------------------------

    @property
    def hardcover(self):
        return self.kind == "cover" and self.binding == "hardcover"

    @property
    def spec(self):
        """The printer's rules for this cover (see units.cover_spec)."""
        return units.cover_spec(self.printer, self.binding)

    @property
    def board_w_in(self):
        """Width of the front (or back) of the closed book."""
        return self.trim_w_in + (self.spec["board_dw"] if self.hardcover else 0.0)

    @property
    def board_h_in(self):
        return self.trim_h_in + (self.spec["board_dh"] if self.hardcover else 0.0)

    @property
    def gutter_px(self):
        """IngramSpark hardcovers: a hinge strip between each board and the spine."""
        return self.spec["gutter"] * self.dpi if self.hardcover else 0.0

    @property
    def spine_in(self):
        if self.spine_override_in > 0:
            return self.spine_override_in
        return units.spine_width_in(self.pages, self.paper, self.binding, self.printer)

    @property
    def spine_px(self):
        return self.spine_in * self.dpi if self.kind == "cover" else 0.0

    @property
    def trim_width(self):
        if self.kind == "cover":
            return 2 * self.board_w_in * self.dpi + 2 * self.gutter_px + self.spine_px
        return self.width

    @property
    def trim_height(self):
        if self.kind == "cover":
            return self.board_h_in * self.dpi
        return self.height

    @property
    def page_width(self):
        return self.trim_width + 2 * self.bleed

    @property
    def page_height(self):
        return self.trim_height + 2 * self.bleed

    def page_rect(self):
        """The whole document, bleed included."""
        return QRectF(0, 0, self.page_width, self.page_height)

    def trim_rect(self):
        b = self.bleed
        return QRectF(b, b, self.trim_width, self.trim_height)

    def regions(self):
        """Named areas used for guides, alignment and export."""
        page = self.page_rect()
        trim = self.trim_rect()
        out = {"page": page, "trim": trim}
        if self.kind == "cover":
            tw = self.board_w_in * self.dpi
            g = self.gutter_px
            b = self.bleed
            h = self.trim_height
            out["back"] = QRectF(b, b, tw, h)
            out["spine"] = QRectF(b + tw + g, b, self.spine_px, h)
            out["front"] = QRectF(b + tw + 2 * g + self.spine_px, b, tw, h)
        return out

    def safe_rects(self):
        """Areas where important text should stay."""
        m = self.margin
        regs = self.regions()
        if self.kind == "cover":
            sm = self.spine_margin_in * self.dpi
            hinge = self.spec["hinge"] * self.dpi if self.hardcover else 0.0
            out = [regs["back"].adjusted(m, m, -m - hinge, -m),
                   regs["front"].adjusted(m + hinge, m, -m, -m)]
            spine = regs["spine"].adjusted(sm, m, -sm, -m)
            if spine.width() > 0:
                out.append(spine)
            return out
        if m > 0:
            return [regs["trim"].adjusted(m, m, -m, -m)]
        return []

    def hinge_rects(self):
        """Hardcover only: the strips beside the spine where the cover bends."""
        if not self.hardcover:
            return []
        regs = self.regions()
        back, front, spine = regs["back"], regs["front"], regs["spine"]
        g = self.gutter_px
        if g > 0:
            return [QRectF(back.right(), back.top(), g, back.height()),
                    QRectF(spine.right(), spine.top(), g, spine.height())]
        hinge = self.spec["hinge"] * self.dpi
        return [QRectF(back.right() - hinge, back.top(), hinge, back.height()),
                QRectF(front.left(), front.top(), hinge, front.height())]

    def barcode_rect(self):
        """Where KDP prints the barcode: 2 x 1.2 in, lower right of the back."""
        if self.kind != "cover" or not self.barcode:
            return None
        back = self.regions()["back"]
        d = self.dpi
        bw, bh = self.spec["barcode"]
        w, h, gap = bw * d, bh * d, 0.25 * d
        side = gap + (self.spec["hinge"] * d if self.hardcover else 0.0)
        return QRectF(back.right() - side - w, back.bottom() - gap - h, w, h)

    def describe(self):
        """One line for the status bar."""
        u = self.unit
        if self.kind == "cover":
            name = "Hardcover" if self.hardcover else "Paperback"
            printer = units.PRINTER_NAMES.get(self.printer, "")
            return (f"{printer} {name.lower()} {self.trim_w_in:g} x {self.trim_h_in:g} in, "
                    f"{self.pages} pages, spine {self.spine_in:.3f} in")
        return (f"{units.fmt(self.trim_width, u, self.dpi)} x "
                f"{units.fmt(self.trim_height, u, self.dpi)} at {self.dpi:g} dpi")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


def cover_settings(trim_w_in=6.0, trim_h_in=9.0, pages=200, paper="white",
                   bleed_in=None, margin_in=None, dpi=300.0, binding="paperback",
                   printer="kdp"):
    """A full cover. For hardcovers the bleed is the wrap round the boards."""
    spec = units.cover_spec(printer, binding)
    if bleed_in is None:
        bleed_in = spec["wrap"]
    if margin_in is None:
        margin_in = spec["safe"]
    return DocSettings(kind="cover", dpi=dpi, unit="in",
                       bleed=bleed_in * dpi, margin=margin_in * dpi,
                       trim_w_in=trim_w_in, trim_h_in=trim_h_in,
                       pages=pages, paper=paper, binding=binding, printer=printer,
                       spine_margin_in=spec["spine_margin"])


def page_settings(width, height, unit="px", dpi=72.0, bleed=0.0, margin=0.0,
                  background="#ffffffff"):
    """Width, height, bleed and margin are given in ``unit``."""
    return DocSettings(kind="page", dpi=dpi, unit=unit,
                       width=units.to_px(width, unit, dpi),
                       height=units.to_px(height, unit, dpi),
                       bleed=units.to_px(bleed, unit, dpi),
                       margin=units.to_px(margin, unit, dpi),
                       background=background)
