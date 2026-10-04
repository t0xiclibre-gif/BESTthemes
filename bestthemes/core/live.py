"""Fonds d'écran animés : scènes dessinées avec Cairo, aux couleurs d'une palette.

Indépendant de l'interface : la version Linux (GTK) et la version Windows (Qt) affichent les
mêmes scènes. Chaque scène est créée pour une taille donnée puis dessinée à l'instant `t`
(en secondes) ; les éléments fixes sont pré-calculés une fois pour garder chaque image rapide.
"""
import math
import random

import cairo

from . import colors as C
from . import wallpaper as WP

SCENES = {}  # id -> classe


def scene(cls):
    SCENES[cls.id] = cls
    return cls


def labels():
    return {k: v.label for k, v in SCENES.items()}


def find_palette(pid):
    """Palette par identifiant (ou la première si elle n'existe plus)."""
    from . import generator
    try:
        return generator.palette(pid)
    except KeyError:
        return generator.load_palettes()[0]


def create(scene_id, w, h, palette, seed=1):
    cls = SCENES.get(scene_id) or next(iter(SCENES.values()))
    return cls(max(16, int(w)), max(16, int(h)), palette, seed)


class Scene:
    id = ""
    label = ""
    desc = ""

    def __init__(self, w, h, palette, seed=1):
        self.w, self.h = w, h
        self.p = palette
        self.rnd = random.Random(seed)
        self.bg, self.deep, self.a, self.a2, self.a3 = WP._palette_colors(palette)
        self.space = WP._space(self.deep)
        self.setup()

    def setup(self):
        pass

    def draw(self, ctx, t):
        raise NotImplementedError

    # -------------------------------------------------------------- outils

    def surface(self, w=None, h=None, fmt=cairo.FORMAT_ARGB32):
        s = cairo.ImageSurface(fmt, int(w or self.w), int(h or self.h))
        return s, cairo.Context(s)

    def sprite(self, col, radius, core=0.0, alpha=1.0):
        """Halo lumineux pré-rendu (bien plus rapide qu'un dégradé recalculé à chaque image)."""
        d = max(2, int(radius * 2) + 2)
        s, c = self.surface(d, d)
        r, g, b = C.to_rgb(col)
        grad = cairo.RadialGradient(d / 2, d / 2, 0, d / 2, d / 2, radius)
        grad.add_color_stop_rgba(0, r, g, b, alpha)
        if core:
            grad.add_color_stop_rgba(core, r, g, b, alpha * 0.85)
        grad.add_color_stop_rgba(1, r, g, b, 0)
        c.set_source(grad)
        c.paint()
        return s

    @staticmethod
    def blit(ctx, surf, x, y, alpha=1.0):
        ctx.set_source_surface(surf, x - surf.get_width() / 2, y - surf.get_height() / 2)
        if alpha >= 0.999:
            ctx.paint()
        else:
            ctx.paint_with_alpha(max(0.0, alpha))


def render(sc, t):
    """Une image de la scène (cairo.ImageSurface RGB24)."""
    s = cairo.ImageSurface(cairo.FORMAT_RGB24, sc.w, sc.h)
    sc.draw(cairo.Context(s), t)
    return s


# ======================================================================= scènes


@scene
class Aurora(Scene):
    id, label = "aurora", "Aurore boréale"
    desc = "Des voiles de lumière ondulent au-dessus des montagnes."

    def setup(self):
        w, h, rnd = self.w, self.h, self.rnd
        self.back, c = self.surface(fmt=cairo.FORMAT_RGB24)
        night = C.darken(self.space, 0.2)
        c.set_source(WP._lin(0, 0, 0, h, [(0, C.darken(night, 0.4), 1), (1, C.mix(night, self.a, 0.18), 1)]))
        c.paint()
        WP._stars_layer(c, w, int(h * 0.8), rnd, int(w * h / 3500), 0.55)
        self.front, c = self.surface()
        for i, col in enumerate((C.mix(night, self.a2, 0.25), C.darken(night, 0.5))):
            c.move_to(0, h)
            c.line_to(0, h * (0.72 + 0.1 * i))
            x = 0
            while x < w:
                x += w * rnd.uniform(0.03, 0.08)
                c.line_to(x, h * (0.72 + 0.1 * i) - h * rnd.uniform(0.0, 0.14 - 0.05 * i))
            c.line_to(w, h)
            c.close_path()
            WP._src(c, col)
            c.fill()
        vivid = [C.mix(c_, "#6dffc0", 0.25) if i == 0 else C.lighten(c_, 0.15)
                 for i, c_ in enumerate((self.a, self.a2, self.a3))]
        self.bands = [(col, h * (0.18 + 0.11 * i), rnd.uniform(0, 6.28), rnd.uniform(0.15, 0.3))
                      for i, col in enumerate(vivid)]
        self.twinkle = [(rnd.random() * w, rnd.random() * h * 0.6, rnd.uniform(0.8, 2.2), rnd.uniform(0, 6.28))
                        for _ in range(30)]
        # les voiles sont flous : calculés en demi-résolution (4 fois moins de pixels)
        self.soft, self.sctx = self.surface(w // 2, h // 2)

    def draw(self, ctx, t):
        w = self.w
        ctx.set_source_surface(self.back)
        ctx.paint()
        sc = self.sctx
        sc.set_operator(cairo.OPERATOR_CLEAR)
        sc.paint()
        sc.set_operator(cairo.OPERATOR_ADD)
        sc.save()
        sc.scale(0.5, 0.5)
        self._veils(sc, t)
        sc.restore()
        ctx.save()
        ctx.scale(2, 2)
        ctx.set_source_surface(self.soft)
        ctx.get_source().set_filter(cairo.FILTER_BILINEAR)
        ctx.paint()  # OVER : ADD + agrandissement n'a pas de chemin rapide dans pixman
        ctx.restore()
        for x, y, r, ph in self.twinkle:
            ctx.arc(x, y, r * max(1, w / 1600), 0, 2 * math.pi)
            ctx.set_source_rgba(1, 1, 1, 0.35 + 0.35 * math.sin(t * 2.2 + ph))
            ctx.fill()
        ctx.set_source_surface(self.front)
        ctx.paint()

    def _veils(self, ctx, t):
        w, h = self.w, self.h
        step = max(12, w // 40)
        for col, base, ph, sp in self.bands:
            r, g, b = C.to_rgb(col)
            top = [(x, base + h * 0.07 * math.sin(x / w * 5 + ph + t * sp)
                    + h * 0.03 * math.sin(x / w * 11 - t * sp * 1.7)) for x in range(0, w + step, step)]
            pulse = 0.8 + 0.2 * math.sin(t * 0.6 + ph)
            # voile : bande verticale qui s'estompe vers le bas, plus un liseré lumineux
            for depth, alpha in ((h * 0.22, 0.32), (h * 0.05, 0.42)):
                ctx.move_to(*top[0])
                for x, y in top[1:]:
                    ctx.line_to(x, y)
                for x, y in reversed(top):
                    ctx.line_to(x, y + depth)
                ctx.close_path()
                g_ = cairo.LinearGradient(0, base - h * 0.1, 0, base + h * 0.1 + depth)
                g_.add_color_stop_rgba(0, r, g, b, alpha * pulse)
                g_.add_color_stop_rgba(0.35, r, g, b, alpha * 0.6 * pulse)
                g_.add_color_stop_rgba(1, r, g, b, 0)
                ctx.set_source(g_)
                ctx.fill()


@scene
class Warp(Scene):
    id, label = "warp", "Voyage spatial"
    desc = "Les étoiles défilent doucement, comme à bord d'un vaisseau."

    def setup(self):
        self.back, c = self.surface(fmt=cairo.FORMAT_RGB24)
        c.set_source(WP._lin(0, 0, self.w, self.h, [(0, C.darken(self.space, 0.5), 1),
                                                   (1, C.darken(self.space, 0.2), 1)]))
        c.paint()
        WP._nebula_cloud(c, self.w, self.h, self.p, self.rnd, 0.5)
        self.stars = [self._new(self.rnd.random()) for _ in range(int(260 * max(1, self.w * self.h / 1.5e6)))]
        self.cols = [(1, 1, 1), C.to_rgb(C.lighten(self.a, 0.5)), C.to_rgb(C.lighten(self.a2, 0.5))]

    def _new(self, z):
        return [self.rnd.uniform(-1, 1), self.rnd.uniform(-1, 1), z, self.rnd.randrange(3)]

    def draw(self, ctx, t):
        w, h = self.w, self.h
        ctx.set_source_surface(self.back)
        ctx.paint()
        cx, cy = w / 2, h / 2
        speed = 0.06
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        for s in self.stars:
            z = (s[2] - t * speed) % 1.0
            z0 = min(1.0, z + 0.02)
            zz = max(z, 0.02)
            x, y = cx + s[0] / zz * w * 0.25, cy + s[1] / zz * h * 0.25
            x0, y0 = cx + s[0] / z0 * w * 0.25, cy + s[1] / z0 * h * 0.25
            if not (-10 < x < w + 10 and -10 < y < h + 10):
                continue
            a = min(1.0, (1 - z) * 1.4)
            r, g, b = self.cols[s[3]]
            ctx.set_line_width(max(1.0, (1 - z) * 3.2 * w / 1600))
            ctx.move_to(x0, y0)
            ctx.line_to(x, y)
            ctx.set_source_rgba(r, g, b, a)
            ctx.stroke()


@scene
class Fireflies(Scene):
    id, label = "fireflies", "Lucioles"
    desc = "Des lucioles flottent dans une forêt au crépuscule."

    def setup(self):
        w, h, rnd = self.w, self.h, self.rnd
        self.back, c = self.surface(fmt=cairo.FORMAT_RGB24)
        dusk = {"name": self.p.get("name", ""), "bg": C.darken(self.space, 0.1), "accent": self.a,
                "accent2": self.a2, "accent3": self.a3}
        WP._forest(c, w, h, dusk, random.Random(7))
        c.set_source_rgba(0, 0, 0.05, 0.45)
        c.paint()
        glow = C.mix(self.a3, "#fff3a0", 0.6)
        self.sprites = [self.sprite(glow, max(4, w * 0.012), 0.12), self.sprite(C.lighten(self.a, 0.4), max(3, w * 0.008), 0.15)]
        self.flies = [(rnd.random() * w, h * rnd.uniform(0.3, 0.95), rnd.uniform(0.1, 0.35), rnd.uniform(0, 6.28),
                       rnd.uniform(0.3, 1.2), rnd.randrange(2)) for _ in range(int(55 * max(1, w / 1400)))]

    def draw(self, ctx, t):
        w, h = self.w, self.h
        ctx.set_source_surface(self.back)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_ADD)
        for x, y, sp, ph, blink, k in self.flies:
            xx = (x + math.sin(t * sp + ph) * w * 0.05 + t * sp * w * 0.004) % (w + 40) - 20
            yy = y + math.sin(t * sp * 1.3 + ph * 2) * h * 0.04
            a = 0.35 + 0.65 * max(0.0, math.sin(t * blink + ph)) ** 2
            self.blit(ctx, self.sprites[k], xx, yy, a)
        ctx.set_operator(cairo.OPERATOR_OVER)


@scene
class Ocean(Scene):
    id, label = "ocean", "Vagues"
    desc = "Des vagues roulent lentement sous un ciel dégradé."

    def setup(self):
        w, h = self.w, self.h
        self.back, c = self.surface(fmt=cairo.FORMAT_RGB24)
        c.set_source(WP._lin(0, 0, 0, h, [(0, self.deep, 1), (1, C.mix(self.bg, self.a2, 0.25), 1)]))
        c.paint()
        WP._spot(c, w * 0.7, h * 0.3, h * 0.45, C.lighten(self.a3, 0.4), 0.5)
        self.layers = []
        for i in range(6):
            t = i / 5
            col = C.mix(C.mix(self.a, self.a2, t), self.deep, 0.25 + 0.1 * (1 - t))
            self.layers.append((col, h * (0.45 + 0.09 * i), h * (0.045 + 0.012 * self.rnd.random()),
                                (1.1 + self.rnd.random() * 1.2) * 2 * math.pi / w, self.rnd.uniform(0, 6.28),
                                (0.25 + 0.35 * t) * (1 if i % 2 else -1)))

    def draw(self, ctx, t):
        w, h = self.w, self.h
        ctx.set_source_surface(self.back)
        ctx.paint()
        step = max(6, w // 120)
        for col, base, amp, freq, ph, sp in self.layers:
            ctx.move_to(0, h)
            for x in range(0, w + step, step):
                ctx.line_to(x, base + amp * math.sin(x * freq + ph + t * sp)
                            + amp * 0.4 * math.sin(x * freq * 2.3 + ph - t * sp * 1.6))
            ctx.line_to(w, h)
            ctx.close_path()
            ctx.set_source(WP._lin(0, base - amp, 0, h, [(0, col, 0.88), (1, C.darken(col, 0.4), 0.96)]))
            ctx.fill()


@scene
class Bokeh(Scene):
    id, label = "bokeh", "Bokeh"
    desc = "Des bulles de lumière floues montent doucement."

    def setup(self):
        w, h, rnd = self.w, self.h, self.rnd
        self.back, c = self.surface(fmt=cairo.FORMAT_RGB24)
        c.set_source(WP._lin(0, 0, w, h, [(0, C.darken(self.space, 0.3), 1),
                                         (1, C.darken(C.mix(self.space, self.a, 0.3), 0.2), 1)]))
        c.paint()
        cols = (self.a, self.a2, self.a3, "#ffd8a8")
        self.sprites = []
        for col in cols:
            for size in (0.03, 0.06, 0.1):
                self.sprites.append(self.sprite(col, min(w, h) * size, 0.82, 0.55))
        self.items = [(rnd.random() * w, rnd.random(), rnd.uniform(0.008, 0.03), rnd.uniform(0, 6.28),
                       rnd.randrange(len(self.sprites)), rnd.uniform(0.25, 0.8)) for _ in range(45)]

    def draw(self, ctx, t):
        w, h = self.w, self.h
        ctx.set_source_surface(self.back)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_ADD)
        for x, y, sp, ph, k, al in self.items:
            yy = h * 1.15 - ((y + t * sp) % 1.3) * h
            xx = x + math.sin(t * 0.3 + ph) * w * 0.02
            self.blit(ctx, self.sprites[k], xx, yy, al * (0.7 + 0.3 * math.sin(t * 0.8 + ph)))
        ctx.set_operator(cairo.OPERATOR_OVER)


@scene
class Rain(Scene):
    id, label = "rain", "Pluie sur la ville"
    desc = "La pluie tombe devant les lumières floues de la ville."

    def setup(self):
        w, h, rnd = self.w, self.h, self.rnd
        self.back, c = self.surface(fmt=cairo.FORMAT_RGB24)
        night = C.darken(self.space, 0.1)
        c.set_source(WP._lin(0, 0, 0, h, [(0, night, 1), (1, C.mix(night, self.a2, 0.3), 1)]))
        c.paint()
        c.set_operator(cairo.OPERATOR_SCREEN)
        for _ in range(70):
            col = rnd.choice((self.a, self.a2, self.a3, "#ffcf7a", "#ffcf7a"))
            WP._spot(c, rnd.random() * w, h * rnd.uniform(0.45, 1.0), min(w, h) * rnd.uniform(0.02, 0.07),
                     col, rnd.uniform(0.2, 0.5), 0, (0.8, 0.3))
        self.drops = [(rnd.random(), rnd.random(), rnd.uniform(0.6, 1.0)) for _ in range(int(320 * max(1, w / 1600)))]

    def draw(self, ctx, t):
        w, h = self.w, self.h
        ctx.set_source_surface(self.back)
        ctx.paint()
        ln = h * 0.035
        ctx.set_line_width(max(1.0, w / 1400))
        for layer in (0, 1):
            for x, y, sp in self.drops[layer::2]:
                s = sp * (1.0 if layer else 0.7)
                yy = ((y + t * s * 1.3) % 1.1) * h - ln
                xx = (x * w + yy * 0.12) % w
                ctx.move_to(xx, yy)
                ctx.line_to(xx + ln * 0.12 * s, yy + ln * s)
            ctx.set_source_rgba(0.85, 0.9, 1.0, 0.18 if layer == 0 else 0.32)
            ctx.stroke()


@scene
class Snow(Scene):
    id, label = "snow", "Neige"
    desc = "La neige tombe sur les montagnes."

    def setup(self):
        w, h, rnd = self.w, self.h, self.rnd
        self.back, c = self.surface(fmt=cairo.FORMAT_RGB24)
        winter = dict(self.p, bg=C.mix(self.bg, "#c8d6ea", 0.35))
        WP._mountains(c, w, h, winter, random.Random(3))
        c.set_source_rgba(0.05, 0.08, 0.15, 0.25)
        c.paint()
        self.flakes = [(rnd.random(), rnd.random(), rnd.uniform(0.5, 1.0), rnd.uniform(0, 6.28))
                       for _ in range(int(300 * max(1, w / 1600)))]

    def draw(self, ctx, t):
        w, h = self.w, self.h
        ctx.set_source_surface(self.back)
        ctx.paint()
        base = max(1.0, w / 900)
        for near in (0, 1):
            for x, y, s, ph in self.flakes[near::2]:
                size = base * (s * (2.2 if near else 1.2))
                sp = s * (0.06 if near else 0.035)
                yy = ((y + t * sp) % 1.05) * h - 4
                xx = (x * w + math.sin(t * 0.7 * s + ph) * w * 0.015 + t * w * 0.004) % w
                ctx.new_sub_path()
                ctx.arc(xx, yy, size, 0, 2 * math.pi)
            ctx.set_source_rgba(1, 1, 1, 0.55 if near == 0 else 0.9)
            ctx.fill()


@scene
class Synthwave(Scene):
    id, label = "synthwave", "Synthwave"
    desc = "Soleil rétro et grille néon qui avance vers vous."

    def setup(self):
        w, h = self.w, self.h
        self.hz = h * 0.6
        self.back, c = self.surface(fmt=cairo.FORMAT_RGB24)
        WP._synthwave(c, w, h, self.p, random.Random(5))
        # on efface la grille fixe : elle sera redessinée en mouvement
        night = C.darken(C.mix(self.deep, self.a2, 0.25), 0.35)
        c.set_source(WP._lin(0, self.hz, 0, h, [(0, C.darken(night, 0.4), 1), (1, C.darken(night, 0.1), 1)]))
        c.rectangle(0, self.hz + h * 0.004, w, h)
        c.fill()
        WP._grid_lines(c, w, h, self.hz + h * 0.004, self.a, 0, horizontal=False)
        self.glow = self.sprite(self.a, w * 0.45, 0, 0.3)

    def draw(self, ctx, t):
        ctx.set_source_surface(self.back)
        ctx.paint()
        WP._grid_lines(ctx, self.w, self.h, self.hz + self.h * 0.004, self.a, (t * 0.5) % 1.0, vertical=False)
        self.blit(ctx, self.glow, self.w / 2, self.hz, 0.8 + 0.2 * math.sin(t * 1.5))


@scene
class Matrix(Scene):
    id, label = "matrix", "Code"
    desc = "Une pluie de caractères façon Matrix, à vos couleurs."

    def setup(self):
        w, h, rnd = self.w, self.h, self.rnd
        self.cell = max(10, int(h / 40))
        self.cols = int(w / self.cell) + 1
        self.heads = [rnd.uniform(-1.0, 1.0) for _ in range(self.cols)]
        self.speed = [rnd.uniform(0.18, 0.45) for _ in range(self.cols)]
        # caractères présents dans toutes les polices à chasse fixe (Windows compris)
        self.chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<>*+=$#%&@{}[]/\\|"
        self.buf, c = self.surface(fmt=cairo.FORMAT_RGB24)
        self.night = C.to_rgb(C.darken(self.space, 0.5))
        c.set_source_rgb(*self.night)
        c.paint()
        self.col = C.to_rgb(C.lighten(self.a, 0.15))
        self.last = None
        for i in range(60):  # quelques secondes d'avance : les traînées sont déjà là
            self.draw(None, i / 20)
        self.last = None

    def draw(self, ctx, t):
        c = cairo.Context(self.buf)
        dt = 0.05 if self.last is None else max(0.0, min(0.2, t - self.last))
        self.last = t
        # estompe l'image précédente : les traînées s'effacent toutes seules
        c.set_source_rgba(*self.night, min(1.0, dt * 3.2))
        c.paint()
        c.select_font_face("monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        c.set_font_size(self.cell * 0.9)
        r, g, b = self.col
        for i in range(self.cols):
            prev = self.heads[i]
            self.heads[i] += self.speed[i] * dt * 1.6
            if self.heads[i] > 1.15:
                self.heads[i] = self.rnd.uniform(-0.6, 0.0)
                prev = self.heads[i]
            y0, y1 = int(prev * self.h / self.cell), int(self.heads[i] * self.h / self.cell)
            for row in range(y0, y1 + 1):
                if row < 0:
                    continue
                c.move_to(i * self.cell, (row + 1) * self.cell)
                c.set_source_rgba(r, g, b, 0.9)
                c.show_text(self.rnd.choice(self.chars))
            if y1 >= 0:  # tête plus claire
                c.move_to(i * self.cell, (y1 + 1) * self.cell)
                c.set_source_rgba(0.95, 1, 0.95, 0.95)
                c.show_text(self.rnd.choice(self.chars))
        if ctx is not None:
            ctx.set_source_surface(self.buf)
            ctx.paint()


@scene
class Nebula(Scene):
    id, label = "nebula", "Nébuleuse"
    desc = "Une nébuleuse tourne lentement parmi les étoiles."

    def setup(self):
        w, h, rnd = self.w, self.h, self.rnd
        d = int(math.hypot(w, h)) + 4
        self.cloud, c = self.surface(d, d)
        WP._nebula_cloud(c, d, d, self.p, random.Random(11))
        WP._nebula_cloud(c, d, d, self.p, random.Random(12), 0.6)
        self.back, c = self.surface(fmt=cairo.FORMAT_RGB24)
        c.set_source(WP._lin(0, 0, w, h, [(0, C.darken(self.space, 0.6), 1), (1, C.darken(self.space, 0.3), 1)]))
        c.paint()
        WP._stars_layer(c, w, h, rnd, int(w * h / 2500), 0.5)
        self.near = [(rnd.random() * w, rnd.random() * h, rnd.uniform(0.8, 2.0), rnd.uniform(0, 6.28)) for _ in range(60)]
        self.star = self.sprite("#ffffff", max(3, w * 0.006), 0.1)

    def draw(self, ctx, t):
        w, h = self.w, self.h
        ctx.set_source_surface(self.back)
        ctx.paint()
        ctx.save()
        ctx.translate(w / 2, h / 2)
        ctx.rotate(t * 0.012)
        sc = 1.05 + 0.04 * math.sin(t * 0.05)
        ctx.scale(sc, sc)
        d = self.cloud.get_width()
        ctx.set_source_surface(self.cloud, -d / 2, -d / 2)
        ctx.get_source().set_filter(cairo.FILTER_FAST)
        ctx.paint()
        ctx.restore()
        ctx.set_operator(cairo.OPERATOR_ADD)
        for x, y, r, ph in self.near:
            xx = (x + t * w * 0.003 * r) % w
            self.blit(ctx, self.star, xx, y, 0.35 + 0.4 * (0.5 + 0.5 * math.sin(t * r + ph)))
        ctx.set_operator(cairo.OPERATOR_OVER)


@scene
class Lava(Scene):
    id, label = "lava", "Lampe à lave"
    desc = "De grandes bulles de couleur se mélangent lentement."

    def setup(self):
        rnd = self.rnd
        # tout est flou : dessiné au tiers de la taille puis agrandi
        self.sw, self.sh = max(16, self.w // 3), max(16, self.h // 3)
        self.small, self.sctx = self.surface(self.sw, self.sh, cairo.FORMAT_RGB24)
        self.base = C.darken(self.deep, 0.3) if C.is_dark(self.deep) else C.darken(self.deep, 0.15)
        cols = (self.a, self.a2, self.a3, C.mix(self.a, self.a2, 0.5), C.mix(self.a2, self.a3, 0.5))
        self.blobs = []
        for i in range(8):
            spr = self.sprite(cols[i % len(cols)], min(self.sw, self.sh) * rnd.uniform(0.35, 0.6), 0.3, 0.85)
            self.blobs.append((spr, rnd.uniform(0.04, 0.09), rnd.uniform(0.03, 0.07), rnd.uniform(0, 6.28),
                               rnd.uniform(0, 6.28)))

    def draw(self, ctx, t):
        c, w, h = self.sctx, self.sw, self.sh
        WP._src(c, self.base)
        c.paint()
        for spr, fx, fy, px, py in self.blobs:
            x = w * (0.5 + 0.45 * math.sin(t * fx + px))
            y = h * (0.5 + 0.45 * math.sin(t * fy + py))
            self.blit(c, spr, x, y, 0.8)
        ctx.save()
        ctx.scale(self.w / w, self.h / h)
        ctx.set_source_surface(self.small)
        ctx.get_source().set_filter(cairo.FILTER_BILINEAR)
        ctx.get_source().set_extend(cairo.EXTEND_PAD)
        ctx.paint()
        ctx.restore()


@scene
class Flow(Scene):
    id, label = "flow", "Dégradé vivant"
    desc = "Un dégradé doux dont les couleurs se déplacent lentement (style macOS)."

    def setup(self):
        rnd = self.rnd
        cols = [self.deep, C.mix(self.deep, self.a, 0.7), self.a, self.a2, self.a3,
                C.mix(self.a2, self.a3, 0.5), C.mix(self.bg, self.a, 0.5), C.lighten(self.a2, 0.25)]
        self.n = 3
        self.vcol = [[C.to_rgb(rnd.choice(cols)) for _ in range(self.n + 1)] for _ in range(self.n + 1)]
        self.ph = [[(rnd.uniform(0, 6.28), rnd.uniform(0.1, 0.25)) for _ in range(self.n + 1)] for _ in range(self.n + 1)]
        # dégradé très doux : calculé en petit puis agrandi, la différence est invisible
        self.small, self.sctx = self.surface(max(8, self.w // 6), max(8, self.h // 6), cairo.FORMAT_RGB24)

    def draw(self, ctx, t):
        self._mesh(self.sctx, self.small.get_width(), self.small.get_height(), t)
        ctx.save()
        ctx.scale(self.w / self.small.get_width(), self.h / self.small.get_height())
        ctx.set_source_surface(self.small)
        ctx.get_source().set_filter(cairo.FILTER_BILINEAR)
        ctx.get_source().set_extend(cairo.EXTEND_PAD)
        ctx.paint()
        ctx.restore()

    def _mesh(self, ctx, w, h, t):
        n = self.n
        pts = []
        for j in range(n + 1):
            row = []
            for i in range(n + 1):
                inner = 0 < i < n and 0 < j < n
                ph, sp = self.ph[j][i]
                dx = math.sin(t * sp + ph) * w * 0.12 if inner else 0
                dy = math.cos(t * sp * 0.8 + ph) * h * 0.12 if inner else 0
                row.append((w * (-0.2 + 1.4 * i / n) + dx, h * (-0.2 + 1.4 * j / n) + dy))
            pts.append(row)
        m = cairo.MeshPattern()
        for j in range(n):
            for i in range(n):
                quad = (pts[j][i], pts[j][i + 1], pts[j + 1][i + 1], pts[j + 1][i])
                m.begin_patch()
                m.move_to(*quad[0])
                for q in quad[1:] + quad[:1]:
                    m.line_to(*q)
                for k, (jj, ii) in enumerate(((j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i))):
                    m.set_corner_color_rgb(k, *self.vcol[jj][ii])
                m.end_patch()
        ctx.set_source(m)
        ctx.paint()


@scene
class Particles(Scene):
    id, label = "network", "Réseau"
    desc = "Des points reliés par des fils lumineux dérivent lentement."

    def setup(self):
        w, h, rnd = self.w, self.h, self.rnd
        self.back, c = self.surface(fmt=cairo.FORMAT_RGB24)
        c.set_source(WP._lin(0, 0, w, h, [(0, C.darken(self.space, 0.3), 1),
                                         (1, C.mix(C.darken(self.space, 0.2), self.a2, 0.15), 1)]))
        c.paint()
        n = int(70 * max(1, w * h / 2e6))
        self.pts = [(rnd.random(), rnd.random(), rnd.uniform(-1, 1) * 0.01, rnd.uniform(-1, 1) * 0.01) for _ in range(n)]
        self.col = C.to_rgb(C.lighten(self.a, 0.2))
        self.dot = self.sprite(C.lighten(self.a2, 0.3), max(3, w * 0.004), 0.3)

    def draw(self, ctx, t):
        w, h = self.w, self.h
        ctx.set_source_surface(self.back)
        ctx.paint()
        pos = []
        for x, y, vx, vy in self.pts:
            xx = (x + vx * t) % 1.0
            yy = (y + vy * t) % 1.0
            pos.append((xx * w, yy * h))
        lim = min(w, h) * 0.16
        lim2 = lim * lim
        r, g, b = self.col
        ctx.set_line_width(max(1.0, w / 1600))
        for i, (x1, y1) in enumerate(pos):
            for x2, y2 in pos[i + 1:]:
                d2 = (x1 - x2) ** 2 + (y1 - y2) ** 2
                if d2 < lim2:
                    ctx.move_to(x1, y1)
                    ctx.line_to(x2, y2)
                    ctx.set_source_rgba(r, g, b, 0.45 * (1 - d2 / lim2))
                    ctx.stroke()
        for x, y in pos:
            self.blit(ctx, self.dot, x, y)
