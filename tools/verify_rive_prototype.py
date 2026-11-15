"""Verify and render the editable prototype with the official Rive CLI."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "animation/rive/spark"
OUT = ROOT / ".cache/rive-research"
STATES = ("idle", "move", "attack", "defend", "charge", "hit", "victory", "defeat")


def run(cli, *args):
    return subprocess.run(
        [cli, *map(str, args)],
        check=True,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )


def main():
    cli = shutil.which("rive") or str(
        Path(os.environ["USERPROFILE"]) / ".rive/bin/rive.exe"
    )
    OUT.mkdir(parents=True, exist_ok=True)
    run(cli, PROJECT, "--verify", "--format=json")
    inspected = json.loads(run(cli, "inspect", PROJECT, "--summary").stdout)
    assert not inspected["problems"], inspected["problems"]
    tree = ET.parse(PROJECT / "scene.rml")
    assert {e.get("name") for e in tree.findall(".//LinearAnimation")} == set(STATES)
    parts = {e.get("name") for e in tree.findall(".//Node")}
    assert {
        "Head",
        "Body",
        "Arm L",
        "Arm R",
        "Wheel L",
        "Wheel R",
        "Tracks",
        "Eyes",
    } <= parts
    assert len(tree.findall(".//ViewModelPropertyNumber")) == 52
    assert not tree.findall(".//ScriptAsset"), (
        "The runtime asset must not contain scripts"
    )
    captures = OUT / "captures"
    captures.mkdir(exist_ok=True)
    commands, frames = [], []
    for i, state in enumerate(STATES):
        commands.append(f"data mode={i}")
        for step in range(1, 9):
            commands.append("advance 6")
            path = captures / f"{state}-{step:02}.png"
            commands.append(f"screenshot {path.as_posix()}")
            frames.append((state, path))
    command_file = OUT / "capture-commands.txt"
    command_file.write_text("\n".join(commands) + "\nquit\n", encoding="utf-8")
    rendered = run(cli, PROJECT, f"--commands={command_file}")
    (OUT / "capture.log").write_text(
        rendered.stdout + rendered.stderr, encoding="utf-8"
    )
    assert "err " not in rendered.stdout, rendered.stdout
    differences = {}
    for state in STATES:
        hashes = {
            hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in frames
            if name == state
        }
        assert len(hashes) > 1, f"{state} did not animate"
        differences[state] = len(hashes)
    bench = run(cli, PROJECT, "--bench=600")
    log = bench.stdout + bench.stderr
    (OUT / "rive-benchmark.log").write_text(log, encoding="utf-8")
    metrics = {}
    for name in ("advance", "render"):
        match = re.search(
            rf"bench {name}: mean ([\d.]+)ms p50 ([\d.]+)ms p95 ([\d.]+)ms max ([\d.]+)ms",
            log,
        )
        assert match, log
        metrics[name] = dict(
            zip(("mean_ms", "p50_ms", "p95_ms", "max_ms"), map(float, match.groups()))
        )
    protected = json.loads((OUT / "python-baseline.json").read_text(encoding="utf-8"))[
        "protected_sources_sha256"
    ]
    changed = [
        name
        for name, digest in protected.items()
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest
    ]
    assert not changed, changed
    report = {
        "cli": run(cli, "--version").stdout.strip(),
        "inspect_problems": [],
        "animation_states": list(STATES),
        "moving_captures_per_state": differences,
        "headless_rive_frames": 600,
        "headless_rive_timing": metrics,
        "protected_game_files_unchanged": len(protected),
        "player_data_accessed": False,
        "physical_mobile_performance_verified": False,
        "native_flet_integration_verified": False,
        "note": "CLI headless timings are not device FPS.",
    }
    (OUT / "prototype-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
