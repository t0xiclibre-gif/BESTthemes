"""Page d'accueil."""
from pathlib import Path

from gi.repository import GdkPixbuf, Gtk

from ..core import applier, packs, scanner
from . import packs_page, previews
from . import widgets as W


class HomePage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)

        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        W.add_class(hero, "hero")
        hero.pack_start(W.label("Bienvenue dans BESTthemes", "hero-title"), False, False, 0)
        hero.pack_start(W.label("Changez l'apparence de votre Linux Mint en un clic : thèmes, icônes, "
                                "curseurs, barre des tâches, dock et fonds d'écran. Tout est "
                                "réversible avec le bouton « Annuler ».", wrap=True), False, False, 0)
        actions = Gtk.Box(spacing=10)
        actions.set_margin_top(8)
        for text, icon, pid in (("Essayer un pack", "starred-symbolic", "packs"),
                                ("Fonds d'écran", "image-x-generic-symbolic", "wallpapers"),
                                ("Télécharger des thèmes", "folder-download-symbolic", "workshop"),
                                ("Créer mon thème", "applications-science-symbolic", "creator")):
            actions.pack_start(W.button(text, icon, on_click=lambda p=pid: win.go(p)), False, False, 0)
        hero.pack_start(actions, False, False, 0)
        content.pack_start(hero, False, False, 0)

        content.pack_start(W.section_title("Votre bureau actuel"), False, False, 0)
        self.current = W.flowbox(2, 4)
        content.pack_start(self.current, False, False, 0)

        content.pack_start(W.section_title("Packs à la une"), False, False, 0)
        featured = W.flowbox(1, 3)
        ids = ["macos-light", "gen-nord", "windows11-dark", "gen-synthwave", "catppuccin", "gen-mint"]
        for p in packs.load():
            if p["id"] in ids:
                featured.add(packs_page.pack_card(win, p))
        content.pack_start(featured, False, False, 0)
        more = W.button("Voir tous les packs", css="big-button", on_click=lambda: win.go("packs"))
        more.set_halign(Gtk.Align.START)
        content.pack_start(more, False, False, 0)

        safety = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        W.add_class(safety, "info-box")
        safety.pack_start(W.label("<b>Aucun risque</b>", markup=True), False, False, 0)
        safety.pack_start(W.label(
            "Avant chaque changement, BESTthemes enregistre votre configuration. Le bouton "
            "« Annuler » en haut à gauche revient en arrière, et le menu ☰ permet de retrouver "
            "votre bureau tel qu'il était au premier lancement.", wrap=True), False, False, 0)
        content.pack_start(safety, False, False, 0)

        self.pack_start(W.scrolled(content), True, True, 0)
        self.refresh()

    def refresh(self):
        W.clear(self.current)
        cur = applier.current()
        gtk_t = scanner.find("gtk", cur["gtk"])
        if gtk_t:
            col = previews.gtk_theme_colors(str(gtk_t.path))
            p = W.Preview(lambda cr, w, h: previews.draw_window_mock(cr, w, h, col), 220, 130,
                          bg="#8f9bb3")
        else:
            p = W.Preview(lambda cr, w, h: None, 220, 130, bg="#8f9bb3")
        self._add(p, "Thème", cur["gtk"], "themes", "gtk")
        self._add(W.Preview(lambda cr, w, h: previews.draw_icons(cr, w, h, cur["icons"], 4, 36),
                            220, 130, bg="#e7e9ee"), "Icônes", cur["icons"], "themes", "icons")
        cur_t = scanner.find("cursors", cur["cursors"])
        self._add(W.Preview(lambda cr, w, h: cur_t and previews.draw_cursors(cr, w, h, cur_t.path),
                            220, 130, bg="#f2f2f5"), "Curseur", cur["cursors"], "themes", "cursors")
        wp = cur.get("wallpaper") or ""
        pb = None
        if wp and Path(wp).is_file():
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(wp, 440, 260, True)
            except Exception:  # noqa: BLE001
                pb = None
        self._add(W.Preview(lambda cr, w, h: pb and previews.cover_pixbuf(cr, pb, w, h, 10),
                            220, 130, bg="#555a66"), "Fond d'écran", Path(wp).name or "—",
                  "themes", "wallpaper")
        self.current.show_all()

    def _add(self, preview, title, value, page, kind):
        card = W.Card(preview, title, value or "—",
                      on_activate=lambda: self.win.go(page, kind=kind))
        self.current.add(card)

    def on_changed(self):
        self.refresh()

    def on_show(self):
        self.refresh()
