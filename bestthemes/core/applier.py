"""Application des réglages d'apparence sur XFCE."""
from pathlib import Path

from . import animations, backup, paths, scanner, settings, xfconf

BUTTON_LAYOUTS = {
    "macos": "CHM|",
    "windows": "O|HMC",
    "minimal": "O|C",
    "elementary": "C|M",
}


def current():
    return {
        "gtk": xfconf.get("xsettings", "/Net/ThemeName", ""),
        "xfwm4": xfconf.get("xfwm4", "/general/theme", ""),
        "icons": xfconf.get("xsettings", "/Net/IconThemeName", ""),
        "cursors": xfconf.get("xsettings", "/Gtk/CursorThemeName", ""),
        "cursor_size": xfconf.get_int("xsettings", "/Gtk/CursorThemeSize", 24),
        "font": xfconf.get("xsettings", "/Gtk/FontName", ""),
        "wallpaper": current_wallpaper(),
        "button_layout": xfconf.get("xfwm4", "/general/button_layout", ""),
    }


def _set_gtk(name):
    xfconf.set("xsettings", "/Net/ThemeName", name)
    animations.sync_decorations(name)  # bordures quand Compiz est actif
    if settings.get("sync_wm_with_gtk"):
        t = scanner.find("xfwm4", name)
        if t:
            _set_xfwm4(name)


def _set_xfwm4(name):
    xfconf.set("xfwm4", "/general/theme", name)


def _set_icons(name):
    xfconf.set("xsettings", "/Net/IconThemeName", name)


def _set_cursor(name, size=None):
    xfconf.set("xsettings", "/Gtk/CursorThemeName", name)
    if size:
        xfconf.set("xsettings", "/Gtk/CursorThemeSize", int(size))
    # Pour le bureau et les applis non-GTK (fond d'écran, Qt, Xorg)
    f = paths.USER_ICONS / "default" / "index.theme"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"[Icon Theme]\nName=Default\nComment=Géré par BESTthemes\nInherits={name}\n")


def _wallpaper_props():
    return [p for p in xfconf.list_props("xfce4-desktop", "/backdrop") if p.endswith("/last-image")]


def current_wallpaper():
    props = _wallpaper_props()
    for p in props:
        if "workspace0" in p:
            return xfconf.get("xfce4-desktop", p, "")
    return xfconf.get("xfce4-desktop", props[0], "") if props else ""


def _set_wallpaper(path):
    from . import livewall  # un fond animé cacherait le nouveau fond fixe
    if livewall.config()["enabled"]:
        livewall.stop()
    path = str(Path(path).resolve())
    props = _wallpaper_props() or ["/backdrop/screen0/monitor0/workspace0/last-image"]
    for p in props:
        xfconf.set("xfce4-desktop", p, path)
        xfconf.set("xfce4-desktop", p.replace("/last-image", "/image-style"), 5, "int")


def _set_font(font):
    xfconf.set("xsettings", "/Gtk/FontName", font)


def _set_button_layout(layout):
    layout = BUTTON_LAYOUTS.get(layout, layout)
    xfconf.set("xfwm4", "/general/button_layout", layout)
    animations.sync_decorations(xfconf.get("xsettings", "/Net/ThemeName", ""), layout)


def _set_dark_panel(dark):
    xfconf.set("xfce4-panel", "/panels/dark-mode", bool(dark))


_SETTERS = {
    "gtk": _set_gtk,
    "xfwm4": _set_xfwm4,
    "icons": _set_icons,
    "wallpaper": _set_wallpaper,
    "font": _set_font,
    "button_layout": _set_button_layout,
    "dark_panel": _set_dark_panel,
}

ORDER = ["gtk", "xfwm4", "icons", "cursors", "wallpaper", "font", "button_layout", "dark_panel"]


def apply(changes, label="Modification", snapshot=True):
    """Applique un dict de changements, avec un seul instantané pour pouvoir annuler."""
    if snapshot:
        backup.snapshot(label)
    for key in ORDER:
        if key not in changes or changes[key] in (None, ""):
            continue
        if key == "cursors":
            _set_cursor(changes["cursors"], changes.get("cursor_size"))
        else:
            _SETTERS[key](changes[key])
    if "cursor_size" in changes and "cursors" not in changes:
        xfconf.set("xsettings", "/Gtk/CursorThemeSize", int(changes["cursor_size"]))


def apply_one(kind, name):
    labels = {"gtk": "Thème des applications", "xfwm4": "Bordures de fenêtres",
              "icons": "Icônes", "cursors": "Curseur", "wallpaper": "Fond d'écran"}
    if kind == "plank":
        from . import plank
        backup.snapshot("Thème du dock")
        plank.set("theme", name)
        return
    apply({kind: name}, f"{labels.get(kind, kind)} : {name}")
