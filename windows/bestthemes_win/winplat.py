"""Accès à Windows : registre (HKCU uniquement), SystemParametersInfo, notifications.

Sur un autre système (développement sous Linux), un registre simulé stocké en JSON
remplace le vrai : toute l'application peut ainsi être testée sans Windows.
"""
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
CREATE_NO_WINDOW = 0x08000000

# Types de valeurs du registre
SZ, EXPAND_SZ, BINARY, DWORD = "sz", "expand_sz", "binary", "dword"


def app_data_dir():
    if IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")
        return base / "BESTthemes"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "bestthemes-win-demo"


DATA = app_data_dir()


def windows_build():
    if IS_WINDOWS:
        return sys.getwindowsversion().build
    return int(os.environ.get("BT_FAKE_BUILD", "22631"))


def is_win11():
    return windows_build() >= 22000


# ======================================================================= registre

if IS_WINDOWS:
    import winreg

    _TYPES = {SZ: winreg.REG_SZ, EXPAND_SZ: winreg.REG_EXPAND_SZ,
              BINARY: winreg.REG_BINARY, DWORD: winreg.REG_DWORD}
    _RTYPES = {v: k for k, v in _TYPES.items()}

    def reg_get(path, name):
        """Renvoie (valeur, type) ou None. `path` est relatif à HKEY_CURRENT_USER."""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
                value, t = winreg.QueryValueEx(k, name)
        except OSError:
            return None
        if isinstance(value, bytes):
            value = value.hex()
        return value, _RTYPES.get(t, SZ)

    def reg_set(path, name, value, vtype):
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as k:
            if vtype == BINARY and isinstance(value, str):
                value = bytes.fromhex(value)
            winreg.SetValueEx(k, name, 0, _TYPES[vtype], value)

    def reg_delete(path, name):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, name)
        except OSError:
            pass

    def reg_delete_tree(path):
        """Supprime une clé et ses sous-clés (sous HKCU)."""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0,
                                winreg.KEY_READ | winreg.KEY_WRITE) as k:
                while True:
                    try:
                        sub = winreg.EnumKey(k, 0)
                    except OSError:
                        break
                    reg_delete_tree(path + "\\" + sub)
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
        except OSError:
            pass

    def reg_key_exists(path):
        try:
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CURRENT_USER, path))
            return True
        except OSError:
            return False
else:
    _LOCK = threading.Lock()
    _FAKE = DATA / "fake_registry.json"

    def _load():
        try:
            return json.loads(_FAKE.read_text())
        except (OSError, ValueError):
            return {}

    def _save(d):
        _FAKE.parent.mkdir(parents=True, exist_ok=True)
        _FAKE.write_text(json.dumps(d, indent=1, sort_keys=True))

    def reg_get(path, name):
        with _LOCK:
            v = _load().get(path.lower(), {}).get(name.lower())
        return (v[0], v[1]) if v else None

    def reg_set(path, name, value, vtype):
        if vtype == BINARY and isinstance(value, (bytes, bytearray)):
            value = bytes(value).hex()
        with _LOCK:
            d = _load()
            d.setdefault(path.lower(), {})[name.lower()] = [value, vtype]
            _save(d)

    def reg_delete(path, name):
        with _LOCK:
            d = _load()
            d.get(path.lower(), {}).pop(name.lower(), None)
            _save(d)

    def reg_delete_tree(path):
        with _LOCK:
            d = _load()
            p = path.lower()
            for k in [k for k in d if k == p or k.startswith(p + "\\")]:
                del d[k]
            _save(d)

    def reg_key_exists(path):
        p = path.lower()
        return any(k == p or k.startswith(p + "\\") for k in _load())


def reg_value(path, name, default=None):
    r = reg_get(path, name)
    return r[0] if r else default


def reg_set_keep(path, name, value, default_type):
    """Écrit en conservant le type existant (texte ou nombre) si la valeur existe déjà."""
    r = reg_get(path, name)
    vtype = r[1] if r and r[1] in (SZ, DWORD) else default_type
    reg_set(path, name, int(value) if vtype == DWORD else str(value), vtype)


# ======================================================================= API Win32

SPI = {
    "SETDESKWALLPAPER": 0x0014,
    "SETCURSORS": 0x0057,
    "GETANIMATION": 0x0048, "SETANIMATION": 0x0049,
    "GETDRAGFULLWINDOWS": 0x0026, "SETDRAGFULLWINDOWS": 0x0025,
    "GETMENUANIMATION": 0x1002, "SETMENUANIMATION": 0x1003,
    "GETCOMBOBOXANIMATION": 0x1004, "SETCOMBOBOXANIMATION": 0x1005,
    "GETLISTBOXSMOOTHSCROLLING": 0x1006, "SETLISTBOXSMOOTHSCROLLING": 0x1007,
    "GETMENUFADE": 0x1012, "SETMENUFADE": 0x1013,
    "GETTOOLTIPANIMATION": 0x1016, "SETTOOLTIPANIMATION": 0x1017,
    "GETTOOLTIPFADE": 0x1018, "SETTOOLTIPFADE": 0x1019,
    "GETCURSORSHADOW": 0x101A, "SETCURSORSHADOW": 0x101B,
    "GETDROPSHADOW": 0x1024, "SETDROPSHADOW": 0x1025,
    "GETCLIENTAREAANIMATION": 0x1042, "SETCLIENTAREAANIMATION": 0x1043,
    "GETSELECTIONFADE": 0x1014, "SETSELECTIONFADE": 0x1015,
}
SPIF_UPDATE = 0x01 | 0x02  # SPIF_UPDATEINIFILE | SPIF_SENDCHANGE

_fake_spi = {}

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _shell32 = ctypes.WinDLL("shell32")

    class ANIMATIONINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("iMinAnimate", ctypes.c_int)]

    def spi_get_bool(name):
        v = wintypes.BOOL()
        _user32.SystemParametersInfoW(SPI["GET" + name], 0, ctypes.byref(v), 0)
        return bool(v.value)

    def spi_set_bool(name, value):
        # Pour ces réglages, la valeur passe par pvParam (casté en pointeur)
        return bool(_user32.SystemParametersInfoW(SPI["SET" + name], 0,
                                                  ctypes.c_void_p(1 if value else 0), SPIF_UPDATE))

    def spi_set_uiparam(name, value):
        """Réglages dont la valeur passe par uiParam (ex. DRAGFULLWINDOWS)."""
        return bool(_user32.SystemParametersInfoW(SPI["SET" + name], 1 if value else 0, None,
                                                  SPIF_UPDATE))

    def get_min_animate():
        ai = ANIMATIONINFO(ctypes.sizeof(ANIMATIONINFO), 0)
        _user32.SystemParametersInfoW(SPI["GETANIMATION"], ai.cbSize, ctypes.byref(ai), 0)
        return bool(ai.iMinAnimate)

    def set_min_animate(on):
        ai = ANIMATIONINFO(ctypes.sizeof(ANIMATIONINFO), 1 if on else 0)
        return bool(_user32.SystemParametersInfoW(SPI["SETANIMATION"], ai.cbSize,
                                                  ctypes.byref(ai), SPIF_UPDATE))

    def set_wallpaper_spi(path):
        return bool(_user32.SystemParametersInfoW(SPI["SETDESKWALLPAPER"], 0, str(path), SPIF_UPDATE))

    def reload_cursors():
        return bool(_user32.SystemParametersInfoW(SPI["SETCURSORS"], 0, None, SPIF_UPDATE))

    def broadcast(area):
        """Prévient toutes les fenêtres qu'un réglage a changé (WM_SETTINGCHANGE)."""
        HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG = 0xFFFF, 0x001A, 0x0002
        res = wintypes.DWORD()
        _user32.SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, area,
                                    SMTO_ABORTIFHUNG, 2000, ctypes.byref(res))

    def refresh_shell_icons():
        SHCNE_ASSOCCHANGED, SHCNF_IDLIST = 0x08000000, 0x0000
        _shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
        try:  # vide le cache d'icônes de l'Explorateur ; facultatif
            run_hidden(["ie4uinit.exe", "-show"], wait=False)
        except OSError:
            pass

    FILE_ATTRIBUTE_READONLY, FILE_ATTRIBUTE_HIDDEN, FILE_ATTRIBUTE_SYSTEM = 0x1, 0x2, 0x4

    def get_attrs(path):
        a = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        return 0 if a == 0xFFFFFFFF else a

    def set_attrs(path, attrs):
        ctypes.windll.kernel32.SetFileAttributesW(str(path), attrs)

    def known_folder(name):
        """Chemin réel d'un dossier personnel (Documents, Images…) même s'il a été déplacé."""
        guids = {
            "Desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
            "Documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
            "Downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
            "Music": "{4BD8D571-6D19-48D3-BE97-422220080E43}",
            "Pictures": "{33E28130-4E1E-4676-835A-98395C3BC3BB}",
            "Videos": "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}",
        }

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

        g = GUID()
        ctypes.oledll.ole32.CLSIDFromString(guids[name], ctypes.byref(g))
        p = ctypes.c_wchar_p()
        hr = _shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(p))
        if hr != 0 or not p.value:
            raise OSError(f"Dossier introuvable : {name}")
        result = Path(p.value)
        ctypes.windll.ole32.CoTaskMemFree(p)
        return result
else:
    def spi_get_bool(name):
        return _fake_spi.get(name, True)

    def spi_set_bool(name, value):
        _fake_spi[name] = bool(value)
        return True

    spi_set_uiparam = spi_set_bool

    def get_min_animate():
        return _fake_spi.get("MINANIMATE", True)

    def set_min_animate(on):
        _fake_spi["MINANIMATE"] = bool(on)
        return True

    def set_wallpaper_spi(path):
        _fake_spi["WALLPAPER"] = str(path)
        return True

    def reload_cursors():
        return True

    def broadcast(area):
        pass

    def refresh_shell_icons():
        pass

    FILE_ATTRIBUTE_READONLY, FILE_ATTRIBUTE_HIDDEN, FILE_ATTRIBUTE_SYSTEM = 0x1, 0x2, 0x4

    def get_attrs(path):
        return _fake_spi.get(("attrs", str(path)), 0)

    def set_attrs(path, attrs):
        _fake_spi[("attrs", str(path))] = attrs

    def known_folder(name):
        d = DATA / "fake_home" / name
        d.mkdir(parents=True, exist_ok=True)
        return d


def run_hidden(cmd, wait=True, timeout=None):
    """Lance une commande sans jamais ouvrir de fenêtre de terminal."""
    kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
    if IS_WINDOWS:
        kwargs["creationflags"] = CREATE_NO_WINDOW
    if not IS_WINDOWS:
        return subprocess.CompletedProcess(cmd, 0, b"", b"") if wait else None
    if wait:
        return subprocess.run(cmd, timeout=timeout, **kwargs)
    kwargs.update(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # personne ne lira la sortie
    return subprocess.Popen(cmd, **kwargs)


def restart_explorer():
    """Relance l'Explorateur Windows (barre des tâches) pour appliquer certains réglages."""
    if not IS_WINDOWS:
        return
    run_hidden(["taskkill", "/f", "/im", "explorer.exe"], timeout=20)
    # Windows relance en général l'Explorateur tout seul : en lancer un second ouvrirait
    # une fenêtre « Ce PC ». On ne le relance que s'il n'est pas revenu.
    import time
    for _ in range(16):
        time.sleep(0.5)
        if _explorer_running():
            return
    windir = os.environ.get("WINDIR", r"C:\Windows")
    subprocess.Popen([os.path.join(windir, "explorer.exe")], creationflags=CREATE_NO_WINDOW,
                     close_fds=True)


def _explorer_running():
    try:
        r = run_hidden(["tasklist", "/fi", "imagename eq explorer.exe", "/fo", "csv", "/nh"], timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return b"explorer.exe" in (r.stdout or b"").lower()


def open_url(url):
    import webbrowser
    webbrowser.open(url)
