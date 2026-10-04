"""Page « Dock » : Plank, le dock façon macOS."""
import subprocess

from gi.repository import Gtk

from ..core import plank, scanner
from . import previews
from . import widgets as W
from .panel_page import Burst

HIDE_MODES = [
    ("none", "Toujours visible"),
    ("intelligent", "Intelligent"),
    ("auto", "Se cacher automatiquement"),
    ("window-dodge", "S'écarter des fenêtres"),
    ("dodge-maximized", "S'écarter des fenêtres agrandies"),
]
POSITIONS = [("bottom", "En bas"), ("left", "À gauche"), ("right", "À droite"), ("top", "En haut")]


class DockPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self._updating = False
        self._themes_loaded = False
        self.burst = Burst(win, "Réglages du dock")
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.pack_start(W.scrolled(self.content), True, True, 0)
        self.build()

    def build(self):
        W.clear(self.content)
        self._themes_loaded = False
        self.content.pack_start(W.page_header(
            "Dock",
            "Plank est un dock élégant façon macOS : vos applications favorites en bas de "
            "l'écran, avec effet de zoom."), False, False, 0)
        if not plank.installed():
            self._build_install()
        else:
            self._build_settings()
        self.content.show_all()

    def _build_install(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        W.add_class(box, "info-box")
        box.pack_start(W.label("<b>Le dock n'est pas encore installé</b>", markup=True), False, False, 0)
        box.pack_start(W.label("Cliquez sur le bouton ci-dessous : Linux Mint vous demandera votre mot "
                               "de passe, puis Plank sera installé automatiquement (environ 1 Mo).",
                               wrap=True), False, False, 0)
        self.install_btn = W.button("Installer le dock", "folder-download-symbolic",
                                    css="suggested-action big-button", on_click=self.install)
        self.install_btn.set_halign(Gtk.Align.START)
        self.install_spinner = Gtk.Spinner()
        row = Gtk.Box(spacing=10)
        row.pack_start(self.install_btn, False, False, 0)
        row.pack_start(self.install_spinner, False, False, 0)
        box.pack_start(row, False, False, 0)
        self.content.pack_start(box, False, False, 0)

    def install(self, then=None):
        if plank.installed():
            if then:
                then()
            return
        if getattr(self, "install_btn", None):
            self.install_btn.set_sensitive(False)
            self.install_spinner.start()

        def done(res):
            ok, msg = res
            if ok:
                plank.enable(True)
                self.build()
                self.win.toast("✓ Dock installé et lancé")
                if then:
                    then()
            else:
                self.build()
                if msg != "Installation annulée.":
                    W.error_dialog(self.win, "L'installation du dock a échoué",
                                   msg or "Erreur inconnue.")

        W.run_async(plank.install, done, lambda e: (self.build(), W.error_dialog(
            self.win, "L'installation du dock a échoué", str(e))))

    def _build_settings(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        W.add_class(box, "settings-box")
        grid = Gtk.Grid(column_spacing=16, row_spacing=12)
        r = 0
        grid.attach(W.label("Afficher le dock"), 0, r, 1, 1)
        self.enabled = Gtk.Switch()
        self.enabled.set_halign(Gtk.Align.START)
        self.enabled.connect("notify::active", self._on_enable)
        grid.attach(self.enabled, 1, r, 1, 1)
        r += 1
        grid.attach(W.label("Position"), 0, r, 1, 1)
        self.position = Gtk.ComboBoxText()
        for k, v in POSITIONS:
            self.position.append(k, v)
        self.position.connect("changed", lambda c: self._set("position", c.get_active_id()))
        grid.attach(self.position, 1, r, 1, 1)
        r += 1
        grid.attach(W.label("Taille des icônes"), 0, r, 1, 1)
        self.icon_size = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 24, 128, 2)
        self.icon_size.set_hexpand(True)
        self.icon_size.set_size_request(320, -1)
        self.icon_size.set_value_pos(Gtk.PositionType.RIGHT)
        self.icon_size.connect("value-changed", lambda s: self._set("icon-size", int(s.get_value())))
        grid.attach(self.icon_size, 1, r, 1, 1)
        r += 1
        grid.attach(W.label("Effet de zoom"), 0, r, 1, 1)
        zbox = Gtk.Box(spacing=10)
        self.zoom = Gtk.Switch()
        self.zoom.set_valign(Gtk.Align.CENTER)
        self.zoom.connect("notify::active", lambda s, _p: self._set("zoom-enabled", s.get_active()))
        self.zoom_pct = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 100, 200, 5)
        self.zoom_pct.set_hexpand(True)
        self.zoom_pct.set_value_pos(Gtk.PositionType.RIGHT)
        self.zoom_pct.connect("value-changed", lambda s: self._set("zoom-percent", int(s.get_value())))
        zbox.pack_start(self.zoom, False, False, 0)
        zbox.pack_start(self.zoom_pct, True, True, 0)
        grid.attach(zbox, 1, r, 1, 1)
        r += 1
        grid.attach(W.label("Masquage"), 0, r, 1, 1)
        self.hide = Gtk.ComboBoxText()
        for k, v in HIDE_MODES:
            self.hide.append(k, v)
        self.hide.connect("changed", lambda c: self._set("hide-mode", c.get_active_id()))
        grid.attach(self.hide, 1, r, 1, 1)
        box.pack_start(grid, False, False, 0)
        extra = Gtk.Box(spacing=8)
        extra.pack_start(W.button("Préférences de Plank…", "preferences-system-symbolic",
                                  on_click=self._prefs), False, False, 0)
        box.pack_start(extra, False, False, 0)
        box.pack_start(W.label("Astuce : pour ajouter une application au dock, lancez-la puis "
                               "faites un clic droit sur son icône → « Garder dans le dock ».",
                               "hint", wrap=True), False, False, 0)
        self.content.pack_start(box, False, False, 0)

        head = Gtk.Box(spacing=10)
        head.pack_start(W.section_title("Thèmes du dock"), False, False, 0)
        head.pack_end(W.button("Trouver plus de thèmes", "folder-download-symbolic",
                               on_click=lambda: self.win.go("workshop", kind="plank")), False, False, 0)
        self.content.pack_start(head, False, False, 0)
        self.themes = W.flowbox(2, 4)
        self.content.pack_start(self.themes, False, False, 0)
        self.read()
        self.load_themes()

    def _prefs(self):
        try:
            subprocess.Popen(["plank", "--preferences"], start_new_session=True)
        except OSError as e:
            W.error_dialog(self.win, "Impossible d'ouvrir les préférences", str(e))

    def read(self):
        if not plank.installed() or not hasattr(self, "enabled"):
            return
        self._updating = True
        self.enabled.set_active(plank.running() or plank.autostart_enabled())
        self.position.set_active_id(plank.get("position") or "bottom")
        try:
            self.icon_size.set_value(int(plank.get("icon-size") or 48))
            self.zoom_pct.set_value(int(plank.get("zoom-percent") or 150))
        except ValueError:
            pass
        self.zoom.set_active((plank.get("zoom-enabled") or "false") == "true")
        self.hide.set_active_id(plank.get("hide-mode") or "intelligent")
        self._updating = False

    def _set(self, key, value):
        if self._updating or value is None:
            return
        self.burst.touch()
        plank.set(key, value)

    def _on_enable(self, sw, _p):
        if self._updating:
            return
        self.burst.touch()
        plank.enable(sw.get_active())

    def load_themes(self):
        if self._themes_loaded or not hasattr(self, "themes"):
            return
        self._themes_loaded = True
        W.clear(self.themes)
        current = plank.get("theme")
        self.cards = {}
        for t in scanner.scan("plank"):
            prev = W.Preview(lambda cr, w, h, t=t: previews.draw_plank(cr, w, h, t.path), 240, 90,
                             bg="#7d8fb3")
            card = W.Card(prev, t.name, "Installé par vous" if t.user else "Système",
                          on_activate=lambda t=t: self._apply_theme(t.name), active=t.name == current)
            self.cards[t.name] = card
            self.themes.add(card)
        self.themes.show_all()

    def _apply_theme(self, name):
        from ..core import backup
        backup.snapshot(f"Thème du dock : {name}")
        plank.set("theme", name)
        if not plank.running():
            plank.enable(True)
        self.win.applied(f"Thème du dock : {name}")

    def invalidate(self):
        self._themes_loaded = False

    def on_show(self):
        if plank.installed() and not hasattr(self, "enabled"):
            self.build()
        self.read()
        self.load_themes()

    def on_changed(self):
        self.read()
        current = plank.get("theme") if plank.installed() else None
        for name, card in getattr(self, "cards", {}).items():
            card.set_active(name == current)
