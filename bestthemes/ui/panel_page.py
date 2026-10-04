"""Page « Panneau » : la barre des tâches XFCE."""
import subprocess

from gi.repository import GLib, Gtk

from ..core import backup, panel, plank
from . import previews
from . import widgets as W


class Burst:
    """Regroupe une rafale de modifications (ex. glisser un curseur) en un seul « Annuler »."""

    def __init__(self, win, label):
        self.win = win
        self.label = label
        self.timer = None

    def touch(self):
        if self.timer is None:
            backup.snapshot(self.label)
        else:
            GLib.source_remove(self.timer)

        def end():
            self.timer = None
            self.win.changed()
            return False
        self.timer = GLib.timeout_add(1200, end)


def draw_preset(cr, w, h, p):
    grad_top, grad_bot = "#6a85b6", "#bac8e0"
    import cairo
    g = cairo.LinearGradient(0, 0, w, h)
    for off, c in ((0, grad_top), (1, grad_bot)):
        r, gg, b = previews.C.to_rgb(c)
        g.add_color_stop_rgba(off, r, gg, b, 1)
    cr.set_source(g)
    cr.paint()
    sz = max(6, p["size"] / 4.5)
    alpha = p.get("opacity", 1.0)
    cr.set_source_rgba(0.13, 0.13, 0.16, alpha)
    pos = p["position"]
    length = p["length"] / 100
    if pos == "top":
        cr.rectangle(w * (1 - length) / 2, 0, w * length, sz)
    elif pos == "left":
        cr.rectangle(0, 0, sz, h)
    elif pos == "right":
        cr.rectangle(w - sz, 0, sz, h)
    else:
        if p.get("autohide"):
            cr.set_source_rgba(0.13, 0.13, 0.16, 0.35)
        cr.rectangle(w * (1 - length) / 2, h - sz, w * length, sz)
    cr.fill()
    # icônes de la barre
    cr.set_source_rgba(1, 1, 1, 0.8)
    n = 5
    isz = sz * 0.55
    for i in range(n):
        if pos in ("left", "right"):
            x = (sz - isz) / 2 + (w - sz if pos == "right" else 0)
            y = 8 + i * (isz + 5)
        else:
            x = w * (1 - length) / 2 + 6 + i * (isz + 5)
            y = (sz - isz) / 2 + (0 if pos == "top" else h - sz)
        previews.rounded_rect(cr, x, y, isz, isz, 2)
        cr.fill()
    if p.get("plank"):
        cr.set_source_rgba(1, 1, 1, 0.45)
        previews.rounded_rect(cr, w * 0.3, h - 16, w * 0.4, 13, 5)
        cr.fill()
        for i, c in enumerate(("#e5484d", "#f5a524", "#30a46c", "#3584e4", "#9b59b6")):
            cr.arc(w * 0.34 + i * w * 0.08, h - 9.5, 4, 0, 6.3)
            previews.rgb(cr, c)
            cr.fill()
    # fenêtre
    cr.set_source_rgba(1, 1, 1, 0.9)
    previews.rounded_rect(cr, w * 0.3, h * 0.25, w * 0.42, h * 0.42, 5)
    cr.fill()


class PanelPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self._updating = False
        self.burst = Burst(win, "Réglages du panneau")
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.pack_start(W.page_header(
            "Panneau",
            "La barre des tâches de XFCE. Choisissez une disposition toute faite ou réglez-la "
            "vous-même ; les changements sont visibles immédiatement."), False, False, 0)

        content.pack_start(W.section_title("Dispositions prêtes"), False, False, 0)
        fb = W.flowbox(2, 4)
        for p in panel.PRESETS:
            prev = W.Preview(lambda cr, w, h, p=p: draw_preset(cr, w, h, p), 230, 130)
            card = W.Card(prev, p["name"], p["desc"], on_activate=lambda p=p: self._preset(p))
            fb.add(card)
        content.pack_start(fb, False, False, 0)

        content.pack_start(W.section_title("Réglages"), False, False, 0)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        W.add_class(box, "settings-box")
        grid = Gtk.Grid(column_spacing=16, row_spacing=12)
        r = 0

        grid.attach(W.label("Position"), 0, r, 1, 1)
        self.position = Gtk.ComboBoxText()
        for k, v in panel.POSITION_LABELS.items():
            self.position.append(k, v)
        self.position.connect("changed", self._on_position)
        grid.attach(self.position, 1, r, 1, 1)

        def scale(lo, hi, step, fmt=None):
            s = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, step)
            s.set_hexpand(True)
            s.set_size_request(320, -1)
            s.set_value_pos(Gtk.PositionType.RIGHT)
            if fmt:
                s.connect("format-value", lambda _s, v: fmt(v))
            return s

        r += 1
        grid.attach(W.label("Épaisseur"), 0, r, 1, 1)
        self.size = scale(16, 96, 1, lambda v: f"{int(v)} px")
        self.size.connect("value-changed", lambda s: self._apply(panel.set_size, int(s.get_value())))
        grid.attach(self.size, 1, r, 1, 1)
        r += 1
        grid.attach(W.label("Longueur"), 0, r, 1, 1)
        self.length = scale(10, 100, 1, lambda v: f"{int(v)} %")
        self.length.connect("value-changed", lambda s: self._apply(panel.set_length, int(s.get_value())))
        grid.attach(self.length, 1, r, 1, 1)
        r += 1
        grid.attach(W.label("Taille des icônes"), 0, r, 1, 1)
        self.icons = scale(0, 64, 2, lambda v: "Auto" if v == 0 else f"{int(v)} px")
        self.icons.connect("value-changed", lambda s: self._apply(panel.set_icon_size, int(s.get_value())))
        grid.attach(self.icons, 1, r, 1, 1)
        r += 1
        grid.attach(W.label("Opacité"), 0, r, 1, 1)
        self.opacity = scale(0.2, 1.0, 0.05, lambda v: f"{int(round(v * 100))} %")
        self.opacity.connect("value-changed", lambda s: self._apply(panel.set_opacity, s.get_value()))
        grid.attach(self.opacity, 1, r, 1, 1)
        r += 1
        grid.attach(W.label("Masquage automatique"), 0, r, 1, 1)
        self.autohide = Gtk.ComboBoxText()
        for k, v in (("0", "Jamais"), ("1", "Intelligent (si une fenêtre la recouvre)"), ("2", "Toujours")):
            self.autohide.append(k, v)
        self.autohide.connect("changed", lambda c: self._apply(panel.set_autohide, int(c.get_active_id() or 0)))
        grid.attach(self.autohide, 1, r, 1, 1)
        r += 1
        grid.attach(W.label("Mode sombre du panneau"), 0, r, 1, 1)
        self.dark = Gtk.Switch()
        self.dark.set_halign(Gtk.Align.START)
        self.dark.connect("notify::active", lambda s, _p: self._apply(panel.set_dark, s.get_active()))
        grid.attach(self.dark, 1, r, 1, 1)
        box.pack_start(grid, False, False, 0)

        extra = Gtk.Box(spacing=8)
        extra.set_margin_top(6)
        extra.pack_start(W.button("Ajouter des éléments au panneau…", "list-add-symbolic",
                                  on_click=lambda: self._run(["xfce4-panel", "--add"])), False, False, 0)
        extra.pack_start(W.button("Réglages avancés…", "preferences-system-symbolic",
                                  on_click=lambda: self._run(["xfce4-panel", "--preferences"])), False, False, 0)
        extra.pack_start(W.button("Redémarrer le panneau", "view-refresh-symbolic",
                                  on_click=lambda: self._run(["xfce4-panel", "-r"])), False, False, 0)
        box.pack_start(extra, False, False, 0)
        content.pack_start(box, False, False, 0)

        self.pack_start(W.scrolled(content), True, True, 0)
        self.read()

    def _run(self, cmd):
        try:
            subprocess.Popen(cmd, start_new_session=True)
        except OSError as e:
            W.error_dialog(self.win, "Impossible de lancer la commande", str(e))

    def read(self):
        self._updating = True
        s = panel.read()
        self.position.set_active_id(s["position"])
        self.size.set_value(s["size"])
        self.length.set_value(s["length"])
        self.icons.set_value(s["icon_size"])
        self.opacity.set_value(s["opacity"])
        self.autohide.set_active_id(str(s["autohide"]))
        self.dark.set_active(s["dark"])
        self._updating = False

    def _apply(self, func, value):
        if self._updating:
            return
        self.burst.touch()
        func(value)

    def _on_position(self, combo):
        pos = combo.get_active_id()
        if pos:
            self._apply(panel.set_position, pos)

    def _preset(self, p):
        if p.get("plank") and not plank.installed():
            if W.confirm(self.win, "Installer le dock ?",
                         f"La disposition « {p['name']} » utilise le dock Plank, qui n'est pas "
                         "encore installé. Voulez-vous l'installer maintenant ? "
                         "(votre mot de passe sera demandé)", "Installer"):
                self.win.go("dock")
                self.win.pages["dock"].install(then=lambda: self._preset(p))
                return
        panel.apply_preset(p)
        self.read()
        self.win.applied(f"Disposition « {p['name']} » appliquée")

    def on_show(self):
        self.read()

    def on_changed(self):
        self.read()
