"""Emplacements standard utilisés par BESTthemes."""
import os
from pathlib import Path

HOME = Path.home()

APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"

USER_THEMES = HOME / ".themes"
USER_ICONS = HOME / ".icons"
USER_PLANK_THEMES = HOME / ".local/share/plank/themes"

THEME_DIRS = [USER_THEMES, HOME / ".local/share/themes", Path("/usr/share/themes")]
ICON_DIRS = [USER_ICONS, HOME / ".local/share/icons", Path("/usr/share/icons")]
PLANK_THEME_DIRS = [USER_PLANK_THEMES, Path("/usr/share/plank/themes")]

STATE_DIR = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share")) / "bestthemes"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "bestthemes"
SNAPSHOT_DIR = STATE_DIR / "snapshots"
WALLPAPER_DIR = STATE_DIR / "wallpapers"
INSTALLED_DB = STATE_DIR / "installed.json"

USER_DIRS = [USER_THEMES, USER_ICONS, USER_PLANK_THEMES,
             HOME / ".local/share/themes", HOME / ".local/share/icons"]


def ensure_dirs():
    for d in (USER_THEMES, USER_ICONS, USER_PLANK_THEMES, STATE_DIR,
              CACHE_DIR, SNAPSHOT_DIR, WALLPAPER_DIR):
        d.mkdir(parents=True, exist_ok=True)


def is_user_path(path):
    """Vrai si `path` est dans un dossier de thèmes de l'utilisateur (donc supprimable)."""
    p = Path(path).resolve()
    for d in USER_DIRS:
        try:
            p.relative_to(d.resolve())
            return p != d.resolve()
        except (ValueError, FileNotFoundError):
            continue
    return False
