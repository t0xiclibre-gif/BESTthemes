"""Génère bestthemes.ico (multi-tailles) depuis l'icône SVG du projet."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "windows")]

from PySide6.QtGui import QGuiApplication  # noqa: E402

from bestthemes_win.core.icons import render_ico  # noqa: E402

if __name__ == "__main__":
    app = QGuiApplication([])
    out = ROOT / "windows" / "bestthemes_win" / "data" / "bestthemes.ico"
    render_ico(ROOT / "packaging" / "icons" / "bestthemes.svg", out)
    print("Icône créée :", out)
