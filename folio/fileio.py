"""Saving and opening .folio files.

A .folio file is a zip archive:

* ``document.json`` - page settings, objects and groups
* ``assets/<id>.<ext>`` - placed images, byte for byte as imported
* ``thumbnail.png`` - a small picture of the page
"""

import json
import os
import zipfile

FORMAT = "folio"
VERSION = 1


class FolioFileError(Exception):
    pass


def used_assets(snap):
    return {d.get("asset") for d in snap["items"] if d.get("kind") == "image"}


def save_document(scene, path, thumbnail_png=None):
    snap = scene.snapshot()
    assets = scene.assets
    assets.flush()
    used = [aid for aid in used_assets(snap) if assets.has(aid)]
    data = {
        "format": FORMAT,
        "version": VERSION,
        "doc": snap["doc"],
        "items": snap["items"],
        "groups": snap["groups"],
        "slices": snap["slices"],
        "guides": snap["guides"],
        "assets": {aid: {"ext": assets.ext[aid], "name": assets.names.get(aid, "")}
                   for aid in used},
    }
    tmp = path + ".saving"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("document.json", json.dumps(data, indent=1))
        for aid in used:
            z.writestr(f"assets/{aid}.{assets.ext[aid]}", assets.bytes_of(aid),
                       compress_type=zipfile.ZIP_STORED)
        if thumbnail_png:
            z.writestr("thumbnail.png", thumbnail_png, compress_type=zipfile.ZIP_STORED)
    os.replace(tmp, path)


def read_thumbnail(path):
    """The small picture saved inside a .folio file, as PNG bytes, or None."""
    try:
        with zipfile.ZipFile(path) as z:
            return z.read("thumbnail.png")
    except (OSError, KeyError, zipfile.BadZipFile):
        return None


def load_document(path):
    """Return (snapshot, {asset id: (bytes, ext, name)})."""
    try:
        with zipfile.ZipFile(path) as z:
            data = json.loads(z.read("document.json").decode("utf-8"))
            if data.get("format") != FORMAT:
                raise FolioFileError("This is not a Folio file.")
            if int(data.get("version", 0)) > VERSION:
                raise FolioFileError("This file was made by a newer version of Folio.")
            assets = {}
            for aid, info in data.get("assets", {}).items():
                ext = info.get("ext", "png")
                try:
                    blob = z.read(f"assets/{aid}.{ext}")
                except KeyError:
                    continue
                assets[aid] = (blob, ext, info.get("name", ""))
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise FolioFileError(f"The file could not be read ({exc}).") from exc
    snap = {"doc": data.get("doc", {}), "items": data.get("items", []),
            "groups": data.get("groups", {}), "slices": data.get("slices"),
            "guides": data.get("guides")}
    return snap, assets
