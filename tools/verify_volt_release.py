"""Verify Volt-only source scope and the real APK's new renderer/assets.

These are static source/package checks, not Android execution or FPS tests.
The baseline is the snapshot taken before the Volt task, preserving earlier
accepted v32 work even when it has not yet been committed to Git.
"""

import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import sys
import wave
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / ".cache/volt-refinement/before"
ABIS = ("arm64-v8a", "armeabi-v7a", "x86_64")
MARKERS = ("flutter-canvas-articulated", "voltPower", "volt_pulse", "volt_charge", "volt_storm", "volt_shutdown")
VOLT_SOUNDS = tuple(f"volt_{cue}.wav" for cue in ("pulse", "charge", "storm", "shutdown"))
COMBAT_FILES = ("combat_rules.py", "robot_arena.py", "armory.py")


class VerificationError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unchanged_file(current, baseline, label):
    before = Path(baseline).read_bytes()
    after = Path(current).read_bytes()
    require(after == before, f"Out-of-scope change: {label}")
    return {"sha256": sha256(after), "bytes": len(after), "unchanged": True}


def ability_rows(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    assignments = [node.value for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "_ROWS" for target in node.targets)]
    require(len(assignments) == 1 and isinstance(assignments[0], ast.Dict), "Expected one literal robot_abilities._ROWS dictionary")
    table = assignments[0]
    rows = {}
    for key, value in zip(table.keys, table.values):
        identity = ast.literal_eval(key)
        require(isinstance(identity, str) and identity not in rows, "Duplicate or invalid ability identity")
        rows[identity] = ast.dump(value, include_attributes=False)
    require(len(rows) == 32 and "volt" in rows, "Expected the existing 32 robot ability identities")
    return rows


def xml_structure(element):
    """Ignore formatting/attribute ordering, preserve geometry and child order."""
    return [element.tag, sorted(element.attrib.items()), (element.text or "").strip(),
            [xml_structure(child) for child in element]]


def xml_digest(element):
    return sha256(json.dumps(xml_structure(element), ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def named_nodes(path, kind):
    root = ET.parse(path).getroot()
    nodes = {}
    for node in root.findall(kind):
        name = node.get("name")
        require(name and name not in nodes, f"Duplicate or unnamed RML {kind}")
        nodes[name] = node
    require(len(nodes) == 32, f"Expected 32 RML {kind} nodes")
    return nodes


def verify_scope(root=ROOT, baseline=BASELINE):
    root, baseline = Path(root), Path(baseline)
    current_src, before_src = root / "src", baseline / "src"
    rows, before_rows = ability_rows(current_src / "robot_abilities.py"), ability_rows(before_src / "robot_abilities.py")
    require(rows.keys() == before_rows.keys(), "Robot identities changed")
    others = sorted(set(rows) - {"volt"})
    require(all(rows[identity] == before_rows[identity] for identity in others), "Other robot ability rows changed")
    report = {
        "comparison_baseline": str(baseline),
        "unchanged_other_ability_rows": {"count": len(others), "ast_sha256": sha256(json.dumps({i: rows[i] for i in others}, sort_keys=True).encode())},
        "existing_rive": unchanged_file(current_src / "assets/animation/game_robot.riv", before_src / "assets/animation/game_robot.riv", "game_robot.riv"),
        "combat_resolvers": {name: unchanged_file(current_src / name, before_src / name, name) for name in COMBAT_FILES},
        "other_portraits": {},
        "rml_other_artboards": {},
        "rml_other_view_models": {},
    }
    for identity in others:
        relative = Path("assets/art/portraits") / f"{identity}.svg"
        report["other_portraits"][identity] = unchanged_file(current_src / relative, before_src / relative, str(relative))
    current_rml = root / "animation/rive/game_robot/scene.rml"
    before_rml = baseline / "animation/rive/game_robot/scene.rml"
    for kind, excluded, key in [("Artboard", "volt", "rml_other_artboards"), ("ViewModel", "Motion_volt", "rml_other_view_models")]:
        current_nodes, old_nodes = named_nodes(current_rml, kind), named_nodes(before_rml, kind)
        require(current_nodes.keys() == old_nodes.keys(), f"RML {kind} names changed")
        require(excluded in current_nodes, f"Missing Volt {kind}")
        for name in sorted(set(current_nodes) - {excluded}):
            digest, before_digest = xml_digest(current_nodes[name]), xml_digest(old_nodes[name])
            require(digest == before_digest, f"Out-of-scope RML {kind} change: {name}")
            report[key][name] = {"sha256": digest, "structurally_unchanged": True}
        require(len(report[key]) == 31, f"Expected 31 preserved {kind} nodes")
    audio = current_src / "assets/audio"
    before_audio = before_src / "assets/audio"
    old_files = sorted(path for path in before_audio.rglob("*") if path.is_file())
    require(bool(old_files), "Baseline audio is missing")
    old_relatives = {path.relative_to(before_audio).as_posix() for path in old_files}
    report["existing_audio"] = {}
    for path in old_files:
        relative = path.relative_to(before_audio)
        report["existing_audio"][relative.as_posix()] = unchanged_file(audio / relative, path, "audio/" + relative.as_posix())
    new_relatives = {path.relative_to(audio).as_posix() for path in audio.rglob("*") if path.is_file()} - old_relatives
    require(new_relatives == set(VOLT_SOUNDS), "Expected exactly four new Volt WAV files")
    report["volt_audio"] = {}
    for name in VOLT_SOUNDS:
        data = (audio / name).read_bytes()
        with wave.open(io.BytesIO(data), "rb") as sound:
            require(sound.getnframes() > 0 and sound.getcomptype() == "NONE", f"Invalid or empty Volt PCM WAV: {name}")
            report["volt_audio"][name] = {"sha256": sha256(data), "bytes": len(data),
                "channels": sound.getnchannels(), "sample_rate": sound.getframerate(),
                "duration_seconds": round(sound.getnframes() / sound.getframerate(), 4)}
    require(len({item["sha256"] for item in report["volt_audio"].values()}) == 4, "Volt sound files are identical")
    portrait = current_src / "assets/art/portraits/volt.svg"
    old_portrait = before_src / "assets/art/portraits/volt.svg"
    report["volt_portrait"] = {"sha256": file_hash(portrait), "bytes": portrait.stat().st_size,
                               "changed": portrait.read_bytes() != old_portrait.read_bytes()}
    require(report["volt_portrait"]["changed"], "The new Volt portrait was not installed")
    report["counts"] = {"other_robot_portraits": len(report["other_portraits"]),
                        "other_ability_rows": len(others), "other_artboards": len(report["rml_other_artboards"]),
                        "other_view_models": len(report["rml_other_view_models"]),
                        "unchanged_existing_audio": len(old_files), "new_volt_audio": len(VOLT_SOUNDS),
                        "unchanged_combat_files": len(COMBAT_FILES)}
    return report


def verify_package(apk, scope, root=ROOT):
    apk, root = Path(apk), Path(root)
    require(apk.is_file(), "Final APK is not ready")
    result = {"apk": str(apk.resolve()), "bytes": apk.stat().st_size, "sha256": file_hash(apk),
              "native_marker_checks": {}, "asset_checks": {}}
    with zipfile.ZipFile(apk) as package:
        native_abis = {name.split("/")[1] for name in package.namelist()
                       if name.startswith("lib/") and name.endswith("/libapp.so")}
        require(native_abis == set(ABIS), "APK libapp.so ABI inventory changed")
        for abi in ABIS:
            binary = package.read(f"lib/{abi}/libapp.so")
            require(all(marker.encode("ascii") in binary for marker in MARKERS), f"Volt renderer/audio marker absent in {abi} libapp.so")
            result["native_marker_checks"][abi] = {"sha256": sha256(binary), "bytes": len(binary), "markers_present": list(MARKERS)}
        with zipfile.ZipFile(io.BytesIO(package.read("assets/app.zip"))) as app:
            checks = ["assets/animation/game_robot.riv", "assets/art/portraits/volt.svg"]
            checks.extend("assets/audio/" + name for name in VOLT_SOUNDS)
            checks.extend("assets/audio/" + name for name in scope["existing_audio"])
            checks.extend(f"assets/art/portraits/{identity}.svg" for identity in scope["other_portraits"])
            for name in checks:
                expected = (root / "src" / name).read_bytes()
                actual = app.read(name)
                require(actual == expected, f"APK contains stale or altered asset: {name}")
                result["asset_checks"][name] = {"sha256": sha256(actual), "bytes": len(actual), "matches_source": True}
    result["counts"] = {"abis": len(result["native_marker_checks"]), "markers_per_abi": len(MARKERS),
                        "verified_assets": len(result["asset_checks"])}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-number", type=int, default=33)
    args = parser.parse_args()
    if args.build_number <= 0:
        parser.error("--build-number must be positive")
    output = ROOT / f"build/volt-verification-v{args.build_number}"
    output.mkdir(parents=True, exist_ok=True)
    report_file = output / "scope-and-package.json"
    report = {"build": args.build_number, "status": "checking", "main_game": True,
              "physical_android_tested": False,
              "measurement": "Static source-scope and APK-content checks; no Android execution or FPS claim"}
    try:
        apk = ROOT / f"build/apk-game-v{args.build_number}/clicker.apk"
        require(apk.is_file(), "Final APK is not ready")
        report["scope"] = verify_scope()
        report["package"] = verify_package(apk, report["scope"])
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error) if isinstance(error, VerificationError) else type(error).__name__
        raise
    finally:
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"build": args.build_number, "status": "passed", "report": str(report_file),
                      "scope_counts": report["scope"]["counts"], "package_counts": report["package"]["counts"],
                      "apk_sha256": report["package"]["sha256"], "physical_android_tested": False}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Volt verification stopped: " + (str(error) if isinstance(error, VerificationError) else type(error).__name__), file=sys.stderr)
        raise SystemExit(1)
