"""Packs : un look complet (thème, icônes, curseur, panneau, dock, fond) en un clic."""
import json

from . import applier, backup, generator, panel, paths, plank, scanner, wallpaper

_FILE = paths.DATA_DIR / "packs.json"


def load():
    return json.loads(_FILE.read_text())["packs"]


def get(pack_id):
    return next((p for p in load() if p["id"] == pack_id), None)


def needs_download(pack):
    return any(isinstance(pack.get(k), dict) and "catalog" in pack[k]
               and not scanner.exists(_kind(k), pack[k].get("theme", ""))
               for k in ("gtk", "icons", "cursors", "plank"))


def _kind(key):
    return {"gtk": "gtk", "icons": "icons", "cursors": "cursors", "plank": "plank"}[key]


def _resolve_installed(kind, wanted, items):
    """Trouve le nom réel du thème installé (les archives ne respectent pas toujours le nom)."""
    if wanted and scanner.exists(kind, wanted):
        return wanted
    candidates = [i for i in items if kind in i[1]]
    if wanted:
        for name, _, _ in candidates:
            if name.lower() == wanted.lower():
                return name
        for name, _, _ in candidates:
            if wanted.lower() in name.lower():
                return name
    return candidates[0][0] if candidates else None


def _from_catalog(spec, kind, progress, cancel):
    from ..workshop import catalog
    item = catalog.get(spec["catalog"])
    if item is None:
        return None
    wanted = spec.get("theme")
    if wanted and scanner.exists(kind, wanted):
        return wanted
    items = item.installed_items()
    name = _resolve_installed(kind, wanted, items) if items else None
    if name and (not wanted or wanted.lower() in name.lower()):
        return name
    progress(f"Téléchargement de {item.name}…", None)
    items = item.install(spec.get("file"), progress=lambda f, _b: progress(None, f), cancel=cancel)
    return _resolve_installed(kind, wanted, items)


def _from_system(spec, kind):
    for name in spec.get("system", []):
        if scanner.exists(kind, name):
            return name
    return None


def resolve(spec, kind, progress, cancel):
    if spec is None:
        return None
    if isinstance(spec, str):
        return spec if scanner.exists(kind, spec) else None
    name = None
    if "catalog" in spec:
        name = _from_catalog(spec, kind, progress, cancel)
    if not name and "system" in spec:
        name = _from_system(spec, kind)
    return name


def apply(pack, progress=lambda text, frac: None, cancel=None):
    """Applique un pack. Peut être appelé depuis un thread. Renvoie la liste d'avertissements."""
    warnings = []
    changes = {}
    pal = None
    if pack.get("palette"):
        pal = generator.palette(pack["palette"])

    gtk = pack.get("gtk")
    if isinstance(gtk, dict) and "generate" in gtk:
        progress("Création du thème…", None)
        gp = generator.palette(gtk["generate"])
        res = generator.generate(gp, gtk.get("style", "macos"), plank=True)
        changes["gtk"] = res["gtk"]
        changes["xfwm4"] = res["xfwm4"]
        if pack.get("plank") == "generated":
            pack = {**pack, "plank": res["plank"]}
    else:
        name = resolve(gtk, "gtk", progress, cancel)
        if name:
            changes["gtk"] = name
            wm = pack.get("xfwm4") or name
            if scanner.exists("xfwm4", wm):
                changes["xfwm4"] = wm
        elif gtk:
            warnings.append("Le thème des fenêtres n'a pas pu être installé.")

    for key in ("icons", "cursors"):
        name = resolve(pack.get(key), key, progress, cancel)
        if name:
            changes[key] = name
        elif pack.get(key):
            warnings.append(f"{'Icônes' if key == 'icons' else 'Curseur'} non disponible(s).")
    if pack.get("cursor_size"):
        changes["cursor_size"] = pack["cursor_size"]

    if pack.get("wallpaper"):
        progress("Création du fond d'écran…", None)
        wp = pack["wallpaper"]
        wpal = generator.palette(wp.get("palette", pack.get("palette")))
        changes["wallpaper"] = str(wallpaper.generate(wpal, wp.get("style"), wp.get("seed")))
    if pack.get("button_layout"):
        changes["button_layout"] = pack["button_layout"]
    if "dark_panel" in pack:
        changes["dark_panel"] = pack["dark_panel"]
    if pack.get("font"):
        changes["font"] = pack["font"]

    progress("Application…", None)
    backup.snapshot(f"Pack : {pack['name']}")
    applier.apply(changes, snapshot=False)

    if pack.get("panel"):
        color = None
        if pal:
            from . import colors as C
            color = C.to_rgb(generator.derive(pal)["panel"])
        panel.apply_preset(pack["panel"], snapshot=False, panel_color=color)

    plank_theme = pack.get("plank")
    if plank_theme == "generated":  # seulement valable avec un thème généré
        plank_theme = None
    if plank_theme:
        if plank.installed():
            name = resolve(plank_theme, "plank", progress, cancel) if isinstance(plank_theme, dict) \
                else plank_theme
            if name:
                plank.set("theme", name)
        else:
            warnings.append("Le dock Plank n'est pas installé : installez-le depuis la page « Dock ».")
    return warnings
