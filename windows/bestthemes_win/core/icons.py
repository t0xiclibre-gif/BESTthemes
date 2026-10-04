"""Packs d'icônes : convertit un thème d'icônes Linux (SVG/PNG) en .ico pour Windows.

Windows ne permet pas de changer toutes les icônes du système sans droits admin ni
patch, mais on peut changer, pour l'utilisateur et de façon réversible :
  - les icônes du bureau (Ce PC, Corbeille vide/pleine, Réseau, Dossier personnel,
    Panneau de configuration) ;
  - les icônes des dossiers personnels (Documents, Images, Musique, Vidéos,
    Téléchargements, Bureau) via leur desktop.ini.
"""
import json
import re
import shutil
from pathlib import Path

from .. import winplat as wp

CLSID = r"Software\Microsoft\Windows\CurrentVersion\Explorer\CLSID"
DESKTOP_ITEMS = {
    "computer": ("{20D04FE0-3AEA-1069-A2D8-08002B30309D}", "Ce PC",
                 ["computer", "user-home-computer", "system", "drive-harddisk"]),
    "home": ("{59031a47-3f72-44a7-89c5-5595fe6b30ee}", "Dossier personnel",
             ["user-home", "folder-home", "user-identity"]),
    "network": ("{F02C1A0D-BE21-4350-88B0-7367FC96EF3C}", "Réseau",
                ["network-workgroup", "network-server", "network", "folder-network"]),
    "control": ("{5399E694-6CE5-4D6C-8FCE-1D8870FDCBA0}", "Panneau de configuration",
                ["preferences-system", "systemsettings", "preferences-desktop", "configure"]),
}
TRASH_CLSID = "{645FF040-5081-101B-9F08-00AA002F954E}"
TRASH_NAMES = {"Empty": ["user-trash", "trashcan_empty", "user-trash-empty"],
               "Full": ["user-trash-full", "trashcan_full"]}
FOLDERS = {
    "Documents": ["folder-documents", "folder-document"],
    "Pictures": ["folder-pictures", "folder-images", "folder-image"],
    "Music": ["folder-music", "folder-sound"],
    "Videos": ["folder-videos", "folder-video"],
    "Downloads": ["folder-download", "folder-downloads"],
    "Desktop": ["user-desktop", "folder-desktop"],
}
FOLDER_LABELS = {"Documents": "Documents", "Pictures": "Images", "Music": "Musique",
                 "Videos": "Vidéos", "Downloads": "Téléchargements", "Desktop": "Bureau"}
GENERIC_FOLDER = ["folder", "inode-directory", "folder-blue"]

TRACKED = ([(f"{CLSID}\\{guid}\\DefaultIcon", "") for guid, _, _ in DESKTOP_ITEMS.values()]
           + [(f"{CLSID}\\{TRASH_CLSID}\\DefaultIcon", n) for n in ("", "Empty", "Full")])

SIZES = [256, 64, 48, 40, 32, 24, 20, 16]


def root():
    d = wp.DATA / "Icons"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------- recherche dans un thème Linux

_SIZE_RX = re.compile(r"(\d+)(?:x\d+)?(?:@(\d)x)?")


def _dir_score(rel):
    """Plus le score est grand, meilleure est la source (SVG > grandes PNG)."""
    s = rel.lower()
    if "scalable" in s:
        return 10_000
    m = _SIZE_RX.search(s)
    if m:
        n = int(m.group(1)) * int(m.group(2) or 1)
        return n
    return 1


def find_icon(theme_dir, names, extra_dirs=()):
    """Cherche la meilleure image pour une liste de noms d'icônes (hors icônes symboliques)."""
    best = None
    for base in [Path(theme_dir), *map(Path, extra_dirs)]:
        if not base.is_dir():
            continue
        for name in names:
            for f in base.rglob(name + ".*"):
                if f.suffix.lower() not in (".svg", ".png") or "symbolic" in str(f).lower():
                    continue
                try:
                    if not f.resolve().is_file():
                        continue
                except OSError:
                    continue
                score = _dir_score(str(f.relative_to(base)))
                if f.suffix.lower() == ".svg":
                    score = max(score, 5000)
                if best is None or score > best[0]:
                    best = (score, f)
            if best:
                return best[1]
    return None


def inherited_dirs(theme_dir):
    """Thèmes parents (Inherits=) installés à côté, pour trouver les icônes manquantes."""
    idx = Path(theme_dir) / "index.theme"
    out = []
    if idx.is_file():
        m = re.search(r"^Inherits\s*=\s*(.+)$", idx.read_text(errors="replace"), re.M)
        if m:
            for name in m.group(1).split(","):
                d = Path(theme_dir).parent / name.strip()
                if d.is_dir():
                    out.append(d)
    return out


# ---------------------------------------------------------------- rendu en .ico


def render_ico(src, dest):
    """Convertit un SVG ou PNG en .ico multi-tailles (Qt pour le SVG, Pillow pour l'ICO)."""
    from PIL import Image
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PySide6.QtGui import QImage, QPainter

    src = Path(src)
    big = 256
    if src.suffix.lower() == ".svg":
        from PySide6.QtSvg import QSvgRenderer
        r = QSvgRenderer(str(src))
        if not r.isValid():
            raise ValueError(f"SVG illisible : {src.name}")
        img = QImage(big, big, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r.render(p)
        p.end()
    else:
        img = QImage(str(src))
        if img.isNull():
            raise ValueError(f"Image illisible : {src.name}")
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    import io
    pil = Image.open(io.BytesIO(bytes(ba))).convert("RGBA")
    if pil.size != (big, big):
        pil = pil.resize((big, big), Image.LANCZOS)
    pil.save(dest, format="ICO", sizes=[(s, s) for s in SIZES])
    return Path(dest)


# ---------------------------------------------------------------- packs


def build_pack(theme_dir, name=None):
    """Prépare un pack d'icônes Windows à partir d'un thème Linux. Renvoie le dossier."""
    theme_dir = Path(theme_dir)
    name = name or theme_dir.name
    dest = root() / re.sub(r'[<>:"/\\|?*]+', "-", name)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    extra = inherited_dirs(theme_dir)
    made = {}
    wanted = {**{k: v[2] for k, v in DESKTOP_ITEMS.items()},
              **{f"trash-{k.lower()}": v for k, v in TRASH_NAMES.items()},
              **{f"folder-{k.lower()}": v for k, v in FOLDERS.items()},
              "folder": GENERIC_FOLDER}
    for key, names in wanted.items():
        src = find_icon(theme_dir, names, extra)
        if src is None and key.startswith("folder-"):
            src = find_icon(theme_dir, GENERIC_FOLDER, extra)
        if src is None:
            continue
        try:
            render_ico(src, dest / f"{key}.ico")
            made[key] = f"{key}.ico"
        except (ValueError, OSError):
            continue
    if not made:
        shutil.rmtree(dest, ignore_errors=True)
        raise ValueError("Aucune icône utilisable n'a été trouvée dans ce thème.")
    (dest / "bestthemes.json").write_text(json.dumps({"name": name, "icons": made}, indent=1))
    return dest


def installed():
    out = []
    for d in sorted(root().iterdir(), key=lambda p: p.name.lower()):
        meta = d / "bestthemes.json"
        if meta.is_file():
            try:
                m = json.loads(meta.read_text())
            except ValueError:
                continue
            out.append({"name": m.get("name", d.name), "path": d, "icons": m.get("icons", {})})
    return out


def current():
    return _load_state().get("pack")


# ---------------------------------------------------------------- application

def _state_file():
    return wp.DATA / "icons-state.json"


def _load_state():
    try:
        return json.loads(_state_file().read_text())
    except (OSError, ValueError):
        return {}


def _save_state(s):
    _state_file().write_text(json.dumps(s, indent=1))


def _set_folder_icon(folder, ico):
    """Change l'icône d'un dossier via son desktop.ini (en gardant son contenu existant)."""
    folder = Path(folder)
    ini = folder / "desktop.ini"
    original = None
    if ini.is_file():
        wp.set_attrs(ini, 0)  # retire caché/système pour pouvoir écrire
        raw = ini.read_bytes()
        original = raw
        if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            text = raw.decode("utf-16")
        else:
            text = raw.decode("mbcs" if wp.IS_WINDOWS else "utf-8", errors="replace")
    else:
        text = ""
    if ico is None:
        lines = [ln for ln in text.splitlines() if not re.match(r"\s*IconResource\s*=", ln, re.I)]
    else:
        lines = text.splitlines()
        if not any(ln.strip().lower() == "[.shellclassinfo]" for ln in lines):
            lines = ["[.ShellClassInfo]"] + lines
        lines = [ln for ln in lines if not re.match(r"\s*IconResource\s*=", ln, re.I)]
        i = next(i for i, ln in enumerate(lines) if ln.strip().lower() == "[.shellclassinfo]")
        lines.insert(i + 1, f"IconResource={ico},0")
    ini.write_text("\r\n".join(lines) + "\r\n", encoding="utf-16")
    wp.set_attrs(ini, wp.FILE_ATTRIBUTE_HIDDEN | wp.FILE_ATTRIBUTE_SYSTEM)
    # Windows ne lit desktop.ini que si le dossier a l'attribut lecture seule ou système
    wp.set_attrs(folder, wp.get_attrs(folder) | wp.FILE_ATTRIBUTE_READONLY)
    return original


def apply(pack, folders=True, desktop=True):
    """Applique un pack d'icônes (dict renvoyé par installed()) ou None pour revenir aux icônes Windows."""
    state = _load_state()
    originals = state.setdefault("originals", {})
    d = Path(pack["path"]) if pack else None
    icons = pack["icons"] if pack else {}

    if desktop:
        for key, (guid, _, _) in DESKTOP_ITEMS.items():
            path = f"{CLSID}\\{guid}\\DefaultIcon"
            if pack and key in icons:
                wp.reg_set(path, "", f"{d / icons[key]},0", wp.EXPAND_SZ)
            else:
                wp.reg_delete(path, "")
        tpath = f"{CLSID}\\{TRASH_CLSID}\\DefaultIcon"
        if pack and "trash-empty" in icons:
            empty = f"{d / icons['trash-empty']},0"
            full = f"{d / icons.get('trash-full', icons['trash-empty'])},0"
            wp.reg_set(tpath, "Empty", empty, wp.EXPAND_SZ)
            wp.reg_set(tpath, "Full", full, wp.EXPAND_SZ)
            wp.reg_set(tpath, "", empty, wp.EXPAND_SZ)
        else:
            for n in ("", "Empty", "Full"):
                wp.reg_delete(tpath, n)

    if folders:
        for fname in FOLDERS:
            try:
                folder = wp.known_folder(fname)
            except OSError:
                continue
            if not folder.is_dir():
                continue
            key = f"folder-{fname.lower()}"
            ico = str(d / icons[key]) if pack and key in icons else None
            try:
                orig = _set_folder_icon(folder, ico)
            except OSError:  # dossier protégé (OneDrive, droits) : on passe au suivant
                continue
            if str(folder) not in originals:
                originals[str(folder)] = orig.hex() if orig is not None else None
    state["pack"] = pack["name"] if pack else None
    _save_state(state)
    wp.refresh_shell_icons()


def restore_folders():
    """Remet les desktop.ini des dossiers personnels exactement comme avant BESTthemes."""
    state = _load_state()
    for folder, orig in state.get("originals", {}).items():
        ini = Path(folder) / "desktop.ini"
        try:
            if ini.exists():
                wp.set_attrs(ini, 0)
            if orig is None:
                ini.unlink(missing_ok=True)
            else:
                ini.write_bytes(bytes.fromhex(orig))
                wp.set_attrs(ini, wp.FILE_ATTRIBUTE_HIDDEN | wp.FILE_ATTRIBUTE_SYSTEM)
        except OSError:
            continue
    state["originals"] = {}
    state["pack"] = None
    _save_state(state)


def uninstall(pack):
    if current() == pack["name"]:
        apply(None)
    shutil.rmtree(pack["path"], ignore_errors=True)


def reload():
    wp.refresh_shell_icons()


def capture():
    return {"pack": current()}


def restore(snap):
    """Annulation : réapplique le pack enregistré (ou les icônes d'origine)."""
    name = (snap or {}).get("pack")
    if current() == name:
        return
    pack = next((p for p in installed() if p["name"] == name), None)
    if pack is None:
        apply(None)
        restore_folders()
    else:
        apply(pack)
