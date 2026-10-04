"""Page « Packs » : des looks complets en un clic."""
from functools import lru_cache

from gi.repository import GLib, Gtk

from ..core import generator, packs, panel, wallpaper
from ..core import colors as C
from . import previews
from . import widgets as W


@lru_cache(maxsize=64)
def _wall_surface(palette_id, style, w, h):
    return wallpaper.render(generator.palette(palette_id), style, w, h)


def draw_pack(cr, w, h, pack):
    """Aperçu d'un pack : fond d'écran + fenêtre + panneau."""
    wp = pack.get("wallpaper") or {}
    pal_id = wp.get("palette") or pack.get("palette") or "nord"
    s = _wall_surface(pal_id, wp.get("style", "gradient"), 320, 180)
    cr.save()
    cr.scale(w / 320, h / 180)
    cr.set_source_surface(s, 0, 0)
    cr.paint()
    cr.restore()
    pal = generator.palette(pack.get("palette") or pal_id)
    v = generator.derive(pal)
    col = {"bg": v["bg"], "fg": v["fg"], "base": v["base"], "accent": v["accent"],
           "header": v["header"], "red": v["red"], "yellow": v["yellow"], "green": v["green"]}
    style = (pack.get("gtk") or {}).get("style") or pack.get("button_layout") or "windows"
    preset = next((p for p in panel.PRESETS if p["id"] == pack.get("panel")), None)
    pos = preset["position"] if preset else "bottom"
    ph = 9
    # fenêtre
    cr.save()
    cr.translate(w * 0.18, h * 0.16 + (ph if pos == "top" else 0))
    previews.draw_window_mock(cr, w * 0.64, h * 0.66, col, style, int(pal.get("radius", 8)),
                              show_title=False)
    cr.restore()
    # panneau
    previews.rgb(cr, v["panel"], 0.92)
    if pos == "top":
        cr.rectangle(0, 0, w, ph)
    elif pos == "left":
        cr.rectangle(0, 0, ph + 4, h)
    else:
        length = (preset or {}).get("length", 100) / 100
        cr.rectangle(w * (1 - length) / 2, h - ph - 2, w * length, ph + 2)
    cr.fill()
    if preset and preset.get("plank") or pack.get("plank"):
        previews.rounded_rect(cr, w * 0.33, h - 18, w * 0.34, 14, 5)
        previews.rgb(cr, v["panel"], 0.75)
        cr.fill()
        for i in range(5):
            cr.arc(w * 0.37 + i * w * 0.065, h - 11, 4, 0, 6.3)
            previews.rgb(cr, [v["accent"], v["red"], v["yellow"], v["green"], v["fg"]][i])
            cr.fill()


class ProgressDialog(Gtk.Dialog):
    def __init__(self, parent, title):
        super().__init__(title=title, transient_for=parent, modal=True)
        self.set_default_size(380, -1)
        self.set_deletable(False)
        box = self.get_content_area()
        box.set_border_width(20)
        box.set_spacing(12)
        self.label = W.label("Préparation…", wrap=True)
        self.bar = Gtk.ProgressBar()
        box.pack_start(W.label(f"<b>{GLib.markup_escape_text(title)}</b>", markup=True), False, False, 0)
        box.pack_start(self.label, False, False, 0)
        box.pack_start(self.bar, False, False, 0)
        self._pulse = GLib.timeout_add(120, self._tick)
        self.fraction = None
        self.show_all()

    def _tick(self):
        if self.fraction is None:
            self.bar.pulse()
        return True

    def update(self, text, frac):
        if text:
            self.label.set_text(text)
        self.fraction = frac
        if frac is not None:
            self.bar.set_fraction(frac)

    def finish(self):
        GLib.source_remove(self._pulse)
        self.destroy()


def apply_pack(win, pack):
    dlg = ProgressDialog(win, f"Application du pack « {pack['name']} »")

    def progress(text, frac):
        GLib.idle_add(lambda: dlg.update(text, frac) and False)

    def done(warnings):
        dlg.finish()
        win.applied(f"Pack « {pack['name']} » appliqué")
        if warnings:
            W.error_dialog(win, "Pack appliqué avec des remarques", "\n".join(warnings))

    def err(e):
        dlg.finish()
        win.changed()
        W.error_dialog(win, "Le pack n'a pas pu être appliqué entièrement",
                       f"{e}\n\nVous pouvez revenir en arrière avec « Annuler ».")

    W.run_async(lambda: packs.apply(pack, progress), done, err)


def pack_card(win, pack, width=300, height=170):
    online = any(isinstance(pack.get(k), dict) and "catalog" in pack[k]
                 for k in ("gtk", "icons", "cursors", "plank"))
    preview = W.Preview(lambda cr, w, h, p=pack: draw_pack(cr, w, h, p), width, height)
    card = W.Card(preview, pack["name"], pack["desc"])
    card.actions.pack_start(W.label("Télécharge" if online else "Hors-ligne",
                                    "pill " + ("online" if online else "offline")), False, False, 0)
    pal = generator.palette(pack["palette"])
    for key in ("bg", "accent", "accent2"):
        c = pal.get(key) or C.rotate_hue(pal["accent"], 40)
        sw = W.Preview(lambda cr, w, h, c=c: (previews.rgb(cr, c), cr.paint()), 14, 14, radius=7)
        sw.set_valign(Gtk.Align.CENTER)
        card.actions.pack_start(sw, False, False, 0)
    card.actions.pack_end(W.button("Appliquer", css="suggested-action",
                                   on_click=lambda: apply_pack(win, pack)), False, False, 0)
    return card


class PacksPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.pack_start(W.page_header(
            "Packs",
            "Un look complet en un clic : thème, bordures, icônes, curseur, panneau, dock et fond "
            "d'écran assortis. Les packs « Hors-ligne » sont créés par BESTthemes, les autres "
            "téléchargent les thèmes nécessaires."), False, False, 0)
        all_packs = packs.load()
        for title, sel in (("Inspirés des grands systèmes et thèmes populaires",
                            lambda p: not isinstance(p.get("gtk"), dict) or "generate" not in p["gtk"]),
                           ("Créations BESTthemes (hors-ligne)",
                            lambda p: isinstance(p.get("gtk"), dict) and "generate" in p["gtk"])):
            content.pack_start(W.section_title(title), False, False, 0)
            fb = W.flowbox(1, 4)
            for p in all_packs:
                if sel(p):
                    fb.add(pack_card(win, p))
            content.pack_start(fb, False, False, 0)
        self.pack_start(W.scrolled(content), True, True, 0)
