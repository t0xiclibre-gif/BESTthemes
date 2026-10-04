"""Workshop : catalogue, xfce-look.org, fonds d'écran et outils."""
import threading

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFrame,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QProgressBar,
                               QVBoxLayout, QWidget)

from bestthemes.core import installer
from bestthemes.workshop import pling

from .. import winplat as wp
from ..core import appearance, backup, cursors, icons, tools, workshop
from . import draw
from . import widgets as W

KIND_LABELS = {"cursors": "Curseurs", "icons": "Icônes", "wallpapers": "Fonds d'écran"}


def _num(n):
    return f"{n / 1e6:.1f} M".replace(".", ",") if n >= 1e6 else (f"{n / 1e3:.0f} k" if n >= 1e3 else str(n))


def _placeholder(kind):
    col = {"cursors": ("#7b5cd6", "#c084fc"), "icons": ("#2f9e75", "#7bd389"),
           "wallpapers": ("#3a6fd8", "#7fb2ff")}.get(kind, ("#888888", "#bbbbbb"))
    return lambda p, w, h: (draw.gradient_bg(p, w, h, *col),
                            draw.text(p, w / 2 - 14, h / 2 + 12, {"cursors": "🖱", "icons": "📁",
                                                                  "wallpapers": "🖼"}.get(kind, "★"), 24))


class VariantDialog(QDialog):
    def __init__(self, parent, title, files, default):
        super().__init__(parent)
        self.setWindowTitle(f"Installer {title}")
        self.resize(460, 420)
        v = QVBoxLayout(self)
        v.addWidget(W.label(f"<b>{title}</b> propose plusieurs variantes. Choisissez :", wrap=True))
        self.list = QListWidget()
        for name, _ in files:
            self.list.addItem(installer._strip_ext(name))
        names = [n for n, _ in files]
        self.list.setCurrentRow(names.index(default) if default in names else 0)
        v.addWidget(self.list, 1)
        bb = QDialogButtonBox()
        bb.addButton("Installer", QDialogButtonBox.AcceptRole)
        bb.addButton("Annuler", QDialogButtonBox.RejectRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self.files = files

    def choice(self):
        return self.files[max(0, self.list.currentRow())]


class InstallCard(W.Card):
    def __init__(self, win, preview, title, sub, kind, files_func, default_func, source_id, pills=()):
        super().__init__(preview, title, sub)
        self.win, self.kind, self.files_func = win, kind, files_func
        self.default_func, self.source_id = default_func, source_id
        for p in pills:
            self.actions.addWidget(W.pill(p))
        self.progress = QProgressBar()
        self.progress.setMaximumHeight(8)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.actions.addWidget(self.progress, 1)
        self.actions.addStretch(1)
        self.btns = QHBoxLayout()
        self.actions.addLayout(self.btns)
        self.names = workshop.installed_names(source_id) if workshop.is_installed(source_id, kind) else []
        self.cancel = None
        self._buttons()

    def _clear(self):
        while self.btns.count():
            it = self.btns.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def _buttons(self):
        self._clear()
        if self.names:
            self.btns.addWidget(W.button("Appliquer", self._apply, "primary"))
        else:
            self.btns.addWidget(W.button("⬇ Installer", self._install, "primary"))

    def _install(self):
        self._clear()
        self.btns.addWidget(QLabel("…"))
        W.run_async(self.files_func, self._got_files, self._error)

    def _got_files(self, files):
        if not files:
            self._error(installer.InstallError("Aucun fichier téléchargeable."))
            return
        default = self.default_func(files) if self.default_func else files[0][0]
        choice = next(((n, u) for n, u in files if n == default), files[0])
        if len(files) > 1:
            d = VariantDialog(self.win, self.title.text(), files, default)
            if not d.exec():
                self._buttons()
                return
            choice = d.choice()
        self._download(choice)

    def _download(self, choice):
        self._clear()
        self.cancel = threading.Event()
        self.btns.addWidget(W.button("✕", self.cancel.set, "flat", "Annuler le téléchargement"))
        self.progress.show()
        self.progress.setRange(0, 0)
        bridge = W.Bridge()
        self._bridge = bridge

        def on_msg(frac, _):
            if frac is not None:
                self.progress.setRange(0, 100)
                self.progress.setValue(int(frac * 100))

        bridge.message.connect(on_msg)

        def work():
            return workshop.install(self.kind, choice[0], choice[1], self.source_id,
                                    progress=lambda f, b: bridge.message.emit(f, b), cancel=self.cancel)

        def done(names):
            self.progress.hide()
            self.names = names
            self._buttons()
            self._apply()
            self.win.refresh_pages()

        W.run_async(work, done, self._error)

    def _error(self, e):
        self.progress.hide()
        self._buttons()
        if isinstance(e, installer.Cancelled):
            self.win.toast("Téléchargement annulé")
        else:
            W.error(self.win, "L'installation a échoué", str(e))

    def _apply(self):
        name = self.names[0] if self.names else None
        if not name:
            return
        backup.snapshot(f"{KIND_LABELS[self.kind]} : {self.title.text()}")
        if self.kind == "cursors":
            theme = next((c for c in cursors.installed() if c["name"] in self.names), None)
            if theme:
                cursors.apply(theme)
        elif self.kind == "icons":
            pk = next((p for p in icons.installed() if p["name"] in self.names), None)
            if pk:
                icons.apply(pk)
        else:
            appearance.set_wallpaper(name)
        self.win.applied(f"{self.title.text()} appliqué")


def _tabs(names, on_change, checked=0):
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    group = QButtonGroup(w)
    group.setExclusive(True)
    btns = []
    for i, (key, text) in enumerate(names):
        b = W.button(text, None, "tab")
        b.setCheckable(True)
        b.setChecked(i == checked)
        b.key = key
        group.addButton(b)
        b.clicked.connect(lambda *_, k=key: on_change(k))
        h.addWidget(b)
        btns.append(b)
    h.addStretch(1)
    w.buttons = btns
    return w


class CatalogTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.kind = "all"
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.kinds = _tabs([("all", "Tout"), ("cursors", "Curseurs"), ("icons", "Icônes")], self._set_kind)
        v.addWidget(self.kinds)
        v.addWidget(W.label("Une sélection testée. Les thèmes marqués « Linux » sont convertis "
                            "automatiquement pour Windows à l'installation.", "hint", wrap=True))
        self.grid = W.Grid()
        v.addWidget(self.grid)
        self.cards = []
        self.loaded = False

    def load(self):
        if self.loaded:
            return
        self.loaded = True
        for it in workshop.items():
            img = W.RemoteImage(it.preview_url, 280, 150, _placeholder(it.kind))
            pills = [KIND_LABELS[it.kind], "Linux → Windows" if it.converted else "Windows"]
            c = InstallCard(self.win, img, it.name, it.desc, it.kind, it.list_files,
                            it.default_file, it.id, pills)
            c.kind_ = it.kind
            self.cards.append(c)
            self.grid.add(c)

    def _set_kind(self, k):
        self.kind = k
        for c in self.cards:
            c.setVisible(k == "all" or c.kind_ == k)
        self.grid.flow.invalidate()

    def select(self, kind):
        for b in self.kinds.buttons:
            if b.key == kind:
                b.setChecked(True)
        self._set_kind(kind)


class PlingTab(QWidget):
    def __init__(self, win, kinds, default):
        super().__init__()
        self.win = win
        self.kind = default
        self.page = 0
        self.req = 0
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        if len(kinds) > 1:
            self.kinds = _tabs([(k, KIND_LABELS[k]) for k in kinds], self._set_kind)
            bar.addWidget(self.kinds)
        bar.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher sur xfce-look.org…")
        self.search.setMinimumWidth(260)
        self.search.returnPressed.connect(self.reload)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.reload)
        self.search.textChanged.connect(lambda *_: self.timer.start(600))
        self.sort = QComboBox()
        for k, t in pling.SORTS.items():
            self.sort.addItem(t, k)
        self.sort.currentIndexChanged.connect(lambda *_: self.reload())
        bar.addWidget(self.search)
        bar.addWidget(self.sort)
        bw = QWidget()
        bw.setLayout(bar)
        v.addWidget(bw)
        self.status = W.label("", "hint")
        v.addWidget(self.status)
        self.grid = W.Grid()
        v.addWidget(self.grid)
        self.more = W.button("Afficher plus", self._more)
        self.more.hide()
        v.addWidget(self.more)
        self.loaded = False

    def load(self):
        if not self.loaded:
            self.loaded = True
            self.reload()

    def _set_kind(self, k):
        self.kind = k
        self.reload()

    def select(self, kind):
        if hasattr(self, "kinds"):
            for b in self.kinds.buttons:
                if b.key == kind:
                    b.setChecked(True)
        self._set_kind(kind)

    def reload(self):
        self.page = 0
        self.grid.clear()
        self._fetch()

    def _more(self):
        self.page += 1
        self._fetch()

    def _fetch(self):
        self.req += 1
        req = self.req
        kind, q, sort, page = self.kind, self.search.text().strip(), self.sort.currentData(), self.page
        self.status.setText("Chargement…")
        self.more.hide()

        def done(res):
            if req != self.req:
                return
            items, total = res
            self.status.setText(f"{total} résultat(s)" if total else "Aucun résultat")
            for it in items:
                self._add(it, kind)
            self.more.setVisible((page + 1) * 24 < total)

        def err(e):
            if req == self.req:
                self.status.setText("Impossible de joindre xfce-look.org : vérifiez votre connexion Internet.")

        W.run_async(lambda: pling.search(kind, q, sort, page), done, err)

    def _add(self, it, kind):
        files = [(f.name, f.url) for f in (it.images + it.files if kind == "wallpapers" else it.files)]
        if not files:
            return
        img = W.RemoteImage(it.preview, 280, 150, _placeholder(kind))
        c = InstallCard(self.win, img, it.name, it.summary or it.category, kind,
                        lambda files=files: files, None, f"pling:{it.id}",
                        (f"⬇ {_num(it.downloads)}", f"★ {it.score / 10:.1f}"))
        c.setToolTip(f"{it.name} — par {it.author}")
        self.grid.add(c)


class ToolsTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(W.label("Des applications reconnues pour aller encore plus loin. L'installation "
                            "se fait en un clic, sans terminal (Windows peut demander une autorisation).",
                            "hint", wrap=True))
        if not tools.available():
            box = QFrame()
            box.setProperty("cls", "info")
            bv = QVBoxLayout(box)
            msg = ("L'installateur winget est introuvable : installez « App Installer » depuis le "
                   "Microsoft Store, ou utilisez les boutons « Site officiel »."
                   if wp.IS_WINDOWS else "Mode démonstration : l'installation n'est possible que sous Windows.")
            bv.addWidget(W.label(msg, wrap=True))
            v.addWidget(box)
        self.grid = W.Grid()
        v.addWidget(self.grid)
        self.loaded = False

    def load(self):
        if self.loaded:
            return
        self.loaded = True
        for t in tools.TOOLS:
            prev = W.Preview(lambda p, w, h, t=t: (draw.gradient_bg(p, w, h, "#3d4f8f", "#7a5fb0"),
                                                    draw.text(p, 16, h / 2 + 8, t["name"], 16, "#ffffff", True)),
                             260, 80)
            c = W.Card(prev, t["name"], t["desc"])
            c.actions.addWidget(W.pill(t["tag"]))
            c.actions.addStretch(1)
            c.actions.addWidget(W.button("Site officiel", lambda t=t: wp.open_url(t["url"]), "flat"))
            b = W.button("Installer", None, "primary")
            b.setEnabled(tools.available())
            b.clicked.connect(lambda *_, t=t, b=b: self._install(t, b))
            c.actions.addWidget(b)
            self.grid.add(c)
            W.run_async(lambda t=t: tools.is_installed(t["id"]),
                        lambda ok, b=b: (b.setText("✓ Installé"), b.setEnabled(False)) if ok else None)

    def _install(self, t, b):
        b.setEnabled(False)
        b.setText("Installation…")

        def done(res):
            ok, msg = res
            b.setText("✓ Installé" if ok else "Installer")
            b.setEnabled(not ok)
            if ok:
                self.win.toast(f"✓ {t['name']} installé")
            else:
                W.error(self, f"{t['name']} n'a pas pu être installé", msg)

        W.run_async(lambda: tools.install(t["id"]), done,
                    lambda e: (b.setText("Installer"), b.setEnabled(True), W.error(self, "Erreur", str(e))))


class WorkshopPage(W.Page):
    def __init__(self, win):
        super().__init__(win, "Workshop", "Téléchargez curseurs, icônes, fonds d'écran et outils — sans terminal.")
        self.catalog = CatalogTab(win)
        self.pling = PlingTab(win, ["cursors", "icons"], "cursors")
        self.walls = PlingTab(win, ["wallpapers"], "wallpapers")
        self.tools = ToolsTab(win)
        self.tabs = {"catalog": self.catalog, "pling": self.pling, "wallpapers": self.walls, "tools": self.tools}
        self.tabbar = _tabs([("catalog", "★ Sélection"), ("pling", "🌍 xfce-look.org"),
                             ("wallpapers", "🖼 Fonds d'écran"), ("tools", "🧰 Outils")], self.show_tab)
        self.body.addWidget(self.tabbar)
        # Onglets empilés dans la page (affichés/masqués) : la hauteur suit le contenu visible
        for t in self.tabs.values():
            self.body.addWidget(t)
            t.hide()
        self.current = "catalog"
        self.catalog.show()
        self.finish()

    def show_tab(self, key):
        for b in self.tabbar.buttons:
            b.setChecked(b.key == key)
        for k, t in self.tabs.items():
            t.setVisible(k == key)
        self.current = key
        self.tabs[key].load()

    def on_show(self):
        self.tabs[self.current].load()

    def navigate(self, kind=None, tab=None):
        if tab:
            self.show_tab(tab)
        elif kind in ("cursors", "icons"):
            self.show_tab("catalog")
            self.catalog.select(kind)
