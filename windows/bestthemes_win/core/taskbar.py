"""Barre des tâches, menu Démarrer et Explorateur de fichiers (réglages par utilisateur)."""
from .. import winplat as wp

ADV = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
SEARCH = r"Software\Microsoft\Windows\CurrentVersion\Search"
STUCK = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StuckRects3"
CLASSIC_MENU = r"Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}"
CLASSIC_MENU_SERVER = CLASSIC_MENU + r"\InprocServer32"

# (clé, nom, libellé, valeurs possibles {valeur: texte}, Windows 11 seulement ?)
OPTIONS = {
    "align": (ADV, "TaskbarAl", "Alignement des icônes", {0: "À gauche", 1: "Au centre"}, True),
    "search": (SEARCH, "SearchboxTaskbarMode", "Recherche",
               {0: "Masquée", 1: "Icône", 2: "Champ de recherche"}, False),
    "taskview": (ADV, "ShowTaskViewButton", "Bouton Vue des tâches", {0: "Masqué", 1: "Visible"}, False),
    "widgets": (ADV, "TaskbarDa", "Widgets", {0: "Masqués", 1: "Visibles"}, True),
    "combine": (ADV, "TaskbarGlomLevel", "Regrouper les fenêtres",
                {0: "Toujours", 1: "Quand la barre est pleine", 2: "Jamais"}, False),
    "small": (ADV, "TaskbarSmallIcons", "Petites icônes", {0: "Non", 1: "Oui"}, False),
    "animations": (ADV, "TaskbarAnimations", "Animations de la barre", {0: "Non", 1: "Oui"}, False),
    "start_layout": (ADV, "Start_Layout", "Menu Démarrer",
                     {0: "Par défaut", 1: "Plus d'épingles", 2: "Plus de recommandations"}, True),
    "extensions": (ADV, "HideFileExt", "Extensions des fichiers",
                   {1: "Masquées", 0: "Visibles"}, False),
    "hidden": (ADV, "Hidden", "Fichiers cachés", {2: "Masqués", 1: "Visibles"}, False),
    "compact": (ADV, "UseCompactMode", "Explorateur compact", {0: "Non", 1: "Oui"}, True),
}
DEFAULTS = {"align": 1, "search": 1, "taskview": 1, "widgets": 1, "combine": 0, "small": 0,
            "animations": 1, "start_layout": 0, "extensions": 1, "hidden": 2, "compact": 0}

TRACKED = [(o[0], o[1]) for o in OPTIONS.values()] + [(STUCK, "Settings")]

POSITIONS = {3: "En bas", 1: "En haut", 0: "À gauche", 2: "À droite"}

PRESETS = [
    {"id": "win11", "name": "Windows 11", "desc": "Icônes centrées, recherche en icône.",
     "values": {"align": 1, "search": 1, "taskview": 1, "widgets": 1, "combine": 0},
     "autohide": False},
    {"id": "classic", "name": "Classique", "desc": "Icônes à gauche et champ de recherche, comme Windows 10.",
     "values": {"align": 0, "search": 2, "taskview": 1, "widgets": 0, "combine": 1},
     "autohide": False},
    {"id": "macos", "name": "macOS", "desc": "Barre épurée et centrée qui se cache : parfaite avec un dock (Nexus).",
     "values": {"align": 1, "search": 0, "taskview": 0, "widgets": 0, "combine": 0},
     "autohide": True},
    {"id": "minimal", "name": "Minimal", "desc": "Uniquement vos applications, rien d'autre.",
     "values": {"align": 1, "search": 0, "taskview": 0, "widgets": 0, "combine": 0},
     "autohide": False},
    {"id": "productive", "name": "Productif", "desc": "Fenêtres jamais regroupées, tout est visible d'un coup d'œil.",
     "values": {"align": 0, "search": 1, "taskview": 1, "widgets": 0, "combine": 2},
     "autohide": False},
]


def available(key):
    return not OPTIONS[key][4] or wp.is_win11()


def get(key):
    path, name, _, _, _ = OPTIONS[key]
    v = wp.reg_value(path, name)
    return DEFAULTS[key] if v is None else int(v)


def set(key, value):
    path, name, _, _, _ = OPTIONS[key]
    try:
        wp.reg_set(path, name, int(value), wp.DWORD)
        return True
    except PermissionError:
        # Ex. TaskbarDa est protégé sur certaines versions récentes de Windows 11
        return False


# ---------------------------------------------------------------- StuckRects3 (masquage, position)


def _stuck():
    v = wp.reg_value(STUCK, "Settings")
    return bytearray.fromhex(v) if isinstance(v, str) and len(v) >= 26 else None


def autohide():
    s = _stuck()
    return bool(s and s[8] & 0x01)


def set_autohide(on):
    s = _stuck()
    if s is None:
        return False
    s[8] = (s[8] | 0x01) if on else (s[8] & ~0x01 & 0xFF)
    wp.reg_set(STUCK, "Settings", bytes(s), wp.BINARY)
    return True


def position():
    s = _stuck()
    return s[12] if s else 3


def set_position(pos):
    """Position de la barre : fonctionne sous Windows 10 (Windows 11 l'ignore en partie)."""
    s = _stuck()
    if s is None:
        return False
    s[12] = int(pos)
    wp.reg_set(STUCK, "Settings", bytes(s), wp.BINARY)
    return True


# ---------------------------------------------------------------- menu contextuel classique (Win 11)


def classic_menu():
    return wp.reg_key_exists(CLASSIC_MENU_SERVER)


def set_classic_menu(on):
    if on:
        wp.reg_set(CLASSIC_MENU_SERVER, "", "", wp.SZ)
    else:
        wp.reg_delete_tree(CLASSIC_MENU)


def capture():
    return {"classic_menu": classic_menu()}


def restore(state):
    """Renvoie True si quelque chose a changé (l'Explorateur doit alors redémarrer)."""
    if state and state.get("classic_menu") != classic_menu():
        set_classic_menu(state["classic_menu"])
        return True
    return False


def apply_preset(preset):
    if isinstance(preset, str):
        preset = next(p for p in PRESETS if p["id"] == preset)
    for k, v in preset["values"].items():
        if available(k):
            set(k, v)
    set_autohide(preset.get("autohide", False))


def reload():
    """Ces réglages ne sont relus qu'au redémarrage de l'Explorateur."""
    wp.broadcast("TraySettings")
    wp.restart_explorer()
