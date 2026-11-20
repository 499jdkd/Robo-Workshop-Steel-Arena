"""Build the complete Windows game without modifying any player save."""

import base64
import argparse
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

from flutter_cached import command as flutter_command, environment as flutter_environment

ROOT = Path(__file__).resolve().parents[1]
FLUTTER = Path.home() / "flutter/3.44.8/bin/flutter.bat"


def bundle_wasm(destination):
    with urllib.request.urlopen(
        "https://registry.npmjs.org/@rive-app/flutter-native-wasm/44.0.0", timeout=30
    ) as response:
        package = json.load(response)
    with urllib.request.urlopen(package["dist"]["tarball"], timeout=60) as response:
        archive = response.read()
    expected = package["dist"]["integrity"].removeprefix("sha512-")
    if base64.b64encode(hashlib.sha512(archive).digest()).decode() != expected:
        raise RuntimeError("Rive runtime package integrity check failed")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        for member in tar.getmembers():
            parts = Path(member.name).parts
            if not member.isfile():
                continue
            if len(parts) == 2 and parts[1].lower().startswith(("license", "notice")):
                relative = Path(parts[1])
            elif len(parts) >= 3 and parts[1] in {"wasm", "wasm_compatibility"}:
                relative = Path(*parts[1:])
            else:
                continue
            target = (destination / relative).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise RuntimeError("Unsafe runtime archive path")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tar.extractfile(member).read())
    (destination / "runtime-source.json").write_text(
        json.dumps(
            {
                "package": package["name"],
                "version": package["version"],
                "integrity": package["dist"]["integrity"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-number", type=int, default=21)
    args = parser.parse_args()
    project = ROOT / "tools/game_client"
    subprocess.run(
        [
            *flutter_command(),
            "build",
            "web",
            "--release",
            "--no-web-resources-cdn",
            "--no-wasm-dry-run",
            "--dart-define=RIVE_NATIVE_WASM_HOST=/rive/",
        ],
        cwd=project,
        env=flutter_environment(),
        check=True,
    )
    bundle_wasm(project / "build/web/rive")
    sys.path.insert(0, str(ROOT / "src"))
    from desktop_startup import write_contract
    write_contract(ROOT, project / "build/web")
    output = ROOT / f"build/windows-motion-v{args.build_number}"
    if (output / "Clicker").exists():
        raise RuntimeError("Output already exists; retain it and choose a new version")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--onedir",
            "--windowed",
            "--name",
            "Clicker",
            "--distpath",
            str(output),
            "--workpath",
            str(ROOT / f".cache/windows-motion-v{args.build_number}"),
            "--specpath",
            str(ROOT / f".cache/windows-motion-v{args.build_number}"),
            "--paths",
            str(ROOT / "src"),
            "--hidden-import",
            "main",
            *[arg for module in ("arena_screen", "profile_screen", "shop_screen", "scene_focus", "feature_screens", "collection_ui")
              for arg in ("--hidden-import", module)],
            "--icon",
            str(ROOT / "src/assets/icon.png"),
            "--collect-all",
            "webview",
            "--collect-all",
            "flet_web",
            "--collect-all",
            "flet_rive",
            "--collect-all",
            "flet_ads",
            "--add-data",
            f"{ROOT / 'src/assets'};game_assets",
            "--add-data",
            f"{project / 'build/web'};client",
            str(ROOT / "tools/windows_game.py"),
        ],
        cwd=ROOT,
        check=True,
    )
    shutil.make_archive(str(output / "Clicker-Windows"), "zip", output, "Clicker")
    print(f"Windows game: {output / 'Clicker/Clicker.exe'}")


if __name__ == "__main__":
    main()
