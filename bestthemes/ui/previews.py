"""Rendu des aperçus : thème GTK, bordures xfwm4, icônes, curseurs, dock Plank."""
import configparser
import math
import re
import struct
from functools import lru_cache
from pathlib import Path

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk  # noqa: E402

from ..core import colors as C  # noqa: E402
from ..core import xfconf  # noqa: E402

# ---------------------------------------------------------------- utilitaires cairo


def rgb(cr, hexc, a=1.0):
    r, g, b = C.to_rgb(hexc)
    cr.set_source_rgba(r, g, b, a)


def rounded_rect(cr, x, y, w, h, r):
    r = max(0, min(r, w / 2, h / 2))
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()


def paint_pixbuf(cr, pb, x, y, w=None, h=None):
    if pb is None:
        return
    if w and h and (pb.get_width() != w or pb.get_height() != h):
        pb = pb.scale_simple(max(1, int(w)), max(1, int(h)), GdkPixbuf.InterpType.BILINEAR)
    Gdk.cairo_set_source_pixbuf(cr, pb, x, y)
    cr.paint()


def cover_pixbuf(cr, pb, w, h, radius=0):
    """Dessine pb en mode « couvrir » dans un rectangle w×h."""
    if pb is None:
        return
    pw, ph = pb.get_width(), pb.get_height()
    s = max(w / pw, h / ph)
    nw, nh = max(1, int(pw * s)), max(1, int(ph * s))
    scaled = pb.scale_simple(nw, nh, GdkPixbuf.InterpType.BILINEAR)
    cr.save()
    rounded_rect(cr, 0, 0, w, h, radius)
    cr.clip()
    Gdk.cairo_set_source_pixbuf(cr, scaled, (w - nw) / 2, (h - nh) / 2)
    cr.paint()
    cr.restore()


# ---------------------------------------------------------------- couleurs d'un thème GTK

_COLOR_KEYS = {
    "bg": ["theme_bg_color", "window_bg_color", "bg_color"],
    "fg": ["theme_fg_color", "window_fg_color", "fg_color"],
    "base": ["theme_base_color", "view_bg_color", "base_color"],
    "accent": ["theme_selected_bg_color", "accent_bg_color", "selected_bg_color", "accent_color"],
    "header": ["headerbar_bg_color", "wm_bg", "titlebar_bg_color", "theme_bg_color"],
}


def _read_gtk_css(theme_dir):
    d = Path(theme_dir) / "gtk-3.0"
    css = ""
    f = d / "gtk.css"
    if f.is_file():
        try:
            css = f.read_text(errors="replace")
        except OSError:
            css = ""
    res_file = d / "gtk.gresource"
    if res_file.is_file() and ("resource://" in css or not css.strip()):
        try:
            res = Gio.Resource.load(str(res_file))
            found = _find_in_resource(res, "/", "gtk.css")
            if found:
                data = res.lookup_data(found, Gio.ResourceLookupFlags.NONE)
                css = data.get_data().decode(errors="replace") + css
        except GLib.Error:
            pass
    return css


def _find_in_resource(res, path, name, depth=0):
    if depth > 8:
        return None
    try:
        children = res.enumerate_children(path, Gio.ResourceLookupFlags.NONE)
    except GLib.Error:
        return None
    for c in children:
        if c == name:
            return path + c
    for c in children:
        if c.endswith("/"):
            r = _find_in_resource(res, path + c, name, depth + 1)
            if r:
                return r
    return None


def _parse_color(value, defs, depth=0):
    value = value.strip().rstrip(";").strip()
    if depth > 6:
        return None
    if value.startswith("@"):
        ref = defs.get(value[1:])
        return _parse_color(ref, defs, depth + 1) if ref else None
    m = re.match(r"(shade|lighter|darker|alpha|mix)\s*\((.*)\)$", value, re.S)
    if m:
        fn, args = m.group(1), m.group(2)
        parts = _split_args(args)
        base = _parse_color(parts[0], defs, depth + 1) if parts else None
        if base is None:
            return None
        if fn == "shade" and len(parts) > 1:
            try:
                k = float(parts[1])
            except ValueError:
                return base
            return C.lighten(base, k - 1) if k > 1 else C.darken(base, 1 - k)
        if fn == "lighter":
            return C.lighten(base, 0.1)
        if fn == "darker":
            return C.darken(base, 0.1)
        if fn == "alpha":
            return base
        if fn == "mix" and len(parts) > 2:
            other = _parse_color(parts[1], defs, depth + 1)
            try:
                return C.mix(base, other, float(parts[2])) if other else base
            except ValueError:
                return base
        return base
    rgba = Gdk.RGBA()
    if rgba.parse(value):
        return C.to_hex((rgba.red, rgba.green, rgba.blue))
    return None


def _split_args(s):
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


@lru_cache(maxsize=512)
def gtk_theme_colors(theme_dir):
    css = _read_gtk_css(theme_dir)
    defs = dict(re.findall(r"@define-color\s+([\w-]+)\s+([^;]+);", css))
    out = {}
    for key, names in _COLOR_KEYS.items():
        for n in names:
            if n in defs:
                c = _parse_color(defs[n], defs)
                if c:
                    out[key] = c
                    break
    if "bg" not in out:
        m = re.search(r"(?:^|\})\s*window\.background\s*\{[^}]*?background-color:\s*([^;]+);", css)
        if m:
            out["bg"] = _parse_color(m.group(1), defs) or "#e0e0e0"
    dark_name = "dark" in Path(theme_dir).name.lower()
    bg = out.get("bg") or ("#2b2b2b" if dark_name else "#f2f2f2")
    fg = out.get("fg") or C.readable_on(bg, "#eeeeee", "#2b2b2b")
    return {
        "bg": bg,
        "fg": fg,
        "base": out.get("base") or (C.darken(bg, 0.1) if C.is_dark(bg) else C.lighten(bg, 0.6)),
        "accent": out.get("accent") or "#3584e4",
        "header": out.get("header") or C.shade(bg, 0.05),
        "found": bool(out),
    }


# ---------------------------------------------------------------- maquette de fenêtre

def draw_window_mock(cr, w, h, col, style="windows", radius=8, show_title=True):
    """Dessine une petite fenêtre factice avec les couleurs `col`."""
    bg, fg, base, accent = col["bg"], col["fg"], col["base"], col["accent"]
    header = col.get("header", C.shade(bg, 0.05))
    pad = 6
    x, y, ww, hh = pad, pad, w - 2 * pad, h - 2 * pad
    r = min(radius, 14)
    # ombre
    cr.save()
    rounded_rect(cr, x + 1, y + 3, ww, hh, r)
    cr.set_source_rgba(0, 0, 0, 0.18)
    cr.fill()
    cr.restore()
    rounded_rect(cr, x, y, ww, hh, r)
    rgb(cr, bg)
    cr.fill()
    # barre de titre
    th = max(16, hh * 0.16)
    cr.save()
    rounded_rect(cr, x, y, ww, hh, r)
    cr.clip()
    rgb(cr, header)
    cr.rectangle(x, y, ww, th)
    cr.fill()
    # boutons
    cy = y + th / 2
    if style in ("macos", "circles"):
        cols = [col.get("red", "#ff5f57"), col.get("yellow", "#febc2e"), col.get("green", "#28c840")]
        if style == "circles":
            cols = [col.get("red", "#ff5f57"), accent, accent]
        for i, c in enumerate(cols):
            cr.arc(x + 12 + i * 13, cy, 4.2, 0, 2 * math.pi)
            rgb(cr, c)
            cr.fill()
    else:
        rgb(cr, fg, 0.8)
        cr.set_line_width(1.2)
        bx = x + ww - 12
        cr.move_to(bx - 3.5, cy - 3.5)
        cr.line_to(bx + 3.5, cy + 3.5)
        cr.move_to(bx + 3.5, cy - 3.5)
        cr.line_to(bx - 3.5, cy + 3.5)
        cr.stroke()
        cr.rectangle(bx - 20 - 3.5, cy - 3.5, 7, 7)
        cr.stroke()
        cr.move_to(bx - 40 - 3.5, cy + 1)
        cr.line_to(bx - 40 + 3.5, cy + 1)
        cr.stroke()
    if show_title:
        rgb(cr, fg, 0.55)
        rounded_rect(cr, x + ww / 2 - 22, cy - 2.5, 44, 5, 2.5)
        cr.fill()
    # barre latérale
    sw = ww * 0.28
    rgb(cr, C.mix(bg, header, 0.6))
    cr.rectangle(x, y + th, sw, hh - th)
    cr.fill()
    for i in range(4):
        yy = y + th + 10 + i * 13
        if yy + 8 > y + hh:
            break
        if i == 0:
            rgb(cr, accent)
            rounded_rect(cr, x + 4, yy - 3, sw - 8, 11, 3)
            cr.fill()
            rgb(cr, C.readable_on(accent), 0.9)
        else:
            rgb(cr, fg, 0.45)
        rounded_rect(cr, x + 9, yy + 1, sw * 0.5, 3.5, 1.5)
        cr.fill()
    # contenu
    cx = x + sw + 8
    cw = ww - sw - 16
    rgb(cr, base)
    rounded_rect(cr, cx, y + th + 8, cw, (hh - th) * 0.42, 4)
    cr.fill()
    for i in range(3):
        yy = y + th + 15 + i * 9
        if yy > y + th + 8 + (hh - th) * 0.42 - 5:
            break
        rgb(cr, fg, 0.5 if i else 0.75)
        rounded_rect(cr, cx + 6, yy, cw * (0.7 - i * 0.15), 3.5, 1.5)
        cr.fill()
    # bouton d'accent + bouton normal + interrupteur
    by = y + th + 14 + (hh - th) * 0.42
    bh = max(10, hh * 0.11)
    if by + bh < y + hh - 3:
        rgb(cr, accent)
        rounded_rect(cr, cx, by, cw * 0.38, bh, min(r, bh / 2))
        cr.fill()
        rgb(cr, C.shade(bg, 0.1))
        rounded_rect(cr, cx + cw * 0.42, by, cw * 0.3, bh, min(r, bh / 2))
        cr.fill()
        sx = cx + cw * 0.78
        rgb(cr, accent)
        rounded_rect(cr, sx, by + 1, cw * 0.22, bh - 2, (bh - 2) / 2)
        cr.fill()
        rgb(cr, "#ffffff")
        cr.arc(sx + cw * 0.22 - (bh - 2) / 2, by + bh / 2, (bh - 2) / 2 - 1.5, 0, 2 * math.pi)
        cr.fill()
    cr.restore()


# ---------------------------------------------------------------- xfwm4

def _load_wm_image(d, name):
    for ext in ("png", "svg", "xpm"):
        f = d / f"{name}.{ext}"
        if f.is_file():
            try:
                return GdkPixbuf.Pixbuf.new_from_file(str(f))
            except GLib.Error:
                return None
    return None


@lru_cache(maxsize=256)
def _wm_parts(theme_dir, state):
    d = Path(theme_dir) / "xfwm4"
    parts = {}
    for n in ("top-left", "top-right", "title-1", "title-2", "title-3", "title-4", "title-5",
              "left", "right", "bottom", "bottom-left", "bottom-right"):
        parts[n] = _load_wm_image(d, f"{n}-{state}")
    for b in ("close", "hide", "maximize", "menu", "shade", "stick"):
        parts["btn-" + b] = _load_wm_image(d, f"{b}-{state}")
    return parts


def draw_xfwm4(cr, w, h, theme_dir, body="#f0f0f0"):
    parts = _wm_parts(str(theme_dir), "active")
    tl, tr = parts.get("top-left"), parts.get("top-right")
    t3 = parts.get("title-3") or parts.get("title-1")
    if not t3:
        rgb(cr, "#888888")
        cr.select_font_face("Sans")
        cr.set_font_size(11)
        cr.move_to(10, h / 2)
        cr.show_text("Aperçu indisponible")
        return
    th = t3.get_height()
    x0 = 8
    width = w - 16
    y0 = max(6, (h - (th + 50)) / 2)
    # corps de fenêtre
    rgb(cr, body)
    cr.rectangle(x0, y0 + th, width, h - y0 - th - 8)
    cr.fill()
    lw = parts["left"].get_width() if parts.get("left") else 0
    rw = parts["right"].get_width() if parts.get("right") else 0
    bh = parts["bottom"].get_height() if parts.get("bottom") else 0
    bottom_y = h - 8 - bh
    if parts.get("left"):
        paint_pixbuf(cr, parts["left"], x0, y0 + th, lw, bottom_y - y0 - th)
    if parts.get("right"):
        paint_pixbuf(cr, parts["right"], x0 + width - rw, y0 + th, rw, bottom_y - y0 - th)
    if parts.get("bottom"):
        paint_pixbuf(cr, parts["bottom"], x0, bottom_y, width, bh)
    # barre de titre
    lw_t = tl.get_width() if tl else 0
    rw_t = tr.get_width() if tr else 0
    paint_pixbuf(cr, t3, x0 + lw_t, y0, width - lw_t - rw_t, th)
    if tl:
        paint_pixbuf(cr, tl, x0, y0)
    if tr:
        paint_pixbuf(cr, tr, x0 + width - rw_t, y0)
    layout = xfconf.get("xfwm4", "/general/button_layout", "O|HMC") or "O|HMC"
    left, _, right = layout.partition("|")
    keymap = {"O": "menu", "H": "hide", "M": "maximize", "C": "close", "S": "shade", "T": "stick"}
    x = x0 + lw_t
    for k in left:
        pb = parts.get("btn-" + keymap.get(k, ""))
        if pb:
            paint_pixbuf(cr, pb, x, y0)
            x += pb.get_width()
    x = x0 + width - rw_t
    for k in reversed(right):
        pb = parts.get("btn-" + keymap.get(k, ""))
        if pb:
            x -= pb.get_width()
            paint_pixbuf(cr, pb, x, y0)


# ---------------------------------------------------------------- icônes

ICON_SAMPLES = ["folder", "user-home", "web-browser", "utilities-terminal",
                "accessories-text-editor", "preferences-system", "multimedia-video-player",
                "system-file-manager", "accessories-calculator", "image-viewer"]
ICON_FALLBACKS = {
    "web-browser": ["firefox", "internet-web-browser", "applications-internet"],
    "preferences-system": ["preferences-desktop", "systemsettings", "gnome-settings"],
    "multimedia-video-player": ["vlc", "totem", "applications-multimedia"],
    "system-file-manager": ["thunar", "org.xfce.thunar", "file-manager"],
    "image-viewer": ["eog", "ristretto", "org.xfce.ristretto", "image-x-generic"],
    "accessories-calculator": ["gnome-calculator", "galculator", "calc"],
}


_icon_themes = {}


def icon_theme(name):
    t = _icon_themes.get(name)
    if t is None:
        t = Gtk.IconTheme.new()
        t.set_custom_theme(name)
        _icon_themes[name] = t
    return t


@lru_cache(maxsize=2048)
def theme_icon(theme_name, icon, size):
    t = icon_theme(theme_name)
    for n in [icon] + ICON_FALLBACKS.get(icon, []):
        try:
            info = t.lookup_icon(n, size, Gtk.IconLookupFlags.FORCE_SIZE)
        except GLib.Error:
            info = None
        if info is None:
            continue
        # On évite les icônes venant d'un thème de repli (hicolor/Adwaita) quand c'est possible
        try:
            return info.load_icon()
        except GLib.Error:
            continue
    return None


def draw_icons(cr, w, h, theme_name, count=6, size=40):
    gap = 8
    n = min(count, max(1, int((w - gap) // (size + gap))))
    total = n * size + (n - 1) * gap
    x = (w - total) / 2
    y = (h - size) / 2
    for icon in ICON_SAMPLES[:n]:
        pb = theme_icon(theme_name, icon, size)
        if pb:
            paint_pixbuf(cr, pb, x, y, size, size)
        x += size + gap


# ---------------------------------------------------------------- curseurs (format Xcursor)

CURSOR_SAMPLES = [["left_ptr", "default", "arrow"], ["hand2", "pointer", "hand1"],
                  ["xterm", "text", "ibeam"], ["watch", "wait", "progress"],
                  ["fleur", "move", "all-scroll"]]


@lru_cache(maxsize=1024)
def load_xcursor(path, nominal=32):
    """Lit la première image d'un fichier Xcursor et renvoie une surface cairo."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    if data[:4] != b"Xcur":
        return None
    try:
        _, _, ntoc = struct.unpack_from("<III", data, 4)
        best = None
        for i in range(ntoc):
            typ, sub, pos = struct.unpack_from("<III", data, 16 + i * 12)
            if typ != 0xFFFD0002:
                continue
            if best is None or abs(sub - nominal) < abs(best[0] - nominal):
                best = (sub, pos)
        if best is None:
            return None
        pos = best[1]
        _, typ, _, _, width, height, _, _, _ = struct.unpack_from("<IIIIIIIII", data, pos)
        start = pos + 36
        pixels = bytearray(data[start:start + width * height * 4])
        if len(pixels) < width * height * 4:
            return None
        stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, width)
        if stride != width * 4:
            return None
        return cairo.ImageSurface.create_for_data(pixels, cairo.FORMAT_ARGB32, width, height, stride)
    except struct.error:
        return None


def cursor_file(theme_dir, names):
    d = Path(theme_dir) / "cursors"
    for n in names:
        f = d / n
        if f.exists():
            return str(f.resolve())
    return None


def draw_cursors(cr, w, h, theme_dir, bg=None):
    items = []
    for names in CURSOR_SAMPLES:
        f = cursor_file(theme_dir, names)
        if f:
            s = load_xcursor(f)
            if s:
                items.append(s)
    if not items:
        return
    size = 32
    gap = 14
    total = len(items) * size + (len(items) - 1) * gap
    x = (w - total) / 2
    y = (h - size) / 2
    for s in items:
        cr.save()
        sc = size / max(s.get_width(), s.get_height())
        cr.translate(x, y)
        cr.scale(sc, sc)
        cr.set_source_surface(s, 0, 0)
        cr.paint()
        cr.restore()
        x += size + gap


# ---------------------------------------------------------------- Plank


def _plank_color(v, default):
    try:
        r, g, b, a = (int(float(x)) for x in v.split(";;"))
        return (r / 255, g / 255, b / 255, a / 255)
    except (ValueError, AttributeError):
        return default


@lru_cache(maxsize=256)
def plank_theme(theme_dir):
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        cp.read_string((Path(theme_dir) / "dock.theme").read_text(errors="replace"))
    except (OSError, configparser.Error):
        return {}
    s = dict(cp.items("PlankTheme")) if cp.has_section("PlankTheme") else {}
    return {
        "fill_start": _plank_color(s.get("fillstartcolor"), (0.2, 0.2, 0.2, 0.8)),
        "fill_end": _plank_color(s.get("fillendcolor"), (0.15, 0.15, 0.15, 0.8)),
        "outer": _plank_color(s.get("outerstrokecolor"), (0, 0, 0, 0.5)),
        "inner": _plank_color(s.get("innerstrokecolor"), (1, 1, 1, 0.1)),
        "round": float(s.get("toproundness", 4) or 4),
    }


def draw_plank(cr, w, h, theme_dir, icon_theme_name=None):
    t = plank_theme(str(theme_dir))
    n = 6
    size = 30
    gap = 8
    dw = n * size + (n + 1) * gap
    dh = size + 14
    x = (w - dw) / 2
    y = h - dh - 8
    r = min(t.get("round", 4), dh / 2)
    grad = cairo.LinearGradient(0, y, 0, y + dh)
    grad.add_color_stop_rgba(0, *t.get("fill_start", (0.2, 0.2, 0.2, 0.8)))
    grad.add_color_stop_rgba(1, *t.get("fill_end", (0.15, 0.15, 0.15, 0.8)))
    rounded_rect(cr, x, y, dw, dh + r, r)
    cr.set_source(grad)
    cr.fill_preserve()
    cr.set_source_rgba(*t.get("outer", (0, 0, 0, 0.5)))
    cr.set_line_width(1)
    cr.stroke()
    name = icon_theme_name or xfconf.get("xsettings", "/Net/IconThemeName", "hicolor")
    for i, icon in enumerate(["system-file-manager", "web-browser", "utilities-terminal",
                              "accessories-text-editor", "multimedia-video-player",
                              "preferences-system"]):
        pb = theme_icon(name, icon, size)
        if pb:
            paint_pixbuf(cr, pb, x + gap + i * (size + gap), y + 6, size, size)
