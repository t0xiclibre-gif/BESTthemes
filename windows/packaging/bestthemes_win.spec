# -*- mode: python ; coding: utf-8 -*-
# PyInstaller : construit dist/BESTthemes/BESTthemes.exe
#   pyinstaller windows/packaging/bestthemes_win.spec --noconfirm
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parents[1]

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
    excludes=["gi", "tkinter", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="BESTthemes",
    icon=str(ROOT / "windows" / "bestthemes_win" / "data" / "bestthemes.ico"),
    console=False,
    version=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="BESTthemes")
