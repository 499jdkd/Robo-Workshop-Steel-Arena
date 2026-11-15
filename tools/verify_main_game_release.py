"""Verify the staged main-game APK, including native libraries and animation assets."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tomllib
import zipfile

from verify_google_play import check_native_libraries
from flutter_cached import environment

ROOT = Path(__file__).resolve().parents[1]
SDK = Path.home() / "Android/sdk/build-tools/36.0.0"
JAVA = Path.home() / "java/17.0.13+11"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-number", type=int, default=22)
    args = parser.parse_args()
    os.environ.update(environment())
    stage = ROOT / f".cache/game-test-v{args.build_number}"
    output = ROOT / f"build/apk-game-v{args.build_number}"
    apk = output / "clicker.apk"
    logs = output / "validation"
    logs.mkdir(exist_ok=True)

    def run(name, command):
        env = dict(os.environ, JAVA_HOME=str(JAVA))
        env["PATH"] = str(JAVA / "bin") + os.pathsep + env["PATH"]
        result = subprocess.run([str(x) for x in command], env=env, capture_output=True,
                                encoding="utf-8", errors="replace")
        (logs / name).write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"Failed {name}; see {logs / name}")
        return result.stdout

    signature = run("signature.txt", [SDK / "apksigner.bat", "verify", "--verbose", "--print-certs", apk])
    certificate = re.search(r"certificate SHA-256 digest: (\w+)", signature).group(1)
    assert certificate == "67f16d1bdbaa503c69f514076d056a21a14b5c7e9db7e00b3b485491f9421e85", "Update signing key changed"
    run("alignment.txt", [SDK / "zipalign.exe", "-c", "-P", "16", "-v", "4", apk])
    manifest = run("manifest.txt", [SDK / "aapt2.exe", "dump", "badging", apk])
    assert "name='com.mycompany.clicker'" in manifest
    assert f"versionCode='{args.build_number}'" in manifest
    assert "versionName='0.2.0'" in manifest
    assert "targetSdkVersion:'36'" in manifest
    assert "com.google.android.gms.permission.AD_ID" not in manifest
    xml = run("manifest-xml.txt", [SDK / "aapt2.exe", "dump", "xmltree", "--file", "AndroidManifest.xml", apk])
    assert "ca-app-pub-3940256099942544~3347511713" in xml
    assert "ca-app-pub-4765036354233528~" not in xml
    settings = tomllib.loads((stage / "pyproject.toml").read_text(encoding="utf-8"))
    excludes = {s.replace("\\", "/") for s in settings["tool"]["flet"]["app"]["exclude"]}
    modules = [p for p in (stage / "src").glob("*.py") if p.name not in excludes]
    with zipfile.ZipFile(apk) as package:
        assert package.testzip() is None
        native = check_native_libraries(package, "lib/")
        for abi in ("arm64-v8a", "armeabi-v7a", "x86_64"):
            assert f"lib/{abi}/libpython3.14.so" in package.namelist()
            assert f"lib/{abi}/librive_native.so" in package.namelist()
        with zipfile.ZipFile(io.BytesIO(package.read("assets/app.zip"))) as app:
            assert app.testzip() is None
            for source in modules:
                name = source.with_suffix(".pyc").name
                compiled = app.read(name)
                assert compiled == (stage / "build/python-app" / name).read_bytes(), name
                assert struct.unpack("<III", compiled[4:16])[2] == source.stat().st_size, name
            animation = app.read("assets/animation/game_robot.riv")
            assert animation == (ROOT / "src/assets/animation/game_robot.riv").read_bytes()
            sounds = list((ROOT / "src/assets/audio").glob("*.wav"))
            if not sounds:
                sounds = list((ROOT / "src/assets").rglob("*.wav"))
            assert len(sounds) >= 15
            for source in sounds:
                assert app.read("assets/" + source.relative_to(ROOT / "src/assets").as_posix()) == source.read_bytes()
            for source in (ROOT / "src/assets/art/arena").glob("stage_*.svg"):
                assert app.read("assets/art/arena/" + source.name) == source.read_bytes()
            for name, ad_id in (("advertising.pyc", b"ca-app-pub-3940256099942544/6300978111"),
                               ("rewarded_ads.pyc", b"ca-app-pub-3940256099942544/5224354917")):
                assert ad_id in app.read(name), name
                assert b"ca-app-pub-4765036354233528/" not in app.read(name), name
            assert not any(".signing" in n or n.endswith((".jks", ".keystore")) for n in app.namelist())
        with zipfile.ZipFile(io.BytesIO(package.read("assets/sitepackages.zip"))) as libraries:
            for module in ("flet", "flet_ads", "flet_rive", "httpx"):
                assert any(p.startswith(module + "/") for p in libraries.namelist()), module

    report = dict(apk=str(apk), bytes=apk.stat().st_size,
                  sha256=hashlib.sha256(apk.read_bytes()).hexdigest(), version_code=args.build_number,
                  certificate_sha256=certificate, modules=len(modules),
                  published_rive_bytes=len(animation), sound_assets=len(sounds),
                  native_libraries_16kb=len(native), abis=3, test_ads=True, phone_tested=False)
    (logs / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
