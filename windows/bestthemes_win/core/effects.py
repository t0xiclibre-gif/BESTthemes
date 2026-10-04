"""Effets visuels et animations de Windows (sans outil externe)."""
from .. import winplat as wp

DESKTOP = r"Control Panel\Desktop"

# id -> (libellé, nom SPI, passe par uiParam ?)
EFFECTS = {
    "minimize": ("Animer les fenêtres lors de la réduction et de l'agrandissement", None, False),
    "client": ("Animations dans les fenêtres et les contrôles", "CLIENTAREAANIMATION", False),
    "menu_anim": ("Menus animés", "MENUANIMATION", False),
    "menu_fade": ("Menus en fondu (plutôt que glissés)", "MENUFADE", False),
    "combo": ("Listes déroulantes animées", "COMBOBOXANIMATION", False),
    "smooth": ("Défilement fluide des listes", "LISTBOXSMOOTHSCROLLING", False),
    "tooltip": ("Info-bulles animées", "TOOLTIPANIMATION", False),
    "tooltip_fade": ("Info-bulles en fondu", "TOOLTIPFADE", False),
    "selection_fade": ("Fondu des éléments de menu après un clic", "SELECTIONFADE", False),
    "shadow": ("Ombre sous les fenêtres et les menus", "DROPSHADOW", False),
    "cursor_shadow": ("Ombre sous le curseur", "CURSORSHADOW", False),
    "drag_full": ("Afficher le contenu des fenêtres pendant le déplacement", "DRAGFULLWINDOWS", True),
}

MENU_DELAYS = {0: "Instantané", 100: "Rapide", 200: "Vif", 400: "Normal (Windows)"}

PRESETS = [
    {"id": "fluid", "name": "Fluide (façon macOS)",
     "desc": "Toutes les animations, menus en fondu, ombres douces et menus qui s'ouvrent vite.",
     "values": {k: True for k in EFFECTS}, "menu_delay": 100},
    {"id": "default", "name": "Windows par défaut",
     "desc": "Les réglages d'origine de Windows.",
     "values": {k: True for k in EFFECTS}, "menu_delay": 400},
    {"id": "snappy", "name": "Vif",
     "desc": "Garde les ombres et le fondu, coupe les animations lentes : tout répond instantanément.",
     "values": {**{k: False for k in EFFECTS}, "shadow": True, "cursor_shadow": True,
                "drag_full": True, "menu_fade": True, "smooth": True},
     "menu_delay": 0},
    {"id": "performance", "name": "Performances",
     "desc": "Aucun effet : idéal pour les PC modestes.",
     "values": {k: False for k in EFFECTS}, "menu_delay": 0},
]

TRACKED = [(DESKTOP, "MenuShowDelay"), (DESKTOP, "UserPreferencesMask"),
           (r"Control Panel\Desktop\WindowMetrics", "MinAnimate")]


def get(key):
    if key == "minimize":
        return wp.get_min_animate()
    return wp.spi_get_bool(EFFECTS[key][1])


def set(key, on):
    if key == "minimize":
        return wp.set_min_animate(on)
    _, spi, by_ui = EFFECTS[key]
    return wp.spi_set_uiparam(spi, on) if by_ui else wp.spi_set_bool(spi, on)


def menu_delay():
    try:
        return int(wp.reg_value(DESKTOP, "MenuShowDelay", "400"))
    except (TypeError, ValueError):
        return 400


def set_menu_delay(ms):
    wp.reg_set(DESKTOP, "MenuShowDelay", str(int(ms)), wp.SZ)
    wp.broadcast("WindowMetrics")


def capture():
    return {"values": {k: get(k) for k in EFFECTS}, "menu_delay": menu_delay()}


def restore(state):
    if not state:
        return
    for k, v in state.get("values", {}).items():
        if k in EFFECTS:
            set(k, v)
    if "menu_delay" in state:
        set_menu_delay(state["menu_delay"])


def apply_preset(preset):
    if isinstance(preset, str):
        preset = next(p for p in PRESETS if p["id"] == preset)
    for k, v in preset["values"].items():
        set(k, v)
    set_menu_delay(preset["menu_delay"])
