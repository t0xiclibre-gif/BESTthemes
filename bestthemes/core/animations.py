"""Animations des fenêtres (ouverture, fermeture, réduction) via Compiz.

xfwm4, le gestionnaire de fenêtres d'XFCE, ne sait pas animer les fenêtres.
Pour les animations façon macOS (lampe magique, zoom…), BESTthemes remplace
xfwm4 par Compiz, déjà fourni avec Linux Mint, et sait revenir en arrière.
"""
import os
import shutil
import subprocess
from pathlib import Path

from . import paths

AUTOSTART = Path.home() / ".config/autostart/bestthemes-compiz.desktop"
LAUNCHER = paths.STATE_DIR / "start-compiz.sh"
WM_SCHEMA = "org.gnome.desktop.wm.preferences"
GWD_SCHEMA = "org.compiz.gwd"

# Plugins indispensables pour un bureau utilisable sous Compiz
REQUIRED_PLUGINS = ["composite", "opengl", "decor", "move", "resize", "place", "mousepoll",
                    "animation", "switcher", "grid", "snap", "session", "workarounds",
                    "imgpng", "regex"]

EFFECTS = {
    "None": "Aucune",
    "Zoom": "Zoom",
    "Magic Lamp": "Lampe magique (macOS)",
    "Magic Lamp Wavy": "Lampe magique ondulée",
    "Glide 1": "Glissement",
    "Glide 2": "Glissement doux",
    "Fade": "Fondu",
    "Sidekick": "Tourbillon",
    "Curved Fold": "Pliage",
    "Horizontal Folds": "Pliage en accordéon",
    "Dream": "Rêve",
    "Wave": "Vague",
}

PRESETS = [
    {"id": "macos", "name": "macOS",
     "desc": "Les fenêtres s'ouvrent en zoom et se réduisent dans la barre avec l'effet lampe magique.",
     "open": "Zoom", "close": "Zoom", "minimize": "Magic Lamp", "duration": 220, "wobbly": False},
    {"id": "soft", "name": "Douceur",
     "desc": "Glissement léger et fondu, discret et élégant.",
     "open": "Glide 2", "close": "Fade", "minimize": "Zoom", "duration": 180, "wobbly": False},
    {"id": "fun", "name": "Fun",
     "desc": "Pliages, effet rêve, lampe ondulée et fenêtres élastiques quand on les déplace.",
     "open": "Curved Fold", "close": "Dream", "minimize": "Magic Lamp Wavy", "duration": 320,
     "wobbly": True},
    {"id": "fast", "name": "Rapide",
     "desc": "Un simple fondu très court, pour les ordinateurs modestes.",
     "open": "Fade", "close": "Fade", "minimize": "Fade", "duration": 110, "wobbly": False},
]


# ---------------------------------------------------------------- disponibilité


def compiz_installed():
    return shutil.which("compiz") is not None and shutil.which("gtk-window-decorator") is not None


def compizconfig_available():
    import importlib.util
    return importlib.util.find_spec("compizconfig") is not None


def available():
    return compiz_installed() and compizconfig_available()


def install(packages=("compiz", "compiz-plugins", "compiz-gnome", "python3-compizconfig")):
    """Installe Compiz avec une demande de mot de passe graphique."""
    cmd = ["pkexec", "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y", *packages]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    if r.returncode == 0:
        return True, ""
    if r.returncode in (126, 127):
        return False, "Installation annulée."
    return False, (r.stderr or r.stdout).strip()[-400:]


def running():
    try:
        return subprocess.run(["pgrep", "-x", "compiz"], capture_output=True).returncode == 0
    except OSError:
        return False


def enabled():
    """Vrai si les animations sont actives (ou programmées au démarrage)."""
    return running() or AUTOSTART.is_file()


# ---------------------------------------------------------------- réglages Compiz


def _context():
    import compizconfig
    return compizconfig.Context()


def read_settings():
    """Renvoie {open, close, minimize, duration, wobbly} depuis la config Compiz."""
    ctx = _context()
    an = ctx.Plugins["animation"].Screen

    def first(key):
        v = an[key].Value
        return v[0].split(":", 1)[-1] if v else "None"

    durs = an["open_durations"].Value or [200]
    return {
        "open": first("open_effects"),
        "close": first("close_effects"),
        "minimize": first("minimize_effects"),
        "duration": int(durs[0]),
        "wobbly": bool(ctx.Plugins["wobbly"].Enabled) if "wobbly" in ctx.Plugins else False,
    }


def write_settings(open_fx, close_fx, minimize_fx, duration, wobbly=False):
    """Écrit les effets dans le profil Compiz actuel (gsettings)."""
    ctx = _context()
    for name in REQUIRED_PLUGINS:
        if name in ctx.Plugins:
            ctx.Plugins[name].Enabled = True
    if "wobbly" in ctx.Plugins:
        ctx.Plugins["wobbly"].Enabled = bool(wobbly)
    an = ctx.Plugins["animation"].Screen

    # La 1re règle concerne les fenêtres normales ; on garde les suivantes (menus, bulles)
    def set_first(effects_key, durations_key, effect, dur):
        effects = list(an[effects_key].Value) or ["animation:None"]
        durations = list(an[durations_key].Value) or [dur]
        effects[0] = f"animation:{effect}"
        durations[0] = int(dur)
        if len(durations) < len(effects):
            durations += [durations[-1]] * (len(effects) - len(durations))
        an[effects_key].Value = effects
        an[durations_key].Value = durations

    set_first("open_effects", "open_durations", open_fx, duration)
    set_first("close_effects", "close_durations", close_fx, duration)
    lamp = int(duration * (1.6 if "Lamp" in minimize_fx else 1.0))
    set_first("minimize_effects", "minimize_durations", minimize_fx, lamp)
    set_first("unminimize_effects", "unminimize_durations", minimize_fx, lamp)
    ctx.Write()


# ---------------------------------------------------------------- bordures sous Compiz


def _gs(*args):
    if not shutil.which("gsettings"):
        return None
    try:
        r = subprocess.run(["gsettings", *args], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def sync_decorations(gtk_theme, xfwm_layout=None):
    """Sous Compiz, les bordures sont dessinées d'après le thème Metacity du thème GTK."""
    if not compiz_installed() or not gtk_theme:
        return
    has_metacity = any((d / gtk_theme / "metacity-1").is_dir() for d in paths.THEME_DIRS)
    if has_metacity:
        _gs("set", WM_SCHEMA, "theme", gtk_theme)
    _gs("set", GWD_SCHEMA, "use-metacity-theme", "true" if has_metacity else "false")
    if xfwm_layout:
        _gs("set", WM_SCHEMA, "button-layout", xfwm_to_gnome_layout(xfwm_layout))


def xfwm_to_gnome_layout(layout):
    names = {"O": "menu", "H": "minimize", "M": "maximize", "C": "close", "S": "shade",
             "T": "stick"}
    left, _, right = layout.partition("|")
    conv = lambda part: ",".join(names[c] for c in part if c in names)  # noqa: E731
    return f"{conv(left)}:{conv(right)}"


# ---------------------------------------------------------------- bascule xfwm4 <-> Compiz

LAUNCHER_SCRIPT = """#!/bin/sh
# Lancé par BESTthemes : remplace xfwm4 par Compiz pour avoir les animations.
# Si Compiz plante dans les 20 premières secondes, on revient à xfwm4.
start=$(date +%s)
compiz --replace ccp
code=$?
end=$(date +%s)
if [ $((end - start)) -lt 20 ] && ! pgrep -x xfwm4 >/dev/null; then
    xfwm4 --replace &
fi
exit $code
"""

AUTOSTART_CONTENT = """[Desktop Entry]
Type=Application
Name=Animations des fenêtres (BESTthemes)
Comment=Lance Compiz pour animer les fenêtres
Exec=sh "{launcher}"
X-GNOME-Autostart-enabled=true
OnlyShowIn=XFCE;
Hidden=false
"""


def _write_launcher():
    LAUNCHER.parent.mkdir(parents=True, exist_ok=True)
    LAUNCHER.write_text(LAUNCHER_SCRIPT)
    LAUNCHER.chmod(0o755)


def start_compiz():
    """Active Compiz maintenant et au prochain démarrage."""
    _write_launcher()
    AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART.write_text(AUTOSTART_CONTENT.format(launcher=LAUNCHER))
    if not running():
        subprocess.Popen(["sh", str(LAUNCHER)], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True,
                         env={**os.environ})


def stop_compiz():
    """Revient à xfwm4 (sans animations)."""
    if AUTOSTART.exists():
        AUTOSTART.unlink()
    if running() or not _xfwm4_running():
        subprocess.Popen(["xfwm4", "--replace"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)


def _xfwm4_running():
    try:
        return subprocess.run(["pgrep", "-x", "xfwm4"], capture_output=True).returncode == 0
    except OSError:
        return False


def apply_preset(preset):
    if isinstance(preset, str):
        preset = next(p for p in PRESETS if p["id"] == preset)
    write_settings(preset["open"], preset["close"], preset["minimize"], preset["duration"],
                   preset.get("wobbly", False))


# ---------------------------------------------------------------- sauvegarde / annulation


def capture():
    if not available():
        return None
    state = {"enabled": enabled(),
             "wm_theme": _gs("get", WM_SCHEMA, "theme"),
             "use_metacity": _gs("get", GWD_SCHEMA, "use-metacity-theme"),
             "button_layout": _gs("get", WM_SCHEMA, "button-layout")}
    try:
        state["settings"] = read_settings()
    except Exception:  # noqa: BLE001 — config Compiz illisible : on n'empêche pas la sauvegarde
        state["settings"] = None
    return state


def restore(state):
    if not state or not available():
        return
    for schema, key, val in ((WM_SCHEMA, "theme", state.get("wm_theme")),
                             (GWD_SCHEMA, "use-metacity-theme", state.get("use_metacity")),
                             (WM_SCHEMA, "button-layout", state.get("button_layout"))):
        if val is not None:
            _gs("set", schema, key, val)
    s = state.get("settings")
    if s:
        write_settings(s["open"], s["close"], s["minimize"], s["duration"], s["wobbly"])
    if state.get("enabled") and not enabled():
        start_compiz()
    elif not state.get("enabled") and enabled():
        stop_compiz()
