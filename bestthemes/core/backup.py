"""Instantanés de l'apparence du bureau : tout ce que fait BESTthemes est annulable."""
import json
import time

from . import animations, livewall, paths, plank, xfconf

MAX_SNAPSHOTS = 40

XSETTINGS_KEYS = ["/Net/ThemeName", "/Net/IconThemeName", "/Gtk/CursorThemeName",
                  "/Gtk/CursorThemeSize", "/Gtk/FontName", "/Gtk/DecorationLayout"]
XFWM4_KEYS = ["/general/theme", "/general/button_layout", "/general/title_alignment",
              "/general/title_font"]
PANEL_KEYS = ["position", "size", "length", "background-style", "background-alpha",
              "background-rgba", "icon-size", "mode", "autohide-behavior",
              "position-locked", "enter-opacity", "leave-opacity", "nrows"]
CURSOR_DEFAULT = paths.USER_ICONS / "default" / "index.theme"


def _panel_ids():
    ids = xfconf.get("xfce4-panel", "/panels")
    if isinstance(ids, list):
        return [i.strip() for i in ids if i.strip()]
    return []


def capture():
    state = {"xsettings": {}, "xfwm4": {}, "panels": {}, "desktop": {}, "time": time.time()}
    for k in XSETTINGS_KEYS:
        state["xsettings"][k] = xfconf.get("xsettings", k)
    for k in XFWM4_KEYS:
        state["xfwm4"][k] = xfconf.get("xfwm4", k)
    for pid in _panel_ids():
        # None = propriété absente : elle sera supprimée lors de la restauration
        state["panels"][pid] = {k: xfconf.get("xfce4-panel", f"/panels/panel-{pid}/{k}")
                                for k in PANEL_KEYS}
    state["dark_mode"] = xfconf.get("xfce4-panel", "/panels/dark-mode")
    for prop, val in xfconf.list_values("xfce4-desktop", "/backdrop").items():
        if prop.endswith("/last-image") or prop.endswith("/image-style"):
            state["desktop"][prop] = val
    state["cursor_default"] = CURSOR_DEFAULT.read_text() if CURSOR_DEFAULT.is_file() else None
    state["plank"] = plank.capture()
    state["animations"] = animations.capture()
    state["live"] = livewall.capture()
    return state


def _restore_value(channel, prop, value):
    """La propriété existe en général déjà : xfconf conserve alors son type."""
    if value is None:
        return
    low = str(value).lower()
    if low in ("true", "false"):
        xfconf.set(channel, prop, low == "true")
        return
    try:
        xfconf.set(channel, prop, int(value), "uint" if channel == "xfce4-panel" else "int")
        return
    except ValueError:
        pass
    xfconf.set(channel, prop, str(value))


def restore(state):
    for k, v in state.get("xsettings", {}).items():
        _restore_value("xsettings", k, v)
    for k, v in state.get("xfwm4", {}).items():
        _restore_value("xfwm4", k, v)
    for pid, vals in state.get("panels", {}).items():
        for k, v in vals.items():
            prop = f"/panels/panel-{pid}/{k}"
            if v is None:
                xfconf.reset("xfce4-panel", prop)
            elif isinstance(v, list):
                xfconf.set_array("xfce4-panel", prop, [float(x) for x in v])
            else:
                _restore_value("xfce4-panel", prop, v)
    if state.get("dark_mode") is None:
        xfconf.reset("xfce4-panel", "/panels/dark-mode")
    else:
        _restore_value("xfce4-panel", "/panels/dark-mode", state["dark_mode"])
    for prop, v in state.get("desktop", {}).items():
        _restore_value("xfce4-desktop", prop, v)
    content = state.get("cursor_default")
    if content is None:
        if CURSOR_DEFAULT.is_file():
            CURSOR_DEFAULT.unlink()
    else:
        CURSOR_DEFAULT.parent.mkdir(parents=True, exist_ok=True)
        CURSOR_DEFAULT.write_text(content)
    if state.get("plank"):
        plank.restore(state["plank"])
    if state.get("animations"):
        animations.restore(state["animations"])
    # absent (ancien instantané, état d'origine) = pas de fond animé
    livewall.restore(state.get("live"))


def _snapshots():
    paths.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(paths.SNAPSHOT_DIR.glob("snap-*.json"))


def snapshot(label):
    """Enregistre l'état actuel avant une modification."""
    state = capture()
    state["label"] = label
    name = f"snap-{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time() * 1000) % 1000:03d}.json"
    paths.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    (paths.SNAPSHOT_DIR / name).write_text(json.dumps(state, indent=1))
    snaps = _snapshots()
    for old in snaps[:-MAX_SNAPSHOTS]:
        old.unlink(missing_ok=True)
    return name


def can_undo():
    return bool(_snapshots())


def last_label():
    snaps = _snapshots()
    if not snaps:
        return None
    try:
        return json.loads(snaps[-1].read_text()).get("label")
    except (OSError, ValueError):
        return None


def undo():
    """Restaure le dernier instantané et le supprime. Renvoie son libellé."""
    snaps = _snapshots()
    if not snaps:
        return None
    f = snaps[-1]
    state = json.loads(f.read_text())
    restore(state)
    f.unlink(missing_ok=True)
    return state.get("label", "")


ORIGINAL_FILE = "original.json"


def save_original_once():
    """Sauvegarde l'apparence du bureau au tout premier lancement."""
    f = paths.STATE_DIR / ORIGINAL_FILE
    if not f.exists():
        paths.STATE_DIR.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(capture(), indent=1))


def has_original():
    return (paths.STATE_DIR / ORIGINAL_FILE).exists()


def restore_original():
    f = paths.STATE_DIR / ORIGINAL_FILE
    if not f.exists():
        return False
    snapshot("Avant restauration d'origine")
    restore(json.loads(f.read_text()))
    return True
