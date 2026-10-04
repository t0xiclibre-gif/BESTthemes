"""Briques d'interface communes (Qt)."""
import threading
import traceback

from PySide6.QtCore import QObject, QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLayout, QMessageBox, QPushButton,
                               QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

_workers = set()


class _Worker(QObject):
    done = Signal(object)
    failed = Signal(object)


def run_async(func, on_done=None, on_error=None):
    """Exécute func() dans un thread ; les rappels arrivent dans le thread de l'interface."""
    w = _Worker()
    _workers.add(w)
    if on_done:
        w.done.connect(on_done)
    if on_error:
        w.failed.connect(on_error)
    w.done.connect(lambda *_: _workers.discard(w))
    w.failed.connect(lambda *_: _workers.discard(w))

    def emit(signal, value):
        try:
            signal.emit(value)
        except RuntimeError:  # application fermée pendant le travail : plus personne à prévenir
            pass

    def target():
        try:
            res = func()
        except Exception as e:  # noqa: BLE001 — toute erreur est remontée à l'interface
            traceback.print_exc()
            emit(w.failed, e)
            return
        emit(w.done, res)

    threading.Thread(target=target, daemon=True).start()


class Bridge(QObject):
    """Pour envoyer des mises à jour (progression) depuis un thread."""
    message = Signal(object, object)


# ---------------------------------------------------------------- mise en page fluide


class FlowLayout(QLayout):
    """uniform=True : cartes de même largeur qui remplissent la ligne ; False : chaque
    élément garde sa largeur naturelle (boutons, étiquettes)."""

    def __init__(self, parent=None, spacing=14, uniform=True):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self._uniform = uniform
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        return s

    def _do(self, rect, test):
        x, y, line_h = rect.x(), rect.y(), 0
        visible = [it for it in self._items if not it.widget() or not it.widget().isHidden()]
        if not visible:
            return 0
        if not self._uniform:
            for it in visible:
                sz = it.sizeHint()
                if x > rect.x() and x + sz.width() > rect.right() + 1:
                    x = rect.x()
                    y += line_h + self._spacing
                    line_h = 0
                if not test:
                    it.setGeometry(QRect(QPoint(x, y), sz))
                x += sz.width() + self._spacing
                line_h = max(line_h, sz.height())
            return y + line_h - rect.y()
        w0 = visible[0].sizeHint().width()
        cols = max(1, (rect.width() + self._spacing) // (w0 + self._spacing))
        # Les cartes s'élargissent pour remplir la ligne
        cw = (rect.width() - (cols - 1) * self._spacing) // cols
        for i, it in enumerate(visible):
            if i and i % cols == 0:
                x = rect.x()
                y += line_h + self._spacing
                line_h = 0
            h = it.sizeHint().height()
            if not test:
                it.setGeometry(QRect(QPoint(x, y), QSize(cw, h)))
            x += cw + self._spacing
            line_h = max(line_h, h)
        return y + line_h - rect.y()


class Grid(QWidget):
    """Grille de cartes qui s'adapte à la largeur."""

    def __init__(self, spacing=14):
        super().__init__()
        self.flow = FlowLayout(self, spacing)

    def add(self, w):
        self.flow.addWidget(w)
        return w

    def clear(self):
        while self.flow.count():
            it = self.flow.takeAt(0)
            if it.widget():
                it.widget().deleteLater()


# ---------------------------------------------------------------- images et aperçus


def surface_to_pixmap(surface):
    """cairo.ImageSurface -> QPixmap."""
    w, h = surface.get_width(), surface.get_height()
    data = bytes(surface.get_data())
    fmt = QImage.Format_ARGB32_Premultiplied if surface.get_format() == 0 else QImage.Format_RGB32
    img = QImage(data, w, h, surface.get_stride(), fmt).copy()
    return QPixmap.fromImage(img)


def pil_to_pixmap(im):
    im = im.convert("RGBA")
    data = im.tobytes("raw", "RGBA")
    img = QImage(data, im.width, im.height, im.width * 4, QImage.Format_RGBA8888).copy()
    return QPixmap.fromImage(img)


class Preview(QWidget):
    """Zone dessinée : draw(painter, w, h). Coins arrondis."""

    def __init__(self, draw=None, w=260, h=150, radius=10, pixmap=None, bg=None):
        super().__init__()
        self.draw = draw
        self.pixmap = pixmap
        self.radius = radius
        self.bg = QColor(bg) if bg else None
        self.setMinimumSize(w, h)
        self.setFixedHeight(h)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_pixmap(self, pm):
        self.pixmap = pm
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), self.radius, self.radius)
        p.setClipPath(path)
        if self.bg:
            p.fillRect(self.rect(), self.bg)
        elif self.pixmap is None and self.draw is None:
            p.fillRect(self.rect(), QColor(128, 128, 128, 40))
        if self.pixmap is not None and not self.pixmap.isNull():
            pm = self.pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap((self.width() - pm.width()) // 2, (self.height() - pm.height()) // 2, pm)
        if self.draw:
            try:
                self.draw(p, self.width(), self.height())
            except Exception:  # noqa: BLE001 — un aperçu cassé ne doit pas planter l'appli
                traceback.print_exc()
        p.end()


class RemoteImage(Preview):
    """Image téléchargée en arrière-plan (URL ou fonction qui renvoie l'URL)."""

    _sem = threading.Semaphore(6)

    def __init__(self, source, w=280, h=160, fallback=None):
        super().__init__(fallback, w, h)
        self.source = source
        self._started = False

    def showEvent(self, e):
        super().showEvent(e)
        if not self._started and self.source:
            self._started = True
            run_async(self._fetch, self._loaded, lambda e: None)

    def _fetch(self):
        from bestthemes.workshop import pling
        with self._sem:
            url = self.source() if callable(self.source) else self.source
            if not url:
                return None
            return str(pling.cached_image(url))

    def _loaded(self, path):
        if path:
            img = QImage(path)
            if not img.isNull():
                self.draw = None
                self.set_pixmap(QPixmap.fromImage(img.scaled(720, 480, Qt.KeepAspectRatio,
                                                             Qt.SmoothTransformation)))


# ---------------------------------------------------------------- textes et boutons


def label(text, cls=None, wrap=False):
    lab = QLabel(text)
    if cls:
        lab.setProperty("cls", cls)
    lab.setWordWrap(wrap)
    lab.setTextInteractionFlags(Qt.NoTextInteraction)
    return lab


def button(text, on_click=None, kind=None, tooltip=None):
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    if kind:
        b.setProperty("kind", kind)
    if tooltip:
        b.setToolTip(tooltip)
    if on_click:
        b.clicked.connect(lambda *_: on_click())
    return b


def pill(text, cls="pill"):
    lab = QLabel(text)
    lab.setProperty("cls", cls)
    lab.setMaximumHeight(22)
    return lab


def header(title, subtitle=None):
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 4)
    v.setSpacing(4)
    v.addWidget(label(title, "title"))
    if subtitle:
        v.addWidget(label(subtitle, "subtitle", wrap=True))
    return w


def section(text):
    return label(text, "section")


class Card(QFrame):
    """Carte : aperçu + titre + texte + barre d'actions. Cliquable si on_click."""

    def __init__(self, preview, title, subtitle=None, on_click=None, width=280):
        super().__init__()
        self.setProperty("cls", "card")
        self.on_click = on_click
        self.setMinimumWidth(width)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if on_click:
            self.setCursor(Qt.PointingHandCursor)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 10)
        v.setSpacing(6)
        if preview is not None:
            v.addWidget(preview)
        self.badge = pill("✓ Actif", "badge")
        self.badge.hide()
        top = QHBoxLayout()
        top.setContentsMargins(4, 0, 4, 0)
        self.title = label(title, "card-title")
        top.addWidget(self.title, 1)
        top.addWidget(self.badge)
        v.addLayout(top)
        if subtitle:
            sub = label(subtitle, "card-sub", wrap=True)
            sub.setContentsMargins(4, 0, 4, 0)
            v.addWidget(sub)
        self.actions = QHBoxLayout()
        self.actions.setContentsMargins(4, 2, 4, 0)
        self.actions.setSpacing(6)
        v.addLayout(self.actions)

    def sizeHint(self):
        s = super().sizeHint()
        return QSize(max(self.minimumWidth(), 280), s.height())

    def set_active(self, on, badge=True):
        self.setProperty("active", bool(on))
        self.badge.setVisible(bool(on) and badge)
        self.style().unpolish(self)
        self.style().polish(self)

    def mouseReleaseEvent(self, e):
        if self.on_click and e.button() == Qt.LeftButton:
            self.on_click()
        super().mouseReleaseEvent(e)


def scroll_page(content_widget):
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    sa.setWidget(content_widget)
    return sa


class Page(QWidget):
    """Page avec défilement : self.body (QVBoxLayout) reçoit le contenu."""

    def __init__(self, win, title, subtitle=None):
        super().__init__()
        self.win = win
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        inner.setProperty("cls", "page")
        self.body = QVBoxLayout(inner)
        self.body.setContentsMargins(28, 24, 28, 28)
        self.body.setSpacing(14)
        self.body.addWidget(header(title, subtitle))
        outer.addWidget(scroll_page(inner))

    def finish(self):
        self.body.addStretch(1)

    def on_show(self):
        pass

    def on_changed(self):
        pass


def confirm(parent, title, text, ok="Confirmer"):
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(f"<b>{title}</b>")
    box.setInformativeText(text)
    yes = box.addButton(ok, QMessageBox.AcceptRole)
    box.addButton("Annuler", QMessageBox.RejectRole)
    box.exec()
    return box.clickedButton() is yes


def error(parent, title, text):
    QMessageBox.warning(parent, title, text)


def later(ms, func):
    QTimer.singleShot(ms, func)
