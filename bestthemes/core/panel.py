"""Réglages du panneau XFCE (position, taille, transparence) et préréglages."""
from . import backup, plank, xfconf

CH = "xfce4-panel"

# Positions « aimantées » d'xfce4-panel (champ p= de la propriété position)
POSITIONS = {
    "bottom": "p=10;x=0;y=0",
    "top": "p=6;x=0;y=0",
    "left": "p=7;x=0;y=0",
    "right": "p=3;x=0;y=0",
}
POSITION_LABELS = {"bottom": "En bas", "top": "En haut", "left": "À gauche", "right": "À droite"}

PRESETS = [
    {
        "id": "windows", "name": "Windows",
        "desc": "Grande barre en bas avec les fenêtres ouvertes, comme Windows 10/11.",
        "position": "bottom", "size": 44, "length": 100, "icon_size": 24, "mode": 0,
        "opacity": 1.0, "autohide": 0, "plank": False,
    },
    {
        "id": "macos", "name": "macOS",
        "desc": "Barre fine en haut + dock Plank centré en bas.",
        "position": "top", "size": 28, "length": 100, "icon_size": 16, "mode": 0,
        "opacity": 0.85, "autohide": 0, "plank": True, "plank_position": "bottom",
    },
    {
        "id": "ubuntu", "name": "Ubuntu",
        "desc": "Barre verticale à gauche avec de grandes icônes.",
        "position": "left", "size": 56, "length": 100, "icon_size": 32, "mode": 2,
        "opacity": 1.0, "autohide": 0, "plank": False,
    },
    {
        "id": "gnome", "name": "GNOME",
        "desc": "Barre fine en haut, dock qui se cache automatiquement.",
        "position": "top", "size": 30, "length": 100, "icon_size": 16, "mode": 0,
        "opacity": 1.0, "autohide": 0, "plank": True, "plank_position": "bottom",
        "plank_hide": "intelligent",
    },
    {
        "id": "chromeos", "name": "ChromeOS",
        "desc": "Étagère en bas, icônes moyennes, légèrement transparente.",
        "position": "bottom", "size": 48, "length": 100, "icon_size": 32, "mode": 0,
        "opacity": 0.9, "autohide": 0, "plank": False,
    },
    {
        "id": "minimal", "name": "Minimal",
        "desc": "Barre courte centrée en bas, discrète.",
        "position": "bottom", "size": 38, "length": 60, "icon_size": 22, "mode": 0,
        "opacity": 0.75, "autohide": 0, "plank": False,
    },
    {
        "id": "focus", "name": "Plein écran",
        "desc": "La barre se cache et réapparaît quand la souris touche le bas.",
        "position": "bottom", "size": 40, "length": 100, "icon_size": 24, "mode": 0,
        "opacity": 1.0, "autohide": 2, "plank": False,
    },
    {
        "id": "mint", "name": "Mint d'origine",
        "desc": "Le réglage par défaut de Linux Mint XFCE.",
        "position": "bottom", "size": 32, "length": 100, "icon_size": 0, "mode": 0,
        "opacity": 1.0, "autohide": 0, "plank": False,
    },
]


def panel_ids():
    ids = xfconf.get(CH, "/panels")
    if isinstance(ids, list):
        return [i.strip() for i in ids if i.strip()]
    return []


def main_panel():
    ids = panel_ids()
    return ids[0] if ids else "1"


def _p(pid, key):
    return f"/panels/panel-{pid}/{key}"


def read(pid=None):
    pid = pid or main_panel()
    pos = xfconf.get(CH, _p(pid, "position"), "") or ""
    position = next((k for k, v in POSITIONS.items() if pos.startswith(v.split(";")[0] + ";")),
                    "bottom")
    rgba = xfconf.get(CH, _p(pid, "background-rgba"))
    opacity = 1.0
    if xfconf.get_int(CH, _p(pid, "background-style"), 0) == 1 and isinstance(rgba, list) and len(rgba) == 4:
        try:
            opacity = float(rgba[3])
        except ValueError:
            pass
    return {
        "position": position,
        "size": xfconf.get_int(CH, _p(pid, "size"), 32),
        "length": xfconf.get_int(CH, _p(pid, "length"), 100),
        "icon_size": xfconf.get_int(CH, _p(pid, "icon-size"), 0),
        "mode": xfconf.get_int(CH, _p(pid, "mode"), 0),
        "autohide": xfconf.get_int(CH, _p(pid, "autohide-behavior"), 0),
        "opacity": opacity,
        "dark": xfconf.get_bool(CH, "/panels/dark-mode", False),
    }


def set_position(position, pid=None, mode=None):
    pid = pid or main_panel()
    if mode is None:
        mode = 2 if position in ("left", "right") else 0
    xfconf.set(CH, _p(pid, "mode"), int(mode), "uint")
    xfconf.set(CH, _p(pid, "position"), POSITIONS[position])
    xfconf.set(CH, _p(pid, "position-locked"), True)


def set_size(size, pid=None):
    xfconf.set(CH, _p(pid or main_panel(), "size"), int(size), "uint")


def set_length(length, pid=None):
    xfconf.set(CH, _p(pid or main_panel(), "length"), int(length), "uint")


def set_icon_size(size, pid=None):
    xfconf.set(CH, _p(pid or main_panel(), "icon-size"), int(size), "uint")


def set_autohide(mode, pid=None):
    xfconf.set(CH, _p(pid or main_panel(), "autohide-behavior"), int(mode), "uint")


def set_opacity(opacity, color=None, pid=None):
    """Opacité du fond (1.0 = opaque, utilise alors la couleur du thème)."""
    pid = pid or main_panel()
    if opacity >= 0.999 and not color:
        xfconf.set(CH, _p(pid, "background-style"), 0, "uint")
        return
    if color is None:
        color = (0.12, 0.12, 0.14)
    xfconf.set(CH, _p(pid, "background-style"), 1, "uint")
    xfconf.set_array(CH, _p(pid, "background-rgba"), [*color[:3], float(opacity)])


def set_dark(dark):
    xfconf.set(CH, "/panels/dark-mode", bool(dark))


def apply_preset(preset, snapshot=True, panel_color=None):
    if isinstance(preset, str):
        preset = next(p for p in PRESETS if p["id"] == preset)
    if snapshot:
        backup.snapshot(f"Préréglage du panneau : {preset['name']}")
    pid = main_panel()
    set_position(preset["position"], pid, preset.get("mode"))
    set_size(preset["size"], pid)
    set_length(preset["length"], pid)
    set_icon_size(preset["icon_size"], pid)
    set_autohide(preset.get("autohide", 0), pid)
    set_opacity(preset.get("opacity", 1.0), panel_color, pid)
    if preset.get("plank") and plank.installed():
        plank.set("position", preset.get("plank_position", "bottom"))
        plank.set("hide-mode", preset.get("plank_hide", "window-dodge"))
        plank.enable(True)
    elif not preset.get("plank") and plank.installed() and plank.running():
        plank.enable(False)
