"""Summarize real Flutter FrameTiming samples captured through Chrome CDP."""

import argparse
import json
from pathlib import Path
import statistics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--scenario", choices=("workshop", "combat"), required=True)
    parser.add_argument("--width", type=int, default=844)
    parser.add_argument("--height", type=int, default=390)
    parser.add_argument("--dpr", type=float, default=2)
    parser.add_argument("--minimum-samples", type=int, default=20)
    parser.add_argument("--renderer", default="Factory.rive / CanvasKit")
    args = parser.parse_args()
    data = json.loads((args.capture / "runtime.json").read_text(encoding="utf-8"))
    samples = []
    errors = []
    for event in data["events"]:
        if event.get("method") == "Runtime.exceptionThrown":
            errors.append(event["params"]["exceptionDetails"].get("text", "Exception"))
        if event.get("method") != "Runtime.consoleAPICalled":
            continue
        text = " ".join(
            str(value.get("value", value.get("description", "")))
            for value in event["params"]["args"]
        )
        if text.startswith("RIVE_LAB_METRIC "):
            samples.append(json.loads(text.removeprefix("RIVE_LAB_METRIC ")))
        if event["params"].get("type") == "error":
            errors.append(text[:500])
    valid = [sample for sample in samples[4:] if sample["frames"] >= 60]
    assert len(valid) >= args.minimum_samples, len(valid)
    assert not errors, errors
    report = dict(
        scenario=args.scenario,
        platform="Windows / Chrome headless / Flutter profile",
        renderer=args.renderer,
        measurement="Flutter FrameTiming, 120-frame rolling windows from main game, four warmup samples excluded",
        viewport=[args.width, args.height],
        dpr=args.dpr,
        samples_after_warmup=len(valid),
        median_fps=statistics.median(s["fps"] for s in valid),
        minimum_rolling_fps=min(s["fps"] for s in valid),
        maximum_ui_p95_ms=max(s["ui_p95_ms"] for s in valid),
        maximum_raster_p95_ms=max(s["raster_p95_ms"] for s in valid),
        javascript_errors=errors,
        phone_tested=False,
        main_game=True,
    )
    (args.capture / "frame-timing-samples.json").write_text(
        json.dumps(samples, indent=2), encoding="utf-8"
    )
    (args.capture / "performance-summary.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
