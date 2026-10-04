"""Workshop Windows : catalogue + xfce-look, avec conversion automatique Linux → Windows."""
import json
import re
import shutil
import tempfile
from pathlib import Path

from bestthemes.core import installer
from bestthemes.workshop import catalog as linux_catalog

from .. import winplat as wp
from . import appearance, cursors, icons

_FILE = Path(__file__).resolve().parent.parent / "data" / "catalog_win.json"
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


class Item:
    """Élément du catalogue (natif Windows ou repris du catalogue Linux)."""

    def __init__(self, id, name, kind, desc="", tags=(), files=None, default=None, linux=None,
                 preview_pling=None):
        self.id = id
        self.name = name
        self.kind = kind
        self.desc = desc
        self.tags = list(tags)
        self._files = files
        self.default = default
        self.linux = linux  # CatalogItem Linux réutilisé (curseurs/icônes à convertir)
        self.preview_pling = preview_pling

    @property
    def converted(self):
        return self.linux is not None

    def list_files(self):
        if self._files is not None:
            return [(f["name"], f["url"]) for f in self._files]
        return self.linux.list_files()

    def default_file(self, files):
        if self.linux is not None:
            d = self.linux.default_file(files)
            return d[0] if d else files[0][0]
        return self.default or files[0][0]

    def preview_url(self):
        if self.preview_pling:
            from bestthemes.workshop import pling
            return pling.get_item(self.preview_pling).preview
        if self.linux is not None:
            return self.linux.preview_url()
        return None


_items = None


def items():
    global _items
    if _items is None:
        data = json.loads(_FILE.read_text(encoding="utf-8"))
        _items = [Item(**it) for it in data["items"]]
        for li in linux_catalog.items():
            if li.kind in ("cursors", "icons"):
                tags = list(li.tags) + ["converti depuis Linux"]
                _items.append(Item(f"linux-{li.id}", li.name, li.kind, li.desc, tags, linux=li))
    return _items


# ---------------------------------------------------------------- installation


def _record(source_id, names):
    f = wp.DATA / "workshop.json"
    try:
        db = json.loads(f.read_text())
    except (OSError, ValueError):
        db = {}
    db[source_id] = names
    f.write_text(json.dumps(db, indent=1))


def installed_names(source_id):
    try:
        return json.loads((wp.DATA / "workshop.json").read_text()).get(source_id, [])
    except (OSError, ValueError):
        return []


def is_installed(source_id, kind):
    names = installed_names(source_id)
    if not names:
        return False
    if kind == "cursors":
        have = {c["name"] for c in cursors.installed()}
    elif kind == "icons":
        have = {p["name"] for p in icons.installed()}
    else:
        return any(Path(n).exists() for n in names)
    return any(n in have for n in names)


def install(kind, filename, url, source_id, progress=None, cancel=None):
    """Télécharge puis installe. Renvoie la liste des noms installés (thèmes ou images)."""
    work = Path(tempfile.mkdtemp(prefix="bt-", dir=_tmp_root()))
    try:
        safe = Path(filename).name or "fichier"
        dest = work / safe
        installer.download(url, dest, progress, cancel)
        if kind == "wallpapers":
            names = _install_wallpapers(dest, safe)
        else:
            ex = work / "x"
            installer.extract(dest, ex)
            if kind == "cursors":
                done = cursors.install_extracted(ex)
                names = [json.loads((d / "bestthemes.json").read_text())["name"] for d in done]
            else:
                names = _install_icons(ex)
        if not names:
            raise installer.InstallError("Rien d'utilisable n'a été trouvé dans ce téléchargement.")
        _record(source_id, names)
        return names
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _tmp_root():
    d = wp.DATA / "tmp"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _install_icons(folder):
    roots = [d for d, k in installer.find_roots(folder) if "icons" in k]
    if not roots:
        raise installer.InstallError("Aucun thème d'icônes trouvé dans cette archive.")
    # On privilégie la variante principale (sans -dark/-light) puis les autres
    roots.sort(key=lambda d: (bool(re.search(r"(dark|light)", d.name, re.I)), len(d.name)))
    names = []
    for d in roots[:3]:
        # Les thèmes héritent souvent de leurs variantes : on les place côte à côte
        try:
            names.append(json.loads((icons.build_pack(d) / "bestthemes.json").read_text())["name"])
        except ValueError:
            continue
    return names


def _install_wallpapers(path, filename):
    out_dir = appearance.wallpaper_dir() / "Workshop"
    out_dir.mkdir(parents=True, exist_ok=True)
    if filename.lower().endswith(IMAGE_EXTS):
        dest = out_dir / filename
        shutil.copyfile(path, dest)
        return [str(dest)]
    ex = Path(path).parent / "x"
    installer.extract(path, ex)
    sub = out_dir / installer._strip_ext(filename)
    sub.mkdir(parents=True, exist_ok=True)
    names = []
    for img in sorted(ex.rglob("*")):
        if img.suffix.lower() in IMAGE_EXTS and img.is_file() and img.stat().st_size > 30_000:
            target = sub / img.name
            shutil.copyfile(img, target)
            names.append(str(target))
        if len(names) >= 60:
            break
    return names


def wallpapers():
    """Toutes les images de fonds d'écran gérées par BESTthemes."""
    d = appearance.wallpaper_dir()
    files = [p for p in d.rglob("*") if p.suffix.lower() in IMAGE_EXTS and p.is_file()]
    if wp.IS_WINDOWS:
        sysdir = Path(r"C:\Windows\Web\Wallpaper")
        if sysdir.is_dir():
            files += [p for p in sysdir.rglob("*") if p.suffix.lower() in IMAGE_EXTS]
    def mtime(p):
        try:
            return p.stat().st_mtime
        except OSError:
            return 0

    return sorted(files, key=lambda p: -mtime(p))
