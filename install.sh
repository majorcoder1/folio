#!/usr/bin/env bash
# Add Folio to the applications menu and let .folio files open with it.
# Run it with:  bash install.sh        (bash uninstall.sh removes it again)
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS="$DATA/applications"
ICONS="$DATA/icons/hicolor"
MIME="$DATA/mime"
mkdir -p "$APPS" "$ICONS" "$MIME/packages"

QT_QPA_PLATFORM=offscreen python3 -c "
import sys; sys.path.insert(0, sys.argv[1])
from PyQt5.QtWidgets import QApplication
app = QApplication([])
from folio.icons import save_app_icons
save_app_icons(sys.argv[2])
" "$HERE" "$ICONS"

cat > "$APPS/folio.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Folio
GenericName=Graphic Design
Comment=Design book covers, ebook covers and other graphics
Exec=python3 "$HERE/folio.py" %f
Icon=folio
Terminal=false
Categories=Graphics;VectorGraphics;2DGraphics;
MimeType=application/x-folio;
StartupWMClass=Folio
Keywords=design;cover;book;ebook;vector;graphics;layout;
DESKTOP

cat > "$MIME/packages/folio.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-folio">
    <comment>Folio design</comment>
    <glob pattern="*.folio"/>
    <icon name="application-x-folio"/>
  </mime-type>
</mime-info>
XML

update-mime-database "$MIME" >/dev/null 2>&1 || true
update-desktop-database "$APPS" >/dev/null 2>&1 || true
gtk-update-icon-cache -f -t "$ICONS" >/dev/null 2>&1 || true
echo "Folio is now in your applications menu (under Graphics)."
