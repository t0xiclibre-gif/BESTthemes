"""Widgets et utilitaires communs de l'interface."""
import threading
import traceback

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, GLib, Gtk, Pango  # noqa: E402

from . import previews  # noqa: E402


def run_async(func, on_done=None, on_error=None, *args):
    """Exécute func(*args) dans un thread, puis on_done(result) dans le thread GTK."""

    def worker():
        try:
            result = func(*args)
        except Exception as e:  # noqa: BLE001 — on remonte toute erreur à l'interface
            traceback.print_exc()
            if on_error:
                GLib.idle_add(on_error, e)
            return
        if on_done:
            GLib.idle_add(on_done, result)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t


def idle(func, *args):
    """Appelle func dans le thread GTK (depuis un thread de travail)."""
    def _call():
        func(*args)
        return False
    GLib.idle_add(_call)


def label(text, css=None, xalign=0.0, wrap=False, markup=False, lines=0, ellipsize=False):
    lab = Gtk.Label()
    if markup:
        lab.set_markup(text)
    else:
        lab.set_text(text)
    lab.set_xalign(xalign)
    if wrap:
        lab.set_line_wrap(True)
        lab.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    if lines:
        lab.set_lines(lines)
        lab.set_ellipsize(Pango.EllipsizeMode.END)
    if ellipsize:
        lab.set_ellipsize(Pango.EllipsizeMode.END)
    for c in (css or "").split():
        lab.get_style_context().add_class(c)
    if "pill" in (css or "").split():
        lab.set_valign(Gtk.Align.CENTER)
    return lab


def add_class(widget, *classes):
    ctx = widget.get_style_context()
    for c in classes:
        ctx.add_class(c)
    return widget


def button(text=None, icon=None, css=None, tooltip=None, on_click=None):
    b = Gtk.Button()
    if icon and text:
        box = Gtk.Box(spacing=6)
        box.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON), False, False, 0)
        box.pack_start(Gtk.Label(label=text), False, False, 0)
        b.add(box)
    elif icon:
        b.set_image(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON))
    else:
        b.set_label(text or "")
    if css:
        add_class(b, *css.split())
    if tooltip:
        b.set_tooltip_text(tooltip)
    if on_click:
        b.connect("clicked", lambda *_: on_click())
    return b


def page_header(title, subtitle=None):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    box.pack_start(label(title, "page-title"), False, False, 0)
    if subtitle:
        box.pack_start(label(subtitle, "page-subtitle", wrap=True), False, False, 0)
    return box


class Preview(Gtk.DrawingArea):
    """Zone de dessin : draw_func(cr, largeur, hauteur)."""

    def __init__(self, draw_func, width=240, height=140, bg=None, radius=10):
        super().__init__()
        self.draw_func = draw_func
        self.bg = bg
        self.radius = radius
        self.set_size_request(width, height)
        self.connect("draw", self._on_draw)

    def _on_draw(self, widget, cr):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        previews.rounded_rect(cr, 0, 0, w, h, self.radius)
        cr.clip()
        if self.bg:
            previews.rgb(cr, self.bg)
            cr.paint()
        try:
            self.draw_func(cr, w, h)
        except Exception:  # noqa: BLE001 — un aperçu cassé ne doit pas planter l'appli
            traceback.print_exc()
        return False


class RemoteImage(Gtk.DrawingArea):
    """Image chargée depuis une URL (ou une fonction renvoyant une URL) en arrière-plan."""

    _sem = threading.Semaphore(6)

    def __init__(self, url_or_func, width=260, height=150, radius=10, placeholder=None):
        super().__init__()
        self.pixbuf = None
        self.radius = radius
        self.placeholder = placeholder
        self.set_size_request(width, height)
        self.connect("draw", self._on_draw)
        self._loading = False
        self._source = url_or_func
        self.connect("map", self._start)

    def _start(self, *_):
        if self._loading or self.pixbuf is not None:
            return
        self._loading = True
        run_async(self._fetch, self._loaded, lambda e: None)

    def _fetch(self):
        from ..workshop import pling
        with self._sem:
            url = self._source() if callable(self._source) else self._source
            if not url:
                return None
            path = pling.cached_image(url)
            return GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), 720, 480, True)

    def _loaded(self, pb):
        self.pixbuf = pb
        self.queue_draw()

    def _on_draw(self, widget, cr):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        if self.pixbuf is not None:
            previews.cover_pixbuf(cr, self.pixbuf, w, h, self.radius)
        else:
            previews.rounded_rect(cr, 0, 0, w, h, self.radius)
            cr.set_source_rgba(0.5, 0.5, 0.5, 0.15)
            cr.fill()
            if self.placeholder:
                cr.save()
                previews.rounded_rect(cr, 0, 0, w, h, self.radius)
                cr.clip()
                self.placeholder(cr, w, h)
                cr.restore()
        return False


class Card(Gtk.EventBox):
    """Carte cliquable : aperçu + titre + sous-titre + zone d'actions."""

    def __init__(self, preview, title, subtitle=None, on_activate=None, active=False):
        super().__init__()
        self.on_activate = on_activate
        self.frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        add_class(self.frame, "card")
        self.frame.set_border_width(0)
        self.add(self.frame)
        overlay = Gtk.Overlay()
        overlay.add(preview)
        self.badge = label("✓ Actif", "badge")
        self.badge.set_halign(Gtk.Align.END)
        self.badge.set_valign(Gtk.Align.START)
        self.badge.set_margin_top(8)
        self.badge.set_margin_end(8)
        self.badge.set_no_show_all(True)
        overlay.add_overlay(self.badge)
        self.frame.pack_start(overlay, False, False, 0)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text.set_margin_start(10)
        text.set_margin_end(10)
        self.title = label(title, "card-title", ellipsize=True)
        self.title.set_max_width_chars(20)
        text.pack_start(self.title, False, False, 0)
        if subtitle:
            self.subtitle = label(subtitle, "card-subtitle", lines=2, wrap=True)
            self.subtitle.set_max_width_chars(20)
            text.pack_start(self.subtitle, False, False, 0)
        self.frame.pack_start(text, False, False, 0)
        self.actions = Gtk.Box(spacing=6)
        self.actions.set_margin_start(10)
        self.actions.set_margin_end(10)
        self.actions.set_margin_bottom(10)
        self.frame.pack_start(self.actions, False, False, 0)
        self.set_active(active)
        if on_activate:
            self.connect("button-release-event", self._clicked)
            self.connect("enter-notify-event", lambda *_: add_class(self.frame, "hover"))
            self.connect("leave-notify-event",
                         lambda *_: self.frame.get_style_context().remove_class("hover"))

    def _clicked(self, _w, event):
        if event.button == 1 and self.on_activate:
            self.on_activate()
        return False

    def set_active(self, active):
        ctx = self.frame.get_style_context()
        if active:
            ctx.add_class("active")
            self.badge.show()
        else:
            ctx.remove_class("active")
            self.badge.hide()


def flowbox(min_per_line=1, max_per_line=6):
    fb = Gtk.FlowBox()
    fb.set_selection_mode(Gtk.SelectionMode.NONE)
    fb.set_homogeneous(True)
    fb.set_min_children_per_line(min_per_line)
    fb.set_max_children_per_line(max_per_line)
    fb.set_column_spacing(14)
    fb.set_row_spacing(14)
    fb.set_valign(Gtk.Align.START)
    return fb


def scrolled(child, margin=24):
    sw = Gtk.ScrolledWindow()
    sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.set_margin_start(margin)
    box.set_margin_end(margin)
    box.set_margin_top(margin)
    box.set_margin_bottom(margin)
    box.pack_start(child, True, True, 0)
    sw.add(box)
    return sw


def clear(container):
    for c in container.get_children():
        container.remove(c)
        c.destroy()


def section_title(text):
    return label(text, "section-title")


def color_button(hexc, on_change):
    from gi.repository import Gdk
    rgba = Gdk.RGBA()
    rgba.parse(hexc)
    b = Gtk.ColorButton.new_with_rgba(rgba)
    b.set_use_alpha(False)

    def changed(btn):
        c = btn.get_rgba()
        on_change("#%02x%02x%02x" % (round(c.red * 255), round(c.green * 255), round(c.blue * 255)))

    b.connect("color-set", changed)
    return b


def set_color_button(btn, hexc):
    from gi.repository import Gdk
    rgba = Gdk.RGBA()
    rgba.parse(hexc)
    btn.set_rgba(rgba)


def confirm(parent, title, text, ok_label="Confirmer", destructive=False):
    d = Gtk.MessageDialog(transient_for=parent, modal=True,
                          message_type=Gtk.MessageType.QUESTION,
                          buttons=Gtk.ButtonsType.NONE, text=title)
    d.format_secondary_text(text)
    d.add_button("Annuler", Gtk.ResponseType.CANCEL)
    ok = d.add_button(ok_label, Gtk.ResponseType.OK)
    add_class(ok, "destructive-action" if destructive else "suggested-action")
    r = d.run()
    d.destroy()
    return r == Gtk.ResponseType.OK


def error_dialog(parent, title, text):
    d = Gtk.MessageDialog(transient_for=parent, modal=True, message_type=Gtk.MessageType.ERROR,
                          buttons=Gtk.ButtonsType.OK, text=title)
    d.format_secondary_text(text)
    d.run()
    d.destroy()
