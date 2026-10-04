"""Conversion de curseurs Linux (format Xcursor) en curseurs Windows (.cur / .ani).

Grâce à ça, n'importe quel thème de curseurs de xfce-look.org devient utilisable
sous Windows.
"""
import struct
from pathlib import Path

# Rôle Windows -> noms Xcursor possibles (par ordre de préférence)
ROLE_SOURCES = {
    "Arrow": ["left_ptr", "default", "arrow", "top_left_arrow"],
    "Help": ["help", "question_arrow", "whats_this", "left_ptr_help"],
    "AppStarting": ["progress", "left_ptr_watch", "half-busy"],
    "Wait": ["wait", "watch"],
    "Crosshair": ["crosshair", "cross", "tcross", "cross_reverse"],
    "IBeam": ["text", "xterm", "ibeam"],
    "NWPen": ["pencil", "draft", "draft_large"],
    "No": ["not-allowed", "crossed_circle", "circle", "forbidden", "no-drop"],
    "SizeNS": ["ns-resize", "sb_v_double_arrow", "size_ver", "v_double_arrow", "row-resize"],
    "SizeWE": ["ew-resize", "sb_h_double_arrow", "size_hor", "h_double_arrow", "col-resize"],
    "SizeNWSE": ["nwse-resize", "size_fdiag", "bd_double_arrow", "bottom_right_corner"],
    "SizeNESW": ["nesw-resize", "size_bdiag", "fd_double_arrow", "bottom_left_corner"],
    "SizeAll": ["fleur", "move", "all-scroll", "size_all"],
    "UpArrow": ["up-arrow", "sb_up_arrow", "center_ptr", "up_arrow"],
    "Hand": ["pointer", "hand2", "pointing_hand", "hand1", "hand"],
    "Pin": ["pointer", "hand2", "hand1"],
    "Person": ["pointer", "hand2", "hand1"],
}
ANIMATED_ROLES = {"AppStarting", "Wait"}


# ---------------------------------------------------------------- lecture Xcursor


def read_xcursor(path, nominal=32):
    """Renvoie la liste des images [(w, h, xhot, yhot, delay_ms, argb_bytes)] de la taille
    la plus proche de `nominal` (plusieurs images = curseur animé)."""
    data = Path(path).read_bytes()
    if data[:4] != b"Xcur":
        raise ValueError("pas un fichier Xcursor")
    _, _, ntoc = struct.unpack_from("<III", data, 4)
    toc = []
    for i in range(ntoc):
        typ, sub, pos = struct.unpack_from("<III", data, 16 + i * 12)
        if typ == 0xFFFD0002:
            toc.append((sub, pos))
    if not toc:
        raise ValueError("aucune image")
    sizes = sorted({s for s, _ in toc}, key=lambda s: (abs(s - nominal), -s))
    best = sizes[0]
    frames = []
    for sub, pos in toc:
        if sub != best:
            continue
        _, _, _, _, w, h, xhot, yhot, delay = struct.unpack_from("<IIIIIIIII", data, pos)
        start = pos + 36
        pix = data[start:start + w * h * 4]
        if len(pix) == w * h * 4:
            frames.append((w, h, xhot, yhot, delay or 50, pix))
    return frames


# ---------------------------------------------------------------- écriture .cur


def _unpremultiply_bgra(pix):
    """Xcursor stocke de l'ARGB prémultiplié (octets B,G,R,A) ; le BMP veut du non prémultiplié."""
    out = bytearray(pix)
    for i in range(0, len(out), 4):
        a = out[i + 3]
        if 0 < a < 255:
            out[i] = min(255, out[i] * 255 // a)
            out[i + 1] = min(255, out[i + 1] * 255 // a)
            out[i + 2] = min(255, out[i + 2] * 255 // a)
    return bytes(out)


def _dib(w, h, bgra):
    """Image au format DIB (BITMAPINFOHEADER + pixels de bas en haut + masque AND)."""
    header = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    rows = [bgra[y * w * 4:(y + 1) * w * 4] for y in range(h)]
    pixels = b"".join(reversed(rows))
    mask_row = ((w + 31) // 32) * 4
    mask = b"\x00" * (mask_row * h)
    return header + pixels + mask


def build_cur(frame):
    w, h, xhot, yhot, _, pix = frame
    if w > 256 or h > 256:
        raise ValueError("curseur trop grand")
    img = _dib(w, h, _unpremultiply_bgra(pix))
    entry = struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, xhot, yhot, len(img), 6 + 16)
    return struct.pack("<HHH", 0, 2, 1) + entry + img


def _chunk(cid, data):
    pad = b"\x00" if len(data) % 2 else b""
    return cid + struct.pack("<I", len(data)) + data + pad


def build_ani(frames):
    """Curseur animé Windows (RIFF/ACON)."""
    curs = [build_cur(f) for f in frames]
    n = len(curs)
    # anih : cbSize, nFrames, nSteps, cx, cy, cBitCount, cPlanes, JifRate, flags (AF_ICON)
    anih = struct.pack("<IIIIIIIII", 36, n, n, 0, 0, 0, 0, 2, 1)
    rates = b"".join(struct.pack("<I", max(1, round(f[4] * 60 / 1000))) for f in frames)
    fram = b"fram" + b"".join(_chunk(b"icon", c) for c in curs)
    body = b"ACON" + _chunk(b"anih", anih) + _chunk(b"rate", rates) + _chunk(b"LIST", fram)
    return b"RIFF" + struct.pack("<I", len(body)) + body


# ---------------------------------------------------------------- conversion d'un thème


def _find(cursors_dir, names):
    for n in names:
        f = Path(cursors_dir) / n
        if f.exists():
            try:
                return f.resolve()
            except OSError:
                return f
    return None


def convert_theme(theme_dir, dest_dir, size=32):
    """Convertit un thème Xcursor (dossier contenant cursors/) en fichiers Windows.

    Renvoie {rôle Windows: nom de fichier}. Les rôles introuvables sont omis
    (Windows garde alors son curseur par défaut pour eux).
    """
    src = Path(theme_dir) / "cursors"
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    mapping = {}
    cache = {}
    for role, names in ROLE_SOURCES.items():
        f = _find(src, names)
        if f is None:
            continue
        if f in cache:
            mapping[role] = cache[f]
            continue
        try:
            frames = read_xcursor(f, size)
        except (ValueError, OSError, struct.error):
            continue
        if not frames:
            continue
        if len(frames) > 1:
            name = f"{role}.ani"
            (dest / name).write_bytes(build_ani(frames))
        else:
            name = f"{role}.cur"
            (dest / name).write_bytes(build_cur(frames[0]))
        cache[f] = name
        mapping[role] = name
    return mapping
