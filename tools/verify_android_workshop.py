"""Inspect the built APK without installing it or contacting the player API."""

import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APK = (
    Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build/apk-workshop/clicker.apk"
)
STAGED = ROOT / "build/python-app"
MODULES = (
    "main",
    "main_screen",
    "shop_screen",
    "profile_screen",
    "leaderboard_screen",
    "gameplay",
    "game_session",
    "local_store",
    "leaderboard",
    "ui_shared",
    "advertising",
)

with zipfile.ZipFile(APK) as apk:
    assert apk.testzip() is None, "APK contains damaged files"
    with zipfile.ZipFile(io.BytesIO(apk.read("assets/app.zip"))) as app:
        assert app.testzip() is None, "Python app archive is damaged"
        for module in MODULES:
            name = f"{module}.pyc"
            assert app.read(name) == (STAGED / name).read_bytes(), (
                f"Stale module: {name}"
            )
        for stage in range(6):
            name = f"assets/workshop_{stage}.svg"
            assert app.read(name) == (ROOT / "src" / name).read_bytes(), (
                f"Missing scene: {name}"
            )
        for unused in (
            "assets/tap.png",
            "assets/image3.png",
            "fix.pyc",
            "some.pyc",
            "tempCodeRunnerFile.pyc",
        ):
            assert unused not in app.namelist(), f"Unused file still bundled: {unused}"
    with zipfile.ZipFile(io.BytesIO(apk.read("assets/sitepackages.zip"))) as packages:
        names = packages.namelist()
        for dependency in ("flet", "flet_ads", "httpx"):
            assert any(name.startswith(dependency + "/") for name in names), (
                f"Missing {dependency}"
            )
    for arch in ("arm64-v8a", "armeabi-v7a", "x86_64"):
        assert f"lib/{arch}/libpython3.14.so" in apk.namelist(), f"Missing {arch}"

print(
    json.dumps(
        {
            "apk": str(APK),
            "bytes": APK.stat().st_size,
            "sha256": hashlib.sha256(APK.read_bytes()).hexdigest(),
            "checked_modules": len(MODULES),
            "checked_scenes": 6,
            "checked_abis": 3,
        },
        indent=2,
    )
)
