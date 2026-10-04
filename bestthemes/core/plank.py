"""Gestion du dock Plank (installation, démarrage auto, réglages, thèmes)."""
import shutil
import subprocess
from pathlib import Path

SCHEMA = "net.launchpad.plank.dock.settings:/net/launchpad/plank/docks/dock1/"
AUTOSTART = Path.home() / ".config/autostart/plank.desktop"
KEYS = ["theme", "position", "icon-size", "zoom-enabled", "zoom-percent", "hide-mode", "alignment"]

AUTOSTART_CONTENT = """[Desktop Entry]
Type=Application
Name=Plank
Comment=Dock (géré par BESTthemes)
Exec=plank
Icon=plank
X-GNOME-Autostart-enabled=true
Hidden=false
"""


def installed():
    return shutil.which("plank") is not None


def install(callback=None):
    """Installe Plank avec une demande de mot de passe graphique (pkexec)."""
    cmd = ["pkexec", "env", "DEBIAN_FRONTEND=noninteractive",
           "apt-get", "install", "-y", "plank"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    if r.returncode == 0:
        return True, ""
    if r.returncode in (126, 127):
        return False, "Installation annulée."
    return False, (r.stderr or r.stdout).strip()[-400:]


def running():
    try:
        return subprocess.run(["pgrep", "-x", "plank"], capture_output=True).returncode == 0
    except OSError:
        return False


def start():
    if installed() and not running():
        subprocess.Popen(["plank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)


def stop():
    subprocess.run(["pkill", "-x", "plank"], capture_output=True)


def autostart_enabled():
    if not AUTOSTART.is_file():
        return False
    text = AUTOSTART.read_text(errors="replace")
    return "Hidden=true" not in text and "X-GNOME-Autostart-enabled=false" not in text


def set_autostart(enabled):
    if enabled:
        AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
        AUTOSTART.write_text(AUTOSTART_CONTENT)
    elif AUTOSTART.exists():
        AUTOSTART.unlink()


def enable(on=True):
    set_autostart(on)
    if on:
        start()
    else:
        stop()


def _gs(*args):
    if not shutil.which("gsettings"):
        return None
    try:
        r = subprocess.run(["gsettings", *args], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def get(key):
    v = _gs("get", SCHEMA, key)
    if v is None:
        return None
    return v.strip("'")


def set(key, value):
    if isinstance(value, bool):
        value = "true" if value else "false"
    return _gs("set", SCHEMA, key, str(value)) is not None


def capture():
    if not installed():
        return None
    return {"settings": {k: get(k) for k in KEYS}, "running": running(),
            "autostart": autostart_enabled()}


def restore(state):
    if not installed() or not state:
        return
    for k, v in state.get("settings", {}).items():
        if v is not None:
            set(k, v)
    set_autostart(state.get("autostart", False))
    if state.get("running"):
        start()
    else:
        stop()
