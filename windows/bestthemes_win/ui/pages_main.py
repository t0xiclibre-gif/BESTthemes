"""Pages Accueil, Packs et Apparence."""
import random

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFileDialog, QFrame,
                               QHBoxLayout, QProgressDialog, QPushButton, QVBoxLayout, QWidget)

from bestthemes.core import generator as G

from .. import winplat as wp
from ..core import appearance, backup, packs, taskbar, tools, wallgen, workshop
from . import draw
from . import widgets as W


# ======================================================================= packs


def apply_pack(win, pk):
    dlg = QProgressDialog(f"Application du pack « {pk['name']} »…", None, 0, 0, win)
    dlg.setWindowTitle("BESTthemes")
    dlg.setWindowModality(Qt.WindowModal)
    dlg.setMinimumDuration(0)
    dlg.setCancelButton(None)
    dlg.show()
    bridge = W.Bridge()

    def on_msg(text, frac):
        if text:
            dlg.setLabelText(text)
        if frac is None:
            dlg.setRange(0, 0)
        else:
            dlg.setRange(0, 100)
            dlg.setValue(int(frac * 100))

    bridge.message.connect(on_msg)

    def done(res):
        warnings, restart = res
        dlg.close()
        if restart:
            taskbar.reload()
        win.applied(f"Pack « {pk['name']} » appliqué")
        missing = [t for t in pk.get("tools", []) if not tools.is_installed(t)]
        if warnings:
            W.error(win, "Pack appliqué avec des remarques", "\n".join(warnings))
        elif missing:
            names = ", ".join(t["name"] for t in tools.TOOLS if t["id"] in missing)
            if W.confirm(win, "Aller plus loin ?",
                         f"Ce look est encore plus réussi avec : {names}. "
                         "Les installer depuis l'onglet « Outils » du Workshop ?", "Voir les outils"):
                win.go("workshop", tab="tools")

    def failed(e):
        dlg.close()
        win.changed()
        W.error(win, "Le pack n'a pas pu être appliqué", f"{e}\n\nVous pouvez revenir en arrière avec « Annuler ».")

    W.run_async(lambda: packs.apply(pk, lambda t, f: bridge.message.emit(t, f)), done, failed)


def pack_card(win, pk):
    prev = W.Preview(lambda p, w, h, pk=pk: draw.pack(p, w, h, pk), 280, 158)
    card = W.Card(prev, pk["name"], pk["desc"])
    online = packs.needs_download(pk)
    card.actions.addWidget(W.pill("Télécharge" if online else "Hors-ligne"))
    for c in packs.swatches(pk):
        sw = W.Preview(None, 14, 14, radius=7, bg=c)
        sw.setFixedWidth(14)
        card.actions.addWidget(sw)
    card.actions.addStretch(1)
    card.actions.addWidget(W.button("Appliquer", lambda: apply_pack(win, pk), "primary"))
    return card


class PacksPage(W.Page):
    def __init__(self, win):
        super().__init__(win, "Packs", "Un look complet en un clic : mode, couleur d'accent, fond d'écran, "
                                       "curseurs, icônes, barre des tâches et effets. Tout s'annule avec « Annuler ».")
        all_packs = packs.load()
        for title, sel in (("Inspirés des systèmes et thèmes populaires", packs.needs_download),
                           ("Créations BESTthemes (hors-ligne)", lambda p: not packs.needs_download(p))):
            self.body.addWidget(W.section(title))
            g = W.Grid()
            for pk in all_packs:
                if sel(pk):
                    g.add(pack_card(win, pk))
            self.body.addWidget(g)
        self.finish()


# ======================================================================= accueil


class HomePage(W.Page):
    def __init__(self, win):
        super().__init__(win, "Accueil")
        hero = QFrame()
        hero.setProperty("cls", "hero")
        hv = QVBoxLayout(hero)
        hv.setContentsMargins(26, 22, 26, 22)
        hv.addWidget(W.label("Bienvenue dans BESTthemes", "title"))
        hv.addWidget(W.label("Personnalisez Windows en un clic : couleurs, fonds d'écran, curseurs, "
                             "icônes, barre des tâches et effets. Sans rien casser : tout s'annule.", wrap=True))
        row = QHBoxLayout()
        for text, pid in (("⭐ Essayer un pack", "packs"), ("🖼 Fonds d'écran", "wallpapers"),
                          ("⬇ Workshop", "workshop"), ("🎨 Mes couleurs", "appearance")):
            row.addWidget(W.button(text, lambda p=pid: win.go(p)))
        row.addStretch(1)
        hv.addLayout(row)
        self.body.addWidget(hero)
        if not wp.IS_WINDOWS:
            info = QFrame()
            info.setProperty("cls", "info")
            iv = QVBoxLayout(info)
            iv.addWidget(W.label("Mode démonstration : vous n'êtes pas sous Windows, les réglages sont "
                                 "simulés et rien n'est modifié sur cet ordinateur.", wrap=True))
            self.body.addWidget(info)
        self.body.addWidget(W.section("Packs à la une"))
        g = W.Grid()
        for pk in packs.load():
            if pk["id"] in ("macos-light", "fluent-dark", "nord", "catppuccin", "gen-synthwave", "gen-sakura"):
                g.add(pack_card(win, pk))
        self.body.addWidget(g)
        safe = QFrame()
        safe.setProperty("cls", "info")
        sv = QVBoxLayout(safe)
        sv.addWidget(W.label("<b>Aucun risque</b>"))
        sv.addWidget(W.label("BESTthemes ne modifie aucun fichier système et n'a pas besoin des droits "
                             "administrateur. Avant chaque changement, vos réglages sont enregistrés : "
                             "« Annuler » revient en arrière, et le menu ☰ restaure votre Windows "
                             "tel qu'il était au premier lancement.", wrap=True))
        self.body.addWidget(safe)
        self.finish()


# ======================================================================= apparence


class AppearancePage(W.Page):
    def __init__(self, win):
        super().__init__(win, "Couleurs et fond d'écran",
                         "Mode sombre, couleur d'accent, transparence et fonds d'écran.")
        self._loading = False
        self._amb_cache = None

        # --- mode
        self.body.addWidget(W.section("Mode"))
        mg = W.Grid()
        self.mode_cards = {}
        for mid, name, apps, system in (("light", "Clair", False, False), ("dark", "Sombre", True, True),
                                        ("mixed", "Mixte (barre sombre)", False, True)):
            prev = W.Preview(lambda p, w, h, a=apps, s=system: self._draw_mode(p, w, h, a, s), 220, 120)
            c = W.Card(prev, name, None, lambda a=apps, s=system, n=name: self._set_mode(a, s, n), 220)
            self.mode_cards[mid] = (c, apps, system)
            mg.add(c)
        self.body.addWidget(mg)

        # --- accent
        self.body.addWidget(W.section("Couleur d'accent"))
        box = QFrame()
        box.setProperty("cls", "box")
        bv = QVBoxLayout(box)
        swr = QHBoxLayout()
        swr.setSpacing(8)
        for c in ("#0078d4", "#0063b1", "#8e8cd8", "#744da9", "#b146c2", "#e3008c", "#e81123",
                  "#f7630c", "#ffb900", "#10893e", "#00b294", "#038387", "#5d5a58", "#2d7d9a"):
            b = QPushButton()
            b.setFixedSize(30, 30)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"background:{c}; border-radius:15px; border:2px solid rgba(0,0,0,0.12);")
            b.clicked.connect(lambda *_, c=c: self._set_accent(c))
            swr.addWidget(b)
        more = W.button("Autre couleur…", self._pick_accent)
        swr.addWidget(more)
        swr.addStretch(1)
        bv.addLayout(swr)
        self.chk_auto = QCheckBox("Choisir automatiquement d'après le fond d'écran")
        self.chk_title = QCheckBox("Barres de titre et bordures des fenêtres en couleur d'accent")
        self.chk_taskbar = QCheckBox("Menu Démarrer et barre des tâches en couleur d'accent (mode sombre)")
        self.chk_transp = QCheckBox("Effets de transparence")
        for chk in (self.chk_auto, self.chk_title, self.chk_taskbar, self.chk_transp):
            bv.addWidget(chk)
        self.chk_auto.toggled.connect(lambda on: self._opt("Accent automatique", appearance.set_auto_accent, on))
        self.chk_title.toggled.connect(lambda on: self._opt("Barres de titre", lambda v: appearance.set_accent_options(titlebars=v), on))
        self.chk_taskbar.toggled.connect(lambda on: self._opt("Barre des tâches colorée", lambda v: appearance.set_accent_options(taskbar=v), on))
        self.chk_transp.toggled.connect(lambda on: self._opt("Transparence", appearance.set_transparency, on))
        self.body.addWidget(box)

        # --- ambiances (créateur)
        self.body.addWidget(W.section("Créer une ambiance"))
        self.body.addWidget(W.label("Choisissez une palette et un style : BESTthemes génère un fond "
                                    "d'écran unique et règle le mode et la couleur d'accent assortis.",
                                    "hint", wrap=True))
        amb = QFrame()
        amb.setProperty("cls", "box")
        ah = QHBoxLayout(amb)
        left = QVBoxLayout()
        self.pal_combo = QComboBox()
        for p in G.load_palettes():
            self.pal_combo.addItem(p["name"], p["id"])
        self.style_combo = QComboBox()
        for k, v in wallgen.STYLES.items():
            self.style_combo.addItem(v, k)
        left.addWidget(W.label("Palette"))
        left.addWidget(self.pal_combo)
        left.addWidget(W.label("Style du fond d'écran"))
        left.addWidget(self.style_combo)
        left.addWidget(W.button("🎲 Autre variante", self._reseed))
        left.addWidget(W.button("Créer et appliquer", self._create_ambiance, "primary"))
        left.addStretch(1)
        ah.addLayout(left)
        self.seed = None
        self.amb_preview = W.Preview(self._draw_ambiance, 420, 236)
        ah.addWidget(self.amb_preview, 1)
        self.pal_combo.currentIndexChanged.connect(self._pal_changed)
        self.style_combo.currentIndexChanged.connect(lambda *_: self.amb_preview.update())
        self.body.addWidget(amb)
        self._pal_changed()

        # --- fonds d'écran
        head = QHBoxLayout()
        head.addWidget(W.section("Fonds d'écran"))
        head.addStretch(1)
        head.addWidget(W.button("Choisir une image…", self._pick_wallpaper))
        head.addWidget(W.button("Plus de fonds d'écran (HQ, animés)", lambda: win.go("wallpapers")))
        hw = QWidget()
        hw.setLayout(head)
        self.body.addWidget(hw)
        self.walls = W.Grid()
        self.body.addWidget(self.walls)
        self.finish()
        self.on_changed()
        self._walls_loaded = False

    # ------------------------------------------------------------------ dessin

    def _draw_mode(self, p, w, h, apps_dark, system_dark):
        draw.gradient_bg(p, w, h, "#7f9cc9" if not system_dark else "#2b3a55",
                         "#c9d6ea" if not system_dark else "#4b3f6b")
        draw.window(p, w * 0.14, h * 0.1, w * 0.72, h * 0.68, apps_dark, appearance.accent())
        draw.taskbar(p, w, h, system_dark, appearance.accent())

    def _palette(self):
        return G.palette(self.pal_combo.currentData())

    def _draw_ambiance(self, p, w, h):
        pal = self._palette()
        style = self.style_combo.currentData()
        key = (pal["id"], style, self.seed)
        if self._amb_cache is None or self._amb_cache[0] != key:
            self._amb_cache = (key, W.surface_to_pixmap(draw.W.render(pal, style, 384, 216, self.seed)))
        pm = self._amb_cache[1]
        p.drawPixmap(0, 0, pm.scaled(int(w), int(h), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        dark = G.derive(pal)["dark"]
        draw.window(p, w * 0.15, h * 0.12, w * 0.6, h * 0.62, dark, pal["accent"], True)
        draw.taskbar(p, w, h, dark, pal["accent"], translucent=True)

    def _pal_changed(self):
        pal = self._palette()
        i = self.style_combo.findData(pal.get("wallpaper", "gradient"))
        if i >= 0:
            self.style_combo.setCurrentIndex(i)
        self.seed = None
        self.amb_preview.update()

    def _reseed(self):
        self.seed = random.randint(1, 10 ** 6)
        self.amb_preview.update()

    # ------------------------------------------------------------------ actions

    def _set_mode(self, apps, system, name):
        backup.snapshot(f"Mode {name.lower()}")
        appearance.set_mode(apps_dark=apps, system_dark=system)
        self.win.applied(f"Mode {name.lower()}")

    def _set_accent(self, c):
        backup.snapshot("Couleur d'accent")
        appearance.set_accent(c)
        self.win.applied("Couleur d'accent changée")

    def _pick_accent(self):
        c = QColorDialog.getColor(parent=self, title="Couleur d'accent")
        if c.isValid():
            self._set_accent(c.name())

    def _opt(self, label, func, on):
        if self._loading:
            return
        backup.snapshot(label)
        func(on)
        self.win.applied(f"{label} : {'activé' if on else 'désactivé'}")

    def _create_ambiance(self):
        pal = self._palette()
        style = self.style_combo.currentData()
        seed = self.seed

        def work():
            path = wallgen.generate(pal, style, seed)
            backup.snapshot(f"Ambiance {pal['name']}")
            dark = G.derive(pal)["dark"]
            appearance.set_mode(apps_dark=dark, system_dark=dark)
            appearance.set_accent(pal["accent"])
            appearance.set_wallpaper(path)
            return pal["name"]

        W.run_async(work, lambda n: (self.win.applied(f"Ambiance « {n} » appliquée"), self._load_walls(True)),
                    lambda e: W.error(self, "Impossible de créer l'ambiance", str(e)))

    def _pick_wallpaper(self):
        f, _ = QFileDialog.getOpenFileName(self, "Choisir un fond d'écran", "",
                                           "Images (*.jpg *.jpeg *.png *.bmp *.webp)")
        if f:
            self._apply_wall(f)

    def _apply_wall(self, path):
        backup.snapshot("Fond d'écran")
        appearance.set_wallpaper(path)
        self.win.applied("Fond d'écran appliqué")
        self._load_walls(True)

    def _load_walls(self, force=False):
        if self._walls_loaded and not force:
            return
        self._walls_loaded = True
        self.walls.clear()
        files = workshop.wallpapers()[:120]
        if not files:
            self.walls.add(W.label("Aucun fond d'écran pour l'instant : créez une ambiance ou visitez le Workshop.", "hint"))
        current = appearance.state()["wallpaper"]
        for f in files:
            prev = W.Preview(None, 200, 112)
            card = W.Card(prev, f.stem[:40], None, lambda f=f: self._apply_wall(str(f)), 200)
            card.set_active(str(f) == current)
            self.walls.add(card)
            W.run_async(lambda f=f: _thumb(f),
                        lambda img, prev=prev: prev.set_pixmap(QPixmap.fromImage(img)) if img else None)

    def on_show(self):
        self._load_walls()

    def on_changed(self):
        self._loading = True
        st = appearance.state()
        for mid, (card, apps, system) in self.mode_cards.items():
            card.set_active(st["apps_dark"] == apps and st["system_dark"] == system)
            card.update()
        self.chk_auto.setChecked(st["auto_accent"])
        self.chk_title.setChecked(st["accent_titlebars"])
        self.chk_taskbar.setChecked(st["accent_taskbar"])
        self.chk_transp.setChecked(st["transparency"])
        self._loading = False
        self.update()


def _thumb(path):
    """Vignette (QImage : utilisable hors du thread de l'interface, contrairement à QPixmap)."""
    img = QImage(str(path))
    if img.isNull():
        return None
    return img.scaled(400, 225, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
