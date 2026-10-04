#!/bin/sh
# Construit dist/bestthemes_<version>_all.deb
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/bestthemes/__init__.py")"
BUILD="$(mktemp -d)"
PKG="$BUILD/bestthemes_${VERSION}_all"
trap 'rm -rf "$BUILD"' EXIT

mkdir -p "$PKG/DEBIAN" "$PKG/usr/lib/bestthemes" "$PKG/usr/bin" \
         "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/scalable/apps" \
         "$PKG/usr/share/doc/bestthemes"

# Code de l'application (sans caches Python)
cp -r "$ROOT/bestthemes" "$PKG/usr/lib/bestthemes/"
find "$PKG/usr/lib/bestthemes" -name '__pycache__' -type d -prune -exec rm -rf {} +
install -m 755 "$ROOT/packaging/bestthemes.sh" "$PKG/usr/bin/bestthemes"
install -m 644 "$ROOT/packaging/bestthemes.desktop" "$PKG/usr/share/applications/"
install -m 644 "$ROOT/packaging/icons/bestthemes.svg" "$PKG/usr/share/icons/hicolor/scalable/apps/"
install -m 644 "$ROOT/README.md" "$PKG/usr/share/doc/bestthemes/README.md"
cat > "$PKG/usr/share/doc/bestthemes/copyright" <<COPY
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: bestthemes

Files: *
Copyright: $(date +%Y) BESTthemes
License: GPL-3.0+
 Voir /usr/share/common-licenses/GPL-3.
COPY

SIZE="$(du -sk "$PKG/usr" | cut -f1)"
sed -e "s/@VERSION@/$VERSION/" -e "s/@SIZE@/$SIZE/" "$ROOT/packaging/debian/control" > "$PKG/DEBIAN/control"
install -m 755 "$ROOT/packaging/debian/postinst" "$PKG/DEBIAN/postinst"
install -m 755 "$ROOT/packaging/debian/postrm" "$PKG/DEBIAN/postrm"
find "$PKG" -type d -exec chmod 755 {} +
find "$PKG/usr/lib" -type f -exec chmod 644 {} +

mkdir -p "$ROOT/dist"
dpkg-deb --root-owner-group --build "$PKG" "$ROOT/dist/bestthemes_${VERSION}_all.deb"
echo "Paquet créé : $ROOT/dist/bestthemes_${VERSION}_all.deb"
