"""Créateur de thèmes : choisir ses couleurs et générer un thème complet."""
import random
import shutil

from gi.repository import GLib, Gtk

from ..core import applier, backup, generator, paths, plank, wallpaper
from ..core import colors as C
from . import previews
from . import widgets as W

COLOR_FIELDS = [
    ("bg", "Fond des fenêtres"),
    ("fg", "Texte"),
    ("accent", "Couleur d'accent"),
    ("header", "Barres de titre"),
    ("surface", "Menus et popups"),
    ("base", "Zones de contenu"),
]


class CreatorPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.palettes = generator.load_palettes()
        self.pal = dict(self.palettes[0])
        self.style = "macos"
        self.wall_style = self.pal.get("wallpaper", "gradient")
        self.seed = None
        self._wall_cache = None
        self._redraw_timer = None
        self._loading = False

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.pack_start(W.page_header(
            "Créateur de thèmes",
            "Choisissez une palette de départ, ajustez les couleurs, puis créez votre thème : "
            "applications, bordures de fenêtres, dock et fond d'écran assortis."), False, False, 0)

        content.pack_start(W.section_title("1. Partir d'une palette"), False, False, 0)
        pal_flow = W.flowbox(4, 10)
        pal_flow.set_homogeneous(False)
        for p in self.palettes:
            pal_flow.add(self._palette_chip(p))
        content.pack_start(pal_flow, False, False, 0)

        main = Gtk.Box(spacing=20)
        content.pack_start(main, False, False, 0)

        # ---------- réglages
        form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        W.add_class(form, "settings-box")
        form.set_size_request(340, -1)
        form.pack_start(W.section_title("2. Personnaliser"), False, False, 0)
        grid = Gtk.Grid(column_spacing=12, row_spacing=8)
        row = 0
        grid.attach(W.label("Nom du thème"), 0, row, 1, 1)
        self.name_entry = Gtk.Entry()
        self.name_entry.set_hexpand(True)
        self.name_entry.connect("changed", lambda e: self._set("name", e.get_text().strip() or "Perso"))
        grid.attach(self.name_entry, 1, row, 1, 1)
        self.color_buttons = {}
        for key, text in COLOR_FIELDS:
            row += 1
            grid.attach(W.label(text), 0, row, 1, 1)
            b = W.color_button("#000000", lambda c, k=key: self._set(k, c))
            b.set_halign(Gtk.Align.START)
            self.color_buttons[key] = b
            grid.attach(b, 1, row, 1, 1)
        row += 1
        grid.attach(W.label("Coins arrondis"), 0, row, 1, 1)
        self.radius = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 16, 1)
        self.radius.set_value_pos(Gtk.PositionType.RIGHT)
        self.radius.connect("value-changed", lambda s: self._set("radius", int(s.get_value())))
        grid.attach(self.radius, 1, row, 1, 1)
        row += 1
        grid.attach(W.label("Boutons des fenêtres"), 0, row, 1, 1)
        self.style_combo = Gtk.ComboBoxText()
        for k, v in generator.BUTTON_STYLES.items():
            self.style_combo.append(k, v)
        self.style_combo.set_active_id(self.style)
        self.style_combo.connect("changed", self._style_changed)
        grid.attach(self.style_combo, 1, row, 1, 1)
        row += 1
        grid.attach(W.label("Fond d'écran"), 0, row, 1, 1)
        wbox = Gtk.Box(spacing=6)
        self.wall_combo = Gtk.ComboBoxText()
        for k, v in wallpaper.STYLES.items():
            self.wall_combo.append(k, v)
        self.wall_combo.connect("changed", self._wall_changed)
        wbox.pack_start(self.wall_combo, True, True, 0)
        wbox.pack_start(W.button(icon="view-refresh-symbolic", tooltip="Autre variante",
                                 on_click=self._reseed), False, False, 0)
        grid.attach(wbox, 1, row, 1, 1)
        form.pack_start(grid, False, False, 0)

        self.chk_wall = Gtk.CheckButton(label="Appliquer le fond d'écran")
        self.chk_wall.set_active(True)
        self.chk_plank = Gtk.CheckButton(label="Créer aussi un thème pour le dock")
        self.chk_plank.set_active(True)
        self.chk_layout = Gtk.CheckButton(label="Placer les boutons selon le style choisi")
        self.chk_layout.set_active(True)
        for c in (self.chk_wall, self.chk_plank, self.chk_layout):
            form.pack_start(c, False, False, 0)
        btns = Gtk.Box(spacing=8)
        btns.set_margin_top(6)
        btns.pack_start(W.button("Créer et appliquer", "emblem-ok-symbolic",
                                 css="suggested-action big-button",
                                 on_click=lambda: self._create(True)), False, False, 0)
        btns.pack_start(W.button("Créer seulement", css="big-button",
                                 on_click=lambda: self._create(False)), False, False, 0)
        form.pack_start(btns, False, False, 0)
        main.pack_start(form, False, False, 0)

        # ---------- aperçu
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right.pack_start(W.section_title("Aperçu"), False, False, 0)
        self.preview = W.Preview(self._draw_preview, 560, 340, radius=14)
        self.preview.set_hexpand(True)
        right.pack_start(self.preview, True, True, 0)
        self.contrast_label = W.label("", "hint")
        right.pack_start(self.contrast_label, False, False, 0)
        main.pack_start(right, True, True, 0)

        content.pack_start(W.section_title("Mes créations"), False, False, 0)
        self.mine = W.flowbox(1, 4)
        content.pack_start(self.mine, False, False, 0)

        self.pack_start(W.scrolled(content), True, True, 0)
        self.load_palette(self.pal)
        self.refresh_mine()

    # ------------------------------------------------------------------ palette

    def _palette_chip(self, p):
        def draw(cr, w, h):
            previews.rgb(cr, p["bg"])
            cr.paint()
            previews.rgb(cr, p.get("header") or p["bg"])
            cr.rectangle(0, 0, w, 10)
            cr.fill()
            for i, c in enumerate([p["accent"], p.get("accent2") or p["accent"], p.get("red", "#e5484d")]):
                cr.arc(14 + i * 14, h / 2 + 4, 5, 0, 6.3)
                previews.rgb(cr, c)
                cr.fill()
            previews.rgb(cr, p["fg"], 0.7)
            previews.rounded_rect(cr, 54, h / 2 + 2, w - 64, 4, 2)
            cr.fill()

        b = Gtk.Button()
        W.add_class(b, "flat")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.pack_start(W.Preview(draw, 120, 44, radius=8), False, False, 0)
        box.pack_start(W.label(p["name"], "dim", xalign=0.5), False, False, 0)
        b.add(box)
        b.set_tooltip_text(p["name"])
        b.connect("clicked", lambda *_: self.load_palette(dict(p)))
        return b

    def load_palette(self, p):
        self._loading = True
        v = generator.derive(p)
        self.pal = dict(p)
        for key, _ in COLOR_FIELDS:
            self.pal[key] = p.get(key) or v[key]
            W.set_color_button(self.color_buttons[key], self.pal[key])
        self.name_entry.set_text(p["name"])
        self.radius.set_value(int(p.get("radius", 8)))
        self.wall_style = p.get("wallpaper", "gradient")
        self.wall_combo.set_active_id(self.wall_style)
        self.seed = None
        self._loading = False
        self._invalidate()

    def _set(self, key, value):
        if self._loading:
            return
        self.pal[key] = value
        self._invalidate()

    def _style_changed(self, combo):
        self.style = combo.get_active_id() or "macos"
        self.preview.queue_draw()

    def _wall_changed(self, combo):
        self.wall_style = combo.get_active_id() or "gradient"
        if not self._loading:
            self._invalidate()

    def _reseed(self):
        self.seed = random.randint(1, 1_000_000)
        self._invalidate()

    def _invalidate(self):
        self._wall_cache = None
        if self._redraw_timer:
            GLib.source_remove(self._redraw_timer)

        def fire():
            self._redraw_timer = None
            self.preview.queue_draw()
            return False
        self._redraw_timer = GLib.timeout_add(80, fire)
        self._update_contrast()

    def _update_contrast(self):
        ratio = C.contrast(self.pal["bg"], self.pal["fg"])
        acc = C.contrast(self.pal["accent"], C.readable_on(self.pal["accent"]))
        if ratio < 4.5:
            txt = f"⚠ Contraste texte/fond faible ({ratio:.1f}:1) — le texte risque d'être difficile à lire."
        else:
            txt = f"✓ Bonne lisibilité (contraste {ratio:.1f}:1, accent {acc:.1f}:1)"
        self.contrast_label.set_text(txt)

    # ------------------------------------------------------------------ aperçu

    def _draw_preview(self, cr, w, h):
        if self._wall_cache is None or self._wall_cache[0] != (w, h):
            surf = wallpaper.render(self.pal, self.wall_style, 480, 270, self.seed)
            self._wall_cache = ((w, h), surf)
        surf = self._wall_cache[1]
        cr.save()
        cr.scale(w / 480, h / 270)
        cr.set_source_surface(surf, 0, 0)
        cr.paint()
        cr.restore()
        v = generator.derive(self.pal)
        col = {**{k: v[k] for k in ("bg", "fg", "base", "accent", "header", "red", "yellow", "green")}}
        # panneau
        previews.rgb(cr, v["panel"], 0.95)
        cr.rectangle(0, h - 26, w, 26)
        cr.fill()
        previews.rgb(cr, v["accent"])
        previews.rounded_rect(cr, 8, h - 21, 16, 16, 4)
        cr.fill()
        for i in range(4):
            previews.rgb(cr, v["panel_fg"], 0.5)
            previews.rounded_rect(cr, 36 + i * 46, h - 17, 38, 8, 3)
            cr.fill()
        previews.rgb(cr, v["panel_fg"], 0.8)
        previews.rounded_rect(cr, w - 50, h - 17, 40, 8, 3)
        cr.fill()
        cr.save()
        cr.translate(w * 0.1, h * 0.08)
        previews.draw_window_mock(cr, w * 0.62, h * 0.72, col, self.style, int(self.pal.get("radius", 8)))
        cr.restore()
        # petit menu
        mx, my, mw, mh = w * 0.66, h * 0.3, w * 0.26, h * 0.42
        cr.save()
        previews.rounded_rect(cr, mx + 2, my + 4, mw, mh, 8)
        cr.set_source_rgba(0, 0, 0, 0.25)
        cr.fill()
        previews.rounded_rect(cr, mx, my, mw, mh, min(8, int(self.pal.get("radius", 8))))
        previews.rgb(cr, v["surface"])
        cr.fill()
        for i in range(5):
            y = my + 10 + i * (mh - 20) / 5
            if i == 1:
                previews.rgb(cr, v["accent"])
                previews.rounded_rect(cr, mx + 5, y - 3, mw - 10, (mh - 20) / 5 - 2, 4)
                cr.fill()
                previews.rgb(cr, v["accent_fg"])
            else:
                previews.rgb(cr, v["fg"], 0.7)
            previews.rounded_rect(cr, mx + 12, y + 3, mw * (0.6 - (i % 2) * 0.15), 5, 2)
            cr.fill()
        cr.restore()

    # ------------------------------------------------------------------ création

    def _create(self, apply_now):
        pal = dict(self.pal)
        pal["name"] = self.name_entry.get_text().strip() or "Perso"
        pal["wallpaper"] = self.wall_style
        style = self.style
        want_plank = self.chk_plank.get_active()
        want_wall = self.chk_wall.get_active()
        want_layout = self.chk_layout.get_active()
        seed = self.seed

        def work():
            res = generator.generate(pal, style, plank=want_plank)
            wall = wallpaper.generate(pal, pal["wallpaper"], seed) if want_wall else None
            if apply_now:
                changes = {"gtk": res["gtk"], "xfwm4": res["xfwm4"],
                           "dark_panel": C.is_dark(pal["bg"])}
                if wall:
                    changes["wallpaper"] = str(wall)
                if want_layout:
                    changes["button_layout"] = "macos" if style in ("macos", "circles") else (
                        "minimal" if style == "minimal" else "windows")
                backup.snapshot(f"Thème créé : {res['gtk']}")
                applier.apply(changes, snapshot=False)
                if want_plank and plank.installed():
                    plank.set("theme", res["plank"])
            return res

        def done(res):
            invalid = self.win.pages.get("themes")
            if invalid is not None:
                invalid.invalidate()
            self.refresh_mine()
            if apply_now:
                self.win.applied(f"Thème {res['gtk']} créé et appliqué")
            else:
                self.win.toast(f"✓ Thème {res['gtk']} créé — retrouvez-le dans « Mes thèmes »")

        W.run_async(work, done, lambda e: W.error_dialog(self.win, "Création impossible", str(e)))

    def refresh_mine(self):
        W.clear(self.mine)
        mine = generator.list_generated()
        if not mine:
            self.mine.add(W.label("Vous n'avez pas encore créé de thème.", "hint"))
        for name, meta in mine:
            p = meta.get("palette", {})
            st = meta.get("style", "macos")
            v = generator.derive(p)
            col = {k: v[k] for k in ("bg", "fg", "base", "accent", "header", "red", "yellow", "green")}
            prev = W.Preview(lambda cr, w, h, col=col, st=st, r=int(p.get("radius", 8)):
                             previews.draw_window_mock(cr, w, h, col, st, r), 240, 140, bg="#8f9bb3")
            card = W.Card(prev, p.get("name", name), name)
            card.actions.pack_start(W.button(icon="document-edit-symbolic", css="flat", tooltip="Modifier",
                                             on_click=lambda p=p, st=st: self._edit(p, st)), False, False, 0)
            card.actions.pack_start(W.button(icon="user-trash-symbolic", css="flat", tooltip="Supprimer",
                                             on_click=lambda n=name: self._delete(n)), False, False, 0)
            card.actions.pack_end(W.button("Appliquer", css="suggested-action",
                                           on_click=lambda n=name: self._apply(n)), False, False, 0)
            self.mine.add(card)
        self.mine.show_all()

    def _edit(self, p, style):
        self.load_palette(p)
        self.style_combo.set_active_id(style)

    def _apply(self, name):
        applier.apply({"gtk": name, "xfwm4": name}, f"Thème : {name}")
        if plank.installed() and (paths.USER_PLANK_THEMES / name).is_dir():
            plank.set("theme", name)
        self.win.applied(f"{name} appliqué")

    def _delete(self, name):
        if not W.confirm(self.win, f"Supprimer « {name} » ?", "Ce thème créé sera supprimé.",
                         "Supprimer", True):
            return
        for d in (paths.USER_THEMES / name, paths.USER_PLANK_THEMES / name):
            if d.is_dir():
                shutil.rmtree(d)
        self.refresh_mine()
        page = self.win.pages.get("themes")
        if page is not None:
            page.invalidate()
