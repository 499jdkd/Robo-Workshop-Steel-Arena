"""Verify the current APK against current Python staging and art manifest."""

import hashlib
import io
import json
import struct
import sys
import zipfile
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
APK = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else ROOT / "build/apk-rewarded-v16/clicker.apk"
)
settings = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
excludes = {
    name.replace("\\", "/") for name in settings["tool"]["flet"]["app"]["exclude"]
}
sources = [path for path in (ROOT / "src").glob("*.py") if path.name not in excludes]
art = []
for manifest in ("encoded-assets.json", "motion-assets.json"):
    art.extend(
        json.loads(
            (ROOT / "artwork/robot_collection" / manifest).read_text(encoding="utf-8")
        )
    )
with zipfile.ZipFile(APK) as apk:
    assert apk.testzip() is None, "Damaged APK"
    with zipfile.ZipFile(io.BytesIO(apk.read("assets/app.zip"))) as app:
        assert app.testzip() is None, "Damaged Python payload"
        for source in sources:
            name = source.with_suffix(".pyc").name
            data = app.read(name)
            assert data == (ROOT / "build/python-app" / name).read_bytes(), (
                f"Stale module: {name}"
            )
            flags, _timestamp, size = struct.unpack("<III", data[4:16])
            assert flags == 0 and size == source.stat().st_size, (
                f"Source differs: {name}"
            )
        for record in art:
            data = app.read("assets/" + record["asset"])
            assert hashlib.sha256(data).hexdigest() == record["sha256"], (
                f"Stale artwork: {record['asset']}"
            )
        for name in excludes:
            excluded = (
                str(Path(name).with_suffix(".pyc")).replace("\\", "/")
                if name.endswith(".py")
                else name
            )
            assert excluded not in app.namelist(), f"Excluded file bundled: {excluded}"
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
            "checked_modules": len(sources),
            "checked_art_assets": len(art),
            "checked_abis": 3,
        },
        indent=2,
    )
)
