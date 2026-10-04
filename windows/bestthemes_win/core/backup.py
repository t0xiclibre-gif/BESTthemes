"""Instantanés : toute modification faite par BESTthemes peut être annulée."""
import json
import time

from .. import winplat as wp
from . import appearance, cursors, effects, icons, livewall, taskbar

MAX = 40


def _dir():
    d = wp.DATA / "Snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _tracked():
    out = []
    for m in (appearance, cursors, effects, taskbar, icons):
        out.extend(m.TRACKED)
    return out


def capture():
    reg = {}
    for path, name in _tracked():
        r = wp.reg_get(path, name)
        reg[f"{path}|{name}"] = list(r) if r else None
    return {"registry": reg, "effects": effects.capture(), "icons": icons.capture(),
            "taskbar": taskbar.capture(), "live": livewall.capture(), "time": time.time()}


def _registry_diff(state):
    changed = set()
    for key, val in state.get("registry", {}).items():
        path, name = key.split("|", 1)
        cur = wp.reg_get(path, name)
        cur = list(cur) if cur else None
        if cur != val:
            changed.add(path)
            if val is None:
                wp.reg_delete(path, name)
            else:
                wp.reg_set(path, name, val[0], val[1])
    return changed


def restore(state):
    changed = _registry_diff(state)
    effects.restore(state.get("effects"))
    icons.restore(state.get("icons"))
    menu_changed = taskbar.restore(state.get("taskbar"))
    if any(p.startswith(r"Control Panel\Cursors") or p == cursors.ACCESS for p in changed):
        cursors.reload()
    appearance.reload()
    # absent (ancien instantané, état d'origine) = pas de fond animé
    livewall.restore(state.get("live"))
    if menu_changed or changed & {t[0] for t in taskbar.TRACKED}:
        taskbar.reload()


def snapshot(label):
    state = capture()
    state["label"] = label
    name = f"snap-{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time() * 1000) % 1000:03d}.json"
    (_dir() / name).write_text(json.dumps(state, indent=1))
    snaps = sorted(_dir().glob("snap-*.json"))
    for old in snaps[:-MAX]:
        old.unlink(missing_ok=True)


def last_label():
    snaps = sorted(_dir().glob("snap-*.json"))
    if not snaps:
        return None
    try:
        return json.loads(snaps[-1].read_text()).get("label")
    except (OSError, ValueError):
        return None


def undo():
    snaps = sorted(_dir().glob("snap-*.json"))
    if not snaps:
        return None
    state = json.loads(snaps[-1].read_text())
    restore(state)
    snaps[-1].unlink(missing_ok=True)
    return state.get("label", "")


def save_original_once():
    f = wp.DATA / "original.json"
    if not f.exists():
        wp.DATA.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(capture(), indent=1))


def has_original():
    return (wp.DATA / "original.json").exists()


def restore_original():
    f = wp.DATA / "original.json"
    if not f.exists():
        return False
    snapshot("Avant restauration d'origine")
    restore(json.loads(f.read_text()))
    icons.restore_folders()
    return True
