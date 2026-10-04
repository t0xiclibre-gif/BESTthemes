"""Lecteur du fond d'écran animé (Windows) : `BESTthemes.exe --live`.

Se place derrière les icônes du bureau (fenêtre « WorkerW » de l'Explorateur, comme Lively
Wallpaper ; variante Windows 11 24H2 gérée). Une scène par écran, mise en pause quand une
fenêtre agrandie ou en plein écran la cache. S'arrête dès que le fond animé est désactivé
dans BESTthemes (réglages relus chaque seconde).
Hors Windows (développement) ou avec `--window` : s'affiche dans une fenêtre normale.
"""
import os
import sys
import time

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")  # 1 pixel Qt = 1 pixel de l'écran

from PySide6.QtCore import QRect, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

import cairo  # noqa: E402

from bestthemes.core import live  # noqa: E402

from . import winplat as wp  # noqa: E402
from .core import livewall  # noqa: E402

# ======================================================================= Win32

if wp.IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    u32 = ctypes.WinDLL("user32", use_last_error=True)
    HWND = ctypes.c_void_p
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, wintypes.LPARAM)
    for name, res, args in (
        ("FindWindowW", HWND, [wintypes.LPCWSTR, wintypes.LPCWSTR]),
        ("FindWindowExW", HWND, [HWND, HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]),
        ("SendMessageTimeoutW", ctypes.c_ssize_t, [HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t,
                                                   wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]),
        ("EnumWindows", wintypes.BOOL, [WNDENUMPROC, wintypes.LPARAM]),
        ("SetParent", HWND, [HWND, HWND]),
        ("SetWindowPos", wintypes.BOOL, [HWND, HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                         wintypes.UINT]),
        ("MoveWindow", wintypes.BOOL, [HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]),
        ("GetSystemMetrics", ctypes.c_int, [ctypes.c_int]),
        ("GetWindowLongPtrW", ctypes.c_ssize_t, [HWND, ctypes.c_int]),
        ("SetWindowLongPtrW", ctypes.c_ssize_t, [HWND, ctypes.c_int, ctypes.c_ssize_t]),
        ("SetLayeredWindowAttributes", wintypes.BOOL, [HWND, wintypes.DWORD, ctypes.c_ubyte, wintypes.DWORD]),
        ("GetForegroundWindow", HWND, []),
        ("IsZoomed", wintypes.BOOL, [HWND]),
        ("IsWindowVisible", wintypes.BOOL, [HWND]),
        ("GetWindowRect", wintypes.BOOL, [HWND, ctypes.POINTER(wintypes.RECT)]),
        ("GetClassNameW", ctypes.c_int, [HWND, wintypes.LPWSTR, ctypes.c_int]),
        ("MonitorFromWindow", ctypes.c_void_p, [HWND, wintypes.DWORD]),
    ):
        fn = getattr(u32, name)
        fn.restype = res
        fn.argtypes = args

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)]

    u32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
    SWP = 0x0001 | 0x0002 | 0x0010  # NOSIZE | NOMOVE | NOACTIVATE

    def _class(hwnd):
        buf = ctypes.create_unicode_buffer(64)
        u32.GetClassNameW(hwnd, buf, 64)
        return buf.value

    def attach_to_desktop(hwnd):
        """Met la fenêtre derrière les icônes du bureau. Renvoie la taille du bureau virtuel."""
        progman = u32.FindWindowW("Progman", None)
        if not progman:
            raise RuntimeError("bureau Windows introuvable (Progman)")
        res = ctypes.c_size_t()
        # message non documenté qui demande à l'Explorateur de créer la couche « WorkerW »
        u32.SendMessageTimeoutW(progman, 0x052C, 0xD, 0x1, 0, 1000, ctypes.byref(res))
        u32.SendMessageTimeoutW(progman, 0x052C, 0, 0, 0, 1000, ctypes.byref(res))
        found = {}

        def cb(top, _lp):
            if u32.FindWindowExW(top, None, "SHELLDLL_DefView", None):
                found["workerw"] = u32.FindWindowExW(None, top, "WorkerW", None)
            return True

        u32.EnumWindows(WNDENUMPROC(cb), 0)
        if found.get("workerw"):  # Windows 10 et Windows 11 jusqu'à 23H2
            u32.SetParent(hwnd, found["workerw"])
        else:  # Windows 11 24H2 : la couche WorkerW est un enfant de Progman
            workerw = u32.FindWindowExW(progman, None, "WorkerW", None)
            defview = u32.FindWindowExW(progman, None, "SHELLDLL_DefView", None)
            if not workerw or not defview:
                raise RuntimeError("couche du fond d'écran introuvable (WorkerW)")
            ex = u32.GetWindowLongPtrW(hwnd, -20)
            u32.SetWindowLongPtrW(hwnd, -20, ex | 0x00080000)  # WS_EX_LAYERED
            u32.SetLayeredWindowAttributes(hwnd, 0, 255, 0x2)  # LWA_ALPHA
            u32.SetParent(hwnd, progman)
            u32.SetWindowPos(hwnd, defview, 0, 0, 0, 0, SWP)   # sous les icônes
            u32.SetWindowPos(workerw, hwnd, 0, 0, 0, 0, SWP)   # au-dessus du fond fixe
        vw, vh = u32.GetSystemMetrics(78), u32.GetSystemMetrics(79)
        u32.MoveWindow(hwnd, 0, 0, vw, vh, True)
        attach_to_desktop.progman = progman
        return u32.GetSystemMetrics(76), u32.GetSystemMetrics(77), vw, vh

    def desktop_lost():
        """Vrai si l'Explorateur a redémarré : la fenêtre du bureau a disparu."""
        u32.IsWindow.argtypes = [HWND]
        return not u32.IsWindow(getattr(attach_to_desktop, "progman", None))

    def release_instance():
        h = getattr(single_instance, "handle", None)
        if h:
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(h))
            single_instance.handle = None

    def covered_monitor():
        """Rectangle de l'écran caché par une fenêtre agrandie / plein écran (ou None)."""
        fg = u32.GetForegroundWindow()
        if not fg or not u32.IsWindowVisible(fg):
            return None
        if _class(fg) in ("WorkerW", "Progman", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Windows.UI.Core.CoreWindow"):
            return None
        r = wintypes.RECT()
        u32.GetWindowRect(fg, ctypes.byref(r))
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if not u32.GetMonitorInfoW(u32.MonitorFromWindow(fg, 2), ctypes.byref(mi)):
            return None
        m = mi.rcMonitor
        full = r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom
        if u32.IsZoomed(fg) or full:
            return m.left, m.top, m.right - m.left, m.bottom - m.top
        return None

    def single_instance():
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = ctypes.c_void_p
        single_instance.handle = k32.CreateMutexW(None, False, "Local\\BESTthemesLiveWallpaper")
        return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS
else:
    def attach_to_desktop(hwnd):
        raise RuntimeError("disponible uniquement sous Windows")

    def desktop_lost():
        return False

    def release_instance():
        pass

    def covered_monitor():
        return None

    def single_instance():
        import fcntl
        wp.DATA.mkdir(parents=True, exist_ok=True)
        single_instance.lock = open(wp.DATA / "live.lock", "w")
        try:
            fcntl.flock(single_instance.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False


# ======================================================================= lecteur


class Area:
    """Une scène pour un écran."""

    def __init__(self, rect, cfg, palette):
        self.rect = rect
        rw, rh = livewall.render_size(rect.width(), rect.height(), cfg["quality"])
        self.scene = live.create(cfg["scene"], rw, rh, palette, seed=7)
        self.surf = cairo.ImageSurface(cairo.FORMAT_RGB24, rw, rh)
        self.img = None
        self.paused = False

    def render(self, t):
        if self.paused and self.img is not None:
            return False
        self.scene.draw(cairo.Context(self.surf), t)
        self.surf.flush()
        self.img = QImage(self.surf.get_data(), self.surf.get_width(), self.surf.get_height(),
                          self.surf.get_stride(), QImage.Format_RGB32)
        return True


class LiveWidget(QWidget):
    def __init__(self, windowed):
        super().__init__(None, Qt.Window if windowed else (Qt.FramelessWindowHint | Qt.Tool))
        self.windowed = windowed
        self.setWindowTitle("BESTthemes — fond animé")
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.areas = []
        self.origin = (0, 0)
        self.cfg = None
        self.mtime = None
        self.t0 = time.monotonic()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.check = QTimer(self)
        self.check.timeout.connect(self._check)

    def start(self):
        self.cfg = livewall.config()
        if not self.cfg.get("enabled") and not self.windowed:
            return False
        if self.windowed:
            self.resize(960, 540)
            self.show()
        else:
            self.show()
            # À l'ouverture de session, le bureau n'est pas toujours encore prêt : on patiente
            for attempt in range(30):
                try:
                    x, y, w, h = attach_to_desktop(int(self.winId()))
                    break
                except RuntimeError:
                    if attempt == 29:
                        raise
                    time.sleep(1)
            self.origin = (x, y)
            self.setGeometry(0, 0, w, h)
        self._build()
        self.check.start(1000)
        livewall.write_status(ok=True)
        return True

    def _build(self):
        try:
            self.mtime = os.path.getmtime(livewall._config_file())
        except OSError:
            self.mtime = None
        palette = live.find_palette(self.cfg["palette"])
        if self.windowed:
            rects = [QRect(0, 0, self.width(), self.height())]
        else:
            ox, oy = self.origin
            rects = [s.geometry().translated(-ox, -oy) for s in QGuiApplication.screens()]
        self.areas = [Area(r, self.cfg, palette) for r in rects]
        self.timer.start(max(15, int(1000 / int(self.cfg.get("fps") or 24))))

    def _tick(self):
        t = time.monotonic() - self.t0
        if any([a.render(t) for a in self.areas]):
            self.update()

    def _check(self):
        if not self.windowed and desktop_lost():
            self._restart()
            return
        try:
            mtime = os.path.getmtime(livewall._config_file())
        except OSError:
            mtime = None
        if mtime != self.mtime:
            self.cfg = livewall.config()
            if not self.cfg.get("enabled") and not self.windowed:
                self.stop()
                return
            self._build()
        cov = covered_monitor() if self.cfg.get("pause_when_covered", True) else None
        ox, oy = self.origin
        for a in self.areas:
            a.paused = bool(cov) and a.rect.contains(cov[0] - ox + cov[2] // 2, cov[1] - oy + cov[3] // 2)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.windowed and self.cfg:
            self._build()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        for a in self.areas:
            if a.img is not None:
                p.drawImage(a.rect, a.img)
            else:
                p.fillRect(a.rect, Qt.black)
        p.end()

    def _restart(self):
        """L'Explorateur a redémarré (et détruit notre fenêtre) : on relance un lecteur neuf,
        qui attendra le nouveau bureau avant de s'y placer."""
        self.timer.stop()
        self.check.stop()
        release_instance()
        try:
            livewall._spawn()
        finally:
            QApplication.quit()

    def closeEvent(self, e):
        self.stop()
        e.accept()

    def stop(self):
        self.timer.stop()
        self.check.stop()
        self.hide()
        if not self.windowed:
            livewall.write_status(ok=False)
            try:  # redessine le fond fixe là où l'animation était
                from .core import appearance
                appearance.reload()
            except Exception:  # noqa: BLE001
                pass
        QApplication.quit()


def main():
    windowed = "--window" in sys.argv or not wp.IS_WINDOWS
    if not single_instance():
        return 0  # un lecteur tourne déjà : il relira les nouveaux réglages
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    w = LiveWidget(windowed)
    try:
        if not w.start():
            return 0
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        livewall.write_status(ok=False, error=f"Fond animé impossible sur ce Windows : {e}")
        return 1
    return app.exec()
