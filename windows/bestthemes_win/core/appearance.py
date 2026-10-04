"""Mode sombre/clair, couleur d'accent, transparence, fond d'écran."""
import shutil
import time
from pathlib import Path

from bestthemes.core import colors as C

from .. import winplat as wp

PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
DWM = r"Software\Microsoft\Windows\DWM"
ACCENT = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent"
DESKTOP = r"Control Panel\Desktop"
COLORS = r"Control Panel\Colors"

TRACKED = [
    (PERSONALIZE, "AppsUseLightTheme"), (PERSONALIZE, "SystemUsesLightTheme"),
    (PERSONALIZE, "EnableTransparency"), (PERSONALIZE, "ColorPrevalence"),
    (DWM, "AccentColor"), (DWM, "ColorizationColor"), (DWM, "ColorizationAfterglow"),
    (DWM, "ColorPrevalence"), (DWM, "AccentColorInactive"),
    (ACCENT, "AccentPalette"), (ACCENT, "AccentColorMenu"), (ACCENT, "StartColorMenu"),
    (DESKTOP, "AutoColorization"), (DESKTOP, "Wallpaper"), (DESKTOP, "WallpaperStyle"),
    (DESKTOP, "TileWallpaper"),
]

WALL_STYLES = {"fill": ("10", "0"), "fit": ("6", "0"), "stretch": ("2", "0"),
               "center": ("0", "0"), "tile": ("0", "1"), "span": ("22", "0")}


# ---------------------------------------------------------------- lecture


def state():
    return {
        "apps_dark": wp.reg_value(PERSONALIZE, "AppsUseLightTheme", 1) == 0,
        "system_dark": wp.reg_value(PERSONALIZE, "SystemUsesLightTheme", 0) == 0,
        "transparency": wp.reg_value(PERSONALIZE, "EnableTransparency", 1) == 1,
        "accent": accent(),
        "accent_titlebars": wp.reg_value(DWM, "ColorPrevalence", 0) == 1,
        "accent_taskbar": wp.reg_value(PERSONALIZE, "ColorPrevalence", 0) == 1,
        "auto_accent": str(wp.reg_value(DESKTOP, "AutoColorization", "0")) == "1",
        "wallpaper": wp.reg_value(DESKTOP, "Wallpaper", ""),
    }


def _abgr_to_hex(v):
    v = int(v) & 0xFFFFFFFF
    r, g, b = v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF
    return f"#{r:02x}{g:02x}{b:02x}"


def _hex_to_abgr(h):
    r, g, b = (round(c * 255) for c in C.to_rgb(h))
    return 0xFF000000 | (b << 16) | (g << 8) | r


def _hex_to_argb(h, alpha=0xC4):
    r, g, b = (round(c * 255) for c in C.to_rgb(h))
    return (alpha << 24) | (r << 16) | (g << 8) | b


def _signed(v):
    """winreg attend un entier non signé pour REG_DWORD ; on garde la valeur sur 32 bits."""
    return int(v) & 0xFFFFFFFF


def accent():
    v = wp.reg_value(DWM, "AccentColor")
    return _abgr_to_hex(v) if v is not None else "#0078d4"


def accent_palette(h):
    """Les 8 nuances que Windows utilise pour l'accent (du plus clair au plus foncé)."""
    shades = [C.lighten(h, 0.6), C.lighten(h, 0.4), C.lighten(h, 0.2), h,
              C.darken(h, 0.2), C.darken(h, 0.4), C.darken(h, 0.6), "#696969"]
    data = bytearray()
    for s in shades:
        data += bytes(round(c * 255) for c in C.to_rgb(s)) + b"\x00"
    return bytes(data), shades


# ---------------------------------------------------------------- écriture


def set_mode(apps_dark=None, system_dark=None):
    if apps_dark is not None:
        wp.reg_set(PERSONALIZE, "AppsUseLightTheme", 0 if apps_dark else 1, wp.DWORD)
    if system_dark is not None:
        wp.reg_set(PERSONALIZE, "SystemUsesLightTheme", 0 if system_dark else 1, wp.DWORD)
    wp.broadcast("ImmersiveColorSet")


def set_transparency(on):
    wp.reg_set(PERSONALIZE, "EnableTransparency", 1 if on else 0, wp.DWORD)
    wp.broadcast("ImmersiveColorSet")


def set_accent(h, titlebars=None, taskbar=None):
    """Change la couleur d'accent (menus, boutons, sélection, et en option barres de titre)."""
    palette, shades = accent_palette(h)
    wp.reg_set_keep(DESKTOP, "AutoColorization", 0, wp.DWORD)
    wp.reg_set(ACCENT, "AccentPalette", palette, wp.BINARY)
    # Comme Windows : AccentColorMenu = la couleur choisie (Windows recopie cette valeur dans
    # DWM\AccentColor), StartColorMenu = la nuance suivante, plus foncée.
    wp.reg_set(ACCENT, "AccentColorMenu", _signed(_hex_to_abgr(h)), wp.DWORD)
    wp.reg_set(ACCENT, "StartColorMenu", _signed(_hex_to_abgr(shades[4])), wp.DWORD)
    wp.reg_set(DWM, "AccentColor", _signed(_hex_to_abgr(h)), wp.DWORD)
    wp.reg_set(DWM, "ColorizationColor", _signed(_hex_to_argb(h)), wp.DWORD)
    wp.reg_set(DWM, "ColorizationAfterglow", _signed(_hex_to_argb(h)), wp.DWORD)
    if titlebars is not None:
        wp.reg_set(DWM, "ColorPrevalence", 1 if titlebars else 0, wp.DWORD)
    if taskbar is not None:
        wp.reg_set(PERSONALIZE, "ColorPrevalence", 1 if taskbar else 0, wp.DWORD)
    wp.broadcast("ImmersiveColorSet")


def set_auto_accent(on):
    wp.reg_set_keep(DESKTOP, "AutoColorization", 1 if on else 0, wp.DWORD)
    wp.broadcast("ImmersiveColorSet")


def set_accent_options(titlebars=None, taskbar=None):
    if titlebars is not None:
        wp.reg_set(DWM, "ColorPrevalence", 1 if titlebars else 0, wp.DWORD)
    if taskbar is not None:
        wp.reg_set(PERSONALIZE, "ColorPrevalence", 1 if taskbar else 0, wp.DWORD)
    wp.broadcast("ImmersiveColorSet")


def wallpaper_dir():
    d = wp.DATA / "Wallpapers"
    d.mkdir(parents=True, exist_ok=True)
    return d


def set_wallpaper(path, style="fill"):
    """Applique un fond d'écran (copié dans le dossier de BESTthemes pour qu'il reste)."""
    src = Path(path)
    dest = src
    if wallpaper_dir() not in src.resolve().parents:
        dest = wallpaper_dir() / f"{int(time.time())}-{src.name}"
        shutil.copyfile(src, dest)
    from . import livewall  # un fond animé cacherait le nouveau fond fixe
    if livewall.config()["enabled"]:
        livewall.stop()
    ws, tile = WALL_STYLES.get(style, WALL_STYLES["fill"])
    wp.reg_set(DESKTOP, "WallpaperStyle", ws, wp.SZ)
    wp.reg_set(DESKTOP, "TileWallpaper", tile, wp.SZ)
    wp.set_wallpaper_spi(str(dest))
    wp.reg_set(DESKTOP, "Wallpaper", str(dest), wp.SZ)
    return dest


def reload():
    """Réapplique ce qui est stocké dans le registre (après une restauration)."""
    w = wp.reg_value(DESKTOP, "Wallpaper", "")
    if w:
        wp.set_wallpaper_spi(w)
    wp.broadcast("ImmersiveColorSet")
