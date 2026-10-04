"""Détection des thèmes installés sur le système."""
import configparser
from dataclasses import dataclass, field
from pathlib import Path

from . import paths

KINDS = ("gtk", "xfwm4", "icons", "cursors", "plank")


@dataclass
class ThemeInfo:
    name: str          # nom du dossier (identifiant utilisé par XFCE)
    path: Path
    kind: str
    title: str = ""    # nom lisible
    user: bool = False
    extra: dict = field(default_factory=dict)

    @property
    def label(self):
        return self.title or self.name


def read_index_theme(path):
    """Lit un index.theme et renvoie (section, dict) ou (None, {})."""
    f = Path(path) / "index.theme"
    if not f.is_file():
        return None, {}
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        cp.read_string(f.read_text(errors="replace"))
    except (configparser.Error, OSError):
        return None, {}
    for section in ("Icon Theme", "X-GNOME-Metatheme", "Desktop Entry"):
        if cp.has_section(section):
            return section, dict(cp.items(section))
    return None, {}


def detect_kinds(d):
    """Renvoie l'ensemble des types de thème contenus dans le dossier `d`."""
    d = Path(d)
    kinds = set()
    if not d.is_dir():
        return kinds
    if (d / "gtk-3.0").is_dir() or (d / "gtk-4.0").is_dir() or (d / "gtk-2.0").is_dir():
        kinds.add("gtk")
    if (d / "xfwm4").is_dir():
        kinds.add("xfwm4")
    if (d / "cursors").is_dir():
        kinds.add("cursors")
    if (d / "dock.theme").is_file():
        kinds.add("plank")
    section, data = read_index_theme(d)
    if section == "Icon Theme" and data.get("directories"):
        kinds.add("icons")
    return kinds


def _iter_dirs(roots):
    seen = set()
    for root in roots:
        if not root.is_dir():
            continue
        try:
            entries = sorted(root.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            continue
        for d in entries:
            if d.name in seen or d.name.startswith(".") or not d.is_dir():
                continue
            if d.name in ("default", "hicolor", "locolor"):
                continue
            seen.add(d.name)
            yield root, d


def scan(kind):
    """Liste les thèmes installés d'un type donné."""
    result = []
    if kind in ("gtk", "xfwm4"):
        roots = paths.THEME_DIRS
    elif kind in ("icons", "cursors"):
        roots = paths.ICON_DIRS
    else:
        roots = paths.PLANK_THEME_DIRS
    for root, d in _iter_dirs(roots):
        kinds = detect_kinds(d)
        if kind == "gtk" and not (d / "gtk-3.0").is_dir():
            continue
        if kind not in kinds:
            continue
        _, data = read_index_theme(d)
        title = data.get("name", "") if kind in ("icons", "cursors") else ""
        result.append(ThemeInfo(name=d.name, path=d, kind=kind, title=title,
                                user=paths.is_user_path(d)))
    return result


def scan_all():
    return {k: scan(k) for k in KINDS}


def find(kind, name):
    for t in scan(kind):
        if t.name == name:
            return t
    return None


def exists(kind, name):
    return find(kind, name) is not None
