# test_plugins/test_updater.py
"""Unit tests for GitHub auto-update channel selection and tree swap."""
import unittest
from pathlib import Path

from utils.update_checker import normalize_update_channel, should_auto_install
from utils.updater import is_preserved_rel, restore_install_tree, swap_install_tree


class TestUpdateChannel(unittest.TestCase):
    def test_normalize_unknown_channel_uses_release(self):
        self.assertEqual(normalize_update_channel("release"), "release")
        self.assertEqual(normalize_update_channel("MAIN"), "main")
        self.assertEqual(normalize_update_channel("nightly"), "release")
        self.assertEqual(normalize_update_channel(""), "release")

    def test_release_installs_only_when_newer(self):
        target = {
            "channel": "release",
            "ref": "v1.5.0",
            "version": "1.5.0",
            "zipball_url": "https://example.test/v1.5.0.zip",
        }
        self.assertTrue(should_auto_install(target, "1.4.0", None))
        self.assertFalse(should_auto_install(target, "1.5.0", None))
        self.assertFalse(
            should_auto_install(target, "1.4.0", {"channel": "release", "ref": "v1.5.0"})
        )

    def test_main_installs_when_sha_changes(self):
        target = {
            "channel": "main",
            "ref": "abc123",
            "zipball_url": "https://example.test/abc123.zip",
        }
        self.assertTrue(should_auto_install(target, "1.4.0", None))
        self.assertTrue(
            should_auto_install(target, "1.4.0", {"channel": "main", "ref": "old"})
        )
        self.assertFalse(
            should_auto_install(target, "1.4.0", {"channel": "main", "ref": "abc123"})
        )

    def test_preserved_paths(self):
        self.assertTrue(is_preserved_rel("config.ini"))
        self.assertTrue(is_preserved_rel("solis_history.db"))
        self.assertTrue(is_preserved_rel("venv/Lib/site.py"))
        self.assertTrue(is_preserved_rel("solar_monitoring.log.1"))
        self.assertFalse(is_preserved_rel("main.py"))
        self.assertFalse(is_preserved_rel("plugins/battery/seplos_bms_v2_plugin.py"))


class TestTreeSwap(unittest.TestCase):
    def test_swap_keeps_user_files_and_can_roll_back(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            install = Path(tmp) / "install"
            new_tree = Path(tmp) / "new"
            install.mkdir()
            (install / "config.ini").write_text("user-config", encoding="utf-8")
            (install / "solis_history.db").write_text("history", encoding="utf-8")
            (install / "main.py").write_text("old", encoding="utf-8")
            (install / "old_only.py").write_text("gone", encoding="utf-8")
            (install / "venv").mkdir()
            (install / "venv" / "marker.txt").write_text("keep", encoding="utf-8")

            (new_tree / "pkg").mkdir(parents=True)
            payload = new_tree / "pkg"
            (payload / "config.ini").write_text("evil", encoding="utf-8")
            (payload / "main.py").write_text("new", encoding="utf-8")
            (payload / "new_only.py").write_text("added", encoding="utf-8")

            backup = swap_install_tree(install, payload)
            self.assertEqual((install / "config.ini").read_text(encoding="utf-8"), "user-config")
            self.assertEqual((install / "solis_history.db").read_text(encoding="utf-8"), "history")
            self.assertEqual((install / "venv" / "marker.txt").read_text(encoding="utf-8"), "keep")
            self.assertEqual((install / "main.py").read_text(encoding="utf-8"), "new")
            self.assertTrue((install / "new_only.py").is_file())
            self.assertFalse((install / "old_only.py").exists())

            restore_install_tree(install, backup)
            self.assertEqual((install / "main.py").read_text(encoding="utf-8"), "old")
            self.assertTrue((install / "old_only.py").is_file())
            self.assertFalse((install / "new_only.py").exists())
            self.assertEqual((install / "config.ini").read_text(encoding="utf-8"), "user-config")


if __name__ == "__main__":
    unittest.main()
