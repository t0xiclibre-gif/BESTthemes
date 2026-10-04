"""Thèmes de curseurs Windows : installation (sans droits admin), application, taille."""
import json
import re
import shutil
from pathlib import Path

from bestthemes.core import scanner

from .. import winplat as wp
from . import xcur2win

CURSORS = r"Control Panel\Cursors"
SCHEMES = r"Control Panel\Cursors\Schemes"
ACCESS = r"Software\Microsoft\Accessibility"

# Ordre utilisé par Windows dans Control Panel\Cursors\Schemes
ROLES = ["Arrow", "Help", "AppStarting", "Wait", "Crosshair", "IBeam", "NWPen", "No",
         "SizeNS", "SizeWE", "SizeNWSE", "SizeNESW", "SizeAll", "UpArrow", "Hand", "Pin", "Person"]
ROLE_LABELS = {"Arrow": "Normal", "Hand": "Lien", "IBeam": "Texte", "Wait": "Occupé",
               "AppStarting": "Travail en arrière-plan", "SizeAll": "Déplacer"}

TRACKED = [(CURSORS, r) for r in ROLES] + [(CURSORS, ""), (CURSORS, "CursorBaseSize"),
                                           (ACCESS, "CursorSize"), (CURSORS, "precisionhair")]

SIZES = {32: "Normale", 48: "Grande", 64: "Très grande", 96: "Énorme"}


def root():
    d = wp.DATA / "Cursors"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------- détection / installation


def parse_inf(inf_path):
    """Lit un install.inf de thème de curseurs : renvoie (nom, {rôle: fichier})."""
    text = Path(inf_path).read_text(errors="replace")
    strings = {}
    m = re.search(r"^\[Strings\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S | re.I)
    if m:
        for line in m.group(1).splitlines():
            line = line.split(";", 1)[0].strip()
            if "=" in line:
                k, v = line.split("=", 1)
                strings[k.strip().lower()] = v.strip().strip('"')

    def expand(s):
        return re.sub(r"%([^%]+)%", lambda mm: strings.get(mm.group(1).lower(), mm.group(0)), s)

    name = strings.get("scheme_name") or Path(inf_path).parent.name
    mapping = {}
    for line in text.splitlines():
        mm = re.match(r'\s*HKCU\s*,\s*"Control Panel\\Cursors"\s*,\s*([^,]*),[^,]*,\s*"?([^"\r\n]*)"?',
                      line, re.I)
        if not mm or not mm.group(1).strip():
            continue
        role = mm.group(1).strip().strip('"')
        value = expand(mm.group(2))
        fname = re.split(r"[\\/]", value)[-1]
        for r in ROLES:
            if r.lower() == role.lower():
                mapping[r] = fname
    return name, mapping


def _guess_by_filename(folder):
    """Dossier de .cur/.ani sans install.inf : on devine d'après les noms de fichiers."""
    hints = {
        "Arrow": ["pointer", "normal", "arrow", "default", "select"],
        "Help": ["help"], "AppStarting": ["work", "appstarting", "working", "background"],
        "Wait": ["busy", "wait"], "Crosshair": ["cross", "precision"], "IBeam": ["text", "beam"],
        "NWPen": ["hand", "pen", "handwriting"], "No": ["unavailable", "no", "not"],
        "SizeNS": ["vert", "ns"], "SizeWE": ["horz", "horiz", "we"], "SizeNWSE": ["dgn1", "nwse"],
        "SizeNESW": ["dgn2", "nesw"], "SizeAll": ["move", "all"], "UpArrow": ["alternate", "up"],
        "Hand": ["link", "hand"], "Pin": ["pin", "location"], "Person": ["person"],
    }
    files = [p for p in Path(folder).iterdir() if p.suffix.lower() in (".cur", ".ani")]
    mapping = {}
    for role, words in hints.items():
        for w in words:
            hit = next((f for f in files if f.stem.lower().replace("-", "").startswith(w)
                        and f.name not in mapping.values()), None)
            if hit:
                mapping[role] = hit.name
                break
    return mapping


def find_windows_schemes(folder):
    """Dossiers contenant des curseurs Windows (.cur/.ani), avec ou sans install.inf."""
    found = []
    for d in [Path(folder), *[p for p in Path(folder).rglob("*") if p.is_dir()]]:
        try:
            files = list(d.iterdir())
        except OSError:
            continue
        if not any(f.suffix.lower() in (".cur", ".ani") for f in files):
            continue
        inf = next((f for f in files if f.suffix.lower() == ".inf"), None)
        if inf:
            name, mapping = parse_inf(inf)
        else:
            name, mapping = d.name, _guess_by_filename(d)
        if mapping.get("Arrow"):
            found.append((d, name, mapping))
    return found


def _safe_name(name):
    return re.sub(r'[<>:"/\\|?*]+', "-", name).strip(" .") or "Curseurs"


def install_folder(folder, name, mapping):
    """Copie un thème Windows dans le dossier de BESTthemes."""
    dest = root() / _safe_name(name)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    out = {}
    for role, fname in mapping.items():
        src = Path(folder) / fname
        if not src.is_file():
            # Les .inf ne respectent pas toujours la casse
            src = next((p for p in Path(folder).iterdir() if p.name.lower() == fname.lower()), None)
        if src is None:
            continue
        shutil.copyfile(src, dest / src.name)
        out[role] = src.name
    (dest / "bestthemes.json").write_text(json.dumps({"name": name, "roles": out}, indent=1))
    return dest


def install_from_xcursor(theme_dir, name=None):
    """Convertit puis installe un thème de curseurs Linux."""
    name = name or Path(theme_dir).name
    dest = root() / _safe_name(name)
    if dest.exists():
        shutil.rmtree(dest)
    mapping = xcur2win.convert_theme(theme_dir, dest)
    if "Arrow" not in mapping:
        shutil.rmtree(dest, ignore_errors=True)
        raise ValueError("Ce thème de curseurs n'a pas pu être converti.")
    (dest / "bestthemes.json").write_text(json.dumps({"name": name, "roles": mapping,
                                                      "converted": True}, indent=1))
    return dest


def install_extracted(folder):
    """Installe tous les thèmes trouvés dans une archive extraite. Renvoie [dossiers]."""
    installed = []
    for d, name, mapping in find_windows_schemes(folder):
        installed.append(install_folder(d, name, mapping))
    if not installed:
        for d, kinds in _xcursor_roots(folder):
            try:
                installed.append(install_from_xcursor(d))
            except ValueError:
                continue
    return installed


def _xcursor_roots(folder):
    from bestthemes.core.installer import find_roots
    return [(d, k) for d, k in find_roots(folder) if "cursors" in k]


# ---------------------------------------------------------------- liste / application


def installed():
    out = []
    for d in sorted(root().iterdir(), key=lambda p: p.name.lower()):
        meta = d / "bestthemes.json"
        if meta.is_file():
            try:
                m = json.loads(meta.read_text())
            except ValueError:
                continue
            out.append({"name": m.get("name", d.name), "path": d, "roles": m.get("roles", {}),
                        "converted": m.get("converted", False)})
    return out


def current():
    return wp.reg_value(CURSORS, "", "") or "Windows par défaut"


def apply(theme):
    """theme : dict renvoyé par installed(), ou None pour les curseurs Windows d'origine."""
    if theme is None:
        for r in ROLES:
            wp.reg_set(CURSORS, r, "", wp.EXPAND_SZ)
        wp.reg_set(CURSORS, "", "", wp.SZ)
        wp.reload_cursors()
        return
    d = Path(theme["path"])
    paths = {r: str(d / f) for r, f in theme["roles"].items()}
    for r in ROLES:
        wp.reg_set(CURSORS, r, paths.get(r, ""), wp.EXPAND_SZ)
    if "Crosshair" in paths:
        wp.reg_set(CURSORS, "precisionhair", paths["Crosshair"], wp.EXPAND_SZ)
    wp.reg_set(CURSORS, "", theme["name"], wp.SZ)
    wp.reg_set(SCHEMES, theme["name"], ",".join(paths.get(r, "") for r in ROLES), wp.EXPAND_SZ)
    wp.reload_cursors()


def uninstall(theme):
    if current() == theme["name"]:
        apply(None)
    wp.reg_delete(SCHEMES, theme["name"])
    shutil.rmtree(theme["path"], ignore_errors=True)


def size():
    return int(wp.reg_value(CURSORS, "CursorBaseSize", 32) or 32)


def set_size(px):
    """Taille des curseurs (Windows 10 1903+). Peut nécessiter une reconnexion pour certains."""
    px = int(px)
    wp.reg_set(CURSORS, "CursorBaseSize", px, wp.DWORD)
    wp.reg_set(ACCESS, "CursorSize", max(1, min(15, (px - 32) // 16 + 1)), wp.DWORD)
    wp.reload_cursors()


def reload():
    wp.reload_cursors()


# Petite aide pour la page : un dossier de thème Linux est-il un thème de curseurs ?
def is_xcursor_theme(d):
    return "cursors" in scanner.detect_kinds(d)

