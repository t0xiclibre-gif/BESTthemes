"""BESTthemes — personnalisez Linux Mint XFCE sans terminal."""
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from . import __version__  # noqa: E402
from .core import backup, paths, xfconf  # noqa: E402
from .ui import widgets as W  # noqa: E402

APP_ID = "io.github.bestthemes"

PAGES = [
    ("home", "Accueil", "go-home-symbolic"),
    ("packs", "Packs", "starred-symbolic"),
    ("themes", "Mes thèmes", "applications-graphics-symbolic"),
    ("wallpapers", "Fonds d'écran", "image-x-generic-symbolic"),
    ("workshop", "Workshop", "folder-download-symbolic"),
    ("creator", "Créateur", "applications-science-symbolic"),
    ("panel", "Panneau", "view-continuous-symbolic"),
    ("dock", "Dock", "view-app-grid-symbolic"),
    ("animations", "Animations", "applications-multimedia-symbolic"),
]


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="BESTthemes")
        self.set_default_size(1180, 780)
        self.set_icon_name("bestthemes")
        self.pages = {}

        hb = Gtk.HeaderBar(show_close_button=True)
        hb.set_title("BESTthemes")
        hb.set_subtitle("Votre bureau, en mieux")
        self.set_titlebar(hb)
        self.undo_btn = W.button("Annuler", "edit-undo-symbolic", tooltip="Annuler la dernière modification",
                                 on_click=self.undo)
        hb.pack_start(self.undo_btn)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
        menu = Gio.Menu()
        menu.append("Restaurer mon bureau d'origine", "win.restore-original")
        menu.append("Ouvrir le dossier des thèmes", "win.open-themes")
        menu.append("À propos de BESTthemes", "win.about")
        menu_btn.set_menu_model(menu)
        hb.pack_end(menu_btn)
        for name, cb in (("restore-original", self.restore_original),
                         ("open-themes", self.open_themes_dir), ("about", self.about)):
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", lambda *_a, f=cb: f())
            self.add_action(act)

        overlay = Gtk.Overlay()
        self.add(overlay)
        root = Gtk.Box()
        overlay.add(root)

        # Barre latérale
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        W.add_class(side, "app-sidebar")
        side.set_size_request(210, -1)
        logo = W.label("<span size='x-large' weight='heavy'>BEST</span><span size='x-large' weight='light'>themes</span>",
                       "logo", markup=True, xalign=0.5)
        logo.set_margin_top(18)
        logo.set_margin_bottom(14)
        side.pack_start(logo, False, False, 0)
        self.nav = Gtk.ListBox()
        self.nav.set_selection_mode(Gtk.SelectionMode.SINGLE)
        W.add_class(self.nav, "nav")
        for pid, title, icon in PAGES:
            row = Gtk.ListBoxRow()
            row.page_id = pid
            box = Gtk.Box(spacing=12)
            box.set_margin_start(14)
            box.set_margin_end(14)
            box.set_margin_top(10)
            box.set_margin_bottom(10)
            box.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.LARGE_TOOLBAR), False, False, 0)
            box.pack_start(W.label(title, "nav-label"), False, False, 0)
            row.add(box)
            self.nav.add(row)
        self.nav.connect("row-selected", self._on_nav)
        side.pack_start(self.nav, True, True, 0)
        ver = W.label(f"v{__version__} · Linux Mint XFCE", "dim", xalign=0.5)
        ver.set_margin_bottom(12)
        side.pack_end(ver, False, False, 0)
        root.pack_start(side, False, False, 0)
        root.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(150)
        root.pack_start(self.stack, True, True, 0)

        # Notification (toast)
        self.toast_revealer = Gtk.Revealer()
        self.toast_revealer.set_halign(Gtk.Align.CENTER)
        self.toast_revealer.set_valign(Gtk.Align.END)
        self.toast_revealer.set_margin_bottom(24)
        self.toast_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        tbox = Gtk.Box(spacing=12)
        W.add_class(tbox, "toast")
        self.toast_label = W.label("", "toast-label")
        self.toast_undo = W.button("Annuler", css="flat toast-button", on_click=self.undo)
        close = W.button(icon="window-close-symbolic", css="flat toast-button",
                         on_click=lambda: self.toast_revealer.set_reveal_child(False))
        tbox.pack_start(self.toast_label, True, True, 0)
        tbox.pack_start(self.toast_undo, False, False, 0)
        tbox.pack_start(close, False, False, 0)
        self.toast_revealer.add(tbox)
        overlay.add_overlay(self.toast_revealer)
        self._toast_timeout = None

        self.show_all()
        self.toast_undo.hide()
        self.update_undo()
        self.nav.select_row(self.nav.get_row_at_index(0))

        if not xfconf.available():
            GLib.idle_add(lambda: W.error_dialog(
                self, "XFCE introuvable",
                "BESTthemes est conçu pour Linux Mint XFCE : « xfconf-query » est absent, "
                "les réglages ne pourront pas être appliqués.") and False)

    # ------------------------------------------------------------------ navigation

    def _page(self, pid):
        page = self.pages.get(pid)
        if page is None:
            from .ui import (animations_page, creator_page, dock_page, home, packs_page,
                             panel_page, themes_page, wallpapers_page, workshop_page)
            factory = {
                "home": home.HomePage, "packs": packs_page.PacksPage,
                "themes": themes_page.ThemesPage, "workshop": workshop_page.WorkshopPage,
                "wallpapers": wallpapers_page.WallpapersPage,
                "creator": creator_page.CreatorPage, "panel": panel_page.PanelPage,
                "dock": dock_page.DockPage, "animations": animations_page.AnimationsPage,
            }[pid]
            page = factory(self)
            page.show_all()
            self.stack.add_named(page, pid)
            self.pages[pid] = page
        return page

    def _on_nav(self, _lb, row):
        if row is None:
            return
        page = self._page(row.page_id)
        self.stack.set_visible_child(page)
        if hasattr(page, "on_show"):
            page.on_show()

    def go(self, pid, **kwargs):
        page = self._page(pid)
        for row in self.nav.get_children():
            if row.page_id == pid:
                self.nav.select_row(row)
                if kwargs and hasattr(page, "navigate"):
                    page.navigate(**kwargs)
                return

    def changed(self):
        """Une modification a été appliquée : rafraîchir les pages visibles."""
        self.update_undo()
        for page in self.pages.values():
            if hasattr(page, "on_changed"):
                page.on_changed()

    # ------------------------------------------------------------------ notifications

    def toast(self, text, undo=False, timeout=5):
        self.toast_label.set_text(text)
        self.toast_undo.set_visible(undo and backup.can_undo())
        self.toast_revealer.set_reveal_child(True)
        if self._toast_timeout:
            GLib.source_remove(self._toast_timeout)

        def hide():
            self.toast_revealer.set_reveal_child(False)
            self._toast_timeout = None
            return False
        self._toast_timeout = GLib.timeout_add_seconds(timeout, hide)

    def applied(self, text):
        self.changed()
        self.toast(f"✓ {text}", undo=True)

    def update_undo(self):
        label = backup.last_label()
        self.undo_btn.set_sensitive(label is not None)
        self.undo_btn.set_tooltip_text(f"Annuler : {label}" if label else "Rien à annuler")

    def undo(self):
        label = backup.undo()
        self.changed()
        if label is not None:
            self.toast(f"↶ Annulé : {label}")
        else:
            self.toast("Rien à annuler")

    def restore_original(self):
        if not backup.has_original():
            self.toast("Aucune sauvegarde d'origine trouvée")
            return
        if W.confirm(self, "Restaurer le bureau d'origine ?",
                     "Le thème, les icônes, le curseur, le fond d'écran et le panneau "
                     "reviendront à leur état du premier lancement de BESTthemes. "
                     "Vos thèmes téléchargés restent installés.", "Restaurer"):
            backup.restore_original()
            self.applied("Bureau d'origine restauré")

    def open_themes_dir(self):
        Gio.AppInfo.launch_default_for_uri(paths.USER_THEMES.as_uri(), None)

    def about(self):
        d = Gtk.AboutDialog(transient_for=self, modal=True)
        d.set_program_name("BESTthemes")
        d.set_version(__version__)
        d.set_logo_icon_name("bestthemes")
        d.set_comments("Thèmes, icônes, curseurs, panneau, dock et fonds d'écran pour "
                       "Linux Mint XFCE — en quelques clics, sans terminal.\n\n"
                       "Les thèmes du Workshop viennent de xfce-look.org / pling.com et de "
                       "GitHub ; ils appartiennent à leurs auteurs respectifs.")
        d.set_license_type(Gtk.License.GPL_3_0)
        d.run()
        d.destroy()


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.win = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        paths.ensure_dirs()
        try:
            backup.save_original_once()
        except Exception as e:  # noqa: BLE001
            print("Sauvegarde d'origine impossible :", e, file=sys.stderr)
        provider = Gtk.CssProvider()
        provider.load_from_path(str(paths.DATA_DIR / "style.css"))
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        icon_dir = paths.DATA_DIR / "icons"
        if icon_dir.is_dir():
            Gtk.IconTheme.get_default().append_search_path(str(icon_dir))
        from .core import wallpaper
        wallpaper.SCREEN = wallpaper.screen_size()

    def do_activate(self):
        if self.win is None:
            self.win = MainWindow(self)
        self.win.present()


def main():
    return App().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
