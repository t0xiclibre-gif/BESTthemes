"""Page « Animations » : effets d'ouverture, de fermeture et de réduction des fenêtres."""
import math
import time

from gi.repository import GLib, Gtk

from ..core import animations, backup
from . import previews
from . import widgets as W

CYCLE = 3.2  # secondes par boucle d'aperçu


def _ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _window(cr, x, y, w, h, alpha=1.0):
    previews.rounded_rect(cr, x, y, w, h, 6)
    cr.set_source_rgba(0.97, 0.97, 0.98, alpha)
    cr.fill()
    cr.save()
    previews.rounded_rect(cr, x, y, w, h, 6)
    cr.clip()
    cr.set_source_rgba(0.17, 0.18, 0.22, alpha)
    cr.rectangle(x, y, w, max(4, h * 0.16))
    cr.fill()
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        r, g, b = previews.C.to_rgb(c)
        cr.set_source_rgba(r, g, b, alpha)
        cr.arc(x + 8 + i * 9, y + h * 0.08, max(1.5, h * 0.035), 0, 2 * math.pi)
        cr.fill()
    cr.set_source_rgba(0.35, 0.52, 0.89, alpha * 0.85)
    cr.rectangle(x + w * 0.06, y + h * 0.28, w * 0.25, h * 0.6)
    cr.fill()
    cr.restore()


def _lamp(cr, x, y, w, h, tx, ty, p, wavy=False):
    """Effet lampe magique : la fenêtre s'aspire vers (tx, ty), p = 0 (normale) → 1 (réduite)."""
    import cairo
    iw, ih = max(1, int(w)), max(1, int(h))
    src = cairo.ImageSurface(cairo.FORMAT_ARGB32, iw, ih)
    _window(cairo.Context(src), 0, 0, iw, ih)
    slices = 48
    sh = ih / slices
    for i in range(slices):
        f = i / slices
        # le bas de la fenêtre part en premier vers l'icône
        k = _ease(min(1.0, max(0.0, p * 1.8 - (1 - f) * 0.8)))
        width = w * (1 - k) + 4 * k
        cx = x + w / 2 + (tx - x - w / 2) * k
        if wavy:
            cx += math.sin(f * 9 + p * 12) * 24 * k * (1 - k)
        sy = y + f * h
        yy = sy + (ty - sy) * _ease(max(0.0, p * 1.4 - (1 - f) * 0.4))
        cr.save()
        cr.rectangle(cx - width / 2, yy, width, sh + 1)
        cr.clip()
        cr.translate(cx - width / 2, yy)
        cr.scale(width / iw, 1)
        cr.set_source_surface(src, 0, -i * sh)
        cr.paint()
        cr.restore()


def draw_effect(cr, w, h, preset, t):
    """Boucle : ouverture (0–0.25), pause, réduction (0.45–0.75), pause."""
    g = cairo_gradient(w, h)
    cr.set_source(g)
    cr.paint()
    # barre des tâches + icône cible
    cr.set_source_rgba(0.1, 0.1, 0.13, 0.85)
    cr.rectangle(0, h - 14, w, 14)
    cr.fill()
    tx, ty = w * 0.5, h - 7
    cr.set_source_rgba(0.35, 0.52, 0.89, 1)
    previews.rounded_rect(cr, tx - 5, ty - 5, 10, 10, 2)
    cr.fill()

    ww, wh = w * 0.56, (h - 14) * 0.62
    x, y = (w - ww) / 2, (h - 14 - wh) / 2
    if t < 0.25:
        _effect_in(cr, preset["open"], x, y, ww, wh, _ease(t / 0.25), tx, ty)
    elif t < 0.45:
        _window(cr, x, y, ww, wh)
    elif t < 0.75:
        p = (t - 0.45) / 0.3
        fx = preset["minimize"]
        if "Lamp" in fx:
            _lamp(cr, x, y, ww, wh, tx, ty, p, wavy="Wavy" in fx)
        else:
            _effect_in(cr, fx, x, y, ww, wh, 1 - _ease(p), tx, ty)


def cairo_gradient(w, h):
    import cairo
    g = cairo.LinearGradient(0, 0, w, h)
    g.add_color_stop_rgb(0, 0.42, 0.52, 0.71)
    g.add_color_stop_rgb(1, 0.73, 0.55, 0.78)
    return g


def _effect_in(cr, fx, x, y, w, h, p, tx, ty):
    """Dessine la fenêtre à la progression p (0 = invisible, 1 = normale)."""
    cx, cy = x + w / 2, y + h / 2
    if fx in ("None",):
        if p > 0.5:
            _window(cr, x, y, w, h)
        return
    if fx == "Fade":
        _window(cr, x, y, w, h, p)
        return
    if fx in ("Zoom", "Magic Lamp", "Magic Lamp Wavy"):
        s = 0.1 + 0.9 * p
        ox = tx + (cx - tx) * p
        oy = ty + (cy - ty) * p
        _window(cr, ox - w * s / 2, oy - h * s / 2, w * s, h * s, min(1, p * 1.5))
        return
    if fx in ("Glide 1", "Glide 2"):
        s = 0.75 + 0.25 * p
        dy = (1 - p) * (h * 0.35 if fx == "Glide 1" else h * 0.15)
        _window(cr, cx - w * s / 2, cy - h * s / 2 - dy, w * s, h * s, p)
        return
    if fx == "Sidekick":
        cr.save()
        cr.translate(cx, cy)
        cr.rotate((1 - p) * math.pi * 1.5)
        s = 0.2 + 0.8 * p
        _window(cr, -w * s / 2, -h * s / 2, w * s, h * s, p)
        cr.restore()
        return
    if fx in ("Curved Fold", "Horizontal Folds"):
        folds = 1 if fx == "Curved Fold" else 4
        hh = h * p
        cr.save()
        cr.rectangle(x - 2, cy - hh / 2, w + 4, hh)
        cr.clip()
        _window(cr, x, y, w, h, 0.4 + 0.6 * p)
        cr.restore()
        for i in range(folds):
            cr.set_source_rgba(0, 0, 0, 0.15 * (1 - p))
            cr.rectangle(x, cy - hh / 2 + i * hh / folds, w, hh / folds / 2)
            cr.fill()
        return
    if fx in ("Dream", "Wave"):
        slices = 24
        for i in range(slices):
            f = i / slices
            off = math.sin(f * 10 + p * 8) * (1 - p) * 14
            cr.save()
            cr.rectangle(x - 20, y + f * h, w + 40, h / slices + 1)
            cr.clip()
            _window(cr, x + off, y, w, h, p)
            cr.restore()
        return
    _window(cr, x, y, w, h, p)


class EffectPreview(W.Preview):
    """Aperçu animé (ne tourne que lorsqu'il est visible)."""

    def __init__(self, preset, width=260, height=150):
        self.preset = preset
        self.t0 = time.monotonic()
        self.timer = None
        super().__init__(self._draw, width, height)
        self.connect("map", lambda *_: self._start())
        self.connect("unmap", lambda *_: self._stop())

    def _start(self):
        if self.timer is None:
            self.timer = GLib.timeout_add(33, self._tick)

    def _stop(self):
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None

    def _tick(self):
        self.queue_draw()
        return True

    def _draw(self, cr, w, h):
        dur_scale = max(0.6, min(2.0, self.preset.get("duration", 200) / 200))
        t = ((time.monotonic() - self.t0) / (CYCLE * dur_scale)) % 1.0
        draw_effect(cr, w, h, self.preset, t)


class AnimationsPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self._updating = False
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.pack_start(W.scrolled(self.content), True, True, 0)
        self.build()

    def build(self):
        W.clear(self.content)
        self.content.pack_start(W.page_header(
            "Animations des fenêtres",
            "Des fenêtres qui s'ouvrent en douceur et se réduisent dans la barre avec l'effet "
            "« lampe magique », comme sur Mac."), False, False, 0)
        if not animations.available():
            self._build_install()
        else:
            self._build_main()
        self.content.show_all()

    # ------------------------------------------------------------------ installation

    def _build_install(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        W.add_class(box, "info-box")
        box.pack_start(W.label("<b>Compiz n'est pas installé</b>", markup=True), False, False, 0)
        box.pack_start(W.label("Les animations utilisent Compiz, un gestionnaire de fenêtres avec "
                               "effets. Cliquez sur le bouton : votre mot de passe sera demandé, "
                               "puis tout s'installe automatiquement.", wrap=True), False, False, 0)
        self.install_btn = W.button("Installer Compiz", "folder-download-symbolic",
                                    css="suggested-action big-button", on_click=self._install)
        self.install_btn.set_halign(Gtk.Align.START)
        box.pack_start(self.install_btn, False, False, 0)
        self.content.pack_start(box, False, False, 0)

    def _install(self):
        self.install_btn.set_sensitive(False)
        self.install_btn.set_label("Installation…")

        def done(res):
            ok, msg = res
            self.build()
            if ok:
                self.win.toast("✓ Compiz installé")
            elif msg != "Installation annulée.":
                W.error_dialog(self.win, "L'installation a échoué", msg or "Erreur inconnue.")

        W.run_async(animations.install, done,
                    lambda e: (self.build(), W.error_dialog(self.win, "L'installation a échoué", str(e))))

    # ------------------------------------------------------------------ réglages

    def _build_main(self):
        top = Gtk.Box(spacing=14)
        W.add_class(top, "settings-box")
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        txt.pack_start(W.label("<b>Animations</b>", markup=True), False, False, 0)
        self.status = W.label("", "hint")
        txt.pack_start(self.status, False, False, 0)
        top.pack_start(txt, True, True, 0)
        self.switch = Gtk.Switch()
        self.switch.set_valign(Gtk.Align.CENTER)
        self.switch.connect("notify::active", self._on_switch)
        top.pack_start(self.switch, False, False, 0)
        self.content.pack_start(top, False, False, 0)

        self.content.pack_start(W.section_title("Styles"), False, False, 0)
        fb = W.flowbox(2, 4)
        self.cards = {}
        for p in animations.PRESETS:
            card = W.Card(EffectPreview(p), p["name"], p["desc"],
                          on_activate=lambda p=p: self._apply_preset(p))
            self.cards[p["id"]] = card
            fb.add(card)
        self.content.pack_start(fb, False, False, 0)

        self.content.pack_start(W.section_title("Sur mesure"), False, False, 0)
        box = Gtk.Box(spacing=20)
        W.add_class(box, "settings-box")
        grid = Gtk.Grid(column_spacing=16, row_spacing=12)
        self.combos = {}
        for r, (key, text) in enumerate((("open", "Ouverture"), ("close", "Fermeture"),
                                         ("minimize", "Réduction"))):
            grid.attach(W.label(text), 0, r, 1, 1)
            c = Gtk.ComboBoxText()
            for fx, name in animations.EFFECTS.items():
                c.append(fx, name)
            c.connect("changed", lambda *_: self._custom_changed())
            self.combos[key] = c
            grid.attach(c, 1, r, 1, 1)
        grid.attach(W.label("Durée"), 0, 3, 1, 1)
        self.duration = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 80, 600, 10)
        self.duration.set_size_request(260, -1)
        self.duration.set_value_pos(Gtk.PositionType.RIGHT)
        self.duration.connect("format-value", lambda _s, v: f"{int(v)} ms")
        self.duration.connect("value-changed", lambda *_: self._custom_changed())
        grid.attach(self.duration, 1, 3, 1, 1)
        grid.attach(W.label("Fenêtres élastiques"), 0, 4, 1, 1)
        self.wobbly = Gtk.Switch()
        self.wobbly.set_halign(Gtk.Align.START)
        self.wobbly.connect("notify::active", lambda *_: self._custom_changed())
        grid.attach(self.wobbly, 1, 4, 1, 1)
        apply_btn = W.button("Appliquer", css="suggested-action", on_click=self._apply_custom)
        apply_btn.set_halign(Gtk.Align.START)
        grid.attach(apply_btn, 1, 5, 1, 1)
        box.pack_start(grid, False, False, 0)
        self.custom_preview = EffectPreview(self._custom_preset(), 320, 190)
        self.custom_preview.set_valign(Gtk.Align.START)
        box.pack_start(self.custom_preview, False, False, 0)
        self.content.pack_start(box, False, False, 0)

        note = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        W.add_class(note, "info-box")
        note.pack_start(W.label("<b>Bon à savoir</b>", markup=True), False, False, 0)
        note.pack_start(W.label(
            "XFCE ne sait pas animer les fenêtres : quand les animations sont activées, BESTthemes "
            "remplace son gestionnaire de fenêtres (xfwm4) par Compiz. Les bordures des fenêtres "
            "suivent alors le thème des applications quand il le permet (WhiteSur, Dracula, Mint-L…), "
            "sinon un style simple aux couleurs du thème. Si l'écran clignote ou si quelque chose "
            "ne va pas, désactivez l'interrupteur ou cliquez sur « Annuler » : XFCE revient "
            "comme avant. Si Compiz plante au démarrage, XFCE reprend la main tout seul.",
            wrap=True), False, False, 0)
        self.content.pack_start(note, False, False, 0)
        self.read()

    def _custom_preset(self):
        if not hasattr(self, "combos"):
            return dict(animations.PRESETS[0])
        return {"open": self.combos["open"].get_active_id() or "Zoom",
                "close": self.combos["close"].get_active_id() or "Zoom",
                "minimize": self.combos["minimize"].get_active_id() or "Magic Lamp",
                "duration": int(self.duration.get_value()),
                "wobbly": self.wobbly.get_active()}

    def _custom_changed(self):
        if self._updating:
            return
        self.custom_preview.preset = self._custom_preset()

    def read(self):
        if not hasattr(self, "switch"):
            return
        self._updating = True
        on = animations.enabled()
        self.switch.set_active(on)
        self.status.set_text("Activées (Compiz)" if animations.running() else
                             "Activées au prochain démarrage" if on else
                             "Désactivées — XFCE standard (xfwm4)")
        try:
            s = animations.read_settings()
        except Exception:  # noqa: BLE001
            s = dict(animations.PRESETS[0])
        for key in ("open", "close", "minimize"):
            self.combos[key].set_active_id(s[key] if s[key] in animations.EFFECTS else "None")
        self.duration.set_value(s["duration"])
        self.wobbly.set_active(s["wobbly"])
        current = None
        for p in animations.PRESETS:
            if all(p[k] == s[k] for k in ("open", "close", "minimize")):
                current = p["id"]
        for pid, card in self.cards.items():
            card.set_active(on and pid == current)
        self.custom_preview.preset = self._custom_preset()
        self._updating = False

    def _on_switch(self, sw, _p):
        if self._updating:
            return
        if sw.get_active():
            self._enable(None, "Animations activées")
        else:
            backup.snapshot("Désactiver les animations")
            animations.stop_compiz()
            self._after("Animations désactivées")

    def _apply_preset(self, p):
        self._enable(p, f"Animations « {p['name']} »")

    def _apply_custom(self):
        self._enable(self._custom_preset(), "Animations personnalisées")

    def _enable(self, preset, label):
        if not animations.enabled() and not W.confirm(
                self.win, "Activer les animations ?",
                "Le gestionnaire de fenêtres va être remplacé par Compiz : l'écran peut "
                "clignoter une seconde. Vous pourrez revenir en arrière à tout moment.",
                "Activer"):
            self.read()
            return
        backup.snapshot(label)
        if preset:
            animations.write_settings(preset["open"], preset["close"], preset["minimize"],
                                      preset["duration"], preset.get("wobbly", False))
        else:
            # Première activation : style macOS par défaut
            s = animations.read_settings()
            if s["minimize"] not in ("Magic Lamp", "Magic Lamp Wavy"):
                animations.apply_preset("macos")
        from ..core import applier, xfconf
        animations.sync_decorations(applier.current()["gtk"],
                                    xfconf.get("xfwm4", "/general/button_layout", None))
        animations.start_compiz()
        self._after(label)

    def _after(self, text):
        self.win.applied(text)
        GLib.timeout_add(1500, lambda: (self.read(), False)[1])

    def on_show(self):
        if animations.available() and not hasattr(self, "switch"):
            self.build()
        self.read()

    def on_changed(self):
        self.read()
