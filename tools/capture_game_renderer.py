"""Capture the real GPU game client via Chrome's testing protocol (no player data)."""

import argparse
import base64
import functools
import http.server
import json
from pathlib import Path
import subprocess
import threading
import time
from urllib.request import urlopen

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="before")
    parser.add_argument("--port", type=int, default=18552)
    parser.add_argument(
        "--client", type=Path, default=ROOT / "tools/game_client/build/web"
    )
    parser.add_argument("--width", type=int, default=844)
    parser.add_argument("--height", type=int, default=390)
    parser.add_argument("--dpr", type=float, default=1)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--network", action="store_true", help="Record verbose network events for startup diagnosis")
    args = parser.parse_args()
    out = ROOT / ".cache/rework-review" / args.name
    out.mkdir(parents=True, exist_ok=True)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Quiet, directory=str(args.client))
    )
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    chrome = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
    if not chrome.exists():
        chrome = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    log = (out / "chrome.log").open("w")
    child = subprocess.Popen(
        [
            str(chrome),
            "--headless=new",
            "--no-first-run",
            "--remote-debugging-port=19225",
            "--remote-allow-origins=http://localhost",
            f"--user-data-dir={out.resolve() / 'chrome-profile'}",
            "--hide-scrollbars",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "about:blank",
        ],
        stdout=log,
        stderr=log,
    )
    events = []
    try:
        for _ in range(100):
            try:
                tabs = json.load(urlopen("http://127.0.0.1:19225/json", timeout=1))
                target = next(t for t in tabs if t["type"] == "page")
                break
            except (OSError, StopIteration):
                time.sleep(0.1)
        with connect(
            target["webSocketDebuggerUrl"],
            origin="http://localhost",
            max_size=40_000_000,
        ) as ws:
            counter = 0

            def call(method, params=None):
                nonlocal counter
                counter += 1
                identity = counter
                ws.send(
                    json.dumps(
                        {"id": identity, "method": method, "params": params or {}}
                    )
                )
                while True:
                    value = json.loads(ws.recv(timeout=30))
                    if value.get("id") == identity:
                        if "error" in value:
                            raise RuntimeError(value)
                        return value.get("result", {})
                    events.append(value)

            call("Runtime.enable")
            call("Page.enable")
            if args.network:
                call("Network.enable")
            call(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": args.width,
                    "height": args.height,
                    "deviceScaleFactor": args.dpr,
                    "mobile": False,
                },
            )
            call(
                "Page.navigate",
                {
                    "url": f"http://127.0.0.1:{httpd.server_port}/?server=http://127.0.0.1:{args.port}"
                },
            )
            for seconds in (
                10,
                max(1, (args.seconds - 10) / 2),
                max(1, (args.seconds - 10) / 2),
            ):
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    try:
                        events.append(json.loads(ws.recv(timeout=min(.2, max(.001, deadline-time.monotonic())))))
                    except TimeoutError:
                        pass
                image = call(
                    "Page.captureScreenshot",
                    {"format": "png", "captureBeyondViewport": False},
                )
                (out / f"frame-{counter}.png").write_bytes(
                    base64.b64decode(image["data"])
                )
            result = call(
                "Runtime.evaluate",
                {
                    "expression": "JSON.stringify({title:document.title,resources:performance.getEntriesByType('resource').map(e=>({name:e.name,size:e.transferSize,start_ms:e.startTime,duration_ms:e.duration,decoded_bytes:e.decodedBodySize})),text:document.body.innerText})",
                    "returnByValue": True,
                },
            )
            (out / "runtime.json").write_text(
                json.dumps(
                    {"page": result, "events": events}, ensure_ascii=False, indent=2
                ),
                encoding="utf8",
            )
        print(out, flush=True)
    finally:
        child.terminate()
        child.wait(timeout=10)
        httpd.shutdown()
        log.close()


if __name__ == "__main__":
    main()
