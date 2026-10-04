"""Accès à l'API OCS de pling.com (xfce-look.org, gnome-look.org)."""
import hashlib
import html
import re
from dataclasses import dataclass, field

from ..core import paths
from ..core.installer import USER_AGENT, is_archive_name

API = "https://api.pling.com/ocs/v1/content/data"
CATEGORIES = {
    "gtk": "135",
    "xfwm4": "138",
    "icons": "132",
    "cursors": "107",
    "plank": "273",
    "wallpapers": "295",
}
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
SORTS = {"down": "Les plus téléchargés", "new": "Les plus récents", "high": "Les mieux notés"}


@dataclass
class PlingFile:
    name: str
    url: str
    size_kb: int = 0
    version: str = ""


@dataclass
class PlingItem:
    id: str
    name: str
    summary: str = ""
    description: str = ""
    author: str = ""
    downloads: int = 0
    score: int = 0
    category: str = ""
    preview: str = ""
    previews: list = field(default_factory=list)
    changed: str = ""
    page: str = ""
    files: list = field(default_factory=list)
    images: list = field(default_factory=list)  # fichiers image téléchargeables (fonds d'écran)


def _session():
    import requests
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


_SESSION = None


def session():
    global _SESSION
    if _SESSION is None:
        _SESSION = _session()
    return _SESSION


def _clean(text):
    text = re.sub(r"<br\s*/?>", "\n", text or "", flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[/?[a-z]+[^\]]*\]", "", text)  # BBCode
    return html.unescape(text).strip()


def _parse(it):
    files = []
    images = []
    for i in range(1, 100):
        name = it.get(f"downloadname{i}")
        link = it.get(f"downloadlink{i}")
        if not name or not link:
            continue
        if str(it.get(f"downloadprice{i}", "0")) not in ("0", "", "0.00"):
            continue
        if name.lower().endswith(IMAGE_EXTS):
            images.append(PlingFile(name=name, url=link))
            continue
        if not is_archive_name(name):
            continue
        try:
            size = int(it.get(f"downloadsize{i}") or 0)
        except ValueError:
            size = 0
        files.append(PlingFile(name=name, url=link, size_kb=size,
                               version=it.get(f"download_version{i}") or ""))
    previews = [it.get(f"previewpic{i}") for i in range(1, 10) if it.get(f"previewpic{i}")]
    return PlingItem(
        id=str(it.get("id")),
        name=_clean(it.get("name", "")),
        summary=_clean(it.get("summary", "")),
        description=_clean(it.get("description", ""))[:1500],
        author=it.get("personid", ""),
        downloads=int(it.get("downloads") or 0),
        score=int(float(it.get("score") or 0)),
        category=it.get("typename", ""),
        preview=it.get("smallpreviewpic1") or (previews[0] if previews else ""),
        previews=previews,
        changed=(it.get("changed") or "")[:10],
        page=it.get("detailpage", ""),
        files=files,
        images=images,
    )


def search(kind, query="", sort="down", page=0, pagesize=24):
    params = {"format": "json", "categories": CATEGORIES[kind], "sortmode": sort,
              "page": page, "pagesize": pagesize}
    if query:
        params["search"] = query
    r = session().get(API, params=params, timeout=25)
    r.raise_for_status()
    data = r.json()
    items = [_parse(it) for it in (data.get("data") or [])]
    return items, int(data.get("totalitems") or 0)


def get_item(item_id):
    r = session().get(f"{API}/{item_id}", params={"format": "json"}, timeout=25)
    r.raise_for_status()
    data = r.json().get("data")
    if isinstance(data, list):
        data = data[0] if data else None
    if not data:
        raise LookupError(f"Élément {item_id} introuvable")
    return _parse(data)


def cached_image(url, max_bytes=6_000_000):
    """Télécharge une image (aperçu) dans le cache et renvoie son chemin local."""
    if not url:
        return None
    d = paths.CACHE_DIR / "thumbs"
    d.mkdir(parents=True, exist_ok=True)
    f = d / hashlib.sha1(url.encode()).hexdigest()
    if f.exists() and f.stat().st_size > 0:
        return f
    r = session().get(url, timeout=25)
    r.raise_for_status()
    content = r.content[:max_bytes]
    f.write_bytes(content)
    return f
