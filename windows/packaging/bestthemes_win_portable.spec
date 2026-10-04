# -*- mode: python ; coding: utf-8 -*-
# PyInstaller : construit dist/BESTthemes-Portable-x.y.z.exe — un seul fichier, sans installation,
# à copier sur une clé USB. Les réglages et sauvegardes restent dans %LOCALAPPDATA%\BESTthemes
# de chaque PC (chaque PC garde donc son propre « bureau d'origine »).
#   pyinstaller windows/packaging/bestthemes_win_portable.spec --noconfirm
import re
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parents[1]
VERSION = re.search(r'__version__\s*=\s*"([^"]+)"',
                    (ROOT / "windows" / "bestthemes_win" / "__init__.py").read_text()).group(1)

datas = [
    (str(ROOT / "bestthemes" / "data" / "palettes.json"), "bestthemes/data"),
    (str(ROOT / "bestthemes" / "workshop" / "catalog.json"), "bestthemes/workshop"),
    (str(ROOT / "windows" / "bestthemes_win" / "data"), "bestthemes_win/data"),
]

a = Analysis(
    [str(ROOT / "windows" / "launcher.py")],
    pathex=[str(ROOT), str(ROOT / "windows")],
    datas=datas,
    hiddenimports=["PySide6.QtSvg", "cairo", "PIL.IcoImagePlugin", "PIL.CurImagePlugin"],
    excludes=["gi", "tkinter", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore", "PySide6.QtQml",
              "PySide6.QtQuick", "PySide6.QtPdf", "PySide6.QtMultimedia", "setuptools"],
    noarchive=False,
)
# Traductions Qt et modules QML inutiles : allège l'exécutable.
a.datas = [d for d in a.datas if "translations" not in d[0] and "/qml/" not in d[0].replace("\\", "/")]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name=f"BESTthemes-Portable-{VERSION}",
    icon=str(ROOT / "windows" / "bestthemes_win" / "data" / "bestthemes.ico"),
    console=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
)
