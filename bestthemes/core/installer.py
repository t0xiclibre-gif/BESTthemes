"""Téléchargement, extraction sécurisée et installation de thèmes."""
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path

from . import paths, scanner

USER_AGENT = "BESTthemes/1.0 (+https://github.com/bestthemes)"
ARCHIVE_EXTS = (".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2", ".tar",
                ".zip", ".tar.zst", ".tzst", ".bz2", ".xz", ".gz")


class InstallError(Exception):
    pass


class Cancelled(InstallError):
    pass


def is_archive_name(name):
    n = name.lower()
    return n.endswith(ARCHIVE_EXTS) or ".tar" in n


MAX_DOWNLOAD = 1_000_000_000      # 1 Go : aucun thème n'est aussi gros
MAX_EXTRACTED = 4_000_000_000     # protection contre les « bombes » zip


def download(url, dest, progress=None, cancel=None, timeout=60):
    """Télécharge `url` dans `dest`. progress(fraction|None, octets) est appelé régulièrement."""
    import requests
    with requests.get(url, stream=True, timeout=timeout,
                      headers={"User-Agent": USER_AGENT}) as r:
        if r.status_code != 200:
            raise InstallError(f"Téléchargement impossible (HTTP {r.status_code}).")
        total = int(r.headers.get("content-length") or 0)
        done = 0
        last = 0.0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if cancel is not None and cancel.is_set():
                    raise Cancelled("Annulé.")
                f.write(chunk)
                done += len(chunk)
                if done > MAX_DOWNLOAD:
                    raise InstallError("Fichier beaucoup trop volumineux pour un thème.")
                now = time.monotonic()
                if progress and now - last > 0.1:
                    last = now
                    progress(done / total if total else None, done)
        if progress:
            progress(1.0, done)
    return dest


def _within(base, target):
    base = os.path.realpath(base)
    target = os.path.realpath(target)
    return target == base or target.startswith(base + os.sep)


def _sniff(path):
    with open(path, "rb") as f:
        head = f.read(8)
    if head.startswith(b"PK"):
        return "zip"
    if head.startswith(b"\x28\xb5\x2f\xfd"):
        return "zst"
    return "tar"


def extract(archive, dest):
    """Extrait une archive (zip, tar.*, tar.zst) en refusant toute sortie du dossier."""
    archive = Path(archive)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    kind = _sniff(archive)
    if kind == "zst":
        if not shutil.which("zstd"):
            raise InstallError("Archive .zst : le paquet « zstd » est nécessaire.")
        tar_path = dest.parent / (dest.name + ".tar")
        try:
            subprocess.run(["zstd", "-d", "-q", "-f", str(archive), "-o", str(tar_path)], check=True,
                           timeout=600, capture_output=True)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            tar_path.unlink(missing_ok=True)
            raise InstallError(f"Archive .zst illisible : {e}")
        try:
            return extract(tar_path, dest)
        finally:
            tar_path.unlink(missing_ok=True)
    if kind == "zip":
        try:
            with zipfile.ZipFile(archive) as z:
                if sum(i.file_size for i in z.infolist()) > MAX_EXTRACTED:
                    raise InstallError("Archive trop volumineuse une fois décompressée.")
                for info in z.infolist():
                    target = dest / info.filename
                    if not _within(dest, target):
                        raise InstallError(f"Archive dangereuse : {info.filename}")
                    # Les liens symboliques zip (attribut unix 0o120000)
                    if (info.external_attr >> 16) & 0o170000 == 0o120000:
                        link = z.read(info).decode(errors="replace")
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if _within(dest, target.parent / link):
                            try:
                                os.symlink(link, target)
                            except OSError:  # déjà là, ou liens interdits (Windows)
                                pass
                        continue
                    z.extract(info, dest)
        except zipfile.BadZipFile as e:
            raise InstallError(f"Archive zip invalide : {e}")
        return dest
    try:
        with tarfile.open(archive) as t:
            t.extractall(dest, filter="data")
    except (tarfile.TarError, OSError) as e:
        raise InstallError(f"Archive invalide ou non prise en charge : {e}")
    return dest


def _nested_archives(d):
    return [p for p in Path(d).rglob("*") if p.is_file() and is_archive_name(p.name)
            and p.stat().st_size > 0]


def find_roots(d, max_depth=5):
    """Trouve tous les dossiers de thème (les plus hauts) sous `d`."""
    roots = []

    def walk(p, depth):
        kinds = scanner.detect_kinds(p)
        if kinds:
            roots.append((p, kinds))
            # Un thème GTK peut contenir des sous-thèmes ? Non : on s'arrête là.
            return
        if depth >= max_depth:
            return
        try:
            children = sorted(c for c in p.iterdir() if c.is_dir() and not c.is_symlink())
        except OSError:
            return
        for c in children:
            if c.name.startswith(".") or c.name in ("__MACOSX", "src", ".git"):
                continue
            walk(c, depth + 1)

    walk(Path(d), 0)
    return roots


def target_dir_for(kinds):
    if "plank" in kinds:
        return paths.USER_PLANK_THEMES
    if kinds & {"gtk", "xfwm4"}:
        return paths.USER_THEMES
    return paths.USER_ICONS


def _strip_ext(name):
    n = name
    for ext in sorted(ARCHIVE_EXTS, key=len, reverse=True):
        if n.lower().endswith(ext):
            return n[: -len(ext)]
    return n


def install_archive(archive, source_id=None, display_name=None):
    """Installe tous les thèmes trouvés dans l'archive. Renvoie [(nom, kinds, chemin)]."""
    paths.ensure_dirs()
    archive = Path(archive)
    with tempfile.TemporaryDirectory(prefix="bt-", dir=paths.CACHE_DIR) as tmp:
        ex = Path(tmp) / "x"
        extract(archive, ex)
        roots = find_roots(ex)
        if not roots:
            # Archive contenant d'autres archives (ex. pack de thèmes zip)
            for i, nested in enumerate(_nested_archives(ex)[:30]):
                sub = Path(tmp) / f"n{i}"
                try:
                    extract(nested, sub)
                except InstallError:
                    continue
                roots.extend(find_roots(sub))
        if not roots:
            raise InstallError("Aucun thème reconnu dans cette archive "
                               "(il faut peut-être l'installer à la main).")
        installed = []
        for root, kinds in roots:
            name = root.name
            if root == ex or name in ("x",):
                name = _strip_ext(display_name or archive.name)
            name = name.strip().replace("/", "-") or "Theme"
            target = target_dir_for(kinds) / name
            if target.exists() or target.is_symlink():
                if target.is_symlink() or target.is_file():
                    target.unlink()
                else:
                    shutil.rmtree(target)
            shutil.move(str(root), str(target))
            installed.append((name, sorted(kinds), str(target)))
    _record(source_id or archive.name, installed)
    _refresh_icon_cache(installed)
    return installed


def _refresh_icon_cache(installed):
    if not shutil.which("gtk-update-icon-cache"):
        return
    for _, kinds, path in installed:
        if "icons" in kinds:
            subprocess.run(["gtk-update-icon-cache", "-f", "-q", path],
                           capture_output=True)


def _load_db():
    try:
        return json.loads(paths.INSTALLED_DB.read_text())
    except (OSError, ValueError):
        return {}


def _record(source_id, installed):
    db = _load_db()
    entry = db.setdefault(str(source_id), {"items": []})
    known = {i[2] for i in entry["items"]}
    for item in installed:
        if item[2] not in known:
            entry["items"].append(list(item))
    entry["time"] = time.time()
    paths.INSTALLED_DB.parent.mkdir(parents=True, exist_ok=True)
    paths.INSTALLED_DB.write_text(json.dumps(db, indent=1))


def installed_items(source_id):
    """Éléments installés depuis une source et toujours présents sur le disque."""
    entry = _load_db().get(str(source_id))
    if not entry:
        return []
    return [i for i in entry["items"] if Path(i[2]).exists()]


def is_installed(source_id):
    return bool(installed_items(source_id))


def uninstall_path(path):
    p = Path(path)
    if not paths.is_user_path(p):
        raise InstallError("Seuls les thèmes installés dans votre dossier personnel "
                           "peuvent être supprimés.")
    if p.is_symlink() or p.is_file():
        p.unlink()
    elif p.exists():
        shutil.rmtree(p)


def uninstall_source(source_id):
    db = _load_db()
    entry = db.pop(str(source_id), None)
    if entry:
        for item in entry["items"]:
            try:
                uninstall_path(item[2])
            except InstallError:
                pass
        paths.INSTALLED_DB.write_text(json.dumps(db, indent=1))


def install_url(url, filename, source_id=None, progress=None, cancel=None):
    paths.ensure_dirs()
    with tempfile.TemporaryDirectory(prefix="bt-dl-", dir=paths.CACHE_DIR) as tmp:
        safe = Path(filename).name or "archive"
        dest = Path(tmp) / safe
        download(url, dest, progress, cancel)
        return install_archive(dest, source_id=source_id, display_name=safe)
