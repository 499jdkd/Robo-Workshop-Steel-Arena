"""Check the robot APK's payload against the generated art and current staging."""

import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APK = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build/apk-robots/clicker.apk"
STAGED = ROOT / "build/python-app"
manifest = json.loads(
    (ROOT / "artwork/robot_collection/encoded-assets.json").read_text(encoding="utf-8")
)
modules = [
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
    "robot_catalog",
    "robot_ui",
    "asset_layout",
]
with zipfile.ZipFile(APK) as apk:
    assert apk.testzip() is None, "Damaged APK"
    with zipfile.ZipFile(io.BytesIO(apk.read("assets/app.zip"))) as app:
        assert app.testzip() is None, "Damaged Python payload"
        for module in modules:
            name = f"{module}.pyc"
            assert app.read(name) == (STAGED / name).read_bytes(), (
                f"Stale module: {name}"
            )
        for record in manifest:
            name = "assets/" + record["asset"]
            data = app.read(name)
            assert hashlib.sha256(data).hexdigest() == record["sha256"], (
                f"Stale artwork: {name}"
            )
            assert data == (ROOT / "src" / name).read_bytes(), (
                f"Different artwork: {name}"
            )
        unused = [
            "tap.png",
            "image3.png",
            "image4.png",
            "image5.png",
            "boost.png",
            "robot2.png",
            *(f"workshop_{index}.svg" for index in range(6)),
        ]
        assert not any("assets/" + name in app.namelist() for name in unused), (
            "Unused old art bundled"
        )
    with zipfile.ZipFile(io.BytesIO(apk.read("assets/sitepackages.zip"))) as packages:
        for dependency in ("flet", "flet_ads", "httpx"):
            assert any(
                name.startswith(dependency + "/") for name in packages.namelist()
            ), f"Missing {dependency}"
    for architecture in ("arm64-v8a", "armeabi-v7a", "x86_64"):
        assert f"lib/{architecture}/libpython3.14.so" in apk.namelist(), (
            f"Missing {architecture}"
        )

print(
    json.dumps(
        {
            "apk": str(APK),
            "bytes": APK.stat().st_size,
            "sha256": hashlib.sha256(APK.read_bytes()).hexdigest(),
            "checked_modules": len(modules),
            "checked_art_assets": len(manifest),
            "webp_bytes": sum(record["bytes"] for record in manifest),
            "checked_abis": 3,
        },
        indent=2,
    )
)
