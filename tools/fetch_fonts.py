"""Download Folio's bundled fonts from Google Fonts.

Every font here is free to use, including on books you sell, and may be
shipped with software (SIL Open Font License or Apache License). Each
family keeps its licence file next to the font files.

    python3 tools/fetch_fonts.py STAGING_FOLDER DEST_FOLDER [FAMILY ...]

Fonts are downloaded into STAGING_FOLDER, checked, then copied into
DEST_FOLDER (normally the project's fonts/ folder) with a fonts.json index.
"""

import json
import os
import shutil
import sys
import time
import urllib.parse
import urllib.request

FAMILIES = {
    "serif": [
        "Playfair Display", "Cormorant Garamond", "EB Garamond", "Libre Baskerville",
        "Lora", "Merriweather", "Crimson Text", "Cinzel", "Cinzel Decorative",
        "Spectral", "Prata", "Marcellus", "Cardo", "Vollkorn", "Alegreya",
        "DM Serif Display", "Abril Fatface", "Yeseva One", "Old Standard TT",
        "Bodoni Moda", "Libre Caslon Text", "Fraunces", "Rozha One", "Gloock",
        "Sorts Mill Goudy", "IM Fell English", "Roboto Slab", "Arvo", "Bitter",
        "Zilla Slab", "Alfa Slab One",
    ],
    "sans": [
        "Montserrat", "Oswald", "Bebas Neue", "Anton", "Raleway", "Poppins",
        "Roboto", "Open Sans", "Josefin Sans", "Archivo Black", "League Spartan",
        "Barlow Condensed", "Fjalla One", "Teko", "Kanit", "Exo 2", "Work Sans",
        "Nunito", "Quicksand", "Staatliches", "Philosopher", "Righteous",
    ],
    "script": [
        "Great Vibes", "Dancing Script", "Pacifico", "Satisfy", "Kaushan Script",
        "Sacramento", "Allura", "Parisienne", "Pinyon Script", "Alex Brush",
        "Tangerine", "Caveat", "Amatic SC", "Shadows Into Light", "Permanent Marker",
        "Homemade Apple", "Rock Salt", "Lobster", "Courgette",
    ],
    "display": [
        "Creepster", "Nosifer", "Special Elite", "Uncial Antiqua", "MedievalSharp",
        "Pirata One", "UnifrakturMaguntia", "Orbitron", "Audiowide", "Bungee",
        "Bangers", "Luckiest Guy", "Fredoka", "Chewy", "Black Ops One", "Rye",
        "Monoton", "Mountains of Christmas", "Press Start 2P",
    ],
}

WANTED = ("Regular", "Italic", "Bold", "BoldItalic")
MAX_FILE = 6 * 1024 * 1024
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Folio font fetcher"}


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def manifest(family):
    url = "https://fonts.google.com/download/list?family=" + urllib.parse.quote(family)
    raw = get(url).decode("utf-8", "replace")
    return json.loads(raw[raw.index("{"):])["manifest"]


def style_of(filename):
    base = os.path.splitext(os.path.basename(filename))[0]
    return base.rsplit("-", 1)[-1] if "-" in base else "Regular"


WIDTHS = ("Condensed", "Expanded", "Narrow", "Wide", "Compressed")


def cut_of(filename):
    """The part between the family and the style, e.g. '72pt' or 'Condensed'."""
    base = os.path.splitext(os.path.basename(filename))[0].rsplit("-", 1)[0]
    return base.split("_", 1)[1] if "_" in base else ""


def cut_rank(cut):
    """Lower is better: the normal cut, then normal width at the largest
    optical size (finer detail for big cover titles), then anything else."""
    if not cut:
        return (0, 0)
    if any(w in cut for w in WIDTHS):
        return (2, 0)
    size = "".join(ch for ch in cut if ch.isdigit())
    return (1, -int(size) if size else 0)


def pick_files(refs):
    """Regular, Italic, Bold and Bold Italic of the most normal cut."""
    static = [r for r in refs if r["filename"].lower().endswith((".ttf", ".otf"))
              and "VariableFont" not in r["filename"]]
    if not static:
        return []
    best = min(cut_rank(cut_of(r["filename"])) for r in static)
    static = [r for r in static if cut_rank(cut_of(r["filename"])) == best]
    chosen = {}
    for r in static:
        style = style_of(r["filename"])
        if style in WANTED and style not in chosen:
            chosen[style] = r
    if not chosen:
        chosen["Regular"] = static[0]
    return list(chosen.values())


def looks_like_font(data):
    return data[:4] in (b"\x00\x01\x00\x00", b"OTTO", b"true") and len(data) < MAX_FILE


def main(staging, dest, only=()):
    os.makedirs(staging, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    index_path = os.path.join(dest, "fonts.json")
    index = {}
    if only and os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as fh:
            index = json.load(fh)
    failed = []
    for category, families in FAMILIES.items():
        for family in families:
            if only and family not in only:
                continue
            folder_name = family.replace(" ", "_")
            stage = os.path.join(staging, folder_name)
            shutil.rmtree(stage, ignore_errors=True)
            os.makedirs(stage, exist_ok=True)
            try:
                m = manifest(family)
                files = pick_files(m.get("fileRefs", []))
                if not files:
                    raise ValueError("no font files listed")
                saved = []
                for ref in files:
                    url = ref["url"]
                    if not url.startswith("https://fonts.gstatic.com/"):
                        raise ValueError("unexpected download address")
                    data = get(url)
                    if not looks_like_font(data):
                        raise ValueError(f"{ref['filename']} is not a font file")
                    name = os.path.basename(ref["filename"])
                    with open(os.path.join(stage, name), "wb") as fh:
                        fh.write(data)
                    saved.append(name)
                licences = [f for f in m.get("files", [])
                            if f["filename"].upper().startswith(("OFL", "LICENSE", "UFL"))]
                if not licences:
                    raise ValueError("no licence file")
                for lic in licences:
                    with open(os.path.join(stage, os.path.basename(lic["filename"])), "w",
                              encoding="utf-8") as fh:
                        fh.write(lic["contents"])
                target = os.path.join(dest, folder_name)
                shutil.rmtree(target, ignore_errors=True)
                shutil.copytree(stage, target)
                index[family] = {"category": category, "folder": folder_name,
                                 "files": saved,
                                 "licence": os.path.basename(licences[0]["filename"])}
                print(f"ok   {family}: {', '.join(saved)}", flush=True)
            except Exception as exc:  # keep going; report at the end
                failed.append(f"{family}: {exc}")
                print(f"FAIL {family}: {exc}", flush=True)
            time.sleep(0.15)
    with open(index_path, "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=1, sort_keys=True)
    print(f"\n{len(index)} families saved, {len(failed)} failed")
    for line in failed:
        print("  ", line)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], tuple(sys.argv[3:]))
