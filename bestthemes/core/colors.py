"""Petits utilitaires de couleur (hex <-> rgb, mélange, luminance)."""
import colorsys


def to_rgb(h):
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02x}" for c in rgb[:3])


def mix(a, b, t):
    """Mélange a vers b (t=0 -> a, t=1 -> b)."""
    ra, rb = to_rgb(a), to_rgb(b)
    return to_hex(tuple(x + (y - x) * t for x, y in zip(ra, rb)))


def lighten(c, t):
    return mix(c, "#ffffff", t)


def darken(c, t):
    return mix(c, "#000000", t)


def luminance(c):
    def ch(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in to_rgb(c))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def is_dark(c):
    return luminance(c) < 0.25


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable_on(bg, light="#ffffff", dark="#1b1b1b"):
    return light if contrast(bg, light) >= contrast(bg, dark) else dark


def shade(c, t):
    """Éclaircit les couleurs sombres et assombrit les claires (pour les survols)."""
    return lighten(c, t) if is_dark(c) else darken(c, t)


def rgba(c, a):
    r, g, b = (round(v * 255) for v in to_rgb(c))
    return f"rgba({r},{g},{b},{a})"


def plank_color(c, a=255):
    r, g, b = (round(v * 255) for v in to_rgb(c))
    return f"{r};;{g};;{b};;{a}"


def rotate_hue(c, deg):
    h, l, s = colorsys.rgb_to_hls(*to_rgb(c))
    return to_hex(colorsys.hls_to_rgb((h + deg / 360) % 1, l, s))
