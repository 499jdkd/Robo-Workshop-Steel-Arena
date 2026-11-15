"""Reproducible Python/Flet transport baseline, not a GPU/FPS measurement.

Run with the isolated prototypes/rive_robot environment. Saves legacy fixtures
for the Flutter A/B lab and hashes the protected game source files.
"""

import base64
import hashlib
import json
import math
import statistics
import sys
import time
from dataclasses import is_dataclass
from enum import Enum
from pathlib import Path

import flet as ft
from flet.messaging.protocol import configure_encode_object_for_msgpack

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "prototypes/rive_robot")]

from control import RobotRive

from robot_motion import robot_actor, workshop_activity

ENCODE = configure_encode_object_for_msgpack(ft.BaseControl)
OUT = ROOT / ".cache/rive-research"


def wire(value, *, portable=False):
    if is_dataclass(value) or isinstance(value, Enum):
        return wire(ENCODE(value), portable=portable)
    if isinstance(value, dict):
        result = {
            str(k.value if isinstance(k, Enum) else k): wire(v, portable=portable)
            for k, v in value.items()
        }
        if portable and isinstance(result.get("src"), str):
            path = ROOT / "src/assets" / result["src"]
            if path.is_file():
                result["src"] = base64.b64encode(path.read_bytes()).decode()
        return result
    if isinstance(value, (list, tuple)):
        return [wire(v, portable=portable) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return 1e9
    return value


def legacy_frame(now):
    travel, _, motion, facing = workshop_activity(now, 42)
    return robot_actor(
        "spark", size=240, now=now, motion=motion, facing=facing, travel=travel
    )


def controls(value):
    if isinstance(value, dict):
        return (1 if "_c" in value else 0) + sum(controls(v) for v in value.values())
    if isinstance(value, list):
        return sum(controls(v) for v in value)
    return 0


def stable_fixture_ids(frame):
    """Keep control identities across poses, like Flet's real patch protocol."""
    next_id = 20000

    def visit(value):
        nonlocal next_id
        if isinstance(value, dict):
            if "_c" in value:
                value["_i"] = next_id
                next_id += 1
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(frame)
    return frame


def measure(factory, n=600):
    elapsed = []
    sizes = []
    count = 0
    for i in range(n + 30):
        start = time.perf_counter_ns()
        data = wire(factory(i / 60))
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
        duration = (time.perf_counter_ns() - start) / 1e6
        if i >= 30:
            elapsed.append(duration)
            sizes.append(len(payload))
            count = controls(data)
    elapsed.sort()
    return {
        "samples": n,
        "build_and_json_ms_median": statistics.median(elapsed),
        "build_and_json_ms_p95": elapsed[int(0.95 * (n - 1))],
        "json_bytes_median": statistics.median(sizes),
        "controls_per_actor": count,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    protected = {
        str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for base in (ROOT / "src", ROOT / "tests")
        for path in base.glob("*.py")
    }
    protected["pyproject.toml"] = hashlib.sha256(
        (ROOT / "pyproject.toml").read_bytes()
    ).hexdigest()
    report = {
        "measurement": "Python construction and JSON serialization only; not rendered FPS",
        "legacy": measure(legacy_frame),
        "rive_semantic_control": measure(
            lambda _: RobotRive(src="spark.riv", width=220, height=240)
        ),
        "protected_sources_sha256": protected,
        "legacy_python_animation_updates_per_second": 1,
        "rive_python_per_frame_updates": 0,
    }
    target = OUT / "python-baseline.json"
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    frames = [
        stable_fixture_ids(wire(legacy_frame(i), portable=True)) for i in range(32)
    ]
    assets = ROOT / "prototypes/rive_robot/assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "legacy_frames.json").write_text(
        json.dumps(frames, ensure_ascii=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "protected_sources_sha256"},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
