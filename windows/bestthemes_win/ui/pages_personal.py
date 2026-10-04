"""Pages Curseurs, Icônes, Barre des tâches et Effets."""
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QVBoxLayout, QWidget)

from .. import winplat as wp
from ..core import backup, cursors, effects, icons, taskbar
from . import draw
from . import widgets as W


def _row(*widgets, stretch_at=None):
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    for i, x in enumerate(widgets):
        if i == stretch_at:
            h.addStretch(1)
        h.addWidget(x)
    if stretch_at is None:
        h.addStretch(1)
    return w


# ======================================================================= curseurs


class CursorsPage(W.Page):
    def __init__(self, win):
        super().__init__(win, "Curseurs",
                         "Cliquez sur un thème pour l'appliquer. Les thèmes Linux de xfce-look.org "
                         "sont convertis automatiquement au format Windows.")
        self.size = QComboBox()
        for px, name in cursors.SIZES.items():
            self.size.addItem(f"{name} ({px} px)", px)
        self.size.currentIndexChanged.connect(self._size_changed)
        self.body.addWidget(_row(W.label("Taille :"), self.size,
                                 W.button("Importer un dossier ou une archive…", self._import),
                                 W.button("⬇ Trouver plus de curseurs", lambda: win.go("workshop", kind="cursors")),
                                 stretch_at=3))
        self.grid = W.Grid()
        self.body.addWidget(self.grid)
        self.finish()
        self._loading = False
        self.refresh()

    def refresh(self):
        self.grid.clear()
        cur = cursors.current()
        default = W.Card(W.Preview(lambda p, w, h: draw.text(p, w / 2 - 70, h / 2 + 5,
                                                              "Curseurs d'origine", 11, "#555555", True),
                                   260, 90, bg="#f2f2f5"),
                         "Windows par défaut", "Les curseurs d'origine de Windows",
                         lambda: self._apply(None))
        default.set_active(cur == "Windows par défaut")
        self.grid.add(default)
        for t in cursors.installed():
            prev = W.Preview(lambda p, w, h, t=t: draw.cursors(p, w, h, t), 260, 90, bg="#f2f2f5")
            sub = "Converti depuis Linux" if t["converted"] else "Thème Windows"
            card = W.Card(prev, t["name"], sub, lambda t=t: self._apply(t))
            card.actions.addStretch(1)
            card.actions.addWidget(W.button("🗑", lambda t=t: self._delete(t), "flat", "Supprimer"))
            card.set_active(cur == t["name"])
            self.grid.add(card)
        self._loading = True
        i = self.size.findData(cursors.size())
        self.size.setCurrentIndex(i if i >= 0 else 0)
        self._loading = False

    def _apply(self, theme):
        backup.snapshot("Curseurs")
        cursors.apply(theme)
        self.win.applied(f"Curseurs : {theme['name'] if theme else 'Windows par défaut'}")

    def _delete(self, t):
        if W.confirm(self, f"Supprimer « {t['name']} » ?", "Ce thème de curseurs sera supprimé.", "Supprimer"):
            cursors.uninstall(t)
            self.refresh()

    def _size_changed(self):
        if self._loading:
            return
        px = self.size.currentData()
        backup.snapshot("Taille du curseur")
        cursors.set_size(px)
        self.win.applied(f"Taille du curseur : {px} px (certaines applis la prennent en compte "
                         "après une reconnexion)")

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importer des curseurs", "",
                                              "Archives et curseurs (*.zip *.tar.gz *.tar.xz *.tgz *.inf)")
        if not path:
            return

        def work():
            import tempfile
            from pathlib import Path
            from bestthemes.core import installer
            p = Path(path)
            if p.suffix.lower() == ".inf":
                return cursors.install_extracted(p.parent)
            tmp = Path(tempfile.mkdtemp(dir=wp.DATA))
            installer.extract(p, tmp)
            return cursors.install_extracted(tmp)

        W.run_async(work, lambda r: (self.refresh(), self.win.toast(
            f"✓ {len(r)} thème(s) importé(s)" if r else "Aucun curseur reconnu dans ce fichier")),
            lambda e: W.error(self, "Import impossible", str(e)))

    def on_changed(self):
        self.refresh()


# ======================================================================= icônes


class IconsPage(W.Page):
    def __init__(self, win):
        super().__init__(win, "Icônes",
                         "Change les icônes du bureau (Ce PC, Corbeille, Réseau…) et de vos dossiers "
                         "(Documents, Images, Musique, Vidéos, Téléchargements). Les packs viennent "
                         "des thèmes Linux, convertis automatiquement.")
        self.chk_desktop = QCheckBox("Icônes du bureau")
        self.chk_desktop.setChecked(True)
        self.chk_folders = QCheckBox("Icônes des dossiers personnels")
        self.chk_folders.setChecked(True)
        self.body.addWidget(_row(self.chk_desktop, self.chk_folders,
                                 W.button("⬇ Trouver plus d'icônes", lambda: win.go("workshop", kind="icons")),
                                 stretch_at=2))
        self.grid = W.Grid()
        self.body.addWidget(self.grid)
        note = QFrame()
        note.setProperty("cls", "info")
        nv = QVBoxLayout(note)
        nv.addWidget(W.label("Windows ne permet pas de changer toutes les icônes du système sans "
                             "modifier ses fichiers (ce que BESTthemes refuse de faire pour votre "
                             "sécurité). Pour aller plus loin, l'outil Windhawk propose des mods "
                             "réversibles.", wrap=True))
        self.body.addWidget(note)
        self.finish()
        self.refresh()

    def refresh(self):
        self.grid.clear()
        cur = icons.current()
        orig = W.Card(W.Preview(lambda p, w, h: draw.text(p, w / 2 - 62, h / 2 + 5, "Icônes d'origine",
                                                           11, "#555555", True), 260, 90, bg="#eef0f4"),
                      "Windows par défaut", "Les icônes d'origine", lambda: self._apply(None))
        orig.set_active(cur is None)
        self.grid.add(orig)
        for pk in icons.installed():
            prev = W.Preview(lambda p, w, h, pk=pk: draw.icons(p, w, h, pk), 260, 90, bg="#eef0f4")
            card = W.Card(prev, pk["name"], f"{len(pk['icons'])} icônes", lambda pk=pk: self._apply(pk))
            card.actions.addStretch(1)
            card.actions.addWidget(W.button("🗑", lambda pk=pk: self._delete(pk), "flat", "Supprimer"))
            card.set_active(cur == pk["name"])
            self.grid.add(card)

    def _apply(self, pk):
        backup.snapshot("Icônes")
        icons.apply(pk, folders=self.chk_folders.isChecked(), desktop=self.chk_desktop.isChecked())
        if pk is None:
            icons.restore_folders()
        self.win.applied(f"Icônes : {pk['name'] if pk else 'Windows par défaut'}")

    def _delete(self, pk):
        if W.confirm(self, f"Supprimer « {pk['name']} » ?", "Ce pack d'icônes sera supprimé.", "Supprimer"):
            icons.uninstall(pk)
            self.refresh()

    def on_changed(self):
        self.refresh()


# ======================================================================= barre des tâches


class TaskbarPage(W.Page):
    def __init__(self, win):
        super().__init__(win, "Barre des tâches et Explorateur",
                         "Disposition de la barre, menu Démarrer et Explorateur de fichiers. "
                         "L'Explorateur redémarre quelques secondes pour appliquer (les fenêtres de "
                         "dossiers ouvertes se ferment).")
        self._loading = False
        self.body.addWidget(W.section("Dispositions prêtes"))
        g = W.Grid()
        for pr in taskbar.PRESETS:
            prev = W.Preview(lambda p, w, h, pr=pr: self._draw(p, w, h, pr), 240, 110)
            g.add(W.Card(prev, pr["name"], pr["desc"], lambda pr=pr: self._preset(pr), 240))
        self.body.addWidget(g)

        self.body.addWidget(W.section("Réglages"))
        box = QFrame()
        box.setProperty("cls", "box")
        grid = QGridLayout(box)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)
        self.combos = {}
        r = 0
        for key, (_, _, text, values, _) in taskbar.OPTIONS.items():
            if not taskbar.available(key):
                continue
            c = QComboBox()
            for v, t in values.items():
                c.addItem(t, v)
            c.currentIndexChanged.connect(lambda *_, k=key: self._changed(k))
            self.combos[key] = c
            grid.addWidget(W.label(text), r // 2, (r % 2) * 2)
            grid.addWidget(c, r // 2, (r % 2) * 2 + 1)
            r += 1
        self.autohide = QCheckBox("Masquer automatiquement la barre des tâches")
        self.classic = QCheckBox("Menu clic droit classique (Windows 11)")
        self.autohide.toggled.connect(lambda on: self._toggle("Masquage de la barre", taskbar.set_autohide, on))
        self.classic.toggled.connect(lambda on: self._toggle("Menu clic droit", taskbar.set_classic_menu, on))
        grid.addWidget(self.autohide, r // 2 + 1, 0, 1, 2)
        if wp.is_win11():
            grid.addWidget(self.classic, r // 2 + 1, 2, 1, 2)
        if not wp.is_win11():
            self.position = QComboBox()
            for v, t in taskbar.POSITIONS.items():
                self.position.addItem(t, v)
            self.position.currentIndexChanged.connect(
                lambda *_: self._toggle("Position de la barre", taskbar.set_position, self.position.currentData()))
            grid.addWidget(W.label("Position"), r // 2 + 2, 0)
            grid.addWidget(self.position, r // 2 + 2, 1)
        self.body.addWidget(box)
        self.apply_btn = W.button("Appliquer maintenant (redémarre l'Explorateur)", self._restart, "primary")
        self.apply_btn.setEnabled(False)
        self.body.addWidget(_row(self.apply_btn))
        self.finish()
        self.read()

    def _draw(self, p, w, h, pr):
        draw.gradient_bg(p, w, h)
        draw.window(p, w * 0.22, h * 0.1, w * 0.56, h * 0.6, False, "#0078d4")
        v = pr["values"]
        draw.taskbar(p, w, h, True, "#0078d4", v.get("align", 1), v.get("search", 1),
                     pr.get("autohide", False), dock=pr["id"] == "macos")

    def read(self):
        self._loading = True
        for key, c in self.combos.items():
            i = c.findData(taskbar.get(key))
            c.setCurrentIndex(max(0, i))
        self.autohide.setChecked(taskbar.autohide())
        self.classic.setChecked(taskbar.classic_menu())
        if hasattr(self, "position"):
            self.position.setCurrentIndex(max(0, self.position.findData(taskbar.position())))
        self._loading = False

    def _pending(self):
        self.apply_btn.setEnabled(True)
        self.win.toast("Réglage enregistré — cliquez sur « Appliquer maintenant » pour le voir", undo=True)

    def _changed(self, key):
        if self._loading:
            return
        backup.snapshot(taskbar.OPTIONS[key][2])
        if not taskbar.set(key, self.combos[key].currentData()):
            W.error(self, "Réglage protégé", "Windows empêche de modifier ce réglage sur cette version.")
        self._pending()

    def _toggle(self, label, func, value):
        if self._loading:
            return
        backup.snapshot(label)
        func(value)
        self._pending()

    def _preset(self, pr):
        if not W.confirm(self, f"Disposition « {pr['name']} »",
                         "L'Explorateur Windows va redémarrer quelques secondes : les fenêtres de "
                         "dossiers ouvertes seront fermées.", "Appliquer"):
            return
        backup.snapshot(f"Barre des tâches : {pr['name']}")
        taskbar.apply_preset(pr)
        taskbar.reload()
        self.read()
        self.win.applied(f"Barre des tâches « {pr['name']} »")

    def _restart(self):
        taskbar.reload()
        self.apply_btn.setEnabled(False)
        self.win.toast("✓ Explorateur redémarré")

    def on_changed(self):
        self.read()


# ======================================================================= effets


class EffectsPage(W.Page):
    def __init__(self, win):
        super().__init__(win, "Animations et effets",
                         "Les animations de Windows : ouverture et réduction des fenêtres, menus en "
                         "fondu, ombres… Rendez Windows plus fluide ou plus rapide.")
        self._loading = False
        g = W.Grid()
        self.cards = {}
        icons_ = {"fluid": "✨", "default": "🪟", "snappy": "⚡", "performance": "🚀"}
        for pr in effects.PRESETS:
            prev = W.Preview(lambda p, w, h, i=icons_[pr["id"]]: (draw.gradient_bg(p, w, h, "#5b6fd6", "#b76bd6"),
                                                                 draw.text(p, w / 2 - 18, h / 2 + 14, i, 26)),
                             220, 90)
            c = W.Card(prev, pr["name"], pr["desc"], lambda pr=pr: self._preset(pr), 220)
            self.cards[pr["id"]] = c
            g.add(c)
        self.body.addWidget(g)
        self.body.addWidget(W.section("Réglages détaillés"))
        box = QFrame()
        box.setProperty("cls", "box")
        bv = QGridLayout(box)
        self.checks = {}
        for i, (key, (text, _, _)) in enumerate(effects.EFFECTS.items()):
            chk = QCheckBox(text)
            chk.toggled.connect(lambda on, k=key: self._set(k, on))
            self.checks[key] = chk
            bv.addWidget(chk, i // 2, i % 2)
        self.delay = QComboBox()
        for ms, name in effects.MENU_DELAYS.items():
            self.delay.addItem(f"{name} ({ms} ms)", ms)
        self.delay.currentIndexChanged.connect(self._delay)
        n = len(effects.EFFECTS)
        bv.addWidget(_row(W.label("Ouverture des sous-menus :"), self.delay), n // 2 + 1, 0, 1, 2)
        self.body.addWidget(box)
        note = QFrame()
        note.setProperty("cls", "info")
        nv = QVBoxLayout(note)
        nv.addWidget(W.label("<b>Animations façon macOS (lampe magique…)</b>"))
        nv.addWidget(W.label("Windows ne propose pas ces effets d'origine. L'outil gratuit Windhawk "
                             "(onglet Outils du Workshop) ajoute des mods d'animation de fenêtres, "
                             "activables et désactivables en un clic.", wrap=True))
        nv.addWidget(_row(W.button("Voir les outils", lambda: win.go("workshop", tab="tools"))))
        self.body.addWidget(note)
        self.finish()
        self.read()

    def read(self):
        self._loading = True
        st = effects.capture()
        for k, chk in self.checks.items():
            chk.setChecked(st["values"][k])
        self.delay.setCurrentIndex(max(0, self.delay.findData(st["menu_delay"])))
        for pid, c in self.cards.items():
            pr = next(p for p in effects.PRESETS if p["id"] == pid)
            c.set_active(all(st["values"][k] == v for k, v in pr["values"].items())
                         and st["menu_delay"] == pr["menu_delay"])
        self._loading = False

    def _preset(self, pr):
        backup.snapshot(f"Effets : {pr['name']}")
        effects.apply_preset(pr)
        self.win.applied(f"Effets « {pr['name']} »")

    def _set(self, key, on):
        if self._loading:
            return
        backup.snapshot(effects.EFFECTS[key][0])
        effects.set(key, on)
        self.win.applied(f"{effects.EFFECTS[key][0]} : {'oui' if on else 'non'}")

    def _delay(self):
        if self._loading:
            return
        backup.snapshot("Délai des menus")
        effects.set_menu_delay(self.delay.currentData())
        self.win.applied("Délai des menus modifié")

    def on_changed(self):
        self.read()
