"""Synthetic verifier tests never inspect or execute the pending real APK."""

import io
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
import wave
import xml.etree.ElementTree as ET
import zipfile

from tools import verify_volt_release as verifier


class VoltReleaseVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.before = Path(self.temp.name) / "before"
        self.current = Path(self.temp.name) / "current"
        self.ids = ["volt", "spark", *[f"robot{i}" for i in range(30)]]
        self.rows = {identity: ("title", "motion", "effect", ("joy",)) for identity in self.ids}
        src = self.before / "src"
        (src / "assets/art/portraits").mkdir(parents=True)
        (src / "assets/audio").mkdir()
        (src / "assets/animation").mkdir()
        (src / "assets/animation/game_robot.riv").write_bytes(b"synthetic unchanged Rive payload")
        for identity in self.ids:
            (src / f"assets/art/portraits/{identity}.svg").write_text(f"<svg>{identity}</svg>")
        for name in verifier.COMBAT_FILES:
            (src / name).write_text("# unchanged combat resolver\n")
        (src / "robot_abilities.py").write_text("_ROWS = " + repr(self.rows), encoding="utf-8")
        rml = self.before / "animation/rive/game_robot/scene.rml"
        rml.parent.mkdir(parents=True)
        root = ET.Element("Rive")
        for identity in self.ids:
            ET.SubElement(ET.SubElement(root, "Artboard", name="Spark" if identity == "spark" else identity), "Node", x="1")
            ET.SubElement(ET.SubElement(root, "ViewModel", name="Motion_" + identity), "Property", value="1")
        ET.ElementTree(root).write(rml)
        self.sound(src / "assets/audio/electric.wav", 10)
        shutil.copytree(self.before, self.current)
        (self.current / "src/assets/art/portraits/volt.svg").write_text("<svg>new Volt portrait</svg>")
        self.rows["volt"] = ("title", "new Volt choreography", "effect", ("joy", "jump"))
        self.write_rows()
        current_rml = self.current / "animation/rive/game_robot/scene.rml"
        tree = ET.parse(current_rml)
        tree.find("Artboard[@name='volt']/Node").set("x", "42")
        tree.find("ViewModel[@name='Motion_volt']/Property").set("value", "42")
        tree.write(current_rml)
        for i, name in enumerate(verifier.VOLT_SOUNDS):
            self.sound(self.current / "src/assets/audio" / name, 20 + i)

    def write_rows(self):
        (self.current / "src/robot_abilities.py").write_text("_ROWS = " + repr(self.rows), encoding="utf-8")

    @staticmethod
    def sound(path, frames):
        with wave.open(str(path), "wb") as sound:
            sound.setnchannels(1)
            sound.setsampwidth(2)
            sound.setframerate(22050)
            sound.writeframes(struct.pack("<h", 200) * frames)

    def package(self, *, missing_marker_abi=None, stale_audio=False, character_audio=False, stale_robot_audio=False):
        apk = Path(self.temp.name) / "synthetic.apk"
        embedded = io.BytesIO()
        with zipfile.ZipFile(embedded, "w") as app:
            for source in (self.current / "src/assets").rglob("*"):
                if source.is_file():
                    data = source.read_bytes()
                    if stale_audio and source.name == "volt_storm.wav":
                        data = b"stale audio"
                    if stale_robot_audio and source.name == "robot_dance_chime.wav":
                        data = b"stale character audio"
                    app.writestr(source.relative_to(self.current / "src").as_posix(), data)
        with zipfile.ZipFile(apk, "w") as package:
            package.writestr("assets/app.zip", embedded.getvalue())
            for abi in verifier.ABIS:
                markers = verifier.MARKERS + (verifier.ROBOT_MARKERS if character_audio else ())
                if abi == missing_marker_abi:
                    markers = markers[:-1]
                package.writestr(f"lib/{abi}/libapp.so", b"\0".join(marker.encode() for marker in markers))
        return apk

    def test_only_volt_may_change_in_portraits_rows_and_rml(self):
        scope = verifier.verify_scope(self.current, self.before)
        self.assertEqual(scope["counts"]["other_robot_portraits"], 31)
        self.assertEqual(scope["counts"]["other_ability_rows"], 31)
        self.assertEqual(scope["counts"]["other_artboards"], 31)
        self.assertEqual(scope["counts"]["other_view_models"], 31)
        self.assertEqual(scope["counts"]["new_volt_audio"], 4)

    def test_other_robot_metadata_change_is_rejected(self):
        self.rows["spark"] = ("changed",)
        self.write_rows()
        with self.assertRaisesRegex(verifier.VerificationError, "Other robot ability rows changed"):
            verifier.verify_scope(self.current, self.before)

    def test_unrelated_portrait_and_combat_changes_are_rejected(self):
        for relative in ["assets/art/portraits/spark.svg", "combat_rules.py"]:
            with self.subTest(relative=relative):
                current = self.current / "src" / relative
                original = current.read_bytes()
                current.write_bytes(b"unrelated change")
                with self.assertRaisesRegex(verifier.VerificationError, "Out-of-scope change"):
                    verifier.verify_scope(self.current, self.before)
                current.write_bytes(original)

    def test_other_view_model_change_is_rejected(self):
        current_rml = self.current / "animation/rive/game_robot/scene.rml"
        tree = ET.parse(current_rml)
        tree.find("ViewModel[@name='Motion_spark']/Property").set("value", "99")
        tree.write(current_rml)
        with self.assertRaisesRegex(verifier.VerificationError, "Out-of-scope RML ViewModel change"):
            verifier.verify_scope(self.current, self.before)

    def test_old_sound_changes_are_rejected(self):
        self.sound(self.current / "src/assets/audio/electric.wav", 50)
        with self.assertRaisesRegex(verifier.VerificationError, "Out-of-scope change: audio/electric.wav"):
            verifier.verify_scope(self.current, self.before)

    def test_real_package_content_checks_cover_all_three_abis(self):
        scope = verifier.verify_scope(self.current, self.before)
        package = verifier.verify_package(self.package(), scope, self.current)
        self.assertEqual(package["counts"]["abis"], 3)
        self.assertEqual(package["counts"]["markers_per_abi"], 6)
        self.assertIn("assets/audio/volt_storm.wav", package["asset_checks"])
        self.assertIn("assets/art/portraits/spark.svg", package["asset_checks"])

    def test_missing_native_marker_or_stale_packaged_audio_is_rejected(self):
        scope = verifier.verify_scope(self.current, self.before)
        for options in [{"missing_marker_abi": "armeabi-v7a"}, {"stale_audio": True}]:
            with self.subTest(options=options), self.assertRaises(verifier.VerificationError):
                verifier.verify_package(self.package(**options), scope, self.current)

    def polish_baseline(self):
        """v35 starts with the four Volt sounds already shipped in v34."""
        for name in verifier.VOLT_SOUNDS:
            shutil.copyfile(self.current / "src/assets/audio" / name, self.before / "src/assets/audio" / name)
        for i, name in enumerate(verifier.ROBOT_SOUNDS):
            self.sound(self.current / "src/assets/audio" / name, 100 + i)

    def test_v36_adds_only_three_small_music_tracks_preserving_every_previous_wav(self):
        self.polish_baseline()
        for name in verifier.ROBOT_SOUNDS:
            shutil.copyfile(self.current/'src/assets/audio'/name,self.before/'src/assets/audio'/name)
        for name in verifier.MUSIC_SOUNDS:
            (self.current/'src/assets/audio'/name).write_bytes(b'OggS'+b'\x00'*1500)
        scope=verifier.verify_scope(self.current,self.before,character_audio=True,application_music=True)
        self.assertEqual(scope['counts']['new_music_audio'],3)
        self.assertEqual(scope['counts']['new_robot_audio'],0)
        (self.current/'src/assets/audio/music_workshop.ogg').write_bytes(b'invalid')
        with self.assertRaisesRegex(verifier.VerificationError,'Invalid or oversized music'):
            verifier.verify_scope(self.current,self.before,character_audio=True,application_music=True)

    def test_v35_permits_only_the_explicit_character_sound_inventory(self):
        self.polish_baseline()
        scope = verifier.verify_scope(self.current, self.before, character_audio=True)
        self.assertEqual(scope["counts"]["unchanged_existing_audio"], 5)
        self.assertEqual(scope["counts"]["new_volt_audio"], 0)
        self.assertEqual(scope["counts"]["new_robot_audio"], 18)
        self.assertEqual(len(scope["robot_audio"]), 18)
        self.assertEqual(scope["counts"]["other_artboards"], 31)
        self.assertEqual(scope["counts"]["unchanged_combat_files"], 3)
        unexpected = self.current / "src/assets/audio/robot_unreviewed.wav"
        self.sound(unexpected, 120)
        with self.assertRaisesRegex(verifier.VerificationError, "Unexpected new audio inventory"):
            verifier.verify_scope(self.current, self.before, character_audio=True)
        unexpected.unlink()
        (self.current / "src/assets/audio" / verifier.ROBOT_SOUNDS[0]).unlink()
        with self.assertRaisesRegex(verifier.VerificationError, "Unexpected new audio inventory"):
            verifier.verify_scope(self.current, self.before, character_audio=True)

    def test_v35_preserves_the_previously_shipped_volt_sounds(self):
        self.polish_baseline()
        self.sound(self.current / "src/assets/audio/volt_storm.wav", 500)
        with self.assertRaisesRegex(verifier.VerificationError, "Out-of-scope change: audio/volt_storm.wav"):
            verifier.verify_scope(self.current, self.before, character_audio=True)

    def test_v35_requires_distinct_valid_character_wavs(self):
        self.polish_baseline()
        source = self.current / "src/assets/audio" / verifier.ROBOT_SOUNDS[0]
        target = self.current / "src/assets/audio" / verifier.ROBOT_SOUNDS[1]
        shutil.copyfile(source, target)
        with self.assertRaisesRegex(verifier.VerificationError, "sound files are identical"):
            verifier.verify_scope(self.current, self.before, character_audio=True)

    def test_v35_package_checks_new_character_sounds_and_native_markers(self):
        self.polish_baseline()
        scope = verifier.verify_scope(self.current, self.before, character_audio=True)
        package = verifier.verify_package(self.package(character_audio=True), scope, self.current)
        self.assertEqual(package["counts"]["markers_per_abi"], 9)
        self.assertIn("assets/audio/robot_dance_chime.wav", package["asset_checks"])
        for options in [{"character_audio": False},
                        {"character_audio": True, "missing_marker_abi": "arm64-v8a"},
                        {"character_audio": True, "stale_robot_audio": True}]:
            with self.subTest(options=options), self.assertRaises(verifier.VerificationError):
                verifier.verify_package(self.package(**options), scope, self.current)


if __name__ == "__main__":
    unittest.main()
