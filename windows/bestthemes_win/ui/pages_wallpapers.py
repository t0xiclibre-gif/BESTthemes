"""Page « Fonds d'écran » : générés en haute qualité, photos libres HQ, fonds animés."""
import random
import sys
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QCheckBox, QComboBox, QFrame, QHBoxLayout, QVBoxLayout, QWidget

import cairo

from bestthemes.core import generator as G
from bestthemes.core import live
from bestthemes.core import wallgallery as gallery
from bestthemes.core import wallpaper as WP

from .. import winplat as wp
from ..core import appearance, backup, livewall, wallgen
from . import widgets as W
from .pages_workshop import _tabs


def _qimage(surface):
    """cairo.ImageSurface -> QImage indépendante (utilisable depuis un thread)."""
    surface.flush()
    fmt = QImage.Format_ARGB32_Premultiplied if surface.get_format() == cairo.FORMAT_ARGB32 else QImage.Format_RGB32
    return QImage(bytes(surface.get_data()), surface.get_width(), surface.get_height(),
                  surface.get_stride(), fmt).copy()


def _palette_combo(default=None):
    combo = QComboBox()
    for p in G.load_palettes():
        combo.addItem(p["name"], p["id"])
    if default:
        i = combo.findData(default)
        if i >= 0:
            combo.setCurrentIndex(i)
    return combo


def _screen_label():
    w, h = wallgen.SCREEN
    return f"{w} × {h}"


# ======================================================================= générés


class GeneratedTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.loaded = False
        self.seed = None
        self.req = 0
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(W.label(f"{len(WP.STYLES)} styles × 30 palettes, dessinés à la taille exacte de votre écran "
                            f"({_screen_label()}) : nets, sans compression ni droits d'auteur. Cliquez pour appliquer.",
                            "hint", wrap=True))
        bar = QHBoxLayout()
        bar.addWidget(W.label("Palette"))
        self.pal = _palette_combo("catppuccin-mocha")
        self.pal.currentIndexChanged.connect(lambda *_: self.reload())
        bar.addWidget(self.pal)
        bar.addWidget(W.button("🎲 Nouvelles variantes", self._reseed))
        self.match = QCheckBox("Accorder Windows (mode sombre/clair et couleur d'accent)")
        bar.addWidget(self.match)
        bar.addStretch(1)
        v.addLayout(bar)
        self.grid = W.Grid()
        v.addWidget(self.grid)

    def load(self):
        if not self.loaded:
            self.loaded = True
            self.reload()

    def _reseed(self):
        self.seed = random.randint(1, 10 ** 6)
        self.reload()

    def reload(self):
        self.req += 1
        req = self.req
        self.grid.clear()
        pal = G.palette(self.pal.currentData())
        for sid, name in WP.STYLES.items():
            prev = W.Preview(None, 240, 135)
            card = W.Card(prev, name, None, lambda s=sid, n=name: self._apply(s, n), 240)
            self.grid.add(card)
            W.run_async(lambda s=sid: _qimage(WP.render(pal, s, 384, 216, self.seed)),
                        lambda img, prev=prev: prev.set_pixmap(QPixmap.fromImage(img)) if req == self.req else None)

    def _apply(self, style, name):
        pal = G.palette(self.pal.currentData())
        seed, match = self.seed, self.match.isChecked()
        self.win.toast(f"Création du fond « {name} » en {_screen_label()}…")

        def work():
            path = wallgen.generate(pal, style, seed)
            backup.snapshot(f"Fond d'écran {name}")
            if match:
                dark = G.derive(pal)["dark"]
                appearance.set_mode(apps_dark=dark, system_dark=dark)
                appearance.set_accent(pal["accent"])
            appearance.set_wallpaper(path)
            return name

        W.run_async(work, lambda n: self.win.applied(f"Fond « {n} » ({pal['name']}) appliqué"),
                    lambda e: W.error(self, "Impossible de créer le fond d'écran", str(e)))


# ======================================================================= photos


class PhotosTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.loaded = False
        self.theme = gallery.THEMES[0][0]
        self.cont = None
        self.req = 0
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(W.label("Des photos primées de Wikimedia Commons (« images remarquables ») et de la NASA, "
                            "sous licence libre. Téléchargées en haute définition (jusqu'à 4K selon votre écran). "
                            "L'auteur et la licence sont indiqués sous chaque image.", "hint", wrap=True))
        chips = QWidget()
        flow = W.FlowLayout(chips, 6, uniform=False)
        self.chips = []
        for tid, label, _src, _q in gallery.THEMES:
            b = W.button(label, None, "tab")
            b.setCheckable(True)
            b.setChecked(tid == self.theme)
            b.clicked.connect(lambda *_, t=tid: self.select(t))
            b.key = tid
            flow.addWidget(b)
            self.chips.append(b)
        v.addWidget(chips)
        self.status = W.label("", "hint")
        v.addWidget(self.status)
        self.grid = W.Grid()
        v.addWidget(self.grid)
        self.more = W.button("Charger plus de photos", self._fetch)
        self.more.hide()
        v.addWidget(self.more, 0, Qt.AlignHCenter)

    def load(self):
        if not self.loaded:
            self.loaded = True
            self.select(self.theme)

    def select(self, tid):
        self.theme = tid
        for b in self.chips:
            b.setChecked(b.key == tid)
        self.cont = None
        self.grid.clear()
        self._fetch()

    def _fetch(self):
        self.req += 1
        req, tid, cont = self.req, self.theme, self.cont
        self.status.setText("Chargement…")
        self.more.hide()

        def done(res):
            if req != self.req:
                return
            photos, nxt = res
            self.cont = nxt
            for ph in photos:
                self._add(ph)
            n = self.grid.flow.count()
            self.status.setText(f"{n} photo(s) haute définition" if n else "Aucune photo pour l'instant.")
            self.more.setVisible(nxt is not None)

        def err(e):
            if req == self.req:
                self.status.setText("Impossible de charger les photos : vérifiez votre connexion Internet.")

        W.run_async(lambda: gallery.browse(tid, cont), done, err)

    def _add(self, ph):
        img = W.RemoteImage(ph.thumb, 280, 158)
        card = W.Card(img, ph.title, ph.credit)
        card.setToolTip(f"{ph.title}\n{ph.credit}\nOriginal : {ph.width} × {ph.height}")
        card.actions.addWidget(W.pill(f"{ph.width}×{ph.height}"))
        card.actions.addStretch(1)
        card.actions.addWidget(W.button("Source", lambda: wp.open_url(ph.page), "flat"))
        b = W.button("Appliquer", None, "primary")
        b.clicked.connect(lambda *_: self._apply(ph, b))
        card.actions.addWidget(b)
        self.grid.add(card)

    def _apply(self, ph, btn):
        btn.setEnabled(False)
        btn.setText("Téléchargement…")
        bridge = W.Bridge()
        bridge.message.connect(lambda frac, _x: btn.setText(f"{int(frac * 100)} %"))

        def work():
            dest = appearance.wallpaper_dir() / "Photos"
            path = gallery.download(ph, dest, wallgen.SCREEN[0], lambda f: bridge.message.emit(f, None))
            backup.snapshot("Fond d'écran (photo)")
            appearance.set_wallpaper(path)
            return path

        def done(_path):
            btn.setText("✓ Appliqué")
            btn.setEnabled(True)
            self.win.applied(f"Photo « {ph.title[:40]} » appliquée")

        def failed(e):
            btn.setText("Appliquer")
            btn.setEnabled(True)
            W.error(self, "Téléchargement impossible", str(e))

        W.run_async(work, done, failed)


# ======================================================================= animés


class LivePreview(QWidget):
    """Aperçu animé d'une scène (s'anime en continu ou seulement au survol)."""

    def __init__(self, scene_id, palette_id, w=240, h=135, always=False, fps=24):
        super().__init__()
        self.scene_id = scene_id
        self.palette_id = palette_id
        self.always = always
        self.scene = None
        self.surf = None
        self.t0 = time.monotonic()
        self.t = 6.0
        self.setMinimumSize(w, h)
        self.setFixedHeight(h)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.fps = fps
        if always:
            self.timer.start(int(1000 / fps))

    def set_scene(self, scene_id=None, palette_id=None):
        if scene_id:
            self.scene_id = scene_id
        if palette_id:
            self.palette_id = palette_id
        self.scene = None
        self.update()

    def _ensure(self):
        w, h = max(16, self.width()), max(16, self.height())
        if self.scene is None or (self.scene.w, self.scene.h) != (w, h):
            self.scene = live.create(self.scene_id, w, h, live.find_palette(self.palette_id), seed=7)
            self.surf = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
            self.scene.draw(cairo.Context(self.surf), self.t)

    def _tick(self):
        if not self.isVisible():
            return
        self.t = 6.0 + time.monotonic() - self.t0
        self._ensure()
        self.scene.draw(cairo.Context(self.surf), self.t)
        self.update()

    def enterEvent(self, e):
        if not self.always:
            self.t0 = time.monotonic() - (self.t - 6.0)
            self.timer.start(int(1000 / self.fps))
        super().enterEvent(e)

    def leaveEvent(self, e):
        if not self.always:
            self.timer.stop()
        super().leaveEvent(e)

    def paintEvent(self, _e):
        self._ensure()
        p = QPainter(self)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 10, 10)
        p.setClipPath(path)
        self.surf.flush()
        img = QImage(self.surf.get_data(), self.surf.get_width(), self.surf.get_height(),
                     self.surf.get_stride(), QImage.Format_RGB32)
        p.drawImage(0, 0, img)
        p.end()


class AnimatedTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.loaded = False
        cfg = livewall.config()
        self.selected = cfg["scene"]
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(W.label("Un fond d'écran qui bouge, derrière vos icônes. Il continue quand BESTthemes est fermé, "
                            "redémarre avec Windows, et se met en pause dès qu'une fenêtre agrandie ou un jeu en "
                            "plein écran le cache (aucun ralentissement).", "hint", wrap=True))

        top = QFrame()
        top.setProperty("cls", "box")
        th = QHBoxLayout(top)
        self.big = LivePreview(self.selected, cfg["palette"], 480, 270, always=True)
        th.addWidget(self.big, 3)
        side = QVBoxLayout()
        self.title = W.label("", "section")
        self.desc = W.label("", "hint", wrap=True)
        side.addWidget(self.title)
        side.addWidget(self.desc)
        side.addWidget(W.label("Couleurs"))
        self.pal = _palette_combo(cfg["palette"])
        self.pal.currentIndexChanged.connect(self._pal_changed)
        side.addWidget(self.pal)
        side.addWidget(W.label("Fluidité"))
        self.fps = QComboBox()
        for k, label in livewall.FPS.items():
            self.fps.addItem(label, k)
        self.fps.setCurrentIndex(max(0, self.fps.findData(cfg["fps"])))
        side.addWidget(self.fps)
        side.addWidget(W.label("Qualité d'image"))
        self.quality = QComboBox()
        for k, (label, _s, mx) in livewall.QUALITY.items():
            self.quality.addItem(f"{label} (jusqu'à {mx} px)", k)
        self.quality.setCurrentIndex(max(0, self.quality.findData(cfg["quality"])))
        side.addWidget(self.quality)
        row = QHBoxLayout()
        self.on_btn = W.button("▶ Activer", self._activate, "primary")
        self.off_btn = W.button("■ Arrêter", self._deactivate)
        row.addWidget(self.on_btn)
        row.addWidget(self.off_btn)
        side.addLayout(row)
        self.state = W.label("", "hint", wrap=True)
        side.addWidget(self.state)
        side.addStretch(1)
        th.addLayout(side, 2)
        v.addWidget(top)
        if getattr(sys, "frozen", False) and "portable" in sys.executable.lower():
            v.addWidget(W.label("Version portable : pour que le fond animé redémarre avec Windows, gardez "
                                "BESTthemes au même endroit (pas sur une clé USB retirée).", "hint", wrap=True))
        v.addWidget(W.section("Choisir une animation"))
        v.addWidget(W.label("Survolez une vignette pour la voir bouger.", "hint"))
        self.grid = W.Grid()
        v.addWidget(self.grid)
        self.cards = {}
        self._select(self.selected)

    def load(self):
        if self.loaded:
            self._refresh_state()
            return
        self.loaded = True
        for sid, cls in live.SCENES.items():
            prev = LivePreview(sid, self.pal.currentData())
            card = W.Card(prev, cls.label, cls.desc, lambda s=sid: self._select(s), 240)
            self.cards[sid] = (card, prev)
            self.grid.add(card)
        self._select(self.selected)
        self._refresh_state()

    def _select(self, sid):
        self.selected = sid
        cls = live.SCENES[sid]
        self.title.setText(cls.label)
        self.desc.setText(cls.desc)
        self.big.set_scene(sid, self.pal.currentData())
        for k, (card, _p) in self.cards.items():
            card.set_active(k == sid, badge=False)

    def _pal_changed(self):
        pid = self.pal.currentData()
        self.big.set_scene(palette_id=pid)
        for _card, prev in self.cards.values():
            prev.set_scene(palette_id=pid)

    def _refresh_state(self):
        cfg = livewall.config()
        on = cfg["enabled"] and livewall.running()
        if on:
            name = live.SCENES.get(cfg["scene"], live.SCENES["aurora"]).label
            self.state.setText(f"● Actif : {name} ({live.find_palette(cfg['palette'])['name']})")
        else:
            self.state.setText("Aucun fond animé actif.")
        self.on_btn.setText("▶ Mettre à jour" if on else "▶ Activer")
        self.off_btn.setEnabled(bool(on or cfg["enabled"]))

    def _activate(self):
        sid, pid = self.selected, self.pal.currentData()
        fps, q = self.fps.currentData(), self.quality.currentData()
        self.on_btn.setEnabled(False)
        self.state.setText("Démarrage du fond animé…")

        def work():
            backup.snapshot(f"Fond animé {live.SCENES[sid].label}")
            return livewall.start(sid, pid, fps, q)

        def done(res):
            ok, msg = res
            self.on_btn.setEnabled(True)
            self._refresh_state()
            if ok:
                self.win.applied(f"Fond animé « {live.SCENES[sid].label} » activé")
            else:
                self.win.changed()
                W.error(self, "Le fond animé n'a pas pu démarrer",
                        f"{msg}\n\nVos réglages n'ont pas changé : vous pouvez annuler avec « Annuler ».")

        W.run_async(work, done, lambda e: (self.on_btn.setEnabled(True), W.error(self, "Erreur", str(e))))

    def _deactivate(self):
        def work():
            backup.snapshot("Arrêt du fond animé")
            livewall.stop()

        W.run_async(work, lambda _r: (self._refresh_state(), self.win.applied("Fond animé arrêté")),
                    lambda e: W.error(self, "Erreur", str(e)))

    def on_changed(self):
        if self.loaded:
            self._refresh_state()


# ======================================================================= page


class WallpapersPage(W.Page):
    def __init__(self, win):
        super().__init__(win, "Fonds d'écran",
                         "Des centaines de fonds en haute qualité : générés à la taille de votre écran, "
                         "photos primées sous licence libre, et fonds animés.")
        self.tabs = {"generated": GeneratedTab(win), "photos": PhotosTab(win), "animated": AnimatedTab(win)}
        self.tabbar = _tabs([("generated", "✨ Générés HQ"), ("photos", "📷 Photos HQ"),
                             ("animated", "🎬 Animés")], self.show_tab)
        self.body.addWidget(self.tabbar)
        for t in self.tabs.values():
            self.body.addWidget(t)
            t.hide()
        self.current = "generated"
        self.tabs["generated"].show()
        self.finish()

    def show_tab(self, key):
        for b in self.tabbar.buttons:
            b.setChecked(b.key == key)
        for k, t in self.tabs.items():
            t.setVisible(k == key)
        self.current = key
        self.tabs[key].load()

    def on_show(self):
        self.tabs[self.current].load()

    def on_changed(self):
        self.tabs["animated"].on_changed()

    def navigate(self, tab=None, **_kw):
        if tab in self.tabs:
            self.show_tab(tab)
