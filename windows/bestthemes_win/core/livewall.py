"""Fond d'écran animé (Windows) : réglages, démarrage/arrêt du lecteur, lancement à l'ouverture de session.

Le lecteur (`BESTthemes.exe --live`) tourne dans son propre processus pour continuer après la
fermeture de BESTthemes. Il se place derrière les icônes du bureau (comme Lively Wallpaper),
sans droits administrateur. Démarrage automatique : clé « Run » de l'utilisateur (HKCU).
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from bestthemes.core.livewall import DEFAULTS, FPS, KEYS, QUALITY, render_size  # noqa: F401 — réexportés

from .. import winplat as wp

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "BESTthemes fond anime"


def _config_file():
    return wp.DATA / "live.json"


def _status_file():
    return wp.DATA / "live-status.json"


def config():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(_config_file().read_text()))
    except (OSError, ValueError):
        pass
    return cfg


def save(cfg):
    f = _config_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=1))
    os.replace(tmp, f)


def status():
    try:
        return json.loads(_status_file().read_text())
    except (OSError, ValueError):
        return {}


def write_status(**kw):
    kw.update(pid=os.getpid(), time=time.time())
    wp.DATA.mkdir(parents=True, exist_ok=True)
    _status_file().write_text(json.dumps(kw))


# ---------------------------------------------------------------- processus


def _alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if wp.IS_WINDOWS:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def running():
    st = status()
    return bool(st.get("ok")) and _alive(st.get("pid"))


def command():
    """Commande qui lance le lecteur : l'exécutable lui-même, ou les sources en développement."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--live"]
    launcher = Path(__file__).resolve().parents[2] / "launcher.py"
    exe = sys.executable
    if wp.IS_WINDOWS and exe.lower().endswith("python.exe"):
        exe = exe[:-10] + "pythonw.exe"
    return [exe, str(launcher), "--live"]


def _spawn():
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
          "close_fds": True}
    if wp.IS_WINDOWS:
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000
    else:
        kw["start_new_session"] = True
    subprocess.Popen(command(), **kw)


def _autostart(on):
    if on:
        wp.reg_set(RUN_KEY, RUN_NAME, subprocess.list2cmdline(command()), wp.SZ)
    else:
        wp.reg_delete(RUN_KEY, RUN_NAME)


def start(scene=None, palette=None, fps=None, quality=None, wait=True):
    """Active le fond animé. Renvoie (ok, message d'erreur)."""
    cfg = config()
    for k, v in (("scene", scene), ("palette", palette), ("fps", fps), ("quality", quality)):
        if v is not None:
            cfg[k] = v
    cfg["enabled"] = True
    save(cfg)
    _autostart(True)
    if running():
        return True, ""  # le lecteur relit les réglages tout seul
    _status_file().unlink(missing_ok=True)
    _spawn()
    if not wait:
        return True, ""
    for _ in range(200):  # la version portable se décompresse d'abord : jusqu'à ~20 s
        time.sleep(0.1)
        st = status()
        if st.get("error"):
            return False, st["error"]
        if st.get("ok"):
            return True, ""
    return False, "Le fond animé n'a pas démarré à temps."


def stop():
    cfg = config()
    cfg["enabled"] = False
    save(cfg)
    _autostart(False)
    if running():
        for _ in range(40):  # le lecteur vérifie ses réglages chaque seconde
            time.sleep(0.1)
            if not running():
                break


def capture():
    cfg = config()
    return {k: cfg[k] for k in KEYS}


def restore(state):
    """Pour Annuler : remet le fond animé dans l'état enregistré (absent = désactivé)."""
    state = state or {"enabled": False}
    cur = capture()
    if not state.get("enabled"):
        if cur["enabled"] or running():
            stop()
        return
    if state != cur or not running():
        start(state.get("scene"), state.get("palette"), state.get("fps"), state.get("quality"), wait=False)
