"""Page « Mes thèmes » : appliquer en un clic ce qui est installé."""
from pathlib import Path

from gi.repository import GdkPixbuf, Gtk

from ..core import applier, installer, paths, scanner, settings
from . import previews
from . import widgets as W

TABS = [
    ("gtk", "Applications"),
    ("xfwm4", "Bordures de fenêtres"),
    ("icons", "Icônes"),
    ("cursors", "Curseurs"),
    ("wallpaper", "Fonds d'écran"),
]

WALLPAPER_DIRS = [paths.WALLPAPER_DIR, Path("/usr/share/backgrounds"),
                  Path.home() / "Images", Path.home() / "Pictures"]
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".svg"}


class ThemeGrid(Gtk.Box):
    def __init__(self, win, kind):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.win = win
        self.kind = kind
        self.cards = {}
        self.loaded = False

        bar = Gtk.Box(spacing=10)
        self.search = Gtk.SearchEntry(placeholder_text="Rechercher…")
        self.search.set_size_request(260, -1)
        self.search.connect("search-changed", lambda *_: self.flow.invalidate_filter())
        bar.pack_start(self.search, False, False, 0)
        self._extra_controls(bar)
        get_more = W.button("Trouver plus de thèmes", "folder-download-symbolic",
                            on_click=lambda: win.go("workshop", kind=kind))
        if kind != "wallpaper":
            bar.pack_end(get_more, False, False, 0)
        self.pack_start(bar, False, False, 0)

        self.flow = W.flowbox(1, 5)
        self.flow.set_filter_func(self._filter)
        self.pack_start(self.flow, True, True, 0)

    def _extra_controls(self, bar):
        if self.kind == "gtk":
            sw = Gtk.Switch(active=settings.get("sync_wm_with_gtk"))
            sw.set_valign(Gtk.Align.CENTER)
            sw.connect("notify::active", lambda s, _p: settings.set("sync_wm_with_gtk", s.get_active()))
            bar.pack_start(sw, False, False, 0)
            bar.pack_start(W.label("Changer aussi les bordures de fenêtres"), False, False, 0)
        elif self.kind == "cursors":
            bar.pack_start(W.label("Taille :"), False, False, 0)
            combo = Gtk.ComboBoxText()
            sizes = [("24", "Normale (24)"), ("32", "Grande (32)"), ("48", "Très grande (48)"),
                     ("64", "Énorme (64)")]
            for sid, text in sizes:
                combo.append(sid, text)
            cur = str(applier.current()["cursor_size"])
            if cur not in dict(sizes):
                combo.append(cur, cur)
            combo.set_active_id(cur)
            combo.connect("changed", lambda c: self._cursor_size(c.get_active_id()))
            bar.pack_start(combo, False, False, 0)
        elif self.kind == "wallpaper":
            bar.pack_start(W.button("Choisir une image…", "document-open-symbolic",
                                    on_click=self._pick_wallpaper), False, False, 0)
            bar.pack_start(W.button("Plus de fonds d'écran (HQ, animés)", "image-x-generic-symbolic",
                                    on_click=lambda: self.win.go("wallpapers")), False, False, 0)

    def _cursor_size(self, size):
        if size:
            applier.apply({"cursor_size": int(size)}, f"Taille du curseur : {size}")
            self.win.applied(f"Taille du curseur : {size} px")

    def _pick_wallpaper(self):
        d = Gtk.FileChooserNative.new("Choisir un fond d'écran", self.win,
                                      Gtk.FileChooserAction.OPEN, "Choisir", "Annuler")
        f = Gtk.FileFilter()
        f.set_name("Images")
        f.add_mime_type("image/*")
        d.add_filter(f)
        if d.run() == Gtk.ResponseType.ACCEPT:
            self._apply(d.get_filename())

    def _filter(self, child):
        q = self.search.get_text().strip().lower()
        if not q:
            return True
        return q in getattr(child, "search_text", "")

    # ------------------------------------------------------------------ remplissage

    def load(self, force=False):
        if self.loaded and not force:
            self.update_active()
            return
        self.loaded = True
        W.clear(self.flow)
        self.cards = {}
        if self.kind == "wallpaper":
            self._load_wallpapers()
            return
        previews.gtk_theme_colors.cache_clear()
        previews._wm_parts.cache_clear()
        themes = scanner.scan(self.kind)
        if not themes:
            self.flow.add(W.label("Aucun thème trouvé. Allez dans le Workshop pour en télécharger !",
                                  "hint"))
        for t in themes:
            card = self._card(t)
            child = Gtk.FlowBoxChild()
            child.search_text = (t.name + " " + t.label).lower()
            child.add(card)
            self.flow.add(child)
            self.cards[t.name] = card
        self.flow.show_all()
        self.update_active()

    def _preview_for(self, t):
        if self.kind == "gtk":
            col = previews.gtk_theme_colors(str(t.path))
            style = "macos" if any(k in t.name.lower() for k in ("whitesur", "mojave", "mac")) else "windows"
            return W.Preview(lambda cr, w, h: previews.draw_window_mock(cr, w, h, col, style),
                             240, 150, bg="#8f9bb3" if not previews.C.is_dark(col["bg"]) else "#3a4256")
        if self.kind == "xfwm4":
            return W.Preview(lambda cr, w, h: previews.draw_xfwm4(cr, w, h, t.path), 240, 110,
                             bg="#9aa5b8")
        if self.kind == "icons":
            return W.Preview(lambda cr, w, h: previews.draw_icons(cr, w, h, t.name, 4, 40), 240, 80,
                             bg="#e7e9ee")
        if self.kind == "cursors":
            return W.Preview(lambda cr, w, h: previews.draw_cursors(cr, w, h, t.path), 240, 80,
                             bg="#f2f2f5")
        return Gtk.Label()

    def _card(self, t):
        sub = "Installé par vous" if t.user else "Système"
        card = W.Card(self._preview_for(t), t.label, sub,
                      on_activate=lambda: self._apply(t.name))
        if t.user:
            delete = W.button(icon="user-trash-symbolic", css="flat", tooltip="Supprimer ce thème",
                              on_click=lambda: self._delete(t))
            card.actions.pack_end(delete, False, False, 0)
        if self.kind == "gtk" and scanner.find("xfwm4", t.name):
            card.actions.pack_start(W.label("+ bordures", "pill"), False, False, 0)
        return card

    def _apply(self, name):
        applier.apply_one(self.kind, name)
        label = dict(TABS)[self.kind]
        self.win.applied(f"{label} : {Path(name).name}")

    def _delete(self, t):
        if not W.confirm(self.win, f"Supprimer « {t.label} » ?",
                         f"Le dossier {t.path} sera supprimé définitivement.", "Supprimer", True):
            return
        try:
            installer.uninstall_path(t.path)
        except installer.InstallError as e:
            W.error_dialog(self.win, "Suppression impossible", str(e))
            return
        self.win.toast(f"🗑 {t.label} supprimé")
        self.load(force=True)

    def _load_wallpapers(self):
        files = []
        for d in WALLPAPER_DIRS:
            if not d.is_dir():
                continue
            try:
                found = sorted((p for p in d.rglob("*") if p.suffix.lower() in IMG_EXT
                                and p.is_file()), key=lambda p: -p.stat().st_mtime)
            except OSError:
                continue
            files.extend(found[:120])
        if not files:
            self.flow.add(W.label("Aucune image trouvée.", "hint"))
        for f in files[:300]:
            area = _Thumb(f)
            card = W.Card(area, f.stem.replace("_", " "), f.parent.name,
                          on_activate=lambda f=f: self._apply(str(f)))
            child = Gtk.FlowBoxChild()
            child.search_text = str(f).lower()
            child.add(card)
            self.flow.add(child)
            self.cards[str(f)] = card
        self.flow.show_all()
        self.update_active()

    def update_active(self):
        cur = applier.current()
        key = {"gtk": "gtk", "xfwm4": "xfwm4", "icons": "icons", "cursors": "cursors",
               "wallpaper": "wallpaper"}[self.kind]
        active = cur.get(key)
        for name, card in self.cards.items():
            card.set_active(name == active)


class _Thumb(W.Preview):
    """Vignette d'image chargée en arrière-plan."""

    def __init__(self, path):
        self.pb = None
        self.path = path
        super().__init__(self._draw, 240, 135)
        self.connect("map", self._start)
        self._started = False

    def _start(self, *_):
        if self._started:
            return
        self._started = True
        W.run_async(lambda: GdkPixbuf.Pixbuf.new_from_file_at_scale(str(self.path), 480, 270, True),
                    self._loaded, lambda e: None)

    def _loaded(self, pb):
        self.pb = pb
        self.queue_draw()

    def _draw(self, cr, w, h):
        if self.pb:
            previews.cover_pixbuf(cr, self.pb, w, h, 10)
        else:
            cr.set_source_rgba(0.5, 0.5, 0.5, 0.2)
            cr.paint()


class ThemesPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.win = win
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        top.set_margin_start(24)
        top.set_margin_end(24)
        top.set_margin_top(24)
        top.pack_start(W.page_header("Mes thèmes",
                                     "Cliquez sur un thème pour l'appliquer immédiatement. "
                                     "Vous pouvez toujours annuler."), False, False, 0)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.grids = {}
        for kind, title in TABS:
            grid = ThemeGrid(win, kind)
            self.grids[kind] = grid
            self.stack.add_titled(W.scrolled(grid), kind, title)
        switcher = Gtk.StackSwitcher(stack=self.stack)
        W.add_class(switcher, "tabs")
        switcher.set_halign(Gtk.Align.START)
        top.pack_start(switcher, False, False, 0)
        self.pack_start(top, False, False, 0)
        self.pack_start(self.stack, True, True, 0)
        self.stack.connect("notify::visible-child-name", lambda *_: self.on_show())

    def on_show(self):
        name = self.stack.get_visible_child_name()
        if name in self.grids:
            self.grids[name].load()

    def on_changed(self):
        for g in self.grids.values():
            if g.loaded:
                g.update_active()

    def invalidate(self):
        for g in self.grids.values():
            g.loaded = False

    def navigate(self, kind=None, reload=False):
        if reload:
            for g in self.grids.values():
                g.loaded = False
        if kind in self.grids:
            self.stack.set_visible_child_name(kind)
        self.on_show()
