"""Package the isolated Android lab and its reproducible verification report."""

import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / ".cache/rive-research"
OUT = ROOT / "build/rive-prototype-v1"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_log(path):
    data = path.read_bytes()
    return data.decode(
        "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig",
        errors="replace",
    )


def main():
    source = (
        ROOT
        / "prototypes/rive_robot/flutter/build/app/outputs/flutter-apk/app-release.apk"
    )
    assert source.is_file(), "Build the Android lab first"
    sdk = Path(
        os.environ.get(
            "ANDROID_HOME", str(Path(os.environ["USERPROFILE"]) / "Android/sdk")
        )
    )
    build_tools = sdk / "build-tools/36.0.0"
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "clicker-rive-lab-arm64.apk"
    shutil.copy2(source, target)
    subprocess.run(
        [str(build_tools / "zipalign.exe"), "-c", "-P", "16", "4", str(target)],
        check=True,
        capture_output=True,
    )
    env = os.environ.copy()
    env["JAVA_HOME"] = str(Path(os.environ["USERPROFILE"]) / "java/17.0.13+11")
    signature = subprocess.run(
        [str(build_tools / "apksigner.bat"), "verify", "--print-certs", str(target)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    (OUT / "apk-signature.txt").write_text(signature.stdout, encoding="utf-8")
    badging = subprocess.run(
        [str(build_tools / "aapt.exe"), "dump", "badging", str(target)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    package = re.search(r"package: name='([^']+)'", badging).group(1)
    assert package == "com.mycompany.clicker_rive_lab", package
    assert "application-debuggable" not in badging
    asset = ROOT / "prototypes/rive_robot/assets/spark.riv"
    elf_count = 0
    with zipfile.ZipFile(target) as archive:
        payload = archive.read("assets/flutter_assets/assets/spark.riv")
        assert payload == asset.read_bytes(), (
            "Bundled rig differs from the official export"
        )
        abis = sorted(
            {
                name.split("/")[1]
                for name in archive.namelist()
                if name.startswith("lib/") and name.endswith(".so")
            }
        )
        assert abis == ["arm64-v8a"], abis
        for name in archive.namelist():
            if not name.startswith("lib/") or not name.endswith(".so"):
                continue
            data = archive.read(name)
            if not data.startswith(b"\x7fELF") or data[4] != 2:
                continue
            assert data[5] == 1
            offset = struct.unpack_from("<Q", data, 32)[0]
            entry_size, count = struct.unpack_from("<HH", data, 54)
            for i in range(count):
                kind, flags, file_offset, virtual_address, _, _, _, alignment = (
                    struct.unpack_from("<IIQQQQQQ", data, offset + i * entry_size)
                )
                if kind == 1:
                    assert alignment >= 16384, (name, alignment)
                    assert file_offset % 16384 == virtual_address % 16384, name
            elf_count += 1
        assert any("librive_native.so" in name for name in archive.namelist())
    baseline = json.loads(
        (RESEARCH / "python-baseline.json").read_text(encoding="utf-8")
    )
    for name, sha in baseline["protected_sources_sha256"].items():
        assert digest(ROOT / name) == sha, name
    for name, sha in {
        "build/apk-rewarded-v16/clicker.apk": "959dbd7871e7d9ce8e783480ffc95a1fbaa472a5ab2e5d1fc0683ceb95bfe7b9",
        "build/play-test-v17/clicker.aab": "a4c1da1ebb45f179c6b5e51b7038007abfcbccc84a673267cddf91c930ffc699",
    }.items():
        assert digest(ROOT / name) == sha, name
    log = read_log(RESEARCH / "native-tests.log")
    assert "+16: All tests passed!" in log, "Run all 16 native tests before packaging"
    hud_log = read_log(RESEARCH / "hud-tests.log")
    assert "+1: All tests passed!" in hud_log, "Run the FPS HUD lifecycle test"
    python_log = read_log(RESEARCH / "before-python-tests.log")
    assert "Ran 186 tests" in python_log and python_log.rstrip().endswith("OK")
    rig = json.loads((RESEARCH / "prototype-report.json").read_text(encoding="utf-8"))
    cpu = json.loads(
        (RESEARCH / "flutter-cpu-benchmark.json").read_text(encoding="utf-8")
    )
    report = {
        "apk": str(target),
        "sha256": digest(target),
        "bytes": target.stat().st_size,
        "package": package,
        "separate_from_player_game": True,
        "release_mode": True,
        "prototype_debug_signing_key": True,
        "apk_signature_verified": True,
        "abis": abis,
        "native_64bit_libraries_checked": elf_count,
        "elf_16kb_alignment": "passed",
        "apk_zip_16kb_alignment": "passed",
        "rive_asset_bytes": len(payload),
        "rive_asset_sha256": digest(asset),
        "official_export_preserved_byte_for_byte": True,
        "rive_export_has_free_plan_branding": True,
        "cli_version": rig["cli"],
        "rive_flutter": "0.14.11",
        "flet": "1.0.4",
        "flet_rive_python": "1.0.4",
        "prototype_only_extension": True,
        "states": rig["animation_states"],
        "headless_rive_benchmark": rig["headless_rive_timing"],
        "flutter_windows_cpu_comparison": cpu,
        "python_flet_construction_comparison": {
            k: baseline[k] for k in ("measurement", "legacy", "rive_semantic_control")
        },
        "native_tests_passed": 17,
        "original_python_tests_passed": 186,
        "original_game_source_files_unchanged": len(
            baseline["protected_sources_sha256"]
        ),
        "original_apk16_and_aab17_unchanged": True,
        "player_data_accessed": False,
        "python_updates_per_animation_frame": 0,
        "robot_prototypes": 1,
        "production_robot_replacements": 0,
        "physical_mobile_tested": False,
        "physical_native_desktop_fps_verified": False,
        "windows_verification": "Real Flutter Windows test engine and Rive C++ import, Factory.flutter, release Rive DLL; offscreen CPU measurements, not screen FPS",
        "mobile_verification": "APK built and statically validated. User will test the phone later.",
    }
    profiles = {}
    for scene in ("idle", "combat"):
        path = RESEARCH / f"chrome-profile-{scene}-summary.json"
        if path.is_file():
            profile = json.loads(path.read_text(encoding="utf-8"))
            assert not profile["flutter_errors"]
            profiles[scene] = profile
    report["chrome_profile_frame_timings"] = profiles
    report["chrome_rive_renderer_verified"] = bool(profiles.get("combat"))
    (OUT / "verification.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    shutil.copy2(asset, OUT / "spark.riv")
    guide = ROOT / "RIVE_PROTOTYPE.md"
    if guide.is_file():
        shutil.copy2(guide, OUT / "README.md")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "apk",
                    "bytes",
                    "sha256",
                    "package",
                    "native_tests_passed",
                    "native_64bit_libraries_checked",
                    "elf_16kb_alignment",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
