"""Collect Flutter's existing 1 Hz profile reports on loopback, or summarise them."""

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import statistics


def summarise(path, output):
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    frames = [event for event in events if event.get("kind") == "frame"]
    errors = [event for event in events if event.get("kind") == "flutter-error"]
    valid = [event for event in frames[4:] if event.get("frames", 0) >= 60 and event.get("unique_vsync_frames", 0) >= 30]
    if len(valid) < 15 or errors:
        raise RuntimeError(f"Insufficient or invalid capture: {len(valid)} samples, {len(errors)} errors")
    def fps(event):
        return event["fps"] * (event["unique_vsync_frames"] - 1) / (event["frames"] - 1)
    result = {
        "platform": "Windows Chrome headless / Flutter profile",
        "measurement": "Flutter FrameTiming, rolling 120 records; four initial reports excluded; duplicate vsync records removed from FPS",
        "samples_after_warmup": len(valid),
        "median_unique_vsync_fps": statistics.median(fps(event) for event in valid),
        "minimum_unique_vsync_fps": min(fps(event) for event in valid),
        "median_raw_fps": statistics.median(event["fps"] for event in valid),
        "maximum_ui_p95_ms": max(event["ui_p95_ms"] for event in valid),
        "maximum_raster_p95_ms": max(event["raster_p95_ms"] for event in valid),
        "viewport": [valid[-1].get("viewport_width"), valid[-1].get("viewport_height")],
        "flutter_errors": errors,
        "physical_android_tested": False,
        "limitations": "One desktop run, overlapping rolling windows. Does not establish Android FPS, thermal stability or long-session performance.",
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


def collect(path, port):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size:
        raise RuntimeError("Retain previous measurements; choose a new output path")
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def headers_for(self, status):
            self.send_response(status)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Content-Length", "0")
            self.end_headers()
        def do_OPTIONS(self):
            self.headers_for(204)
        def do_POST(self):
            if self.path != "/metrics" or self.client_address[0] != "127.0.0.1":
                self.headers_for(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                self.headers_for(400)
                return
            try:
                metric = json.loads(self.rfile.read(length))
                if metric.get("kind") not in {"frame", "flutter-error"}:
                    raise ValueError("Unexpected metric")
                metric["received_utc"] = datetime.now(timezone.utc).isoformat()
                with path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(metric) + "\n")
                self.headers_for(204)
            except (ValueError, TypeError):
                self.headers_for(400)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Loopback metric collector 127.0.0.1:{port}: {path}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18574)
    parser.add_argument("--summarise", action="store_true")
    args = parser.parse_args()
    if args.summarise:
        summarise(args.out, args.out.with_suffix(".summary.json"))
    else:
        collect(args.out.resolve(), args.port)


if __name__ == "__main__":
    main()
