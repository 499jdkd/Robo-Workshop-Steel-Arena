"""Play-test variants must never rewrite the installed-game source or include keys."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_google_play as play


class PlayBuildTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / ".cache/play-build-tests"
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assertTrue(self.root.resolve().is_relative_to(parent.resolve()))
        (self.root / "src/assets").mkdir(parents=True)
        (self.root / "src/advertising.py").write_text(
            'TEST_BANNER_UNIT_ID="demo"\nBANNER_UNIT_ID = "live-banner"\n',
            encoding="utf-8",
        )
        (self.root / "src/rewarded_ads.py").write_text(
            'REWARDED_UNIT_ID = "live-video"\n', encoding="utf-8"
        )
        (self.root / "src/assets/game.txt").write_text("art", encoding="utf-8")
        (self.root / "pyproject.toml").write_text(
            '[tool.flet.android.meta_data]\n"com.google.android.gms.ads.APPLICATION_ID"="live-app"\n'
            '[tool.flet.flutter.pubspec.dependency_overrides]\nflet_ads = { path = "../../extensions/flet_ads" }\n',
            encoding="utf-8",
        )
        (self.root / "private-upload.jks").write_text("private", encoding="utf-8")
        self.stage = self.root / ".cache/play-17"

    def prepare(self, mode="test"):
        return play.prepare_stage(
            self.root, self.stage, number=17, version="0.1.1", ads_mode=mode
        )

    def test_test_ads_only_change_the_isolated_copy(self):
        original = (self.root / "src/advertising.py").read_bytes()
        self.prepare()
        self.assertEqual((self.root / "src/advertising.py").read_bytes(), original)
        self.assertIn(
            play.TEST_BANNER_ID, (self.stage / "src/advertising.py").read_text()
        )
        self.assertIn(
            play.TEST_REWARDED_ID, (self.stage / "src/rewarded_ads.py").read_text()
        )
        self.assertIn(play.TEST_APP_ID, (self.stage / "pyproject.toml").read_text())
        self.assertFalse((self.stage / "private-upload.jks").exists())
        self.assertEqual((self.stage / "src/assets/game.txt").read_text(), "art")

    def test_live_variant_keeps_owner_units(self):
        self.prepare("live")
        self.assertIn('"live-video"', (self.stage / "src/rewarded_ads.py").read_text())
        self.assertIn('"live-app"', (self.stage / "pyproject.toml").read_text())

    def test_live_flet_storage_is_never_staged_or_part_of_build_input(self):
        storage = self.root / "src/.flet/storage/data"
        storage.mkdir(parents=True)
        save = storage / "workshop-save-v2.json"
        save.write_text('"synthetic private save"', encoding="utf-8")
        expected = self.prepare()
        self.assertFalse((self.stage / "src/.flet").exists())
        self.assertFalse(any(".flet" in Path(name).parts
                             for name in expected["input"]["base_sources"]))
        save.write_text('"changed while the app is open"', encoding="utf-8")
        self.assertEqual(self.prepare(), expected)
        self.assertEqual(save.read_text(encoding="utf-8"),
                         '"changed while the app is open"')

    def test_identical_stage_can_be_reused_but_changed_input_is_rejected(self):
        expected = self.prepare()
        self.assertEqual(self.prepare(), expected)
        (self.root / "src/assets/game.txt").write_text("changed")
        with self.assertRaisesRegex(ValueError, "Build inputs changed"):
            self.prepare()

    def test_tampered_stage_is_not_silently_used(self):
        self.prepare()
        (self.stage / "src/rewarded_ads.py").write_text('REWARDED_UNIT_ID="other"')
        with self.assertRaisesRegex(ValueError, "Staged source changed"):
            self.prepare()

    def test_assignment_requires_an_exact_constant_name(self):
        with self.assertRaises(ValueError):
            play.set_string_constant('TEST_BANNER_UNIT_ID="a"', "BANNER_UNIT_ID", "b")
        result = play.set_string_constant(
            'TEST_BANNER_UNIT_ID="a"\nBANNER_UNIT_ID="x"\n', "BANNER_UNIT_ID", "b"
        )
        self.assertIn('TEST_BANNER_UNIT_ID="a"', result)
        self.assertIn('BANNER_UNIT_ID = "b"', result)


if __name__ == "__main__":
    unittest.main()
