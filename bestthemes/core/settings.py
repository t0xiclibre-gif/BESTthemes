"""Préférences de l'application (stockées en JSON)."""
import json

from . import paths

_FILE = paths.STATE_DIR / "settings.json"
DEFAULTS = {
    "sync_wm_with_gtk": True,
    "cursor_size": 24,
    "workshop_sort": "down",
    "show_system_themes": True,
}
_cache = None


def _load():
    global _cache
    if _cache is None:
        try:
            _cache = {**DEFAULTS, **json.loads(_FILE.read_text())}
        except (OSError, ValueError):
            _cache = dict(DEFAULTS)
    return _cache


def get(key):
    return _load().get(key, DEFAULTS.get(key))


def set(key, value):
    data = _load()
    data[key] = value
    paths.STATE_DIR.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(data, indent=1))
