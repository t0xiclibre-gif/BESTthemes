"""Workshop : télécharger et installer des thèmes en un clic."""
import threading

from gi.repository import GLib, Gtk

from ..core import applier, installer
from ..workshop import catalog, pling
from . import previews
from . import widgets as W

KIND_LABELS = {
    "all": "Tout",
    "gtk": "Applications",
    "xfwm4": "Bordures",
    "icons": "Icônes",
    "cursors": "Curseurs",
    "plank": "Dock",
}


def _fmt_num(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} M".replace(".", ",")
    if n >= 1000:
        return f"{n / 1000:.0f} k"
    return str(n)


def _strip(name):
    return installer._strip_ext(name)


def pick_theme(items, kind, filename=None):
    """Choisit le thème à appliquer parmi ceux installés depuis une archive."""
    cands = [i for i in items if kind in i[1]]
    if not cands:
        return None
    if filename:
        stem = _strip(filename).lower()
        for name, _, _ in cands:
            if name.lower() == stem:
                return name
    return cands[0][0]


class VariantDialog(Gtk.Dialog):
    """Choix de la variante à télécharger."""

    def __init__(self, parent, title, files, default=None):
        super().__init__(title=f"Installer {title}", transient_for=parent, modal=True)
        self.set_default_size(460, 420)
        self.add_button("Annuler", Gtk.ResponseType.CANCEL)
        ok = self.add_button("Installer", Gtk.ResponseType.OK)
        W.add_class(ok, "suggested-action")
        box = self.get_content_area()
        box.set_spacing(10)
        box.set_border_width(16)
        box.pack_start(W.label(f"<b>{GLib.markup_escape_text(title)}</b> propose plusieurs variantes. "
                               "Choisissez celle que vous voulez :", markup=True, wrap=True),
                       False, False, 0)
        sw = Gtk.ScrolledWindow()
        sw.set_vexpand(True)
        lb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        group = None
        self.radios = []
        for name, url in files:
            r = Gtk.RadioButton.new_with_label_from_widget(group, _strip(name))
            r.file = (name, url)
            group = group or r
            if default and name == default:
                r.set_active(True)
            lb.pack_start(r, False, False, 0)
            self.radios.append(r)
        sw.add(lb)
        box.pack_start(sw, True, True, 0)
        self.apply_check = Gtk.CheckButton(label="Appliquer directement après l'installation")
        self.apply_check.set_active(True)
        box.pack_start(self.apply_check, False, False, 0)
        self.show_all()

    def choice(self):
        for r in self.radios:
            if r.get_active():
                return r.file
        return None


class InstallCard(W.Card):
    """Carte du Workshop avec bouton d'installation et barre de progression."""

    def __init__(self, win, preview, title, subtitle, kind, files_func, default_func=None,
                 source_id=None, installed_items=None, pills=()):
        super().__init__(preview, title, subtitle)
        self.win = win
        self.kind = kind
        self.files_func = files_func
        self.default_func = default_func
        self.source_id = source_id
        self.cancel = None
        self.items = installed_items or []
        for p in pills:
            self.actions.pack_start(W.label(p, "pill"), False, False, 0)
        self.btn_box = Gtk.Box(spacing=6)
        self.actions.pack_end(self.btn_box, False, False, 0)
        self.progress = Gtk.ProgressBar()
        self.progress.set_no_show_all(True)
        self.progress.set_valign(Gtk.Align.CENTER)
        self.progress.set_hexpand(True)
        self.actions.pack_start(self.progress, True, True, 0)
        self._buttons()

    def _buttons(self):
        W.clear(self.btn_box)
        if self.items:
            self.btn_box.pack_start(W.button(icon="user-trash-symbolic", css="flat",
                                             tooltip="Désinstaller", on_click=self._uninstall),
                                    False, False, 0)
            self.btn_box.pack_start(W.button("Appliquer", css="suggested-action",
                                             on_click=self._apply), False, False, 0)
        else:
            self.btn_box.pack_start(W.button("Installer", "folder-download-symbolic",
                                             css="suggested-action", on_click=self._install),
                                    False, False, 0)
        self.btn_box.show_all()

    def _install(self):
        W.clear(self.btn_box)
        spinner = Gtk.Spinner(active=True)
        self.btn_box.pack_start(spinner, False, False, 0)
        self.btn_box.show_all()
        W.run_async(self.files_func, self._got_files, self._error)

    def _got_files(self, files):
        if not files:
            self._error(installer.InstallError("Aucun fichier téléchargeable n'a été trouvé."))
            return
        default = self.default_func(files) if self.default_func else files[0][0]
        apply_after = True
        choice = next(((n, u) for n, u in files if n == default), files[0])
        if len(files) > 1:
            d = VariantDialog(self.win, self.title.get_text(), files, default)
            resp = d.run()
            choice = d.choice()
            apply_after = d.apply_check.get_active()
            d.destroy()
            if resp != Gtk.ResponseType.OK or not choice:
                self._buttons()
                return
        self._download(choice, apply_after)

    def _download(self, choice, apply_after):
        name, url = choice
        W.clear(self.btn_box)
        self.cancel = threading.Event()
        self.btn_box.pack_start(W.button(icon="process-stop-symbolic", css="flat",
                                         tooltip="Annuler", on_click=self.cancel.set),
                                False, False, 0)
        self.btn_box.show_all()
        self.progress.show()
        self.progress.set_text("Téléchargement…")
        self.progress.set_show_text(True)

        def progress(frac, done):
            def upd():
                if frac is None:
                    self.progress.pulse()
                    self.progress.set_text(f"{done // 1024} Ko")
                else:
                    self.progress.set_fraction(frac)
                    self.progress.set_text(f"{int(frac * 100)} %")
                return False
            GLib.idle_add(upd)

        def work():
            return installer.install_url(url, name, source_id=self.source_id,
                                         progress=progress, cancel=self.cancel)

        def done(items):
            self.progress.hide()
            self.items = installer.installed_items(self.source_id) if self.source_id else items
            self._buttons()
            names = ", ".join(i[0] for i in items[:3]) + ("…" if len(items) > 3 else "")
            if apply_after:
                self._apply(pick_theme(items, self.kind, name))
            else:
                self.win.toast(f"✓ Installé : {names}")
            invalidate_installed(self.win)

        W.run_async(work, done, self._error)

    def _error(self, e):
        self.progress.hide()
        self._buttons()
        if isinstance(e, installer.Cancelled):
            self.win.toast("Téléchargement annulé")
            return
        W.error_dialog(self.win, "L'installation a échoué", str(e))

    def _apply(self, name=None):
        name = name or pick_theme(self.items, self.kind)
        if not name:
            W.error_dialog(self.win, "Rien à appliquer",
                           "Ce téléchargement ne contient pas de thème de ce type.")
            return
        if self.kind == "plank":
            from ..core import plank
            if not plank.installed():
                self.win.toast("Installez d'abord le dock depuis la page « Dock »")
                return
        applier.apply_one(self.kind, name)
        self.win.applied(f"{name} appliqué")

    def _uninstall(self):
        if not W.confirm(self.win, f"Désinstaller « {self.title.get_text()} » ?",
                         "Les fichiers téléchargés seront supprimés.", "Désinstaller", True):
            return
        if self.source_id:
            installer.uninstall_source(self.source_id)
        else:
            for it in self.items:
                try:
                    installer.uninstall_path(it[2])
                except installer.InstallError:
                    pass
        self.items = []
        self._buttons()
        self.win.toast("🗑 Désinstallé")
        invalidate_installed(self.win)


def invalidate_installed(win):
    """Les listes de thèmes installés devront être relues."""
    for pid in ("themes", "dock"):
        page = win.pages.get(pid)
        if page is not None and hasattr(page, "invalidate"):
            page.invalidate()


def kind_bar(kinds, on_change):
    box = Gtk.Box()
    W.add_class(box, "linked")
    group = None
    for k in kinds:
        b = Gtk.RadioButton.new_with_label_from_widget(group, KIND_LABELS[k])
        b.set_mode(False)
        b.kind = k
        group = group or b
        b.connect("toggled", lambda btn: btn.get_active() and on_change(btn.kind))
        box.pack_start(b, False, False, 0)
    return box


def _placeholder_for(kind):
    def draw(cr, w, h):
        col = {"gtk": "#5e81ac", "icons": "#a3be8c", "cursors": "#b48ead",
               "plank": "#d08770", "xfwm4": "#88c0d0"}.get(kind, "#888888")
        previews.rgb(cr, col, 0.35)
        cr.paint()
    return draw


class CatalogTab(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.win = win
        self.kind = "all"
        bar = Gtk.Box(spacing=10)
        self.kinds = kind_bar(["all", "gtk", "icons", "cursors", "plank"], self._set_kind)
        bar.pack_start(self.kinds, False, False, 0)
        self.search = Gtk.SearchEntry(placeholder_text="Filtrer…")
        self.search.connect("search-changed", lambda *_: self.flow.invalidate_filter())
        bar.pack_end(self.search, False, False, 0)
        self.pack_start(bar, False, False, 0)
        info = W.label("Une sélection de thèmes populaires et testés. Cliquez sur « Installer » : "
                       "le téléchargement, l'installation et l'application sont automatiques.",
                       "hint", wrap=True)
        self.pack_start(info, False, False, 0)
        self.flow = W.flowbox(1, 4)
        self.flow.set_filter_func(self._filter)
        self.pack_start(self.flow, True, True, 0)
        self.loaded = False

    def load(self):
        if self.loaded:
            return
        self.loaded = True
        for it in catalog.items():
            src = "GitHub" if it.source == "url" else "xfce-look"
            img = W.RemoteImage((lambda it=it: it.preview_url()) if (it.pling or it.preview_pling) else None,
                                280, 160, placeholder=_placeholder_for(it.kind))
            card = InstallCard(
                self.win, img, it.name, it.desc, it.kind,
                files_func=it.list_files,
                default_func=lambda files, it=it: (it.default_file(files) or files[0])[0],
                source_id=it.source_id, installed_items=it.installed_items(),
                pills=(KIND_LABELS[it.kind], src))
            child = Gtk.FlowBoxChild()
            child.kind = it.kind
            child.search_text = " ".join([it.name, it.desc, *it.tags]).lower()
            child.add(card)
            self.flow.add(child)
        self.flow.show_all()

    def _set_kind(self, kind):
        self.kind = kind
        self.flow.invalidate_filter()

    def _filter(self, child):
        if self.kind != "all" and child.kind != self.kind:
            return False
        q = self.search.get_text().strip().lower()
        return not q or q in child.search_text


class PlingTab(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.win = win
        self.kind = "gtk"
        self.page = 0
        self.total = 0
        self.request = 0
        bar = Gtk.Box(spacing=10)
        self.kinds = kind_bar(["gtk", "xfwm4", "icons", "cursors", "plank"], self._set_kind)
        bar.pack_start(self.kinds, False, False, 0)
        self.sort = Gtk.ComboBoxText()
        for k, v in pling.SORTS.items():
            self.sort.append(k, v)
        self.sort.set_active_id("down")
        self.sort.connect("changed", lambda *_: self.reload())
        bar.pack_end(self.sort, False, False, 0)
        self.search = Gtk.SearchEntry(placeholder_text="Rechercher sur xfce-look.org…")
        self.search.set_size_request(280, -1)
        self.search.connect("activate", lambda *_: self.reload())
        self.search.connect("search-changed", self._debounce)
        bar.pack_end(self.search, False, False, 0)
        self.pack_start(bar, False, False, 0)
        self.pack_start(W.label("Des milliers de thèmes partagés par la communauté sur xfce-look.org. "
                                "Les créations de chacun ne sont pas toutes vérifiées : si un thème "
                                "ne s'applique pas bien, cliquez sur « Annuler ».", "hint", wrap=True),
                        False, False, 0)
        self.status = Gtk.Box(spacing=8)
        self.spinner = Gtk.Spinner()
        self.status_label = W.label("")
        self.status.pack_start(self.spinner, False, False, 0)
        self.status.pack_start(self.status_label, False, False, 0)
        self.pack_start(self.status, False, False, 0)
        self.flow = W.flowbox(1, 4)
        self.pack_start(self.flow, True, True, 0)
        self.more = W.button("Afficher plus", css="big-button", on_click=self._more)
        self.more.set_halign(Gtk.Align.CENTER)
        self.more.set_no_show_all(True)
        self.pack_start(self.more, False, False, 0)
        self.loaded = False
        self._timer = None

    def load(self):
        if not self.loaded:
            self.loaded = True
            self.reload()

    def set_kind(self, kind):
        for b in self.kinds.get_children():
            if b.kind == kind:
                b.set_active(True)

    def _set_kind(self, kind):
        self.kind = kind
        if self.loaded:
            self.reload()

    def _debounce(self, *_):
        if self._timer:
            GLib.source_remove(self._timer)

        def fire():
            self._timer = None
            self.reload()
            return False
        self._timer = GLib.timeout_add(600, fire)

    def reload(self):
        self.page = 0
        W.clear(self.flow)
        self._fetch()

    def _more(self):
        self.page += 1
        self._fetch()

    def _fetch(self):
        self.request += 1
        req = self.request
        self.spinner.start()
        self.status_label.set_text("Chargement…")
        self.more.hide()
        kind, q, sort, page = self.kind, self.search.get_text().strip(), \
            self.sort.get_active_id() or "down", self.page

        def done(res):
            if req != self.request:
                return
            items, total = res
            self.spinner.stop()
            self.total = total
            self.status_label.set_text(f"{total} résultat(s)" if total else "Aucun résultat")
            for it in items:
                self._add(it, kind)
            self.flow.show_all()
            self.more.set_visible((page + 1) * 24 < total)

        def err(e):
            if req != self.request:
                return
            self.spinner.stop()
            self.status_label.set_text("Impossible de joindre xfce-look.org. Vérifiez votre "
                                       f"connexion Internet. ({type(e).__name__})")

        W.run_async(lambda: pling.search(kind, q, sort, page), done, err)

    def _add(self, it, kind):
        img = W.RemoteImage(it.preview, 280, 160, placeholder=_placeholder_for(kind))
        sub = it.summary or it.category
        source_id = f"pling:{it.id}"
        card = InstallCard(
            self.win, img, it.name, sub, kind,
            files_func=lambda it=it: [(f.name, f.url) for f in it.files],
            source_id=source_id, installed_items=installer.installed_items(source_id),
            pills=(f"⬇ {_fmt_num(it.downloads)}", f"★ {it.score / 10:.1f}"))
        card.set_tooltip_text(f"{it.name} — par {it.author}\nMis à jour le {it.changed}")
        child = Gtk.FlowBoxChild()
        child.add(card)
        self.flow.add(child)


class WorkshopPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        top.set_margin_start(24)
        top.set_margin_end(24)
        top.set_margin_top(24)
        top.pack_start(W.page_header("Workshop",
                                     "Téléchargez des thèmes, icônes, curseurs et docks — sans terminal."),
                       False, False, 0)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.catalog = CatalogTab(win)
        self.pling = PlingTab(win)
        self.stack.add_titled(W.scrolled(self.catalog), "catalog", "★ Sélection BESTthemes")
        self.stack.add_titled(W.scrolled(self.pling), "pling", "🌍 xfce-look.org")
        sw = Gtk.StackSwitcher(stack=self.stack)
        W.add_class(sw, "tabs")
        sw.set_halign(Gtk.Align.START)
        top.pack_start(sw, False, False, 0)
        self.pack_start(top, False, False, 0)
        self.pack_start(self.stack, True, True, 0)
        self.stack.connect("notify::visible-child-name", lambda *_: self.on_show())

    def on_show(self):
        if self.stack.get_visible_child_name() == "catalog":
            self.catalog.load()
        else:
            self.pling.load()

    def navigate(self, kind=None, **_):
        if kind in ("xfwm4",):
            self.stack.set_visible_child_name("pling")
            self.pling.set_kind(kind)
        elif kind in ("gtk", "icons", "cursors", "plank"):
            self.stack.set_visible_child_name("catalog")
            for b in self.catalog.kinds.get_children():
                if b.kind == kind:
                    b.set_active(True)
        self.on_show()
