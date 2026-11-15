"""Collect real Flutter FrameTiming reports from the local profile client.

Only listens on loopback. No accounts, player data, or third-party endpoints.
"""

import argparse
import json
import statistics
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/rive-research"


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", choices=("idle", "combat"), default="idle")
    parser.add_argument("--output", type=Path, default=OUT)
    args=parser.parse_args()
    scene=args.scene
    OUT=args.output
    OUT.mkdir(parents=True, exist_ok=True)
    samples = []
    errors = []
    started = time.monotonic()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def answer(self, code):
            self.send_response(code)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.end_headers()

        def do_OPTIONS(self):
            self.answer(204)

        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size < 8192:
                self.answer(400)
                return
            try:
                data = json.loads(self.rfile.read(size))
                data["collector_elapsed_s"] = time.monotonic() - started
                if data.get("kind") == "frame":
                    samples.append(data)
                else:
                    errors.append(data)
                (OUT / "chrome-profile-raw.json").write_text(
                    json.dumps({"samples": samples, "errors": errors}, indent=2),
                    encoding="utf-8",
                )
                self.answer(204)
            except (ValueError, TypeError):
                self.answer(400)

    server = ThreadingHTTPServer(("127.0.0.1", 8833), Handler)
    server.timeout = 0.5
    print("Local Flutter FrameTiming collector listening on 127.0.0.1:8833", flush=True)
    try:
        while time.monotonic() - started < 180 and len(samples) < 24 and not errors:
            server.handle_request()
            if len(samples) and len(samples) % 6 == 0:
                print(f"Received {len(samples)} frame samples", flush=True)
        assert not errors, errors
        assert len(samples) >= 20, f"Only {len(samples)} frame samples arrived"
        valid = [s for s in samples[4:] if s.get("frames", 0) >= 60]
        assert len(valid) >= 12
        report = {
            "scenario": scene,
            "platform": "Windows / Chrome headless / Flutter profile",
            "renderer": "Rive Renderer (Factory.rive) and Flutter CanvasKit",
            "robots": 2,
            "measurement": "Flutter FrameTiming rolling windows; not a phone or native Windows EXE test",
            "samples_after_warmup": len(valid),
            "median_fps": statistics.median(s["fps"] for s in valid),
            "minimum_rolling_fps": min(s["fps"] for s in valid),
            "maximum_ui_p95_ms": max(s["ui_p95_ms"] for s in valid),
            "maximum_raster_p95_ms": max(s["raster_p95_ms"] for s in valid),
            "viewport": [valid[-1]["viewport_width"], valid[-1]["viewport_height"]],
            "flutter_errors": errors,
            "phone_tested": False,
        }
        (OUT / "chrome-profile-summary.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        (OUT / f"chrome-profile-{scene}-summary.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, indent=2), flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
