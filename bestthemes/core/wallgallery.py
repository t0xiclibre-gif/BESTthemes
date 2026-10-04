"""Galerie de photos haute qualité sous licence libre (Wikimedia Commons, NASA).

Commons : uniquement les « images remarquables » (Featured pictures), choisies par la
communauté pour leur qualité. NASA : images du domaine public. Seules les images en
paysage d'au moins 1920 px de large sont proposées ; elles sont téléchargées à la taille de
l'écran (1920 ou 3840 px) et l'auteur et la licence sont enregistrés à côté de l'image.
"""
import hashlib
import json
import re
import time
from pathlib import Path

from . import paths

USER_AGENT = "BESTthemes/1.0 (desktop theme manager; Linux Mint / Windows)"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
NASA_API = "https://images-api.nasa.gov/search"
CACHE_TTL = 24 * 3600
MAX_BYTES = 60_000_000

# (id, libellé, source, catégorie Commons ou recherche NASA)
THEMES = [
    ("landscapes", "Paysages", "commons", "Featured pictures of landscapes"),
    ("mountains", "Montagnes", "commons", "Featured pictures of mountains"),
    ("coasts", "Côtes et mers", "commons", "Featured pictures of coasts"),
    ("water", "Lacs et rivières", "commons", "Featured pictures of bodies of water"),
    ("forests", "Forêts", "commons", "Featured pictures of forests"),
    ("sunsets", "Couchers de soleil", "commons", "Featured pictures of sunsets"),
    ("clouds", "Ciel et nuages", "commons", "Featured pictures of clouds"),
    ("volcanoes", "Volcans", "commons", "Featured pictures of volcanoes"),
    ("night", "Nuit", "commons", "Featured night photography"),
    ("cities", "Villes", "commons", "Featured pictures of cityscapes"),
    ("astronomy", "Astronomie", "commons", "Featured pictures of astronomy"),
    ("satellite", "La Terre vue du ciel", "commons", "Featured pictures taken from satellites"),
    ("nebulae", "Nébuleuses (NASA)", "nasa", "nebula"),
    ("galaxies", "Galaxies (NASA)", "nasa", "galaxy"),
    ("earth", "La Terre depuis l'espace (NASA)", "nasa", "earth from space station"),
    ("planets", "Planètes (NASA)", "nasa", "planet"),
]


class Photo:
    def __init__(self, pid, title, thumb, author, license, page, width, height, source, hq=None, size=0):
        self.id = pid
        self.title = title
        self.thumb = thumb
        self.author = author
        self.license = license
        self.page = page
        self.width = width
        self.height = height
        self.source = source
        self.hq = hq or {}      # largeur -> URL
        self.size = size

    @property
    def credit(self):
        who = self.author or ("NASA" if self.source == "nasa" else "Auteur inconnu")
        return f"{who} — {self.license}" if self.license else who

    def best_url(self, screen_w):
        """URL de la meilleure taille pour cet écran (jamais plus grande que l'original)."""
        want = 3840 if screen_w > 1920 else 1920
        for wdt in sorted(self.hq):
            if wdt >= want:
                return self.hq[wdt]
        return self.hq[max(self.hq)] if self.hq else None


_session = None


def session():
    global _session
    if _session is None:
        import requests
        _session = requests.Session()
        _session.headers["User-Agent"] = USER_AGENT
    return _session


def _cache_dir():
    d = paths.CACHE_DIR / "gallery"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_json(url, params):
    """Requête mise en cache 24 h : on reste poli avec les serveurs (et c'est plus rapide)."""
    key = hashlib.sha1((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    f = _cache_dir() / f"{key}.json"
    if f.exists() and time.time() - f.stat().st_mtime < CACHE_TTL:
        try:
            return json.loads(f.read_text())
        except ValueError:
            pass
    for attempt in range(3):
        r = session().get(url, params=params, timeout=25)
        if r.status_code == 429 and attempt < 2:  # trop de requêtes : on patiente un peu
            time.sleep(2 + attempt * 3)
            continue
        r.raise_for_status()
        data = r.json()
        f.write_text(json.dumps(data))
        return data
    raise RuntimeError("Le serveur est occupé, réessayez dans un instant.")


def _strip_html(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()[:80]


def _landscape_hd(w, h):
    return w >= 1920 and h > 0 and w >= h * 1.25


# ---------------------------------------------------------------- Wikimedia Commons


def _commons(category, cont):
    params = {"action": "query", "format": "json", "formatversion": "2",
              "generator": "categorymembers", "gcmtitle": f"Category:{category}", "gcmtype": "file",
              "gcmlimit": "50", "gcmsort": "timestamp", "gcmdir": "desc",
              "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
              "iiextmetadatafilter": "Artist|LicenseShortName|ObjectName", "iiurlwidth": "640"}
    if cont:
        params.update(cont)
    data = _get_json(COMMONS_API, params)
    out = []
    for pg in data.get("query", {}).get("pages", []):
        info = (pg.get("imageinfo") or [{}])[0]
        w, h = info.get("width", 0), info.get("height", 0)
        if info.get("mime") not in ("image/jpeg", "image/png") or not _landscape_hd(w, h):
            continue
        meta = info.get("extmetadata", {})
        thumb = info.get("thumburl")
        if not thumb or "px-" not in thumb:
            continue
        hq = {}
        for wdt in (1920, 3840):
            if w > wdt:
                hq[wdt] = re.sub(r"/\d+px-", f"/{wdt}px-", thumb, count=1)
        if info.get("size", 0) < MAX_BYTES:
            hq[w] = info.get("url")
        title = _strip_html(meta.get("ObjectName", {}).get("value")) or \
            Path(pg["title"]).stem.replace("File:", "").replace("_", " ")
        out.append(Photo(f"commons-{pg['pageid']}", title[:70], thumb,
                         _strip_html(meta.get("Artist", {}).get("value")),
                         _strip_html(meta.get("LicenseShortName", {}).get("value")),
                         info.get("descriptionurl", ""), w, h, "commons", hq, info.get("size", 0)))
    nxt = data.get("continue")
    return out, ({k: v for k, v in nxt.items()} if nxt else None)


# ---------------------------------------------------------------- NASA


def _nasa(query, cont):
    page = int(cont or 1)
    data = _get_json(NASA_API, {"q": query, "media_type": "image", "page": str(page), "page_size": "60"})
    coll = data.get("collection", {})
    out = []
    for it in coll.get("items", []):
        d = (it.get("data") or [{}])[0]
        links = it.get("links") or []
        canon = next((x for x in links if x.get("rel") == "canonical"), None)
        prev = next((x for x in links if x.get("rel") == "preview"), None) or \
            next((x for x in links if "~medium" in x.get("href", "")), None)
        if not canon or not prev:
            continue
        w, h = canon.get("width", 0), canon.get("height", 0)
        if not _landscape_hd(w, h) or canon.get("size", 0) > MAX_BYTES:
            continue
        medium = next((x for x in links if "~medium" in x.get("href", "")), None)
        thumb = (medium or prev)["href"]
        out.append(Photo(f"nasa-{d.get('nasa_id', '')}", (d.get("title") or "")[:70], thumb,
                         f"NASA{(' / ' + d['center']) if d.get('center') else ''}", "Domaine public",
                         f"https://images.nasa.gov/details/{d.get('nasa_id', '')}", w, h, "nasa",
                         {w: canon["href"]}, canon.get("size", 0)))
    more = any(l.get("rel") == "next" for l in coll.get("links", []))
    return out, (page + 1 if more else None)


# ---------------------------------------------------------------- API publique


def browse(theme_id, cont=None):
    """Renvoie (photos, suite) ; `suite` se passe à l'appel suivant pour charger la page d'après."""
    theme = next((t for t in THEMES if t[0] == theme_id), THEMES[0])
    if theme[2] == "nasa":
        return _nasa(theme[3], cont)
    return _commons(theme[3], cont)


def _safe(name):
    return re.sub(r"[^\w.-]+", "_", name)[:60].strip("_") or "image"


def download(photo, dest_dir, screen_w=1920, progress=None):
    """Télécharge la photo en haute qualité dans dest_dir et enregistre son crédit."""
    url = photo.best_url(screen_w)
    if not url:
        raise RuntimeError("Aucune version haute qualité disponible.")
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = ".png" if url.lower().split("?")[0].endswith(".png") else ".jpg"
    out = dest_dir / f"{_safe(photo.title)}-{_safe(photo.id)}{ext}"
    if out.exists() and out.stat().st_size > 0:
        return out
    tmp = out.with_suffix(out.suffix + ".part")
    with session().get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(256 * 1024):
                f.write(chunk)
                done += len(chunk)
                if done > MAX_BYTES:
                    raise RuntimeError("Image trop volumineuse.")
                if progress and total:
                    progress(done / total)
    tmp.replace(out)
    _save_credit(dest_dir, out.name, photo)
    return out


def _save_credit(dest_dir, filename, photo):
    f = Path(dest_dir) / "credits.json"
    try:
        data = json.loads(f.read_text()) if f.exists() else {}
    except ValueError:
        data = {}
    data[filename] = {"title": photo.title, "author": photo.author, "license": photo.license,
                      "page": photo.page, "source": photo.source}
    f.write_text(json.dumps(data, indent=1, ensure_ascii=False))


def credit_for(path):
    """Crédit enregistré pour une image téléchargée (ou None)."""
    p = Path(path)
    f = p.parent / "credits.json"
    try:
        c = json.loads(f.read_text()).get(p.name) if f.exists() else None
    except (OSError, ValueError):
        return None
    if not c:
        return None
    return f"{c.get('author') or 'Auteur inconnu'} — {c.get('license') or ''}".rstrip(" —")
