"""Lecteur du fond d'écran animé (XFCE) : `bestthemes --live`.

Une fenêtre de type « bureau » par écran, sous toutes les autres. Se met en pause quand une
fenêtre agrandie ou en plein écran la cache, et s'arrête dès que le fond animé est désactivé
dans BESTthemes (réglages relus chaque seconde).
Option de développement : `--window` affiche l'animation dans une fenêtre normale, sans
toucher au bureau.
"""
import fcntl
import json
import os
import signal
import subprocess
import sys
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

import cairo  # noqa: E402

from .core import live, livewall, paths  # noqa: E402

try:
    gi.require_version("Wnck", "3.0")
    from gi.repository import Wnck  # noqa: E402
except (ValueError, ImportError):
    Wnck = None


def _write_status(**kw):
    st = livewall.status() if kw.pop("keep", False) else {}
    st.update(kw, pid=os.getpid(), time=time.time())
    paths.STATE_DIR.mkdir(parents=True, exist_ok=True)
    livewall.STATUS.write_text(json.dumps(st))


class Screen:
    """Une fenêtre d'animation (un écran)."""

    def __init__(self, player, geo, scale, windowed=False):
        self.player = player
        self.geo = geo
        self.scale = scale
        self.scene = None
        self.frame = None
        self.paused = False
        self.win = Gtk.Window(title="BESTthemes — fond animé")
        if windowed:
            self.win.set_default_size(960, 540)
        else:
            self.win.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
            self.win.set_decorated(False)
            self.win.set_skip_taskbar_hint(True)
            self.win.set_skip_pager_hint(True)
            self.win.set_keep_below(True)
            self.win.set_accept_focus(False)
            self.win.stick()
            self.win.move(geo.x, geo.y)
            self.win.set_default_size(geo.width, geo.height)
            self.win.resize(geo.width, geo.height)
        self.win.set_app_paintable(True)
        area = Gtk.DrawingArea()
        area.connect("draw", self._draw)
        area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        area.connect("button-press-event", self._click)
        self.area = area
        self.win.add(area)
        self.win.connect("delete-event", lambda *_: (player.quit(disabled=True), True)[1])
        self.win.show_all()

    def build(self, cfg, palette):
        w, h = self.win.get_size() if self.player.windowed else (self.geo.width, self.geo.height)
        rw, rh = livewall.render_size(w * self.scale, h * self.scale, cfg["quality"])
        self.scene = live.create(cfg["scene"], rw, rh, palette, seed=7)
        self.frame = cairo.ImageSurface(cairo.FORMAT_RGB24, rw, rh)

    def tick(self, t):
        if self.scene is None or self.paused:
            return
        self.scene.draw(cairo.Context(self.frame), t)
        self.area.queue_draw()

    def _draw(self, widget, cr):
        if self.frame is None:
            cr.set_source_rgb(0, 0, 0)
            cr.paint()
            return
        a = widget.get_allocation()
        cr.scale(a.width / self.frame.get_width(), a.height / self.frame.get_height())
        cr.set_source_surface(self.frame)
        cr.get_source().set_filter(cairo.FILTER_BILINEAR)
        cr.paint()

    def _click(self, _w, event):
        if event.button == 3:
            self.player.menu(event)
        return True

    def destroy(self):
        self.win.destroy()


class Player:
    def __init__(self, windowed=False):
        self.windowed = windowed
        self.screens = []
        self.cfg = None
        self.mtime = None
        self.t0 = time.monotonic()
        self.timer = None
        self.stopped_xfdesktop = False
        self.wnck = None
        if Wnck is not None and not windowed:
            try:
                self.wnck = Wnck.Screen.get_default()
            except Exception:  # noqa: BLE001
                self.wnck = None

    # -------------------------------------------------------------- cycle de vie

    def start(self):
        self.cfg = livewall.config()
        if not self.cfg.get("enabled") and not self.windowed:
            return False
        if not self.windowed:
            self._stop_xfdesktop()
        self._build()
        GLib.timeout_add_seconds(1, self._check)
        display = Gdk.Display.get_default()
        if not self.windowed:
            display.connect("monitor-added", lambda *_: self._rebuild_later())
            display.connect("monitor-removed", lambda *_: self._rebuild_later())
        for sig in (signal.SIGTERM, signal.SIGINT):  # fin de session : on ne relance rien
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, sig, lambda: self.quit(session_end=True))
        _write_status(ok=True, stopped_xfdesktop=self.stopped_xfdesktop)
        return True

    def _stop_xfdesktop(self):
        try:
            if subprocess.run(["pgrep", "-x", "xfdesktop"], stdout=subprocess.DEVNULL).returncode == 0:
                subprocess.run(["xfdesktop", "--quit"], timeout=10, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                self.stopped_xfdesktop = True
        except (OSError, subprocess.TimeoutExpired):
            pass
        if livewall.status().get("stopped_xfdesktop"):  # lancement précédent interrompu
            self.stopped_xfdesktop = True

    def _build(self):
        for s in self.screens:
            s.destroy()
        self.screens = []
        try:
            self.mtime = livewall.CONFIG.stat().st_mtime
        except OSError:
            self.mtime = None
        palette = live.find_palette(self.cfg["palette"])
        display = Gdk.Display.get_default()
        monitors = [display.get_monitor(i) for i in range(display.get_n_monitors())]
        if self.windowed:
            monitors = monitors[:1]
        for m in monitors:
            s = Screen(self, m.get_geometry(), m.get_scale_factor(), self.windowed)
            s.build(self.cfg, palette)
            self.screens.append(s)
        if self.timer:
            GLib.source_remove(self.timer)
        fps = int(self.cfg.get("fps") or 24)
        self.timer = GLib.timeout_add(max(15, int(1000 / fps)), self._tick)

    def _rebuild_later(self):
        GLib.timeout_add(800, lambda: (self._build(), False)[1])

    def _tick(self):
        t = time.monotonic() - self.t0
        for s in self.screens:
            s.tick(t)
        return True

    def _check(self):
        self.checks = getattr(self, "checks", 0) + 1
        # À l'ouverture de session, xfdesktop peut démarrer après nous et nous recouvrir
        if not self.windowed and (self.checks < 60 or self.checks % 10 == 0):
            self._stop_xfdesktop()
            if self.stopped_xfdesktop and not livewall.status().get("stopped_xfdesktop"):
                _write_status(ok=True, stopped_xfdesktop=True)
        try:
            mtime = livewall.CONFIG.stat().st_mtime
        except OSError:
            mtime = None
        if mtime != self.mtime:
            self.cfg = livewall.config()
            if not self.cfg.get("enabled") and not self.windowed:
                self.quit(disabled=True)
                return False
            self._build()
        self._update_pause()
        return True

    def _update_pause(self):
        if self.wnck is None or not self.cfg.get("pause_when_covered", True):
            return
        try:
            self.wnck.force_update()
            ws = self.wnck.get_active_workspace()
            wins = [w for w in self.wnck.get_windows_stacked()
                    if not w.is_minimized() and (ws is None or w.is_on_workspace(ws))
                    and w.get_window_type() == Wnck.WindowType.NORMAL]
        except Exception:  # noqa: BLE001
            return
        for s in self.screens:
            g = s.geo
            covered = False
            for w in wins:
                x, y, ww, hh = w.get_geometry()
                cx, cy = x + ww / 2, y + hh / 2
                if g.x <= cx < g.x + g.width and g.y <= cy < g.y + g.height and \
                        (w.is_maximized() or w.is_fullscreen() or (ww >= g.width * 0.95 and hh >= g.height * 0.9)):
                    covered = True
                    break
            s.paused = covered

    def menu(self, event):
        m = Gtk.Menu()
        items = [("Ouvrir BESTthemes", self._open_app),
                 ("Changer de fond animé…", self._open_app),
                 ("Arrêter le fond animé", self._disable)]
        for cmd in ("xfce4-popup-whiskermenu", "xfce4-appfinder"):
            if GLib.find_program_in_path(cmd):
                items.insert(0, ("Applications", lambda c=cmd: subprocess.Popen([c], start_new_session=True)))
                break
        for label, cb in items:
            it = Gtk.MenuItem(label=label)
            it.connect("activate", lambda _i, f=cb: f())
            m.append(it)
        m.show_all()
        m.popup_at_pointer(event)
        self._menu = m

    def _open_app(self):
        cmd, env = livewall.command()
        full = dict(os.environ, PYTHONPATH=env["PYTHONPATH"])
        subprocess.Popen([c for c in cmd if c != "--live"], env=full, start_new_session=True)

    def _disable(self):
        cfg = livewall.config()
        cfg["enabled"] = False
        livewall.save(cfg)
        livewall._write_autostart(False)
        self.quit(disabled=True)

    def quit(self, disabled=False, session_end=False):
        for s in self.screens:
            s.destroy()
        self.screens = []
        if not self.windowed:
            if session_end:
                # la session se ferme : on note juste qu'il faudra rendre le bureau plus tard
                _write_status(ok=False, stopped_xfdesktop=True)
            else:
                if disabled or self.stopped_xfdesktop:
                    livewall.start_xfdesktop()
                _write_status(ok=False, stopped_xfdesktop=False)
        Gtk.main_quit()
        return False


def main():
    windowed = "--window" in sys.argv
    paths.STATE_DIR.mkdir(parents=True, exist_ok=True)
    lock = open(paths.STATE_DIR / "live.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0  # un lecteur tourne déjà : il relira les nouveaux réglages
    if Gdk.Display.get_default() is None:
        return 1
    player = Player(windowed)
    try:
        if not player.start():
            return 0
    except Exception as e:  # noqa: BLE001
        _write_status(ok=False, error=f"Fond animé impossible : {e}")
        if player.stopped_xfdesktop:
            livewall.start_xfdesktop()
        return 1
    Gtk.main()
    return 0
