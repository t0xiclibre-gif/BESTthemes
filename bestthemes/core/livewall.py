"""Fond d'écran animé (XFCE) : réglages, démarrage/arrêt du lecteur, lancement à l'ouverture de session.

Le lecteur (bestthemes/live_player.py) tourne dans son propre processus pour continuer après la
fermeture de BESTthemes. Le bureau XFCE (xfdesktop) ne peut rien afficher derrière ses icônes :
tant que le fond animé est actif, le lecteur remplace donc xfdesktop, et le relance à l'arrêt.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import paths

CONFIG = paths.STATE_DIR / "live.json"
STATUS = paths.STATE_DIR / "live-status.json"
AUTOSTART = Path(os.environ.get("XDG_CONFIG_HOME", paths.HOME / ".config")) / "autostart" / "bestthemes-live.desktop"

FPS = {15: "Économe (15 images/s)", 24: "Fluide (24 images/s)", 30: "Très fluide (30 images/s)"}
QUALITY = {"eco": ("Économe", 0.5, 960), "balanced": ("Équilibrée", 0.67, 1280), "max": ("Maximale", 1.0, 1920)}
DEFAULTS = {"enabled": False, "scene": "aurora", "palette": "nord", "fps": 24, "quality": "balanced",
            "pause_when_covered": True}
KEYS = ("enabled", "scene", "palette", "fps", "quality")


def config():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CONFIG.read_text()))
    except (OSError, ValueError):
        pass
    return cfg


def save(cfg):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=1))
    tmp.replace(CONFIG)


def status():
    try:
        return json.loads(STATUS.read_text())
    except (OSError, ValueError):
        return {}


def render_size(screen_w, screen_h, quality):
    """Taille de calcul des images : l'animation est agrandie à l'écran (économise le processeur)."""
    _label, scale, max_w = QUALITY.get(quality, QUALITY["balanced"])
    w = min(screen_w * scale, max_w)
    return max(160, int(w)), max(90, int(w * screen_h / max(1, screen_w)))


# ---------------------------------------------------------------- processus


def _alive(pid):
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError):
        return False
    try:
        cmd = Path(f"/proc/{int(pid)}/cmdline").read_bytes()
        return b"--live" in cmd
    except OSError:
        return True


def running():
    st = status()
    return bool(st.get("pid")) and _alive(st["pid"])


def command():
    """Commande qui lance le lecteur (paquet installé ou sources)."""
    root = str(paths.APP_DIR.parent)
    return [sys.executable, "-m", "bestthemes", "--live"], {"PYTHONPATH": root}


def _spawn():
    cmd, env = command()
    full_env = dict(os.environ)
    full_env["PYTHONPATH"] = env["PYTHONPATH"] + (":" + full_env["PYTHONPATH"] if full_env.get("PYTHONPATH") else "")
    subprocess.Popen(cmd, env=full_env, start_new_session=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)


def _write_autostart(on):
    if not on:
        AUTOSTART.unlink(missing_ok=True)
        return
    cmd, env = command()
    AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART.write_text(
        "[Desktop Entry]\nType=Application\nName=BESTthemes — fond d'écran animé\n"
        f"Exec=env PYTHONPATH={env['PYTHONPATH']} {' '.join(cmd)}\n"
        "Icon=bestthemes\nX-GNOME-Autostart-enabled=true\nNoDisplay=true\n")


def start_xfdesktop():
    """Relance le bureau XFCE (icônes, clic droit) s'il ne tourne pas."""
    try:
        if subprocess.run(["pgrep", "-x", "xfdesktop"], stdout=subprocess.DEVNULL).returncode != 0:
            subprocess.Popen(["xfdesktop"], start_new_session=True, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    except OSError:
        pass


def ensure_desktop(force=False):
    """Après l'arrêt du fond animé : rend le bureau XFCE s'il avait été remplacé.
    force=True quand le lecteur tournait : la session XFCE a pu être enregistrée sans
    xfdesktop pendant ce temps, il faut alors le relancer même sans l'avoir arrêté nous-mêmes."""
    st = status()
    if not (force or st.get("stopped_xfdesktop")):
        return
    start_xfdesktop()
    if STATUS.exists():
        st["stopped_xfdesktop"] = False
        STATUS.write_text(json.dumps(st))


def start(scene=None, palette=None, fps=None, quality=None, wait=True):
    """Active le fond animé. Renvoie (ok, message d'erreur)."""
    cfg = config()
    for k, v in (("scene", scene), ("palette", palette), ("fps", fps), ("quality", quality)):
        if v is not None:
            cfg[k] = v
    cfg["enabled"] = True
    save(cfg)
    _write_autostart(True)
    if running():
        return True, ""  # le lecteur relit les réglages tout seul
    STATUS.unlink(missing_ok=True)
    _spawn()
    if not wait:
        return True, ""
    for _ in range(60):
        time.sleep(0.1)
        st = status()
        if st.get("error"):
            return False, st["error"]
        if st.get("ok"):
            return True, ""
    return False, "Le fond animé n'a pas démarré."


def stop():
    cfg = config()
    cfg["enabled"] = False
    save(cfg)
    _write_autostart(False)
    was_running = running()
    if was_running:
        for _ in range(40):  # le lecteur vérifie ses réglages chaque seconde
            time.sleep(0.1)
            if not running():
                break
        else:
            try:
                os.kill(int(status()["pid"]), 15)
            except (OSError, KeyError, ValueError):
                pass
            time.sleep(0.5)
    ensure_desktop(force=was_running)


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
