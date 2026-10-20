#!/usr/bin/env bash
# Remove Folio from the applications menu. Your .folio files are not touched.
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
rm -f "$DATA/applications/folio.desktop" "$DATA/mime/packages/folio.xml"
find "$DATA/icons/hicolor" \( -name folio.png -o -name application-x-folio.png \) -delete 2>/dev/null
update-mime-database "$DATA/mime" >/dev/null 2>&1 || true
update-desktop-database "$DATA/applications" >/dev/null 2>&1 || true
echo "Folio has been removed from the menu."
