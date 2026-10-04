"""Catalogue intégré de thèmes sélectionnés (sources pling.com et GitHub)."""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..core import installer
from . import pling

_FILE = Path(__file__).with_name("catalog.json")


@dataclass
class CatalogItem:
    id: str
    name: str
    kind: str
    source: str
    desc: str = ""
    tags: list = field(default_factory=list)
    default: str = ""
    pling: str = ""
    preview_pling: str = ""
    files: list = field(default_factory=list)  # pour source "url"
    _pling_item: object = None

    @property
    def source_id(self):
        return f"catalog:{self.id}"

    def installed(self):
        return installer.is_installed(self.source_id)

    def installed_items(self):
        return installer.installed_items(self.source_id)

    def pling_item(self):
        """Infos complètes depuis pling (mises en cache en mémoire)."""
        pid = self.pling or self.preview_pling
        if not pid:
            return None
        if self._pling_item is None:
            self._pling_item = pling.get_item(pid)
        return self._pling_item

    def preview_url(self):
        it = self.pling_item()
        return it.preview if it else None

    def list_files(self):
        """Renvoie [(nom, url)] des variantes téléchargeables."""
        if self.source == "url":
            return [(f["name"], f["url"]) for f in self.files]
        it = self.pling_item()
        return [(f.name, f.url) for f in it.files] if it else []

    def default_file(self, files=None):
        files = files if files is not None else self.list_files()
        if not files:
            return None
        for name, url in files:
            if name == self.default:
                return name, url
        # Les versions changent (ex. papirus-icon-theme-2025xxxx) : on compare le préfixe
        base = re.split(r"[-_.]\d", self.default or "", maxsplit=1)[0].lower()
        if base:
            for name, url in files:
                if name.lower().startswith(base):
                    return name, url
        return files[0]

    def install(self, filename=None, progress=None, cancel=None):
        files = self.list_files()
        choice = None
        if filename:
            choice = next(((n, u) for n, u in files if n == filename), None)
            if choice is None:
                rx = re.compile(filename, re.I)
                choice = next(((n, u) for n, u in files if rx.search(n)), None)
        choice = choice or self.default_file(files)
        if not choice:
            raise installer.InstallError("Aucun fichier téléchargeable pour ce thème.")
        name, url = choice
        return installer.install_url(url, name, source_id=self.source_id,
                                     progress=progress, cancel=cancel)

    def uninstall(self):
        installer.uninstall_source(self.source_id)


_items = None


def items():
    global _items
    if _items is None:
        data = json.loads(_FILE.read_text())
        _items = [CatalogItem(**it) for it in data["items"]]
    return _items


def get(item_id):
    return next((i for i in items() if i.id == item_id), None)


def by_kind(kind):
    return [i for i in items() if i.kind == kind]
