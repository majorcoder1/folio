"""Fonts that come with Folio, and the font list shown in the Text panel.

The fonts live in the project's ``fonts`` folder, one folder per family
with its licence. They are loaded for Folio only when it starts, so they
work for anyone who runs Folio, without installing anything.
"""

import json
import os
import shutil
import subprocess

from PyQt5.QtGui import QFontDatabase

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")

GROUPS = [
    ("All fonts", None),
    ("Classic (serif)", "serif"),
    ("Modern (sans serif)", "sans"),
    ("Script and handwriting", "script"),
    ("Display and fun", "display"),
    ("Already on this computer", "system"),
]

_bundled = {}       # family name as Qt sees it -> group key
_folders = {}       # family name -> its folder in the fonts folder
_state = {"loaded": False}

# Font names on Linux that are not useful for designing.
_SKIP = ("Math", "Symbols", "LM ", "Latin Modern", "D050000L", "Dingbats")
_ALIASES = {"Sans Serif", "Serif", "Monospace"}


def load_bundled():
    """Load every font in the fonts folder (once). Returns {family: group}."""
    if _state["loaded"]:
        return dict(_bundled)
    _state["loaded"] = True
    try:
        with open(os.path.join(FONT_DIR, "fonts.json"), encoding="utf-8") as fh:
            index = json.load(fh)
    except (OSError, ValueError):
        index = {}
    groups = {info.get("folder"): info.get("category", "display") for info in index.values()}
    if not os.path.isdir(FONT_DIR):
        return {}
    for folder in sorted(os.listdir(FONT_DIR)):
        path = os.path.join(FONT_DIR, folder)
        if not os.path.isdir(path):
            continue
        group = groups.get(folder, "display")
        for name in sorted(os.listdir(path)):
            if not name.lower().endswith((".ttf", ".otf")):
                continue
            fid = QFontDatabase.addApplicationFont(os.path.join(path, name))
            if fid < 0:
                continue
            for family in QFontDatabase.applicationFontFamilies(fid):
                _bundled.setdefault(family, group)
                _folders.setdefault(family, path)
    return dict(_bundled)


def font_files(family):
    """The files that make up a font family (with its licence, for the
    fonts that come with Folio). An empty list if it cannot be found."""
    folder = _folders.get(family)
    if folder and os.path.isdir(folder):
        return sorted(os.path.join(folder, n) for n in os.listdir(folder)
                      if os.path.isfile(os.path.join(folder, n)))
    if not shutil.which("fc-list"):
        return []
    try:
        out = subprocess.run(["fc-list", ":", "family", "file"], capture_output=True,
                             timeout=20, text=True).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    wanted = family.strip().lower()
    found = set()
    for line in out.splitlines():
        path, _, names = line.partition(": ")
        if any(n.strip().lower() == wanted for n in names.split(",")):
            found.add(path.strip())
    return sorted(found)


def bundled_families():
    return dict(_bundled)


def system_families():
    """Fonts already installed, tidied (no duplicates or maths fonts)."""
    db = QFontDatabase()
    out = set()
    for family in db.families(QFontDatabase.Latin):
        if family in _bundled or db.isPrivateFamily(family):
            continue
        base = family.split(" [")[0].strip()
        if base in _bundled or base in _ALIASES or any(word in base for word in _SKIP):
            continue
        out.add(base)
    return sorted(out, key=str.lower)


def families_in(group):
    if group in ("serif", "sans", "script", "display"):
        return sorted((f for f, g in _bundled.items() if g == group), key=str.lower)
    system = system_families()
    if group == "system":
        return system
    return sorted(set(_bundled) | set(system), key=str.lower)
