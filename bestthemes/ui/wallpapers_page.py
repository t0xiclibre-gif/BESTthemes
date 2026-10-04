"""Page « Fonds d'écran » : générés en haute qualité, photos libres HQ, fonds animés."""
import random
import time

import cairo
from gi.repository import GLib, Gtk

from ..core import applier, backup, generator, live, livewall, paths, wallpaper
from ..core import wallgallery as gallery
from . import widgets as W


def _palette_combo(default=None):
    combo = Gtk.ComboBoxText()
    for p in generator.load_palettes():
        combo.append(p["id"], p["name"])
    if not default or not combo.set_active_id(default):
        combo.set_active(0)
    return combo


def _screen_label():
    w, h = wallpaper.screen_size()
    return f"{w} × {h}"


def _child(widget, search=""):
    c = Gtk.FlowBoxChild()
    c.search_text = search
    c.add(widget)
    return c


def _info(text):
    box = Gtk.Box()
    W.add_class(box, "info-box")
    box.pack_start(W.label(text, wrap=True), True, True, 0)
    return box


# ======================================================================= générés


class GeneratedTab(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.win = win
        self.loaded = False
        self.seed = None
        self.req = 0
        self.pack_start(W.label(f"{len(wallpaper.STYLES)} styles × 30 palettes, dessinés à la taille exacte de "
                                f"votre écran ({_screen_label()}) : nets, sans compression ni droits d'auteur. "
                                "Cliquez pour appliquer.", "hint", wrap=True), False, False, 0)
        bar = Gtk.Box(spacing=10)
        bar.pack_start(W.label("Palette"), False, False, 0)
        self.pal = _palette_combo("catppuccin-mocha")
        self.pal.connect("changed", lambda *_: self.reload())
        bar.pack_start(self.pal, False, False, 0)
        bar.pack_start(W.button("Nouvelles variantes", "media-playlist-shuffle-symbolic", on_click=self._reseed),
                       False, False, 0)
        self.pack_start(bar, False, False, 0)
        self.flow = W.flowbox(1, 5)
        self.pack_start(self.flow, False, False, 0)

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
        W.clear(self.flow)
        pal = generator.palette(self.pal.get_active_id())
        for sid, name in wallpaper.STYLES.items():
            holder = {"surf": None}

            def draw(cr, w, h, holder=holder):
                s = holder["surf"]
                if s is None:
                    cr.set_source_rgba(0.5, 0.5, 0.5, 0.15)
                    cr.paint()
                    return
                cr.scale(w / s.get_width(), h / s.get_height())
                cr.set_source_surface(s)
                cr.paint()

            prev = W.Preview(draw, 240, 135)
            card = W.Card(prev, name, None, on_activate=lambda s=sid, n=name: self._apply(s, n))
            self.flow.add(_child(card))

            def done(surf, holder=holder, prev=prev):
                if req == self.req:
                    holder["surf"] = surf
                    prev.queue_draw()

            W.run_async(lambda s=sid: wallpaper.render(pal, s, 384, 216, self.seed), done)
        self.flow.show_all()

    def _apply(self, style, name):
        pal = generator.palette(self.pal.get_active_id())
        seed = self.seed
        self.win.toast(f"Création du fond « {name} » en {_screen_label()}…")

        def work():
            path = wallpaper.generate(pal, style, seed)
            applier.apply({"wallpaper": str(path)}, f"Fond d'écran {name}")
            return name

        W.run_async(work, lambda n: self.win.applied(f"Fond « {n} » ({pal['name']}) appliqué"),
                    lambda e: W.error_dialog(self.win, "Impossible de créer le fond d'écran", str(e)))


# ======================================================================= photos


class PhotosTab(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.win = win
        self.loaded = False
        self.theme = gallery.THEMES[0][0]
        self.cont = None
        self.req = 0
        self.count = 0
        self.pack_start(W.label("Des photos primées de Wikimedia Commons (« images remarquables ») et de la NASA, "
                                "sous licence libre. Téléchargées en haute définition (jusqu'à 4K selon votre "
                                "écran). L'auteur et la licence sont indiqués sous chaque image.", "hint", wrap=True),
                        False, False, 0)
        chips = Gtk.FlowBox()
        chips.set_selection_mode(Gtk.SelectionMode.NONE)
        chips.set_max_children_per_line(20)
        chips.set_column_spacing(6)
        chips.set_row_spacing(6)
        W.add_class(chips, "tabs")
        self.chips = {}
        group = None
        for tid, label, _src, _q in gallery.THEMES:
            b = Gtk.RadioButton.new_with_label_from_widget(group, label)
            b.set_mode(False)
            group = group or b
            b.connect("toggled", lambda btn, t=tid: btn.get_active() and self.select(t))
            self.chips[tid] = b
            chips.add(b)
        self.pack_start(chips, False, False, 0)
        self.status = W.label("", "hint")
        self.pack_start(self.status, False, False, 0)
        self.flow = W.flowbox(1, 4)
        self.pack_start(self.flow, False, False, 0)
        self.more = W.button("Charger plus de photos", on_click=self._fetch)
        self.more.set_halign(Gtk.Align.CENTER)
        self.more.set_no_show_all(True)
        self.pack_start(self.more, False, False, 0)

    def load(self):
        if not self.loaded:
            self.loaded = True
            self.select(self.theme)

    def select(self, tid):
        self.theme = tid
        self.cont = None
        self.count = 0
        W.clear(self.flow)
        self._fetch()

    def _fetch(self):
        self.req += 1
        req, tid, cont = self.req, self.theme, self.cont
        self.status.set_text("Chargement…")
        self.more.hide()

        def done(res):
            if req != self.req:
                return
            photos, nxt = res
            self.cont = nxt
            for ph in photos:
                self._add(ph)
            self.count += len(photos)
            self.flow.show_all()
            self.status.set_text(f"{self.count} photo(s) haute définition" if self.count else "Aucune photo pour l'instant.")
            self.more.set_visible(nxt is not None)

        def err(_e):
            if req == self.req:
                self.status.set_text("Impossible de charger les photos : vérifiez votre connexion Internet.")

        W.run_async(lambda: gallery.browse(tid, cont), done, err)

    def _add(self, ph):
        img = W.RemoteImage(ph.thumb, 280, 158)
        card = W.Card(img, ph.title, ph.credit)
        card.set_tooltip_text(f"{ph.title}\n{ph.credit}\nOriginal : {ph.width} × {ph.height}")
        card.actions.pack_start(W.label(f"{ph.width}×{ph.height}", "pill"), False, False, 0)
        b = W.button("Appliquer", css="suggested-action")
        b.connect("clicked", lambda *_: self._apply(ph, b))
        card.actions.pack_end(b, False, False, 0)
        src = W.button("Source", css="flat", on_click=lambda: Gtk.show_uri_on_window(self.win, ph.page, 0))
        card.actions.pack_end(src, False, False, 0)
        self.flow.add(_child(card))

    def _apply(self, ph, btn):
        btn.set_sensitive(False)
        btn.set_label("Téléchargement…")

        def progress(frac):
            W.idle(btn.set_label, f"{int(frac * 100)} %")

        def work():
            dest = paths.WALLPAPER_DIR / "Photos"
            path = gallery.download(ph, dest, wallpaper.screen_size()[0], progress)
            applier.apply({"wallpaper": str(path)}, "Fond d'écran (photo)")
            return path

        def done(_p):
            btn.set_label("✓ Appliqué")
            btn.set_sensitive(True)
            self.win.applied(f"Photo « {ph.title[:40]} » appliquée")

        def failed(e):
            btn.set_label("Appliquer")
            btn.set_sensitive(True)
            W.error_dialog(self.win, "Téléchargement impossible", str(e))

        W.run_async(work, done, failed)


# ======================================================================= animés


class LivePreview(Gtk.DrawingArea):
    """Aperçu animé d'une scène (en continu, ou seulement au survol)."""

    def __init__(self, scene_id, palette_id, width=240, height=135, always=False, fps=24):
        super().__init__()
        self.scene_id, self.palette_id = scene_id, palette_id
        self.always, self.fps = always, fps
        self.scene = None
        self.surf = None
        self.t = 6.0
        self.t0 = time.monotonic()
        self.timer = None
        self.set_size_request(width, height)
        self.connect("draw", self._draw)
        self.connect("map", lambda *_: self.always and self._play())
        self.connect("unmap", lambda *_: self._pause())

    def set_scene(self, scene_id=None, palette_id=None):
        self.scene_id = scene_id or self.scene_id
        self.palette_id = palette_id or self.palette_id
        self.scene = None
        self.queue_draw()

    def _play(self):
        if self.timer is None:
            self.t0 = time.monotonic() - (self.t - 6.0)
            self.timer = GLib.timeout_add(int(1000 / self.fps), self._tick)

    def _pause(self):
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None

    def hover(self, on):
        if not self.always:
            self._play() if on else self._pause()

    def _tick(self):
        self.t = 6.0 + time.monotonic() - self.t0
        if self.scene is not None:
            self.scene.draw(cairo.Context(self.surf), self.t)
        self.queue_draw()
        return True

    def _draw(self, widget, cr):
        w, h = widget.get_allocated_width(), widget.get_allocated_height()
        if self.scene is None or (self.scene.w, self.scene.h) != (w, h):
            self.scene = live.create(self.scene_id, w, h, live.find_palette(self.palette_id), seed=7)
            self.surf = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
            self.scene.draw(cairo.Context(self.surf), self.t)
        W.previews.rounded_rect(cr, 0, 0, w, h, 10)
        cr.clip()
        cr.set_source_surface(self.surf)
        cr.paint()
        return False


class AnimatedTab(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.win = win
        self.loaded = False
        cfg = livewall.config()
        self.selected = cfg["scene"]
        self.pack_start(W.label("Un fond d'écran qui bouge. Il continue quand BESTthemes est fermé, redémarre "
                                "avec votre session et se met en pause dès qu'une fenêtre agrandie le cache.",
                                "hint", wrap=True), False, False, 0)
        self.pack_start(_info("À savoir : le bureau XFCE ne peut rien afficher derrière ses icônes. Tant que le "
                              "fond animé est actif, les icônes du bureau sont masquées (un clic droit sur le "
                              "bureau ouvre un petit menu). Elles reviennent dès que vous l'arrêtez."),
                        False, False, 0)
        top = Gtk.Box(spacing=16)
        W.add_class(top, "settings-box")
        self.big = LivePreview(self.selected, cfg["palette"], 480, 270, always=True)
        self.big.set_hexpand(True)
        top.pack_start(self.big, True, True, 0)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        side.set_size_request(300, -1)
        self.title = W.label("", "section-title")
        self.desc = W.label("", "hint", wrap=True)
        side.pack_start(self.title, False, False, 0)
        side.pack_start(self.desc, False, False, 0)
        side.pack_start(W.label("Couleurs"), False, False, 0)
        self.pal = _palette_combo(cfg["palette"])
        self.pal.connect("changed", lambda *_: self._pal_changed())
        side.pack_start(self.pal, False, False, 0)
        side.pack_start(W.label("Fluidité"), False, False, 0)
        self.fps = Gtk.ComboBoxText()
        for k, label in livewall.FPS.items():
            self.fps.append(str(k), label)
        self.fps.set_active_id(str(cfg["fps"])) or self.fps.set_active(1)
        side.pack_start(self.fps, False, False, 0)
        side.pack_start(W.label("Qualité d'image"), False, False, 0)
        self.quality = Gtk.ComboBoxText()
        for k, (label, _s, mx) in livewall.QUALITY.items():
            self.quality.append(k, f"{label} (jusqu'à {mx} px)")
        self.quality.set_active_id(cfg["quality"]) or self.quality.set_active(1)
        side.pack_start(self.quality, False, False, 0)
        row = Gtk.Box(spacing=8)
        self.on_btn = W.button("Activer", "media-playback-start-symbolic", css="suggested-action",
                               on_click=self._activate)
        self.off_btn = W.button("Arrêter", "media-playback-stop-symbolic", on_click=self._deactivate)
        row.pack_start(self.on_btn, True, True, 0)
        row.pack_start(self.off_btn, True, True, 0)
        side.pack_start(row, False, False, 6)
        self.state = W.label("", "hint", wrap=True)
        side.pack_start(self.state, False, False, 0)
        top.pack_start(side, False, False, 0)
        self.pack_start(top, False, False, 0)
        self.pack_start(W.section_title("Choisir une animation"), False, False, 0)
        self.pack_start(W.label("Survolez une vignette pour la voir bouger.", "hint"), False, False, 0)
        self.flow = W.flowbox(1, 4)
        self.pack_start(self.flow, False, False, 0)
        self.cards = {}
        self._select(self.selected)

    def load(self):
        if self.loaded:
            self._refresh_state()
            return
        self.loaded = True
        for sid, cls in live.SCENES.items():
            prev = LivePreview(sid, self.pal.get_active_id())
            card = W.Card(prev, cls.label, cls.desc, on_activate=lambda s=sid: self._select(s))
            card.connect("enter-notify-event", lambda *_a, p=prev: p.hover(True))
            card.connect("leave-notify-event", lambda *_a, p=prev: p.hover(False))
            card.badge.set_text("Choisi")
            self.cards[sid] = (card, prev)
            self.flow.add(_child(card))
        self.flow.show_all()
        self._select(self.selected)
        self._refresh_state()

    def _select(self, sid):
        self.selected = sid
        cls = live.SCENES[sid]
        self.title.set_text(cls.label)
        self.desc.set_text(cls.desc)
        self.big.set_scene(sid, self.pal.get_active_id())
        for k, (card, _p) in self.cards.items():
            card.set_active(k == sid)

    def _pal_changed(self):
        pid = self.pal.get_active_id()
        self.big.set_scene(palette_id=pid)
        for _card, prev in self.cards.values():
            prev.set_scene(palette_id=pid)

    def _refresh_state(self):
        cfg = livewall.config()
        on = cfg["enabled"] and livewall.running()
        if on:
            name = live.SCENES.get(cfg["scene"], live.SCENES["aurora"]).label
            self.state.set_text(f"● Actif : {name} ({live.find_palette(cfg['palette'])['name']})")
        else:
            self.state.set_text("Aucun fond animé actif.")
        self.on_btn.get_child().get_children()[1].set_text("Mettre à jour" if on else "Activer")
        self.off_btn.set_sensitive(bool(on or cfg["enabled"]))

    def _activate(self):
        sid, pid = self.selected, self.pal.get_active_id()
        fps, q = int(self.fps.get_active_id() or 24), self.quality.get_active_id() or "balanced"
        self.on_btn.set_sensitive(False)
        self.state.set_text("Démarrage du fond animé…")

        def work():
            backup.snapshot(f"Fond animé {live.SCENES[sid].label}")
            return livewall.start(sid, pid, fps, q)

        def done(res):
            ok, msg = res
            self.on_btn.set_sensitive(True)
            self._refresh_state()
            if ok:
                self.win.applied(f"Fond animé « {live.SCENES[sid].label} » activé")
            else:
                self.win.changed()
                W.error_dialog(self.win, "Le fond animé n'a pas pu démarrer",
                               f"{msg}\n\nVous pouvez revenir en arrière avec « Annuler ».")

        W.run_async(work, done, lambda e: (self.on_btn.set_sensitive(True),
                                           W.error_dialog(self.win, "Erreur", str(e))))

    def _deactivate(self):
        def work():
            backup.snapshot("Arrêt du fond animé")
            livewall.stop()

        W.run_async(work, lambda _r: (self._refresh_state(), self.win.applied("Fond animé arrêté")),
                    lambda e: W.error_dialog(self.win, "Erreur", str(e)))


# ======================================================================= page


class WallpapersPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.win = win
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        top.set_margin_start(24)
        top.set_margin_end(24)
        top.set_margin_top(24)
        top.pack_start(W.page_header("Fonds d'écran",
                                     "Des centaines de fonds en haute qualité : générés à la taille de votre écran, "
                                     "photos primées sous licence libre, et fonds animés."), False, False, 0)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.tabs = {"generated": GeneratedTab(win), "photos": PhotosTab(win), "animated": AnimatedTab(win)}
        for key, title in (("generated", "Générés HQ"), ("photos", "Photos HQ"), ("animated", "Animés")):
            self.stack.add_titled(W.scrolled(self.tabs[key]), key, title)
        switcher = Gtk.StackSwitcher(stack=self.stack)
        W.add_class(switcher, "tabs")
        switcher.set_halign(Gtk.Align.START)
        top.pack_start(switcher, False, False, 0)
        self.pack_start(top, False, False, 0)
        self.pack_start(self.stack, True, True, 0)
        self.stack.connect("notify::visible-child-name", lambda *_: self.on_show())

    def on_show(self):
        name = self.stack.get_visible_child_name()
        if name in self.tabs:
            self.tabs[name].load()

    def on_changed(self):
        if self.tabs["animated"].loaded:
            self.tabs["animated"]._refresh_state()

    def navigate(self, tab=None, **_kw):
        if tab in self.tabs:
            self.stack.set_visible_child_name(tab)
