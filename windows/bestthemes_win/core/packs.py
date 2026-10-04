"""Packs Windows : mode, accent, fond d'écran, curseurs, icônes, barre des tâches, effets."""
import json
from pathlib import Path

from bestthemes.core import colors as C
from bestthemes.core import generator as G

from . import appearance, backup, cursors, effects, icons, taskbar, wallgen, workshop

_FILE = Path(__file__).resolve().parent.parent / "data" / "packs_win.json"


def load():
    return json.loads(_FILE.read_text(encoding="utf-8"))["packs"]


def palette(pack):
    return G.palette(pack["palette"])


def needs_download(pack):
    return bool(pack.get("cursor") or pack.get("icons"))


def _pick(names, prefer):
    if not names:
        return None
    if prefer:
        exact = [n for n in names if n.lower() == prefer.lower()]
        if exact:
            return exact[0]
        part = [n for n in names if prefer.lower() in n.lower()]
        if part:
            # « Regular » plutôt que « Extra-Large » si plusieurs correspondent
            part.sort(key=lambda n: ("large" in n.lower(), len(n)))
            return part[0]
    return names[0]


def _ensure(spec, kind, progress, cancel):
    """Installe l'élément du Workshop si besoin. Renvoie le nom du thème à appliquer."""
    item = next((i for i in workshop.items() if i.id == spec["item"]), None)
    if item is None:
        return None
    have = ([c["name"] for c in cursors.installed()] if kind == "cursors"
            else [p["name"] for p in icons.installed()])
    names = [n for n in workshop.installed_names(item.id) if n in have]
    if not names:
        files = item.list_files()
        if not files:
            return None
        fname = spec.get("file") or item.default_file(files)
        choice = next(((n, u) for n, u in files if n == fname), None)
        if choice is None:
            choice = next(((n, u) for n, u in files if n == item.default_file(files)), files[0])
        progress(f"Téléchargement : {item.name}…", None)
        names = workshop.install(kind, choice[0], choice[1], item.id,
                                 progress=lambda f, _b: progress(None, f), cancel=cancel)
    return _pick(names, spec.get("prefer"))


def apply(pack, progress=lambda text, frac: None, cancel=None):
    """Applique un pack (appelable depuis un thread). Renvoie (avertissements, redémarrer_explorer)."""
    warnings = []
    pal = palette(pack)
    accent = pack.get("accent") or pal["accent"]

    cursor_name = icons_name = None
    if pack.get("cursor"):
        try:
            cursor_name = _ensure(pack["cursor"], "cursors", progress, cancel)
        except Exception as e:  # noqa: BLE001 — un téléchargement raté ne bloque pas le reste
            warnings.append(f"Curseurs non installés : {e}")
    if pack.get("icons"):
        try:
            progress("Préparation des icônes (conversion)…", None)
            icons_name = _ensure(pack["icons"], "icons", progress, cancel)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"Icônes non installées : {e}")

    wall = None
    if pack.get("wallpaper"):
        progress("Création du fond d'écran…", None)
        wpal = G.palette(pack["wallpaper"].get("palette", pack["palette"]))
        wall = wallgen.generate(wpal, pack["wallpaper"].get("style", "gradient"))

    progress("Application…", None)
    backup.snapshot(f"Pack : {pack['name']}")
    appearance.set_mode(apps_dark=pack.get("dark", True), system_dark=pack.get("dark", True))
    appearance.set_accent(accent, titlebars=pack.get("titlebars", False),
                          taskbar=pack.get("taskbar_accent", False))
    appearance.set_transparency(pack.get("transparency", True))
    if wall:
        appearance.set_wallpaper(wall)
    if cursor_name:
        theme = next((c for c in cursors.installed() if c["name"] == cursor_name), None)
        if theme:
            cursors.apply(theme)
    if icons_name:
        p = next((p for p in icons.installed() if p["name"] == icons_name), None)
        if p:
            icons.apply(p)
    if pack.get("effects"):
        effects.apply_preset(pack["effects"])
    restart = False
    if pack.get("taskbar"):
        before = {k: taskbar.get(k) for k in taskbar.OPTIONS} | {"autohide": taskbar.autohide()}
        taskbar.apply_preset(pack["taskbar"])
        after = {k: taskbar.get(k) for k in taskbar.OPTIONS} | {"autohide": taskbar.autohide()}
        restart = before != after
    return warnings, restart


def swatches(pack):
    pal = palette(pack)
    return [pal["bg"], pack.get("accent") or pal["accent"],
            pal.get("accent2") or C.rotate_hue(pal["accent"], 40)]
