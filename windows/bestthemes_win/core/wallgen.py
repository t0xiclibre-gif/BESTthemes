"""Fonds d'écran générés (réutilise le moteur de la version Linux)."""
import time

from bestthemes.core import wallpaper as W

from . import appearance

STYLES = W.STYLES
SCREEN = (1920, 1080)  # remplacé au démarrage par la vraie résolution de l'écran


def generate(palette, style, seed=None, size=None):
    w, h = size or SCREEN
    surf = W.render(palette, style, w, h, seed)
    name = f"{palette['name'].replace(' ', '_').replace('/', '-')}-{style}-{int(time.time())}.png"
    out = appearance.wallpaper_dir() / "Générés" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    surf.write_to_png(str(out))
    return out
