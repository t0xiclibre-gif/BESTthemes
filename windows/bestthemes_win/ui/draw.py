"""Dessins d'aperçus (QPainter)."""
import io
import struct
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPen, QPixmap

from bestthemes.core import colors as C
from bestthemes.core import generator as G
from bestthemes.core import wallpaper as W

from . import widgets as Wd


def qc(h, a=255):
    c = QColor(h)
    c.setAlpha(a)
    return c


def rrect(p, x, y, w, h, r, color):
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawRoundedRect(QRectF(x, y, w, h), r, r)


def window(p, x, y, w, h, dark, accent, titlebar_accent=False, mac=False):
    """Fenêtre façon Windows 11 (ou macOS)."""
    bg = "#272727" if dark else "#f9f9f9"
    fg = "#ffffff" if dark else "#1b1b1b"
    side = "#202020" if dark else "#f0f0f0"
    rrect(p, x + 2, y + 4, w, h, 8, qc("#000000", 50))
    rrect(p, x, y, w, h, 8, qc(bg))
    th = max(14, h * 0.13)
    tb = accent if titlebar_accent else (side if not mac else bg)
    p.save()
    p.setClipRect(QRectF(x, y, w, th + 8))
    rrect(p, x, y, w, th + 8, 8, qc(tb))
    p.restore()
    p.fillRect(QRectF(x, y + th, w, 1), qc(fg, 25))
    tfg = C.readable_on(tb, "#ffffff", "#1b1b1b")
    cy = y + th / 2
    if mac:
        for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
            rrect(p, x + 8 + i * 11 - 3.5, cy - 3.5, 7, 7, 3.5, qc(c))
    else:
        pen = QPen(qc(tfg, 200))
        pen.setWidthF(1.1)
        p.setPen(pen)
        bx = x + w - 12
        p.drawLine(bx - 3, cy - 3, bx + 3, cy + 3)
        p.drawLine(bx + 3, cy - 3, bx - 3, cy + 3)
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(bx - 22, cy - 3, 6, 6))
        p.drawLine(bx - 41, cy, bx - 35, cy)
    # barre latérale + contenu
    sw = w * 0.27
    p.fillRect(QRectF(x, y + th + 1, sw, h - th - 9), qc(side))
    for i in range(4):
        yy = y + th + 9 + i * 12
        if yy + 8 > y + h - 6:
            break
        if i == 0:
            rrect(p, x + 4, yy - 2, sw - 8, 10, 4, qc(accent, 60))
            rrect(p, x + 4, yy, 2.5, 6, 1, qc(accent))
        rrect(p, x + 10, yy + 1, sw * 0.5, 3.5, 1.5, qc(fg, 150 if i == 0 else 90))
    cx = x + sw + 8
    cw = w - sw - 16
    for i in range(3):
        yy = y + th + 10 + i * 9
        rrect(p, cx, yy, cw * (0.75 - i * 0.18), 3.5, 1.5, qc(fg, 170 if i == 0 else 90))
    by = y + h - 22
    if by > y + th + 38:
        rrect(p, cx, by, cw * 0.36, 12, 4, qc(accent))
        rrect(p, cx + cw * 0.4, by, cw * 0.28, 12, 4, qc(fg, 30))
        tx = cx + cw * 0.75
        rrect(p, tx, by + 1, cw * 0.22, 10, 5, qc(accent))
        rrect(p, tx + cw * 0.22 - 9, by + 2.5, 7, 7, 3.5, qc(C.readable_on(accent)))


def taskbar(p, w, h, dark, accent, align=1, search=1, autohide=False, translucent=False,
            dock=False, y=None):
    th = 14
    y = h - th if y is None else y
    col = "#1c1c1c" if dark else "#eeeeee"
    p.fillRect(QRectF(0, y, w, th), qc(col, 150 if translucent else (90 if autohide else 235)))
    n = 6
    s = 8
    total = n * (s + 5) + (24 if search == 2 else 0)
    x = (w - total) / 2 if align == 1 else 8
    rrect(p, x, y + 3, s, s, 2, qc(accent))
    x += s + 5
    if search == 2:
        rrect(p, x, y + 3, 22, s, 4, qc("#888888", 120))
        x += 27
    elif search == 1:
        rrect(p, x, y + 3, s, s, 4, qc("#888888", 140))
        x += s + 5
    for c in ("#f5a524", "#3584e4", "#2ec27e", "#e5484d", "#9b59b6")[: n - 1]:
        rrect(p, x, y + 3, s, s, 2, qc(c))
        x += s + 5
    if dock:
        dw = w * 0.42
        rrect(p, (w - dw) / 2, h - 28, dw, 20, 7, qc("#ffffff" if not dark else "#3a3a3a", 170))
        for i, c in enumerate(("#3584e4", "#e5484d", "#f5a524", "#2ec27e", "#9b59b6", "#888888")):
            rrect(p, (w - dw) / 2 + 8 + i * dw / 6.4, h - 24, 12, 12, 3, qc(c))


@lru_cache(maxsize=64)
def wallpaper_pixmap(palette_id, style, w=320, h=180):
    return Wd.surface_to_pixmap(W.render(G.palette(palette_id), style, w, h))


def pack(p, w, h, pk):
    pal = G.palette(pk["palette"])
    wp = (pk.get("wallpaper") or {})
    pm = wallpaper_pixmap(wp.get("palette", pk["palette"]), wp.get("style", "gradient"))
    p.drawPixmap(0, 0, pm.scaled(int(w), int(h), Qt.KeepAspectRatioByExpanding,
                                 Qt.SmoothTransformation))
    accent = pk.get("accent") or pal["accent"]
    dark = pk.get("dark", True)
    tbp = pk.get("taskbar", "win11")
    window(p, w * 0.17, h * 0.13, w * 0.62, h * 0.62, dark, accent, pk.get("titlebars", False),
           mac=pk["id"].startswith("macos"))
    taskbar(p, w, h, dark, accent, align=0 if tbp in ("classic", "productive") else 1,
            search=2 if tbp == "classic" else (0 if tbp in ("macos", "minimal") else 1),
            autohide=tbp == "macos", translucent=pk.get("transparency", True),
            dock="WinStep.Nexus" in pk.get("tools", []))


def palette_chip(p, w, h, pal):
    p.fillRect(QRectF(0, 0, w, h), qc(pal["bg"]))
    p.fillRect(QRectF(0, 0, w, 9), qc(pal.get("header") or pal["bg"]))
    for i, c in enumerate([pal["accent"], pal.get("accent2") or pal["accent"], pal.get("red", "#e5484d")]):
        rrect(p, 8 + i * 13, h / 2 - 1, 9, 9, 4.5, qc(c))
    rrect(p, 50, h / 2 + 2, w - 60, 4, 2, qc(pal["fg"], 170))


def text(p, x, y, s, size=9, color="#ffffff", bold=False):
    f = QFont()
    f.setPointSizeF(size)
    f.setBold(bold)
    p.setFont(f)
    p.setPen(qc(color))
    p.drawText(int(x), int(y), s)


# ---------------------------------------------------------------- curseurs Windows


def _first_ani_frame(data):
    """Extrait le premier curseur (.cur) d'un fichier .ani (RIFF/ACON)."""
    i = 12
    while i + 8 <= len(data):
        cid = data[i:i + 4]
        size = struct.unpack_from("<I", data, i + 4)[0]
        if cid == b"LIST":
            i += 12  # entre dans la liste (« fram »)
            continue
        if cid == b"icon":
            return data[i + 8:i + 8 + size]
        i += 8 + size + (size & 1)
    return None


def decode_cur(raw, want=32):
    """Décode un .cur (entrées BMP ou PNG) en image Pillow, à la taille la plus proche de `want`."""
    from PIL import Image
    _, _, count = struct.unpack_from("<HHH", raw, 0)
    entries = []
    for i in range(count):
        w, h, _, _, _, _, size, off = struct.unpack_from("<BBBBHHII", raw, 6 + i * 16)
        entries.append(((w or 256), size, off))
    if not entries:
        return None
    w, size, off = min(entries, key=lambda e: (abs(e[0] - want), -e[0]))
    data = raw[off:off + size]
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return Image.open(io.BytesIO(data))
    # Entrée BMP : on la ré-emballe en .ico à une seule image, que Pillow sait lire
    bpp = struct.unpack_from("<H", data, 14)[0] if len(data) >= 16 else 32
    ico = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", w % 256, w % 256, 0, 0, 1, bpp,
                                                      len(data), 22) + data
    return Image.open(io.BytesIO(ico), formats=["ICO"])


@lru_cache(maxsize=512)
def cursor_pixmap(path):
    try:
        raw = Path(path).read_bytes()
        if raw[:4] == b"RIFF":
            raw = _first_ani_frame(raw)
            if raw is None:
                return None
        im = decode_cur(raw)
        if im is None:
            return None
        im.load()
        return Wd.pil_to_pixmap(im)
    except Exception:  # noqa: BLE001 — fichier exotique : pas d'aperçu
        return None


def cursors(p, w, h, theme):
    roles = ["Arrow", "Hand", "IBeam", "Wait", "SizeAll", "Help"]
    pms = []
    for r in roles:
        f = theme["roles"].get(r)
        if f:
            pm = cursor_pixmap(str(Path(theme["path"]) / f))
            if pm:
                pms.append(pm)
    size, gap = 32, 14
    x = (w - (len(pms) * size + (len(pms) - 1) * gap)) / 2
    for pm in pms:
        p.drawPixmap(int(x), int((h - size) / 2), pm.scaled(size, size, Qt.KeepAspectRatio,
                                                             Qt.SmoothTransformation))
        x += size + gap


def icons(p, w, h, pack_):
    keys = ["computer", "folder-documents", "folder-pictures", "folder-music", "folder-downloads",
            "trash-empty"]
    pms = [QPixmap(str(Path(pack_["path"]) / pack_["icons"][k])) for k in keys if k in pack_["icons"]]
    pms = [pm for pm in pms if not pm.isNull()]
    if not pms:
        return
    gap = 10
    size = int(min(44, (w - 16 - gap * (len(pms) - 1)) / len(pms)))
    x = (w - (len(pms) * size + (len(pms) - 1) * gap)) / 2
    for pm in pms:
        p.drawPixmap(int(x), int((h - size) / 2), pm.scaled(size, size, Qt.KeepAspectRatio,
                                                             Qt.SmoothTransformation))
        x += size + gap


def gradient_bg(p, w, h, a="#6a85b6", b="#bac8e0"):
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, qc(a))
    g.setColorAt(1, qc(b))
    p.fillRect(QRectF(0, 0, w, h), g)
