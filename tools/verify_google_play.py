"""Verify the Play AAB, its upload signature and a Google bundletool-derived APK."""

import argparse
import base64
import hashlib
import io
import json
import os
import re
import struct
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
JAVA = Path.home() / "java/17.0.13+11/bin"
SDK = Path.home() / "Android/sdk/build-tools/36.0.0"
BUNDLETOOL = ROOT / ".cache/tools/bundletool-all-1.18.3.jar"
ANDROID = "{http://schemas.android.com/apk/res/android}"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log):
    result = subprocess.run(
        [str(item) for item in command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(
            f"Verification failed: {command[0]} ({result.returncode}); see {log}"
        )
    return result.stdout


def bundle(command, log):
    return run([JAVA / "java.exe", "-Xmx1024m", "-jar", BUNDLETOOL, *command], log)


def check_native_libraries(archive, prefix):
    checked = {}
    for name in archive.namelist():
        if not name.startswith(
            (prefix + "arm64-v8a/", prefix + "x86_64/")
        ) or not name.endswith(".so"):
            continue
        data = archive.read(name)
        assert data[:4] == b"\x7fELF" and data[4] == 2, name
        endian = "<" if data[5] == 1 else ">"
        offset = struct.unpack_from(endian + "Q", data, 32)[0]
        size, count = struct.unpack_from(endian + "HH", data, 54)
        segments = []
        for index in range(count):
            start = offset + index * size
            if struct.unpack_from(endian + "I", data, start)[0] == 1:
                file_offset, virtual_address = struct.unpack_from(
                    endian + "QQ", data, start + 8
                )
                alignment = struct.unpack_from(endian + "Q", data, start + 48)[0]
                assert alignment >= 16384, (name, alignment)
                assert file_offset % 16384 == virtual_address % 16384, name
                segments.append(alignment)
        assert segments, name
        checked[name] = min(segments)
    assert checked, "No 64-bit native libraries found"
    return checked


def check_no_signing_secrets(archive, password, keystore, depth=0):
    checked = 0
    for name in archive.namelist():
        if name.endswith("/"):
            continue
        data = archive.read(name)
        assert password not in data, f"Signing password found in {name}"
        assert keystore not in data, f"Private keystore found in {name}"
        checked += 1
        if depth < 2 and name.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as nested:
                checked += check_no_signing_secrets(nested, password, keystore, depth + 1)
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-number", type=int, default=17)
    args = parser.parse_args()
    os.environ["JAVA_HOME"] = str(JAVA.parent)
    output = ROOT / f"build/play-test-v{args.build_number}"
    stage = ROOT / f".cache/play-test-v{args.build_number}"
    aab = output / "clicker.aab"
    logs = output / "validation"
    logs.mkdir(parents=True, exist_ok=True)
    signing = json.loads(
        (ROOT / ".signing/upload-key.json").read_text(encoding="utf-8")
    )
    expected_bundletool = json.loads(
        BUNDLETOOL.with_suffix(".json").read_text(encoding="utf-8")
    )
    assert sha(BUNDLETOOL) == expected_bundletool["sha256"]
    assert (
        signing["certificate_sha256"]
        != "67f16d1bdbaa503c69f514076d056a21a14b5c7e9db7e00b3b485491f9421e85"
    )
    signature = run(
        [JAVA / "jarsigner.exe", "-J-Duser.language=en", "-verify", aab],
        logs / "aab-signature.txt",
    )
    assert "jar verified" in signature.lower()
    cert_text = run(
        [
            JAVA / "keytool.exe",
            "-J-Duser.language=en",
            "-printcert",
            "-jarfile",
            aab,
            "-rfc",
        ],
        logs / "aab-certificate.pem",
    )
    encoded = re.search(
        r"-----BEGIN CERTIFICATE-----\s*(.*?)\s*-----END CERTIFICATE-----",
        cert_text,
        re.S,
    ).group(1)
    certificate_hash = hashlib.sha256(base64.b64decode(encoded)).hexdigest()
    assert certificate_hash == signing["certificate_sha256"]
    bundle(["validate", f"--bundle={aab}"], logs / "bundletool-validation.txt")
    xml = bundle(
        ["dump", "manifest", f"--bundle={aab}", "--module=base"], logs / "manifest.xml"
    )
    manifest = ET.fromstring(xml)
    assert manifest.get("package") == "com.mycompany.clicker"
    assert manifest.get(ANDROID + "versionCode") == str(args.build_number)
    assert manifest.get(ANDROID + "versionName") == "0.1.1"
    target_sdk = int(manifest.find("uses-sdk").get(ANDROID + "targetSdkVersion"))
    assert target_sdk >= 36
    app = manifest.find("application")
    assert app.get(ANDROID + "debuggable", "false") == "false"
    metadata = {
        element.get(ANDROID + "name"): element.get(ANDROID + "value")
        for element in app.findall("meta-data")
    }
    assert (
        metadata["com.google.android.gms.ads.APPLICATION_ID"]
        == "ca-app-pub-3940256099942544~3347511713"
    )
    permissions = [
        element.get(ANDROID + "name") for element in manifest.findall("uses-permission")
    ]
    for permission in (
        "com.google.android.gms.permission.AD_ID",
        "android.permission.ACCESS_ADSERVICES_AD_ID",
        "android.permission.ACCESS_ADSERVICES_ATTRIBUTION",
        "android.permission.ACCESS_ADSERVICES_TOPICS",
    ):
        assert permission not in permissions
    config = bundle(["dump", "config", f"--bundle={aab}"], logs / "bundle-config.json")
    assert "PAGE_ALIGNMENT_16K" in config
    settings = tomllib.loads((stage / "pyproject.toml").read_text(encoding="utf-8"))
    excludes = {
        name.replace("\\", "/") for name in settings["tool"]["flet"]["app"]["exclude"]
    }
    modules = [
        path for path in (stage / "src").glob("*.py") if path.name not in excludes
    ]
    art = []
    for name in ("encoded-assets.json", "motion-assets.json"):
        art.extend(
            json.loads(
                (ROOT / "artwork/robot_collection" / name).read_text(encoding="utf-8")
            )
        )
    with zipfile.ZipFile(aab) as archive:
        assert archive.testzip() is None
        secret_entries = check_no_signing_secrets(
            archive,
            (ROOT / ".signing" / signing["password_file"]).read_text(encoding="utf-8").strip().encode(),
            (ROOT / ".signing" / signing["keystore_file"]).read_bytes(),
        )
        assert not any(
            name.endswith((".jks", ".keystore")) or ".signing/" in name
            for name in archive.namelist()
        )
        jar_manifest = (
            archive.read("META-INF/MANIFEST.MF")
            .decode()
            .replace("\r\n ", "")
            .replace("\n ", "")
        )
        signed_names = {
            name.rstrip("\r")
            for name in re.findall(r"^Name: (.+)$", jar_manifest, re.M)
        }
        for name in archive.namelist():
            if (
                name.endswith("/")
                or name == "META-INF/MANIFEST.MF"
                or (
                    name.startswith("META-INF/")
                    and name.endswith((".SF", ".RSA", ".DSA", ".EC"))
                )
            ):
                continue
            assert name in signed_names, f"Unsigned entry: {name}"
        native = check_native_libraries(archive, "base/lib/")
        with zipfile.ZipFile(
            io.BytesIO(archive.read("base/assets/app.zip"))
        ) as payload:
            for source in modules:
                name = source.with_suffix(".pyc").name
                data = payload.read(name)
                assert data == (stage / "build/python-app" / name).read_bytes(), name
                assert struct.unpack("<III", data[4:16])[2] == source.stat().st_size, (
                    name
                )
            for record in art:
                assert (
                    hashlib.sha256(
                        payload.read("assets/" + record["asset"])
                    ).hexdigest()
                    == record["sha256"]
                )
            assert b"ca-app-pub-3940256099942544/6300978111" in payload.read(
                "advertising.pyc"
            )
            assert b"ca-app-pub-3940256099942544/5224354917" in payload.read(
                "rewarded_ads.pyc"
            )
            for name in ("advertising.pyc", "rewarded_ads.pyc"):
                assert b"ca-app-pub-4765036354233528/" not in payload.read(name)
        with zipfile.ZipFile(
            io.BytesIO(archive.read("base/assets/sitepackages.zip"))
        ) as packages:
            for name in ("flet", "flet_ads", "httpx"):
                assert any(
                    path.startswith(name + "/") for path in packages.namelist()
                ), name
        for abi in ("arm64-v8a", "armeabi-v7a", "x86_64"):
            assert f"base/lib/{abi}/libpython3.14.so" in archive.namelist()
    derived = stage / "verification"
    derived.mkdir(exist_ok=True)
    apks = derived / "universal.apks"
    password_file = ROOT / ".signing" / signing["password_file"]
    bundle(
        [
            "build-apks",
            f"--bundle={aab}",
            f"--output={apks}",
            "--mode=universal",
            "--overwrite",
            f"--ks={ROOT / '.signing' / signing['keystore_file']}",
            f"--ks-key-alias={signing['alias']}",
            f"--ks-pass=file:{password_file}",
            f"--key-pass=file:{password_file}",
        ],
        logs / "derived-apk-build.txt",
    )
    apk = derived / "local-verification-only.apk"
    with zipfile.ZipFile(apks) as archive:
        apk.write_bytes(archive.read("universal.apk"))
    run(
        [SDK / "zipalign.exe", "-c", "-P", "16", "-v", "4", apk],
        logs / "derived-apk-alignment.txt",
    )
    apk_signature = run(
        [SDK / "apksigner.bat", "verify", "--print-certs", apk],
        logs / "derived-apk-signature.txt",
    )
    assert signing["certificate_sha256"] in apk_signature
    with zipfile.ZipFile(apk) as archive:
        derived_native = check_native_libraries(archive, "lib/")
        assert len(derived_native) == len(native)
    from build_google_play import prepare_stage

    # Re-check original and staged inputs after all build tools have finished.
    prepare_stage(
        ROOT, stage, number=args.build_number, version="0.1.1", ads_mode="test"
    )
    assert (
        sha(ROOT / "build/apk-rewarded-v16/clicker.apk")
        == "959dbd7871e7d9ce8e783480ffc95a1fbaa472a5ab2e5d1fc0683ceb95bfe7b9"
    )
    report = {
        "aab": str(aab),
        "bytes": aab.stat().st_size,
        "sha256": sha(aab),
        "package": manifest.get("package"),
        "version_code": args.build_number,
        "version_name": "0.1.1",
        "target_sdk": target_sdk,
        "upload_certificate_sha256": certificate_hash,
        "debug_certificate": False,
        "aab_signature_verified": True,
        "all_payload_entries_signed": True,
        "bundletool": "1.18.3",
        "bundletool_validation": "passed",
        "native_64bit_libraries_checked": len(native),
        "elf_alignment_16kb": "passed",
        "bundle_zip_alignment": "PAGE_ALIGNMENT_16K",
        "derived_apk_zip_alignment": "passed",
        "derived_apk_generated": True,
        "checked_python_modules": len(modules),
        "checked_art_assets": len(art),
        "checked_abis": 3,
        "derived_apk_signature_verified": True,
        "test_ads_only": True,
        "test_app_id": metadata["com.google.android.gms.ads.APPLICATION_ID"],
        "real_ad_revenue": False,
        "original_live_app_sources_unchanged": True,
        "previous_apk16_unchanged": True,
        "private_keys_in_bundle": False,
        "signing_secret_scan_entries": secret_entries,
        "permissions": permissions,
        "physical_phone_launch_verified": False,
        "play_console_uploaded": False,
        "play_policy_approval_verified": False,
        "signing_key_notice": "Google Play distributed APKs use the Play App Signing key; do not uninstall the existing debug-signed APK16 before backing up local progress",
    }
    (output / "verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
