"""Verify bundled Python code, Rive/sound/font assets and the Windows archive."""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-number", type=int, default=23)
    args = parser.parse_args()
    root = ROOT / f"build/windows-motion-v{args.build_number}"
    game = root / "Clicker"
    exe = game / "Clicker.exe"
    archive = CArchiveReader(str(exe)).open_embedded_archive("PYZ.pyz")
    checked = []
    for name in ("main", "gameplay", "game_session", "battle_ui", "game_animation", "armory",
                 "armory_ui", "online_arena", "online_ui", "online_focus", "robot_catalog",
                 "robot_ui", "scene_focus", "profile_screen", "local_store", "progression"):
        code = archive.extract(name)
        source = ROOT / "src" / (name + ".py")
        assert code == compile(source.read_bytes(), code.co_filename, "exec", dont_inherit=True), name
        checked.append(name)
    assets = game / "_internal/game_assets"
    count = 0
    for source in (ROOT / "src/assets").rglob("*"):
        if source.is_file():
            relative = source.relative_to(ROOT / "src/assets")
            assert (assets / relative).read_bytes() == source.read_bytes(), str(relative)
            count += 1
    client = game / "_internal/client"
    assert (client / "main.dart.js").read_bytes() == (ROOT / "tools/game_client/build/web/main.dart.js").read_bytes()
    fonts = json.loads((client / "assets/FontManifest.json").read_text(encoding="utf-8"))
    roboto = next(f for f in fonts if f["family"] == "Roboto")
    assert len(roboto["fonts"]) == 4
    for font in roboto["fonts"]:
        assert (client / "assets" / font["asset"]).is_file()
    assert (client / "rive/wasm/rive_native.wasm").stat().st_size > 1_000_000
    distribution = root / "Clicker-Windows.zip"
    with zipfile.ZipFile(distribution) as package:
        damaged = package.testzip()
        assert damaged is None, damaged
        assert not any(".signing" in name or name.endswith((".jks", ".keystore")) for name in package.namelist())
        assert package.read("Clicker/Clicker.exe") == exe.read_bytes()
    report = dict(exe=str(exe), zip=str(distribution), bytes=distribution.stat().st_size,
                  sha256=hashlib.sha256(distribution.read_bytes()).hexdigest(),
                  verified_modules=checked, verified_assets=count,
                  published_rive_bytes=(assets / "animation/game_robot.riv").stat().st_size,
                  bundled_roboto_fonts=4, private_keys_bundled=False)
    validation = root / "validation"
    validation.mkdir(exist_ok=True)
    (validation / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
