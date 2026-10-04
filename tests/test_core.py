"""Tests des fonctions cœur (sans toucher au bureau réel).

Lancer :  python3 -m unittest discover -s tests -v
"""
import io
import os
import shutil
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

_TMP = tempfile.mkdtemp(prefix="bt-test-")
os.environ["HOME"] = _TMP
os.environ["XDG_DATA_HOME"] = os.path.join(_TMP, ".local/share")
os.environ["XDG_CACHE_HOME"] = os.path.join(_TMP, ".cache")

from bestthemes.core import (backup, colors, generator, installer, paths,  # noqa: E402
                             scanner, wallpaper)
from bestthemes.workshop import catalog  # noqa: E402


def _add(tar, name, data=b"x"):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


class InstallerTest(unittest.TestCase):
    def setUp(self):
        paths.ensure_dirs()
        self.tmp = Path(tempfile.mkdtemp(dir=_TMP))

    def test_multi_theme_tar(self):
        arc = self.tmp / "pack.tar.gz"
        with tarfile.open(arc, "w:gz") as t:
            _add(t, "Pack/MyGtk/gtk-3.0/gtk.css", b"window{}")
            _add(t, "Pack/MyGtk/xfwm4/themerc", b"")
            _add(t, "Pack/MyIcons/index.theme", b"[Icon Theme]\nName=My\nDirectories=48x48/apps\n")
            _add(t, "Pack/MyCursor/cursors/left_ptr", b"Xcur")
            _add(t, "Pack/MyCursor/index.theme", b"[Icon Theme]\nName=C\n")
        items = installer.install_archive(arc, source_id="t1")
        kinds = {n: set(k) for n, k, _ in items}
        self.assertEqual(kinds["MyGtk"], {"gtk", "xfwm4"})
        self.assertEqual(kinds["MyIcons"], {"icons"})
        self.assertEqual(kinds["MyCursor"], {"cursors"})
        self.assertTrue((paths.USER_THEMES / "MyGtk" / "gtk-3.0" / "gtk.css").is_file())
        self.assertTrue((paths.USER_ICONS / "MyCursor" / "cursors").is_dir())
        self.assertTrue(installer.is_installed("t1"))
        installer.uninstall_source("t1")
        self.assertFalse((paths.USER_THEMES / "MyGtk").exists())

    def test_path_traversal_zip_rejected(self):
        arc = self.tmp / "evil.zip"
        with zipfile.ZipFile(arc, "w") as z:
            z.writestr("../../evil.txt", "boom")
        with self.assertRaises(installer.InstallError):
            installer.extract(arc, self.tmp / "out")
        self.assertFalse((self.tmp.parent / "evil.txt").exists())

    def test_path_traversal_tar_rejected(self):
        arc = self.tmp / "evil.tar"
        with tarfile.open(arc, "w") as t:
            _add(t, "../evil2.txt")
        with self.assertRaises(installer.InstallError):
            installer.extract(arc, self.tmp / "out")

    def test_nested_zip_of_plank_theme(self):
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, "w") as z:
            z.writestr("Dark/dock.theme", "[PlankTheme]\n")
        arc = self.tmp / "outer.zip"
        with zipfile.ZipFile(arc, "w") as z:
            z.writestr("themes/Dark.zip", inner.getvalue())
        items = installer.install_archive(arc, source_id="t2")
        self.assertEqual(items[0][0], "Dark")
        self.assertTrue((paths.USER_PLANK_THEMES / "Dark" / "dock.theme").is_file())

    def test_no_theme(self):
        arc = self.tmp / "nothing.tar.gz"
        with tarfile.open(arc, "w:gz") as t:
            _add(t, "README.md")
        with self.assertRaises(installer.InstallError):
            installer.install_archive(arc)

    def test_user_path_guard(self):
        self.assertFalse(paths.is_user_path("/usr/share/themes/Adwaita"))
        self.assertFalse(paths.is_user_path(paths.USER_THEMES))
        with self.assertRaises(installer.InstallError):
            installer.uninstall_path("/usr/share/themes/Adwaita")


class GeneratorTest(unittest.TestCase):
    def test_all_palettes_generate(self):
        for p in generator.load_palettes():
            for style in generator.BUTTON_STYLES:
                d = Path(tempfile.mkdtemp(dir=_TMP))
                res = generator.generate(p, style, dest_root=d)
                root = d / res["gtk"]
                css = (root / "gtk-3.0" / "gtk.css").read_text()
                self.assertNotIn("${", css, f"variable non remplacée ({p['name']})")
                self.assertTrue((root / "xfwm4" / "themerc").is_file())
                self.assertTrue((root / "xfwm4" / "close-prelight.png").is_file())
                self.assertTrue((d / "plank" / res["plank"] / "dock.theme").is_file())
                self.assertEqual(scanner.detect_kinds(root), {"gtk", "xfwm4"})
                shutil.rmtree(d)

    def test_slug_accents(self):
        self.assertEqual(generator.slug("Forêt d'été"), "Foret-d-ete")

    def test_text_contrast(self):
        for p in generator.load_palettes():
            v = generator.derive(p)
            self.assertGreaterEqual(colors.contrast(v["bg"], v["fg"]), 4.5, p["name"])


class AnimationsTest(unittest.TestCase):
    def test_layout_conversion(self):
        from bestthemes.core import animations
        self.assertEqual(animations.xfwm_to_gnome_layout("CHM|"), "close,minimize,maximize:")
        self.assertEqual(animations.xfwm_to_gnome_layout("O|HMC"), "menu:minimize,maximize,close")

    def test_presets_use_known_effects(self):
        from bestthemes.core import animations
        for p in animations.PRESETS:
            for k in ("open", "close", "minimize"):
                self.assertIn(p[k], animations.EFFECTS)


class WallpaperTest(unittest.TestCase):
    def test_all_styles(self):
        p = generator.palette("nord")
        for style in wallpaper.STYLES:
            s = wallpaper.render(p, style, 160, 90)
            self.assertEqual((s.get_width(), s.get_height()), (160, 90))


class LiveTest(unittest.TestCase):
    def test_all_scenes_animate(self):
        from bestthemes.core import live
        for pid in ("nord", "catppuccin-latte"):  # palette sombre et claire
            p = generator.palette(pid)
            for sid in live.SCENES:
                sc = live.create(sid, 160, 90, p)
                a = bytes(live.render(sc, 1.0).get_data())
                b = bytes(live.render(sc, 3.0).get_data())
                self.assertNotEqual(a, b, f"{sid} ne bouge pas")

    def test_render_size_capped(self):
        from bestthemes.core import livewall
        self.assertEqual(livewall.render_size(3840, 2160, "balanced"), (1280, 720))
        self.assertEqual(livewall.render_size(1920, 1080, "eco"), (960, 540))

    def test_restore_disabled_is_noop(self):
        from bestthemes.core import livewall
        with mock.patch.object(livewall, "_spawn") as spawn, mock.patch.object(livewall, "ensure_desktop") as ed:
            livewall.restore(None)
            livewall.restore({"enabled": False})
        spawn.assert_not_called()
        ed.assert_not_called()
        self.assertFalse(livewall.config()["enabled"])

    def test_start_stop_config_and_autostart(self):
        from bestthemes.core import livewall
        with mock.patch.object(livewall, "_spawn"), mock.patch.object(livewall, "running", return_value=False):
            livewall.start("snow", "dracula", 15, "eco", wait=False)
            self.assertEqual(livewall.capture(), {"enabled": True, "scene": "snow", "palette": "dracula",
                                                  "fps": 15, "quality": "eco"})
            self.assertIn("--live", livewall.AUTOSTART.read_text())
            livewall.stop()
        self.assertFalse(livewall.config()["enabled"])
        self.assertFalse(livewall.AUTOSTART.exists())


class GalleryTest(unittest.TestCase):
    def test_commons_parsing_keeps_hd_landscapes(self):
        from bestthemes.core import wallgallery as g

        def info(w, h, mime="image/jpeg"):
            return {"width": w, "height": h, "mime": mime, "size": 1000, "url": "https://u/orig.jpg",
                    "descriptionurl": "https://c/File:x",
                    "thumburl": "https://thumb/a/ab/X.jpg/960px-X.jpg",
                    "extmetadata": {"Artist": {"value": "<a href='x'>Jean</a>"},
                                    "LicenseShortName": {"value": "CC BY-SA 4.0"}}}

        data = {"query": {"pages": [
            {"pageid": 1, "title": "File:Big.jpg", "imageinfo": [info(5000, 3000)]},
            {"pageid": 2, "title": "File:Portrait.jpg", "imageinfo": [info(3000, 5000)]},
            {"pageid": 3, "title": "File:Small.jpg", "imageinfo": [info(1200, 800)]},
            {"pageid": 4, "title": "File:Anim.gif", "imageinfo": [info(4000, 2000, "image/gif")]},
        ]}, "continue": {"gcmcontinue": "abc", "continue": "gcmcontinue||"}}
        with mock.patch.object(g, "_get_json", return_value=data):
            photos, cont = g.browse("mountains")
        self.assertEqual([p.id for p in photos], ["commons-1"])
        ph = photos[0]
        self.assertEqual(ph.credit, "Jean — CC BY-SA 4.0")
        self.assertEqual(ph.best_url(1920), "https://thumb/a/ab/X.jpg/1920px-X.jpg")
        self.assertEqual(ph.best_url(2560), "https://thumb/a/ab/X.jpg/3840px-X.jpg")
        self.assertEqual(cont["gcmcontinue"], "abc")

    def test_nasa_parsing(self):
        from bestthemes.core import wallgallery as g
        data = {"collection": {"items": [{
            "data": [{"nasa_id": "PIA1", "title": "Nébuleuse", "center": "JPL"}],
            "links": [{"href": "https://n/PIA1~medium.jpg", "rel": "alternate"},
                      {"href": "https://n/PIA1~thumb.jpg", "rel": "preview"},
                      {"href": "https://n/PIA1~orig.jpg", "rel": "canonical", "width": 4000, "height": 2000,
                       "size": 5000}]}], "links": [{"rel": "next"}]}}
        with mock.patch.object(g, "_get_json", return_value=data):
            photos, cont = g.browse("nebulae")
        self.assertEqual(len(photos), 1)
        self.assertEqual(photos[0].best_url(3840), "https://n/PIA1~orig.jpg")
        self.assertEqual(photos[0].license, "Domaine public")
        self.assertEqual(cont, 2)


class DataTest(unittest.TestCase):
    def test_catalog(self):
        ids = set()
        for it in catalog.items():
            self.assertNotIn(it.id, ids)
            ids.add(it.id)
            self.assertIn(it.kind, scanner.KINDS)
            self.assertTrue(it.pling or it.files, it.id)

    def test_packs_reference_valid_data(self):
        from bestthemes.core import packs, panel
        presets = {p["id"] for p in panel.PRESETS}
        for pk in packs.load():
            generator.palette(pk["palette"])
            if pk.get("panel"):
                self.assertIn(pk["panel"], presets)
            for key in ("gtk", "icons", "cursors", "plank"):
                spec = pk.get(key)
                if isinstance(spec, dict) and "catalog" in spec:
                    self.assertIsNotNone(catalog.get(spec["catalog"]), spec)
                if isinstance(spec, dict) and "generate" in spec:
                    generator.palette(spec["generate"])


class BackupTest(unittest.TestCase):
    def test_snapshot_undo_roundtrip(self):
        store = {("xsettings", "/Net/ThemeName"): "Mint-Y",
                 ("xfce4-panel", "/panels"): ["1"],
                 ("xfce4-panel", "/panels/panel-1/size"): "32"}

        def fake_get(ch, prop, default=None):
            return store.get((ch, prop), default)

        def fake_set(ch, prop, value, vtype=None):
            store[(ch, prop)] = str(value).lower() if isinstance(value, bool) else str(value)
            return True

        def fake_reset(ch, prop):
            store.pop((ch, prop), None)
            return True

        with mock.patch.multiple(backup.xfconf, get=fake_get, set=fake_set, reset=fake_reset,
                                 list_values=lambda *a: {}, set_array=lambda *a, **k: True), \
                mock.patch.object(backup.plank, "capture", return_value=None), \
                mock.patch.object(backup.animations, "capture", return_value=None), \
                mock.patch.object(backup.livewall, "restore") as live_restore:
            backup.snapshot("test")
            store[("xsettings", "/Net/ThemeName")] = "Other"
            store[("xfce4-panel", "/panels/panel-1/size")] = "48"
            store[("xfce4-panel", "/panels/panel-1/mode")] = "2"
            self.assertEqual(backup.undo(), "test")
        live_restore.assert_called_once_with({"enabled": False, "scene": "aurora", "palette": "nord",
                                              "fps": 24, "quality": "balanced"})
        self.assertEqual(store[("xsettings", "/Net/ThemeName")], "Mint-Y")
        self.assertEqual(store[("xfce4-panel", "/panels/panel-1/size")], "32")
        self.assertNotIn(("xfce4-panel", "/panels/panel-1/mode"), store)


if __name__ == "__main__":
    unittest.main()
