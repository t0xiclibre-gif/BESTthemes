"""BESTthemes pour Windows — fenêtre principale."""
import os
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, qInstallMessageHandler
from PySide6.QtGui import QAction, QGuiApplication, QIcon
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMainWindow, QMenu, QPushButton, QStackedWidget,
                               QToolButton, QVBoxLayout, QWidget)

from . import __version__
from . import winplat as wp
from .core import appearance, backup, wallgen
from .ui import style
from .ui import widgets as W

PAGES = [
    ("home", "🏠  Accueil"),
    ("packs", "⭐  Packs"),
    ("appearance", "🎨  Couleurs"),
    ("wallpapers", "🖼  Fonds d'écran"),
    ("cursors", "🖱  Curseurs"),
    ("icons", "📁  Icônes"),
    ("taskbar", "▭  Barre des tâches"),
    ("effects", "✨  Animations"),
    ("workshop", "⬇  Workshop"),
]

ICON = Path(__file__).resolve().parent / "data" / "bestthemes.ico"


class Toast(QFrame):
    def __init__(self, parent, on_undo):
        super().__init__(parent)
        self.setObjectName("toast")
        h = QHBoxLayout(self)
        h.setContentsMargins(18, 6, 8, 6)
        self.text = QLabel()
        h.addWidget(self.text)
        self.undo = QPushButton("Annuler")
        self.undo.setCursor(Qt.PointingHandCursor)
        self.undo.clicked.connect(on_undo)
        h.addWidget(self.undo)
        close = QPushButton("✕")
        close.clicked.connect(self.hide)
        h.addWidget(close)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        self.hide()

    def show_text(self, text, undo):
        self.text.setText(text)
        self.undo.setVisible(undo)
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self.timer.start(5000)

    def reposition(self):
        p = self.parentWidget()
        self.move((p.width() - self.width()) // 2 + 110, p.height() - self.height() - 24)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BESTthemes")
        if ICON.exists():
            self.setWindowIcon(QIcon(str(ICON)))
        self.resize(1200, 800)
        self.pages = {}

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(230)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 18, 0, 12)
        logo = W.label("BESTthemes", "logo")
        logo.setAlignment(Qt.AlignCenter)
        sv.addWidget(logo)
        sv.addSpacing(10)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        for pid, title in PAGES:
            it = QListWidgetItem(title)
            it.setData(Qt.UserRole, pid)
            it.setSizeHint(QSize(200, 40))
            self.nav.addItem(it)
        self.nav.currentRowChanged.connect(self._on_nav)
        sv.addWidget(self.nav, 1)

        row = QHBoxLayout()
        row.setContentsMargins(12, 0, 12, 0)
        self.undo_btn = W.button("↶ Annuler", self.undo)
        row.addWidget(self.undo_btn, 1)
        menu_btn = QToolButton()
        menu_btn.setText("☰")
        menu_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(menu_btn)
        for text, cb in (("Restaurer mon Windows d'origine", self.restore_original),
                         ("Ouvrir le dossier de BESTthemes", self.open_data),
                         ("À propos", self.about)):
            a = QAction(text, menu)
            a.triggered.connect(cb)
            menu.addAction(a)
        menu_btn.setMenu(menu)
        row.addWidget(menu_btn)
        sv.addLayout(row)
        ver = W.label(f"v{__version__} · {'Windows 11' if wp.is_win11() else 'Windows 10'}"
                      f"{'' if wp.IS_WINDOWS else ' (démo)'}", "dim")
        ver.setAlignment(Qt.AlignCenter)
        sv.addWidget(ver)
        h.addWidget(side)

        self.stack = QStackedWidget()
        h.addWidget(self.stack, 1)
        self.toast_w = Toast(root, self.undo)
        self.apply_style()
        self.update_undo()
        self.nav.setCurrentRow(0)

    # ------------------------------------------------------------------ apparence de l'appli

    def apply_style(self):
        st = appearance.state()
        QApplication.instance().setStyleSheet(style.stylesheet(st["apps_dark"], st["accent"]))

    # ------------------------------------------------------------------ navigation

    def _page(self, pid):
        if pid not in self.pages:
            from .ui import pages_main as M
            from .ui import pages_personal as P
            from .ui import pages_wallpapers as WL
            from .ui import pages_workshop as WS
            cls = {"home": M.HomePage, "packs": M.PacksPage, "appearance": M.AppearancePage,
                   "wallpapers": WL.WallpapersPage,
                   "cursors": P.CursorsPage, "icons": P.IconsPage, "taskbar": P.TaskbarPage,
                   "effects": P.EffectsPage, "workshop": WS.WorkshopPage}[pid]
            page = cls(self)
            self.pages[pid] = page
            self.stack.addWidget(page)
        return self.pages[pid]

    def _on_nav(self, row):
        if row < 0:
            return
        pid = self.nav.item(row).data(Qt.UserRole)
        print("Page :", pid, file=sys.stderr)
        page = self._page(pid)
        self.stack.setCurrentWidget(page)
        page.on_show()

    def go(self, pid, **kw):
        page = self._page(pid)
        for i in range(self.nav.count()):
            if self.nav.item(i).data(Qt.UserRole) == pid:
                self.nav.setCurrentRow(i)
        if kw and hasattr(page, "navigate"):
            page.navigate(**kw)

    def refresh_pages(self):
        for pid in ("cursors", "icons", "appearance"):
            if pid in self.pages:
                self.pages[pid].on_changed()

    # ------------------------------------------------------------------ notifications / annuler

    def changed(self):
        self.update_undo()
        self.apply_style()
        for page in self.pages.values():
            page.on_changed()

    def applied(self, text):
        self.changed()
        self.toast(f"✓ {text}", undo=True)

    def toast(self, text, undo=False):
        self.toast_w.show_text(text, undo and backup.last_label() is not None)

    def update_undo(self):
        label = backup.last_label()
        self.undo_btn.setEnabled(label is not None)
        self.undo_btn.setToolTip(f"Annuler : {label}" if label else "Rien à annuler")

    def undo(self):
        label = backup.undo()
        self.changed()
        self.toast(f"↶ Annulé : {label}" if label is not None else "Rien à annuler")

    def restore_original(self):
        if W.confirm(self, "Restaurer Windows d'origine ?",
                     "Couleurs, fond d'écran, curseurs, icônes, barre des tâches et effets "
                     "reviendront à leur état du premier lancement de BESTthemes.", "Restaurer"):
            if backup.restore_original():
                self.applied("Windows d'origine restauré")

    def open_data(self):
        wp.DATA.mkdir(parents=True, exist_ok=True)
        if wp.IS_WINDOWS:
            import os
            os.startfile(str(wp.DATA))  # noqa: S606 — ouvre le dossier dans l'Explorateur

    def about(self):
        W.confirm(self, "BESTthemes pour Windows",
                  f"Version {__version__}<br><br>Personnalisez Windows 10 et 11 en un clic, sans "
                  "droits administrateur et sans modifier de fichiers système.<br><br>"
                  "Les thèmes du Workshop viennent de xfce-look.org / pling.com et de GitHub ; "
                  "ils appartiennent à leurs auteurs.", "OK")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.toast_w.isVisible():
            self.toast_w.reposition()


def main():
    if getattr(sys, "frozen", False):
        # Sans console, Qt n'affiche ses messages nulle part : on les envoie au journal.
        qInstallMessageHandler(lambda _mode, _ctx, msg: print("Qt :", msg, file=sys.stderr))
    if wp.IS_WINDOWS:
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BESTthemes.App")
        except Exception:  # noqa: BLE001
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("BESTthemes")
    # Le style natif « Windows 11 » de Qt gère mal les feuilles de style (dessins ratés,
    # plantages) : Fusion est entièrement piloté par la nôtre et identique partout.
    app.setStyle("Fusion")
    screen = QGuiApplication.primaryScreen()
    if screen:
        size = screen.size() * screen.devicePixelRatio()
        wallgen.SCREEN = (max(1280, size.width()), max(720, size.height()))
    try:
        backup.save_original_once()
    except Exception as e:  # noqa: BLE001
        print("Sauvegarde d'origine impossible :", e, file=sys.stderr)
    win = MainWindow()
    win.show()
    code = _selftest(app, win) if "--selftest" in sys.argv else app.exec()
    # Des téléchargements peuvent encore tourner en arrière-plan : on quitte sans laisser
    # Python détruire Qt sous leurs pieds (plantage aléatoire à la fermeture sinon).
    for stream in (sys.stdout, sys.stderr):
        if stream:
            stream.flush()
    os._exit(code)


def _selftest(app, win):
    """Ouvre chaque page puis quitte : sert à vérifier l'exécutable (code 0 = OK).
    Une page toutes les 400 ms, comme un vrai clic (pas de processEvents() en boucle,
    qui provoque des dessins imbriqués)."""
    result = {"code": 0}
    todo = [pid for pid, _ in PAGES]

    def step():
        if not todo:
            app.quit()
            return
        try:
            win.go(todo.pop(0))
        except Exception:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            result["code"] = 1
            app.quit()
            return
        QTimer.singleShot(400, step)

    QTimer.singleShot(500, step)
    QTimer.singleShot(60000, lambda: (result.update(code=2), app.quit()))
    app.exec()
    return result["code"]


if __name__ == "__main__":
    sys.exit(main())
