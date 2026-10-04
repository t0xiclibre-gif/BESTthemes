"""Génération de fonds d'écran assortis aux palettes (dessinés avec Cairo)."""
import math
import random
import zlib
from pathlib import Path

import cairo

from . import colors as C
from . import paths

STYLES = {
    "gradient": "Dégradé doux",
    "waves": "Vagues",
    "mountains": "Montagnes",
    "blobs": "Bulles de lumière",
    "lowpoly": "Low-poly",
    "aurora": "Aurore",
    "stars": "Ciel étoilé",
    "rings": "Anneaux",
    "mesh": "Dégradé fluide",
    "ribbons": "Rubans de soie",
    "synthwave": "Synthwave",
    "nebula": "Nébuleuse",
    "planet": "Planète",
    "dunes": "Dunes",
    "ocean": "Océan au couchant",
    "forest": "Forêt dans la brume",
    "city": "Ville la nuit",
    "clouds": "Mer de nuages",
    "bokeh": "Bokeh",
    "topo": "Courbes de niveau",
    "glass": "Verre dépoli",
    "hexagons": "Hexagones",
}


def _src(ctx, hexc, a=1.0):
    r, g, b = C.to_rgb(hexc)
    ctx.set_source_rgba(r, g, b, a)


def _lin(x0, y0, x1, y1, stops):
    g = cairo.LinearGradient(x0, y0, x1, y1)
    for off, col, a in stops:
        r, gg, b = C.to_rgb(col)
        g.add_color_stop_rgba(off, r, gg, b, a)
    return g


def _palette_colors(p):
    bg = p["bg"]
    accent = p["accent"]
    a2 = p.get("accent2") or C.rotate_hue(accent, 40)
    a3 = p.get("accent3") or C.rotate_hue(accent, -50)
    deep = C.darken(bg, 0.35) if C.is_dark(bg) else C.darken(bg, 0.05)
    return bg, deep, accent, a2, a3


def _gradient(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    ctx.set_source(_lin(0, 0, w, h, [(0, C.mix(deep, a, 0.35), 1), (0.55, C.mix(bg, a2, 0.25), 1),
                                     (1, C.mix(deep, a3, 0.4), 1)]))
    ctx.paint()
    _vignette(ctx, w, h, 0.35)


def _vignette(ctx, w, h, strength):
    g = cairo.RadialGradient(w / 2, h / 2, min(w, h) * 0.3, w / 2, h / 2, max(w, h) * 0.75)
    g.add_color_stop_rgba(0, 0, 0, 0, 0)
    g.add_color_stop_rgba(1, 0, 0, 0, strength)
    ctx.set_source(g)
    ctx.paint()


def _waves(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    ctx.set_source(_lin(0, 0, 0, h, [(0, deep, 1), (1, bg, 1)]))
    ctx.paint()
    layers = 6
    for i in range(layers):
        t = i / (layers - 1)
        col = C.mix(C.mix(a, a2, t), deep, 0.25 + 0.1 * (1 - t))
        base_y = h * (0.45 + 0.09 * i)
        amp = h * (0.05 + 0.02 * rnd.random())
        freq = (1.2 + rnd.random() * 1.3) * 2 * math.pi / w
        phase = rnd.random() * 6.28
        ctx.move_to(0, h)
        for x in range(0, w + 8, 8):
            y = base_y + amp * math.sin(x * freq + phase) + amp * 0.4 * math.sin(x * freq * 2.3 + phase)
            ctx.line_to(x, y)
        ctx.line_to(w, h)
        ctx.close_path()
        ctx.set_source(_lin(0, base_y - amp, 0, h, [(0, col, 0.85), (1, C.darken(col, 0.4), 0.95)]))
        ctx.fill()
    _vignette(ctx, w, h, 0.3)


def _mountains(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    ctx.set_source(_lin(0, 0, 0, h, [(0, C.mix(deep, a2, 0.3), 1), (0.6, C.mix(bg, a, 0.45), 1),
                                     (1, C.lighten(a, 0.3), 1)]))
    ctx.paint()
    # soleil
    sx, sy = w * (0.3 + rnd.random() * 0.4), h * 0.38
    g = cairo.RadialGradient(sx, sy, 0, sx, sy, h * 0.35)
    r, gg, b = C.to_rgb(C.lighten(a3, 0.4))
    g.add_color_stop_rgba(0, r, gg, b, 0.9)
    g.add_color_stop_rgba(0.25, r, gg, b, 0.5)
    g.add_color_stop_rgba(1, r, gg, b, 0)
    ctx.set_source(g)
    ctx.paint()
    layers = 5
    for i in range(layers):
        t = i / (layers - 1)
        col = C.mix(C.mix(a, deep, 0.35), deep, t * 0.9)
        base = h * (0.5 + 0.1 * i)
        ctx.move_to(0, h)
        x = 0
        y = base
        ctx.line_to(0, y)
        while x < w:
            x += w * (0.04 + rnd.random() * 0.08)
            y = base - h * (0.03 + rnd.random() * (0.2 - 0.03 * i))
            ctx.line_to(x, y)
            x += w * (0.03 + rnd.random() * 0.07)
            ctx.line_to(x, base + rnd.random() * h * 0.03)
        ctx.line_to(w, h)
        ctx.close_path()
        _src(ctx, col)
        ctx.fill()


def _blobs(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    _src(ctx, deep)
    ctx.paint()
    cols = [a, a2, a3, C.mix(a, a2, 0.5)]
    for i in range(9):
        x, y = rnd.random() * w, rnd.random() * h
        rad = min(w, h) * (0.25 + rnd.random() * 0.35)
        g = cairo.RadialGradient(x, y, 0, x, y, rad)
        r, gg, b = C.to_rgb(cols[i % len(cols)])
        g.add_color_stop_rgba(0, r, gg, b, 0.55)
        g.add_color_stop_rgba(1, r, gg, b, 0)
        ctx.set_source(g)
        ctx.paint()
    _vignette(ctx, w, h, 0.25)


def _lowpoly(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    cell = max(w, h) / 14
    cols = int(w / cell) + 3
    rows = int(h / cell) + 3
    pts = [[((cx - 1) * cell + (rnd.random() - 0.5) * cell * 0.8,
             (cy - 1) * cell + (rnd.random() - 0.5) * cell * 0.8) for cx in range(cols)]
           for cy in range(rows)]

    def color_at(x, y):
        t = max(0.0, min(1.0, (x / w) * 0.6 + (y / h) * 0.4))
        base = C.mix(C.mix(deep, a, 0.55), C.mix(deep, a2, 0.55), t)
        return C.shade(base, rnd.random() * 0.12)

    for cy in range(rows - 1):
        for cx in range(cols - 1):
            p1, p2, p3, p4 = pts[cy][cx], pts[cy][cx + 1], pts[cy + 1][cx], pts[cy + 1][cx + 1]
            for tri in ((p1, p2, p3), (p2, p4, p3)):
                mx = sum(q[0] for q in tri) / 3
                my = sum(q[1] for q in tri) / 3
                ctx.move_to(*tri[0])
                ctx.line_to(*tri[1])
                ctx.line_to(*tri[2])
                ctx.close_path()
                _src(ctx, color_at(mx, my))
                ctx.fill_preserve()
                ctx.set_line_width(1)
                ctx.stroke()
    _vignette(ctx, w, h, 0.3)


def _aurora(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    ctx.set_source(_lin(0, 0, 0, h, [(0, C.darken(deep, 0.3), 1), (1, deep, 1)]))
    ctx.paint()
    _stars_layer(ctx, w, h, rnd, 180, 0.6)
    for i, col in enumerate((a, a2, a3)):
        base = h * (0.25 + 0.12 * i)
        amp = h * 0.08
        phase = rnd.random() * 6.28
        for k in range(26):
            ctx.new_path()
            off = k * h * 0.008
            for x in range(0, w + 10, 10):
                y = base + amp * math.sin(x / w * 5 + phase) + off
                ctx.line_to(x, y) if x else ctx.move_to(x, y)
            r, g, b = C.to_rgb(col)
            ctx.set_source_rgba(r, g, b, 0.05 * (1 - k / 26))
            ctx.set_line_width(h * 0.05)
            ctx.stroke()
    ctx.move_to(0, h)
    for x in range(0, w + 10, 10):
        ctx.line_to(x, h * 0.88 + h * 0.03 * math.sin(x / w * 9))
    ctx.line_to(w, h)
    ctx.close_path()
    _src(ctx, C.darken(deep, 0.5))
    ctx.fill()


def _stars_layer(ctx, w, h, rnd, n, alpha):
    for _ in range(n):
        x, y = rnd.random() * w, rnd.random() * h
        r = rnd.random() * 1.6 + 0.3
        ctx.arc(x, y, r, 0, 2 * math.pi)
        ctx.set_source_rgba(1, 1, 1, alpha * rnd.random())
        ctx.fill()


def _stars(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    ctx.set_source(_lin(0, 0, w, h, [(0, C.darken(deep, 0.4), 1), (1, C.mix(deep, a, 0.3), 1)]))
    ctx.paint()
    for col in (a, a2):
        x, y = rnd.random() * w, rnd.random() * h
        g = cairo.RadialGradient(x, y, 0, x, y, max(w, h) * 0.45)
        r, gg, b = C.to_rgb(col)
        g.add_color_stop_rgba(0, r, gg, b, 0.35)
        g.add_color_stop_rgba(1, r, gg, b, 0)
        ctx.set_source(g)
        ctx.paint()
    _stars_layer(ctx, w, h, rnd, 600, 0.9)


def _rings(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    _src(ctx, deep)
    ctx.paint()
    cx, cy = w * 0.68, h * 0.55
    for i in range(18, 0, -1):
        t = i / 18
        ctx.arc(cx, cy, max(w, h) * 0.06 * i, 0, 2 * math.pi)
        _src(ctx, C.mix(C.mix(a, a2, t), deep, 0.3 + t * 0.5))
        ctx.fill()
    _vignette(ctx, w, h, 0.35)


# ----------------------------------------------------------------------- styles haute qualité


def _radial(ctx, x, y, r, col, a0, a1=0.0, mid=None):
    g = cairo.RadialGradient(x, y, 0, x, y, max(1.0, r))
    rr, gg, bb = C.to_rgb(col)
    g.add_color_stop_rgba(0, rr, gg, bb, a0)
    if mid is not None:
        g.add_color_stop_rgba(mid[0], rr, gg, bb, mid[1])
    g.add_color_stop_rgba(1, rr, gg, bb, a1)
    ctx.set_source(g)


def _spot(ctx, x, y, r, col, a0, a1=0.0, mid=None):
    """Halo radial dessiné seulement dans son disque (bien plus rapide que paint())."""
    _radial(ctx, x, y, r, col, a0, a1, mid)
    ctx.arc(x, y, max(1.0, r), 0, 2 * math.pi)
    ctx.fill()


def _grain(ctx, w, h, rnd, amount=0.045):
    """Grain très léger : évite les « marches » visibles dans les grands dégradés."""
    n = 128
    data = bytearray(n * n * 4)
    for i in range(n * n):
        a = int(rnd.random() * amount * 255)
        v = a if rnd.random() < 0.5 else 0  # prémultiplié : blanc ou noir translucide
        data[i * 4:i * 4 + 4] = bytes((v, v, v, a))
    tile = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, n, n, n * 4)
    pat = cairo.SurfacePattern(tile)
    pat.set_extend(cairo.EXTEND_REPEAT)
    pat.set_filter(cairo.FILTER_NEAREST)
    ctx.save()
    ctx.set_source(pat)
    ctx.paint()
    ctx.restore()


def _mesh(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    cols = [deep, C.mix(deep, a, 0.7), a, a2, a3, C.mix(a2, a3, 0.5), C.mix(bg, a, 0.5), C.lighten(a2, 0.25)]
    n = 3
    # la grille déborde de l'écran : ses bords courbes restent invisibles
    pts = [[(w * (-0.2 + 1.4 * i / n) + (rnd.random() - 0.5) * w * 0.2 * (0 < i < n),
             h * (-0.2 + 1.4 * j / n) + (rnd.random() - 0.5) * h * 0.2 * (0 < j < n)) for i in range(n + 1)]
           for j in range(n + 1)]
    vcol = [[rnd.choice(cols) for _ in range(n + 1)] for _ in range(n + 1)]
    m = cairo.MeshPattern()

    def ctrl(p0, p1):
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        j1, j2 = (rnd.random() - 0.5) * 0.35, (rnd.random() - 0.5) * 0.35
        return (p0[0] + dx / 3 - dy * j1, p0[1] + dy / 3 + dx * j1,
                p0[0] + dx * 2 / 3 - dy * j2, p0[1] + dy * 2 / 3 + dx * j2)

    edges = {}

    def edge(p0, p1):
        key = (p0, p1)
        if (p1, p0) in edges:
            c = edges[(p1, p0)]
            return (c[2], c[3], c[0], c[1])
        edges[key] = edges.get(key) or ctrl(p0, p1)
        return edges[key]

    for j in range(n):
        for i in range(n):
            c00, c10, c11, c01 = pts[j][i], pts[j][i + 1], pts[j + 1][i + 1], pts[j + 1][i]
            m.begin_patch()
            m.move_to(*c00)
            for q0, q1 in ((c00, c10), (c10, c11), (c11, c01), (c01, c00)):
                e = edge(q0, q1)
                m.curve_to(e[0], e[1], e[2], e[3], *q1)
            for k, (jj, ii) in enumerate(((j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i))):
                m.set_corner_color_rgb(k, *C.to_rgb(vcol[jj][ii]))
            m.end_patch()
    ctx.set_source(m)
    ctx.paint()
    for _ in range(4):
        _spot(ctx, rnd.random() * w, rnd.random() * h, max(w, h) * 0.4, rnd.choice((a, a2, a3)), 0.25)
    _vignette(ctx, w, h, 0.2)


def _ribbons(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    ctx.set_source(_lin(0, 0, w, h, [(0, C.darken(deep, 0.2), 1), (1, C.mix(deep, a, 0.25), 1)]))
    ctx.paint()
    for col in (a, a2, a3):
        y0 = h * (0.2 + rnd.random() * 0.6)
        pts = [(-w * 0.1, y0)]
        for k in range(1, 5):
            pts.append((w * k / 4 + (rnd.random() - 0.5) * w * 0.1, h * (0.15 + rnd.random() * 0.7)))
        spread = h * (0.12 + rnd.random() * 0.1)
        lines = 70
        ctx.set_line_width(max(1.0, h / 900))
        for i in range(lines):
            t = i / (lines - 1)
            off = (t - 0.5) * spread
            twist = math.sin(t * math.pi)
            ctx.new_path()
            ctx.move_to(pts[0][0], pts[0][1] + off)
            for k in range(1, len(pts)):
                x0, y0_ = pts[k - 1]
                x1, y1 = pts[k]
                o = off * (0.4 + 0.6 * math.cos(k * 1.3 + t * 2.0))
                ctx.curve_to(x0 + (x1 - x0) * 0.5, y0_ + o, x0 + (x1 - x0) * 0.5, y1 + o, x1, y1 + o)
            r, g, b = C.to_rgb(C.mix(col, "#ffffff", 0.25 * twist))
            ctx.set_source_rgba(r, g, b, 0.08 + 0.22 * twist)
            ctx.stroke()
    _radial(ctx, w * 0.5, h * 0.5, max(w, h) * 0.6, a, 0.12)
    ctx.paint()
    _vignette(ctx, w, h, 0.45)


def _synthwave(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    hz = h * 0.6
    night = C.darken(C.mix(deep, a2, 0.25), 0.35)
    ctx.set_source(_lin(0, 0, 0, hz, [(0, night, 1), (0.65, C.mix(night, a3, 0.5), 1), (1, C.mix(a, a3, 0.5), 1)]))
    ctx.rectangle(0, 0, w, hz)
    ctx.fill()
    _stars_layer(ctx, w, int(hz * 0.6), rnd, int(w * h / 9000), 0.7)
    sx, sr = w * 0.5, min(w, h) * 0.24
    sy = hz - sr * 0.35
    _radial(ctx, sx, sy, sr * 2.6, a3, 0.45)
    ctx.paint()
    ctx.save()
    ctx.arc(sx, sy, sr, 0, 2 * math.pi)
    ctx.clip()
    ctx.set_source(_lin(0, sy - sr, 0, sy + sr, [(0, C.lighten(a3, 0.45), 1), (0.55, a3, 1), (1, a, 1)]))
    ctx.paint()
    ctx.set_operator(cairo.OPERATOR_CLEAR)
    for i in range(9):
        t = i / 8
        yy = sy + sr * (0.05 + t * 0.95)
        ctx.rectangle(sx - sr, yy, sr * 2, sr * (0.015 + 0.05 * t))
    ctx.fill()
    ctx.restore()
    # redessine le ciel sous les bandes effacées
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_DEST_OVER)
    ctx.set_source(_lin(0, 0, 0, hz, [(0, night, 1), (1, C.mix(a, a3, 0.5), 1)]))
    ctx.rectangle(0, 0, w, hz)
    ctx.fill()
    ctx.restore()
    # montagnes
    for layer, col in ((0, C.mix(night, a, 0.35)), (1, C.darken(night, 0.2))):
        ctx.move_to(0, hz)
        x = 0
        while x < w:
            x += w * (0.03 + rnd.random() * 0.06)
            ctx.line_to(x, hz - h * (0.03 + rnd.random() * (0.12 - layer * 0.05)))
        ctx.line_to(w, hz)
        ctx.close_path()
        _src(ctx, col)
        ctx.fill()
    # sol + grille en perspective
    ctx.set_source(_lin(0, hz, 0, h, [(0, C.darken(night, 0.4), 1), (1, C.darken(night, 0.1), 1)]))
    ctx.rectangle(0, hz, w, h - hz)
    ctx.fill()
    _grid_lines(ctx, w, h, hz, a, 0.0)
    _radial(ctx, w / 2, hz, w * 0.5, a, 0.35)
    ctx.rectangle(0, hz - h * 0.02, w, h * 0.05)
    ctx.fill()


def _grid_lines(ctx, w, h, hz, col, phase, horizontal=True, vertical=True):
    """Grille lumineuse façon années 80 ; phase (0–1) la fait avancer."""
    r, g, b = C.to_rgb(col)
    lines = []
    for i in range(14 if horizontal else 0):
        z = (i + 1 - phase) / 14
        yy = hz + (h - hz) * (z ** 2.2)
        lines.append(((0, yy), (w, yy), z))
    for i in range(-16, 17) if vertical else ():
        lines.append(((w / 2 + i * w * 0.012, hz), (w / 2 + i * w * 0.16, h), 1.0))
    for width, alpha in ((max(3.0, h / 180), 0.18), (max(1.0, h / 700), 0.95)):
        ctx.set_line_width(width)
        for (x0, y0), (x1, y1), z in lines:
            ctx.move_to(x0, y0)
            ctx.line_to(x1, y1)
            ctx.set_source_rgba(r, g, b, alpha * min(1.0, 0.25 + z))
            ctx.stroke()


def _nebula_cloud(ctx, w, h, p, rnd, density=1.0):
    bg, deep, a, a2, a3 = _palette_colors(p)
    x, y = w * rnd.uniform(0.1, 0.3), h * rnd.uniform(0.3, 0.7)
    ang = rnd.uniform(-0.6, 0.6)
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_SCREEN)
    for i in range(int(70 * density)):
        t = i / (70 * density)
        x += math.cos(ang) * w * 0.012 / density
        y += math.sin(ang) * h * 0.012 / density
        ang += rnd.uniform(-0.35, 0.35)
        col = (a, a2, a3)[int(t * 3 + rnd.random()) % 3]
        _spot(ctx, x + rnd.gauss(0, w * 0.05), y + rnd.gauss(0, h * 0.06),
              max(w, h) * rnd.uniform(0.05, 0.16), col, rnd.uniform(0.08, 0.22))
    ctx.restore()


def _space(deep):
    """Fond d'espace : toujours sombre, même avec une palette claire."""
    return deep if C.is_dark(deep) and C.luminance(deep) < 0.08 else C.mix(deep, "#06070d", 0.85)


def _nebula(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    sp = _space(deep)
    ctx.set_source(_lin(0, 0, w, h, [(0, C.darken(sp, 0.5), 1), (1, C.darken(C.mix(sp, a2, 0.15), 0.3), 1)]))
    ctx.paint()
    _stars_layer(ctx, w, h, rnd, int(w * h / 2500), 0.5)
    _nebula_cloud(ctx, w, h, p, rnd)
    # poussières sombres
    for _ in range(14):
        _spot(ctx, rnd.random() * w, rnd.random() * h, max(w, h) * rnd.uniform(0.04, 0.1), "#000000", 0.12)
    _stars_layer(ctx, w, h, rnd, int(w * h / 9000), 0.95)
    for _ in range(int(w * h / 250000) + 3):
        _bright_star(ctx, rnd.random() * w, rnd.random() * h, min(w, h) * rnd.uniform(0.006, 0.015), "#ffffff")


def _bright_star(ctx, x, y, r, col, alpha=1.0):
    _radial(ctx, x, y, r * 4, col, 0.55 * alpha)
    ctx.arc(x, y, r * 4, 0, 2 * math.pi)
    ctx.fill()
    rr, gg, bb = C.to_rgb(col)
    ctx.set_line_width(max(0.6, r * 0.18))
    for dx, dy in ((1, 0), (0, 1)):
        g = cairo.LinearGradient(x - dx * r * 7, y - dy * r * 7, x + dx * r * 7, y + dy * r * 7)
        g.add_color_stop_rgba(0, rr, gg, bb, 0)
        g.add_color_stop_rgba(0.5, rr, gg, bb, 0.8 * alpha)
        g.add_color_stop_rgba(1, rr, gg, bb, 0)
        ctx.set_source(g)
        ctx.move_to(x - dx * r * 7, y - dy * r * 7)
        ctx.line_to(x + dx * r * 7, y + dy * r * 7)
        ctx.stroke()


def _planet(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    sp = _space(deep)
    ctx.set_source(_lin(0, 0, w, h, [(0, C.darken(sp, 0.5), 1), (1, C.darken(sp, 0.2), 1)]))
    ctx.paint()
    _stars_layer(ctx, w, h, rnd, int(w * h / 3000), 0.8)
    _nebula_cloud(ctx, w, h, p, rnd, 0.5)
    px, py, pr = w * 0.68, h * 0.72, min(w, h) * 0.42
    # halo d'atmosphère
    _spot(ctx, px, py, pr * 1.25, a2, 0.0, 0.0, (0.78, 0.55))
    # anneau arrière
    _ring(ctx, px, py, pr, a3, back=True)
    ctx.save()
    ctx.arc(px, py, pr, 0, 2 * math.pi)
    ctx.clip()
    ctx.set_source(_lin(px - pr, py - pr, px + pr, py + pr, [(0, C.lighten(a, 0.25), 1), (0.6, C.mix(a, a2, 0.5), 1),
                                                           (1, C.darken(a2, 0.5), 1)]))
    ctx.paint()
    for i in range(14):  # bandes
        yy = py - pr + (i + rnd.random()) * pr * 2 / 14
        ctx.rectangle(px - pr, yy, pr * 2, pr * rnd.uniform(0.02, 0.08))
        r_, g_, b_ = C.to_rgb(rnd.choice((a, a2, a3, "#ffffff")))
        ctx.set_source_rgba(r_, g_, b_, 0.12)
        ctx.fill()
    g = cairo.RadialGradient(px - pr * 0.45, py - pr * 0.45, pr * 0.1, px, py, pr * 1.05)
    g.add_color_stop_rgba(0, 1, 1, 1, 0.25)
    g.add_color_stop_rgba(0.6, 0, 0, 0, 0.1)
    g.add_color_stop_rgba(1, 0, 0, 0, 0.85)
    ctx.set_source(g)
    ctx.paint()
    ctx.restore()
    _ring(ctx, px, py, pr, a3, back=False)
    # lune
    mx, my, mr = w * 0.22, h * 0.25, pr * 0.12
    ctx.arc(mx, my, mr, 0, 2 * math.pi)
    g = cairo.RadialGradient(mx - mr * 0.4, my - mr * 0.4, 0, mx, my, mr)
    g.add_color_stop_rgb(0, *C.to_rgb(C.lighten(a2, 0.5)))
    g.add_color_stop_rgb(1, *C.to_rgb(C.darken(a2, 0.6)))
    ctx.set_source(g)
    ctx.fill()


def _ring(ctx, px, py, pr, col, back):
    ctx.save()
    ctx.translate(px, py)
    ctx.rotate(-0.35)
    ctx.scale(1, 0.22)
    if back:
        ctx.rectangle(-pr * 3, -pr * 3, pr * 6, pr * 3)
    else:
        ctx.rectangle(-pr * 3, 0, pr * 6, pr * 3)
    ctx.clip()
    r, g, b = C.to_rgb(col)
    for i in range(26):
        rad = pr * (1.25 + i * 0.03)
        ctx.arc(0, 0, rad, 0, 2 * math.pi)
        ctx.set_line_width(pr * 0.025)
        ctx.set_source_rgba(r, g, b, 0.08 + 0.25 * abs(math.sin(i * 0.7)))
        ctx.stroke()
    ctx.restore()


def _smooth_layer(ctx, w, base, amp, rnd, steps=7):
    pts = [(-w * 0.05, base + (rnd.random() - 0.5) * amp)]
    for k in range(1, steps + 1):
        pts.append((w * 1.05 * k / steps, base + (rnd.random() - 0.5) * amp))
    ctx.move_to(*pts[0])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        mx = (x0 + x1) / 2
        ctx.curve_to(mx, y0, mx, y1, x1, y1)
    return pts


def _dunes(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    warm = C.mix(a3, "#f0b070", 0.4)
    ctx.set_source(_lin(0, 0, 0, h * 0.6, [(0, C.mix(deep, a2, 0.4), 1), (1, C.lighten(warm, 0.35), 1)]))
    ctx.paint()
    sx, sy = w * rnd.uniform(0.25, 0.75), h * 0.33
    _radial(ctx, sx, sy, h * 0.5, C.lighten(warm, 0.5), 0.75, 0, (0.08, 0.6))
    ctx.paint()
    for i in range(6):
        t = i / 5
        base = h * (0.48 + 0.1 * i)
        _smooth_layer(ctx, w, base, h * (0.16 - 0.015 * i), rnd, 4 + i)
        ctx.line_to(w * 1.1, h)
        ctx.line_to(-w * 0.1, h)
        ctx.close_path()
        lit = C.mix(C.lighten(warm, 0.2 - 0.15 * t), C.darken(a, 0.2), t * 0.6)
        ctx.set_source(_lin(0, base - h * 0.1, w * 0.3, h, [(0, C.lighten(lit, 0.15), 1), (1, C.darken(lit, 0.45), 1)]))
        ctx.fill()
    _vignette(ctx, w, h, 0.3)


def _ocean(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    hz = h * 0.58
    sun = C.mix(a3, "#ffb36b", 0.5)
    ctx.set_source(_lin(0, 0, 0, hz, [(0, C.mix(deep, a2, 0.35), 1), (0.6, C.mix(a, sun, 0.5), 1),
                                      (1, C.lighten(sun, 0.35), 1)]))
    ctx.rectangle(0, 0, w, hz)
    ctx.fill()
    sx = w * rnd.uniform(0.35, 0.65)
    _radial(ctx, sx, hz, h * 0.6, C.lighten(sun, 0.5), 0.85, 0, (0.06, 0.75))
    ctx.rectangle(0, 0, w, hz)
    ctx.fill()
    for _ in range(7):  # nuages étirés
        cy = rnd.uniform(0.1, 0.45) * hz
        ctx.save()
        ctx.translate(rnd.random() * w, cy)
        ctx.scale(1, 0.08)
        _radial(ctx, 0, 0, w * rnd.uniform(0.15, 0.3), C.mix(sun, "#ffffff", 0.3), 0.35)
        ctx.paint()
        ctx.restore()
    sea = C.darken(C.mix(deep, a, 0.35), 0.25)
    ctx.set_source(_lin(0, hz, 0, h, [(0, C.mix(sea, sun, 0.3), 1), (1, C.darken(sea, 0.4), 1)]))
    ctx.rectangle(0, hz, w, h - hz)
    ctx.fill()
    rr, gg, bb = C.to_rgb(C.lighten(sun, 0.4))
    for i in range(int(h * 0.5)):
        t = rnd.random() ** 1.7
        yy = hz + t * (h - hz)
        spread = w * (0.02 + 0.22 * t)
        xx = sx + rnd.gauss(0, spread * 0.5)
        ln = w * rnd.uniform(0.004, 0.03) * (1 + t * 2)
        ctx.rectangle(xx - ln / 2, yy, ln, max(1.0, h / 900) * (1 + t * 2))
        ctx.set_source_rgba(rr, gg, bb, 0.55 * (1 - t) + 0.05)
        ctx.fill()
    _vignette(ctx, w, h, 0.35)


def _pine(ctx, x, base, height, width):
    tiers = 5
    ctx.move_to(x, base - height)
    for i in range(1, tiers + 1):
        t = i / tiers
        yy = base - height + height * t * 0.92
        ww = width * (0.25 + 0.75 * t) / 2
        ctx.line_to(x + ww, yy)
        ctx.line_to(x + ww * 0.45, yy - height * 0.04)
    for i in range(tiers, 0, -1):
        t = i / tiers
        yy = base - height + height * t * 0.92
        ww = width * (0.25 + 0.75 * t) / 2
        ctx.line_to(x - ww * 0.45, yy - height * 0.04)
        ctx.line_to(x - ww, yy)
    ctx.close_path()
    ctx.rectangle(x - width * 0.04, base - height * 0.1, width * 0.08, height * 0.12)


def _forest(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    sky = C.mix(C.lighten(a2, 0.3), bg, 0.3)
    ctx.set_source(_lin(0, 0, 0, h, [(0, C.mix(deep, a, 0.3), 1), (0.55, sky, 1), (1, C.lighten(sky, 0.2), 1)]))
    ctx.paint()
    _radial(ctx, w * rnd.uniform(0.3, 0.7), h * 0.35, h * 0.5, C.lighten(a3, 0.5), 0.5)
    ctx.paint()
    layers = 6
    for i in range(layers):
        t = i / (layers - 1)
        base = h * (0.62 + 0.09 * i)
        col = C.mix(sky, C.darken(deep, 0.5), 0.25 + 0.75 * t)
        _src(ctx, col)
        ctx.rectangle(0, base - 2, w, h - base + 2)
        ctx.fill()
        x = -w * 0.02
        while x < w * 1.02:
            th = h * (0.12 + 0.12 * t) * rnd.uniform(0.6, 1.25)
            _pine(ctx, x, base + h * 0.01, th, th * 0.38)
            x += th * rnd.uniform(0.12, 0.3)
        ctx.fill()
        if i < layers - 1:  # brume entre les rangées
            ctx.set_source(_lin(0, base - h * 0.08, 0, base + h * 0.04, [(0, sky, 0), (1, sky, 0.45)]))
            ctx.rectangle(0, base - h * 0.08, w, h * 0.12)
            ctx.fill()
    _vignette(ctx, w, h, 0.3)


def _city(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    night = C.darken(deep, 0.55)
    ctx.set_source(_lin(0, 0, 0, h, [(0, night, 1), (0.7, C.mix(night, a2, 0.35), 1), (1, C.mix(night, a, 0.5), 1)]))
    ctx.paint()
    _stars_layer(ctx, w, int(h * 0.5), rnd, int(w * h / 6000), 0.7)
    mx, my, mr = w * rnd.uniform(0.15, 0.85), h * 0.2, min(w, h) * 0.05
    _radial(ctx, mx, my, mr * 5, "#ffffff", 0.18)
    ctx.paint()
    ctx.arc(mx, my, mr, 0, 2 * math.pi)
    _src(ctx, "#f4f1e6")
    ctx.fill()
    win_cols = ["#ffd479", "#ffe8b0", a, a3]
    for layer in range(3):
        t = layer / 2
        col = C.mix(C.mix(night, a2, 0.3), C.darken(night, 0.6), t)
        x = -rnd.random() * w * 0.05
        while x < w:
            bw = w * rnd.uniform(0.03, 0.07) * (1 + t * 0.4)
            bh = h * rnd.uniform(0.15, 0.45) * (1.15 - t * 0.35)
            top = h - bh
            _src(ctx, col)
            ctx.rectangle(x, top, bw, bh)
            ctx.fill()
            if layer == 2 or rnd.random() < 0.5 * t + 0.2:
                cell = max(3.0, w / 320)
                for yy in range(int(top + cell * 2), int(h - cell), int(cell * 2.2)):
                    for xx in range(int(x + cell), int(x + bw - cell), int(cell * 1.9)):
                        if rnd.random() < 0.22 + 0.2 * t:
                            r_, g_, b_ = C.to_rgb(rnd.choice(win_cols))
                            ctx.set_source_rgba(r_, g_, b_, rnd.uniform(0.4, 0.95) * (0.5 + t * 0.5))
                            ctx.rectangle(xx, yy, cell, cell * 1.2)
                            ctx.fill()
            x += bw + w * rnd.uniform(0.0, 0.01)
    ctx.set_source(_lin(0, h * 0.7, 0, h, [(0, a, 0), (1, a, 0.25)]))
    ctx.rectangle(0, h * 0.7, w, h * 0.3)
    ctx.fill()


def _cloud_puff(ctx, x, y, size, col, alpha, rnd):
    for _ in range(9):
        ox, oy = rnd.gauss(0, size * 0.55), rnd.gauss(0, size * 0.12)
        _spot(ctx, x + ox, y + oy, size * rnd.uniform(0.35, 0.7), col, alpha, 0, (0.5, alpha * 0.7))


def _clouds(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    sun = C.mix(a3, "#ffc38a", 0.5)
    ctx.set_source(_lin(0, 0, 0, h, [(0, C.mix(deep, a2, 0.4), 1), (0.55, C.mix(a, sun, 0.55), 1),
                                     (1, C.lighten(sun, 0.4), 1)]))
    ctx.paint()
    _radial(ctx, w * rnd.uniform(0.3, 0.7), h * 0.55, h * 0.7, C.lighten(sun, 0.55), 0.7, 0, (0.05, 0.7))
    ctx.paint()
    for i in range(5):
        t = i / 4
        col = C.mix(C.lighten(sun, 0.3), C.mix(deep, a2, 0.5), t * 0.7)
        for _ in range(7 + i * 2):
            _cloud_puff(ctx, rnd.random() * w, h * (0.55 + 0.1 * i + rnd.uniform(-0.03, 0.03)),
                        w * (0.06 + 0.03 * i), col, 0.35, rnd)
    _vignette(ctx, w, h, 0.25)


def _bokeh(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    ctx.set_source(_lin(0, 0, w, h, [(0, C.darken(deep, 0.45), 1), (1, C.darken(C.mix(deep, a, 0.3), 0.3), 1)]))
    ctx.paint()
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_SCREEN)
    for i in range(int(90 * w * h / 2073600) + 30):
        x, y = rnd.random() * w, h * (0.25 + rnd.random() * 0.75) if rnd.random() < 0.7 else rnd.random() * h
        r = min(w, h) * rnd.uniform(0.01, 0.09)
        col = rnd.choice((a, a2, a3, "#ffd8a8"))
        rr, gg, bb = C.to_rgb(col)
        g = cairo.RadialGradient(x, y, 0, x, y, r)
        al = rnd.uniform(0.15, 0.5)
        g.add_color_stop_rgba(0, rr, gg, bb, al * 0.7)
        g.add_color_stop_rgba(0.85, rr, gg, bb, al)
        g.add_color_stop_rgba(1, rr, gg, bb, 0)
        ctx.set_source(g)
        ctx.arc(x, y, r, 0, 2 * math.pi)
        ctx.fill()
    ctx.restore()
    _vignette(ctx, w, h, 0.4)


def _topo(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    ctx.set_source(_lin(0, 0, w, h, [(0, C.darken(deep, 0.25), 1), (1, C.mix(deep, a2, 0.2), 1)]))
    ctx.paint()
    hills = [(rnd.random(), rnd.random(), rnd.uniform(0.08, 0.25), rnd.uniform(-1, 1.4)) for _ in range(9)]
    nx, ny = 160, 90

    def f(u, v):
        return sum(k * math.exp(-((u - x) ** 2 + ((v - y) * 0.5625) ** 2) / (s * s)) for x, y, s, k in hills)

    grid = [[f(i / nx, j / ny) for i in range(nx + 1)] for j in range(ny + 1)]
    lo = min(min(r) for r in grid)
    hi = max(max(r) for r in grid)
    sx, sy = w / nx, h / ny
    levels = 26
    for li in range(1, levels):
        lv = lo + (hi - lo) * li / levels
        t = li / levels
        r_, g_, b_ = C.to_rgb(C.mix(a, a2, t))
        ctx.set_line_width(max(1.0, h / 700) * (2.2 if li % 5 == 0 else 1))
        for j in range(ny):
            row0, row1 = grid[j], grid[j + 1]
            for i in range(nx):
                v0, v1, v2, v3 = row0[i], row0[i + 1], row1[i + 1], row1[i]
                c = (v0 > lv) | ((v1 > lv) << 1) | ((v2 > lv) << 2) | ((v3 > lv) << 3)
                if c in (0, 15):
                    continue
                x0, y0 = i * sx, j * sy

                def lerp(pa, pb, va, vb):
                    k = (lv - va) / (vb - va) if vb != va else 0.5
                    return pa[0] + (pb[0] - pa[0]) * k, pa[1] + (pb[1] - pa[1]) * k

                corners = ((x0, y0), (x0 + sx, y0), (x0 + sx, y0 + sy), (x0, y0 + sy))
                vals = (v0, v1, v2, v3)
                pts = []
                for e in range(4):
                    ea, eb = e, (e + 1) % 4
                    if (vals[ea] > lv) != (vals[eb] > lv):
                        pts.append(lerp(corners[ea], corners[eb], vals[ea], vals[eb]))
                for k in range(0, len(pts) - 1, 2):
                    ctx.move_to(*pts[k])
                    ctx.line_to(*pts[k + 1])
        ctx.set_source_rgba(r_, g_, b_, 0.35 + 0.4 * (li % 5 == 0))
        ctx.stroke()
    _vignette(ctx, w, h, 0.35)


def _glass(ctx, w, h, p, rnd):
    _blobs(ctx, w, h, p, rnd)
    bg, deep, a, a2, a3 = _palette_colors(p)
    for _ in range(6):
        gw, gh = w * rnd.uniform(0.15, 0.35), h * rnd.uniform(0.15, 0.4)
        x, y = rnd.uniform(-0.05, 0.9) * w, rnd.uniform(-0.05, 0.85) * h
        rad = min(gw, gh) * rnd.uniform(0.08, 0.5)
        _rounded(ctx, x, y, gw, gh, rad)
        ctx.set_source(_lin(x, y, x + gw, y + gh, [(0, "#ffffff", 0.22), (1, "#ffffff", 0.05)]))
        ctx.fill_preserve()
        ctx.set_line_width(max(1.0, h / 600))
        ctx.set_source(_lin(x, y, x + gw, y + gh, [(0, "#ffffff", 0.55), (0.5, "#ffffff", 0.08), (1, "#ffffff", 0.3)]))
        ctx.stroke()
    _vignette(ctx, w, h, 0.2)


def _rounded(ctx, x, y, w, h, r):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def _hexagons(ctx, w, h, p, rnd):
    bg, deep, a, a2, a3 = _palette_colors(p)
    _src(ctx, C.darken(deep, 0.4))
    ctx.paint()
    size = max(w, h) / 26
    hw = math.sqrt(3) * size
    row = 0
    y = -size
    while y < h + size:
        x = -hw + (hw / 2 if row % 2 else 0)
        while x < w + hw:
            t = max(0.0, min(1.0, x / w * 0.65 + y / h * 0.35))
            col = C.mix(C.mix(deep, a, 0.6), C.mix(deep, a2, 0.7), t)
            col = C.shade(col, rnd.uniform(-0.12, 0.12))
            glow = rnd.random() < 0.05
            ctx.new_path()
            for k in range(6):
                ang = math.pi / 6 + k * math.pi / 3
                ctx.line_to(x + size * 0.93 * math.cos(ang), y + size * 0.93 * math.sin(ang))
            ctx.close_path()
            if glow:
                ctx.set_source(_lin(x, y - size, x, y + size, [(0, C.lighten(a3, 0.3), 1), (1, a3, 1)]))
            else:
                ctx.set_source(_lin(x, y - size, x, y + size, [(0, C.lighten(col, 0.08), 1), (1, C.darken(col, 0.12), 1)]))
            ctx.fill()
            x += hw
        y += size * 1.5
        row += 1
    _radial(ctx, w * 0.7, h * 0.3, max(w, h) * 0.6, a2, 0.2)
    ctx.paint()
    _vignette(ctx, w, h, 0.45)


_DRAW = {"gradient": _gradient, "waves": _waves, "mountains": _mountains, "blobs": _blobs,
         "lowpoly": _lowpoly, "aurora": _aurora, "stars": _stars, "rings": _rings,
         "mesh": _mesh, "ribbons": _ribbons, "synthwave": _synthwave, "nebula": _nebula,
         "planet": _planet, "dunes": _dunes, "ocean": _ocean, "forest": _forest, "city": _city,
         "clouds": _clouds, "bokeh": _bokeh, "topo": _topo, "glass": _glass, "hexagons": _hexagons}


SCREEN = None  # taille mémorisée au démarrage (depuis le thread GTK)


def screen_size():
    if SCREEN:
        return SCREEN
    try:
        import gi
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk
        display = Gdk.Display.get_default()
        mon = display.get_primary_monitor() or display.get_monitor(0)
        geo = mon.get_geometry()
        scale = mon.get_scale_factor()
        return max(1280, geo.width * scale), max(720, geo.height * scale)
    except Exception:
        return 1920, 1080


def render(p, style, w=None, h=None, seed=None):
    if w is None or h is None:
        w, h = screen_size()
    s = cairo.ImageSurface(cairo.FORMAT_RGB24, int(w), int(h))
    ctx = cairo.Context(s)
    rnd = random.Random(seed if seed is not None else zlib.crc32(f"{p['name']}/{style}".encode()))
    _DRAW.get(style, _gradient)(ctx, int(w), int(h), p, rnd)
    _grain(ctx, int(w), int(h), rnd)
    return s


def generate(p, style=None, seed=None):
    style = style or p.get("wallpaper", "gradient")
    paths.WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{p['name'].replace(' ', '_').replace('/', '-')}-{style}"
    if seed is not None:
        name += f"-{seed}"
    out = Path(paths.WALLPAPER_DIR) / f"{name}.png"
    render(p, style, seed=seed).write_to_png(str(out))
    return out
