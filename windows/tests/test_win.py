"""Tests de BESTthemes Windows (tournent partout : sous Linux le registre est simulé).

Lancer depuis la racine du dépôt :
    python -m unittest discover -s windows/tests -t windows
"""
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "windows")]
_TMP = tempfile.mkdtemp(prefix="btw-test-")
os.environ["XDG_DATA_HOME"] = _TMP
os.environ["LOCALAPPDATA"] = _TMP
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

_APP = QApplication.instance() or QApplication([])  # une seule application Qt pour tous les tests

from bestthemes_win import winplat as wp  # noqa: E402
from bestthemes_win.core import (appearance, backup, cursors, effects, icons,  # noqa: E402
                                 packs, taskbar, xcur2win)

ON_WINDOWS = wp.IS_WINDOWS


def _xcursor(path, frames):
    """Écrit un petit fichier Xcursor (frames : liste de (taille, délai))."""
    header = struct.pack("<4sIII", b"Xcur", 16, 0x10000, len(frames))
    toc, chunks, pos = b"", b"", 16 + 12 * len(frames)
    for size, delay in frames:
        px = bytes([0, 0, 255, 255]) * (size * size)  # rouge opaque (BGRA)
        chunk = struct.pack("<IIIIIIIII", 36, 0xFFFD0002, size, 1, size, size, 1, 2, delay) + px
        toc += struct.pack("<III", 0xFFFD0002, size, pos)
        chunks += chunk
        pos += len(chunk)
    Path(path).write_bytes(header + toc + chunks)


class CursorConversionTest(unittest.TestCase):
    def test_static_and_animated(self):
        from PIL import Image
        d = Path(tempfile.mkdtemp(dir=_TMP)) / "Theme"
        (d / "cursors").mkdir(parents=True)
        _xcursor(d / "cursors" / "left_ptr", [(32, 0)])
        _xcursor(d / "cursors" / "watch", [(32, 40)] * 4)
        os.symlink("left_ptr", d / "cursors" / "default") if not ON_WINDOWS else None
        out = d.parent / "out"
        mapping = xcur2win.convert_theme(d, out)
        self.assertEqual(mapping["Arrow"], "Arrow.cur")
        self.assertEqual(mapping["Wait"], "Wait.ani")
        im = Image.open(out / "Arrow.cur")
        im.load()
        self.assertEqual(im.size, (32, 32))
        r, g, b, a = im.convert("RGBA").getpixel((5, 5))
        self.assertEqual((r, a), (255, 255))
        ani = (out / "Wait.ani").read_bytes()
        self.assertEqual(ani[:4], b"RIFF")
        self.assertEqual(ani[8:12], b"ACON")
        self.assertEqual(ani.count(b"icon"), 4)

    def test_install_from_xcursor_and_apply_undo(self):
        d = Path(tempfile.mkdtemp(dir=_TMP)) / "Rouge"
        (d / "cursors").mkdir(parents=True)
        _xcursor(d / "cursors" / "left_ptr", [(32, 0)])
        _xcursor(d / "cursors" / "hand2", [(32, 0)])
        cursors.install_from_xcursor(d)
        theme = next(t for t in cursors.installed() if t["name"] == "Rouge")
        backup.snapshot("test curseurs")
        cursors.apply(theme)
        self.assertEqual(cursors.current(), "Rouge")
        self.assertTrue(wp.reg_value(cursors.CURSORS, "Arrow").endswith("Arrow.cur"))
        backup.undo()
        self.assertNotEqual(cursors.current(), "Rouge")

    def test_parse_inf(self):
        d = Path(tempfile.mkdtemp(dir=_TMP))
        (d / "install.inf").write_text(
            '[Wreg]\nHKCU,"Control Panel\\Cursors",Arrow,0x00020000,"%10%\\%CUR_DIR%\\%pointer%"\n'
            'HKCU,"Control Panel\\Cursors",Hand,0x00020000,"%10%\\%CUR_DIR%\\%link%"\n'
            '[Strings]\nCUR_DIR = "Cursors\\Test"\nSCHEME_NAME = "Mon Thème"\n'
            'pointer = "Pointer.cur"\nlink = "Link.cur"\n')
        name, mapping = cursors.parse_inf(d / "install.inf")
        self.assertEqual(name, "Mon Thème")
        self.assertEqual(mapping, {"Arrow": "Pointer.cur", "Hand": "Link.cur"})


class AppearanceTest(unittest.TestCase):
    def test_accent_palette_and_undo(self):
        before = appearance.accent()
        backup.snapshot("accent")
        appearance.set_accent("#ff8800", titlebars=True)
        self.assertEqual(appearance.accent(), "#ff8800")
        data, shades = appearance.accent_palette("#ff8800")
        self.assertEqual(len(data), 32)
        self.assertEqual(shades[3], "#ff8800")
        self.assertTrue(appearance.state()["accent_titlebars"])
        backup.undo()
        self.assertEqual(appearance.accent(), before)

    def test_dark_mode(self):
        appearance.set_mode(apps_dark=True, system_dark=False)
        st = appearance.state()
        self.assertTrue(st["apps_dark"])
        self.assertFalse(st["system_dark"])


class TaskbarTest(unittest.TestCase):
    def test_stuckrects_autohide(self):
        blob = bytearray(48)
        blob[8] = 0x02
        blob[12] = 3
        wp.reg_set(taskbar.STUCK, "Settings", bytes(blob), wp.BINARY)
        self.assertFalse(taskbar.autohide())
        taskbar.set_autohide(True)
        self.assertTrue(taskbar.autohide())
        self.assertEqual(taskbar.position(), 3)

    def test_classic_menu_undo(self):
        backup.snapshot("menu")
        taskbar.set_classic_menu(True)
        self.assertTrue(taskbar.classic_menu())
        backup.undo()
        self.assertFalse(taskbar.classic_menu())


class EffectsTest(unittest.TestCase):
    def test_presets(self):
        effects.apply_preset("performance")
        self.assertFalse(effects.get("menu_anim"))
        self.assertEqual(effects.menu_delay(), 0)
        effects.apply_preset("fluid")
        self.assertTrue(effects.get("minimize"))
        self.assertEqual(effects.menu_delay(), 100)


class IconsTest(unittest.TestCase):
    def test_build_and_apply_pack(self):
        from PySide6.QtGui import QGuiApplication
        self.app = QGuiApplication.instance() or QGuiApplication([])
        d = Path(tempfile.mkdtemp(dir=_TMP)) / "Demo"
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48">'
               '<rect x="4" y="8" width="40" height="32" rx="4" fill="#3584e4"/></svg>')
        for name in ("folder", "folder-documents", "computer", "user-trash", "user-trash-full"):
            f = d / "scalable" / "places" / f"{name}.svg"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(svg)
        (d / "index.theme").write_text("[Icon Theme]\nName=Demo\nDirectories=scalable/places\n")
        pack = icons.build_pack(d)
        meta = next(p for p in icons.installed() if p["name"] == "Demo")
        self.assertIn("computer", meta["icons"])
        self.assertIn("folder-pictures", meta["icons"])  # repli sur l'icône de dossier générique
        from PIL import Image
        ico = Image.open(pack / "computer.ico")
        self.assertIn((256, 256), ico.info["sizes"])
        docs = wp.known_folder("Documents") / "desktop.ini"
        original = docs.read_bytes() if docs.exists() else None  # Windows en crée souvent un
        icons.apply(meta)
        self.assertIn("IconResource=", docs.read_text(encoding="utf-16"))
        self.assertEqual(icons.current(), "Demo")
        icons.apply(None)
        icons.restore_folders()
        self.assertEqual(docs.read_bytes() if docs.exists() else None, original)


class LiveWallpaperTest(unittest.TestCase):
    def test_start_stop_and_undo(self):
        from unittest import mock
        from bestthemes_win.core import livewall
        with mock.patch.object(livewall, "_spawn") as spawn, \
                mock.patch.object(livewall, "running", return_value=False):
            backup.snapshot("avant fond animé")
            livewall.start("rain", "nord", 30, "max", wait=False)
            spawn.assert_called_once()
            self.assertIn("--live", wp.reg_value(livewall.RUN_KEY, livewall.RUN_NAME, ""))
            self.assertEqual(backup.undo(), "avant fond animé")
        self.assertFalse(livewall.config()["enabled"])
        self.assertIsNone(wp.reg_value(livewall.RUN_KEY, livewall.RUN_NAME))

    def test_player_renders_in_window(self):
        from bestthemes_win import live_player
        from bestthemes_win.core import livewall
        cfg = livewall.config()
        cfg.update(enabled=True, scene="flow", palette="dracula")
        livewall.save(cfg)
        w = live_player.LiveWidget(True)
        self.assertTrue(w.start())
        w._tick()
        self.assertTrue(all(a.img is not None for a in w.areas))
        w.timer.stop()
        w.check.stop()
        w.hide()
        cfg["enabled"] = False
        livewall.save(cfg)


class DataTest(unittest.TestCase):
    def test_packs_reference_existing_items(self):
        from bestthemes.core import generator
        from bestthemes_win.core import workshop
        ids = {i.id for i in workshop.items()}
        presets = {p["id"] for p in taskbar.PRESETS}
        fx = {p["id"] for p in effects.PRESETS}
        for pk in packs.load():
            generator.palette(pk["palette"])
            for key in ("cursor", "icons"):
                if pk.get(key):
                    self.assertIn(pk[key]["item"], ids, pk["id"])
            self.assertIn(pk.get("taskbar", "win11"), presets)
            self.assertIn(pk.get("effects", "default"), fx)


if __name__ == "__main__":
    unittest.main()
