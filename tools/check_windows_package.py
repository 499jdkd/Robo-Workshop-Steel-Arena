"""Launch the packaged main-game server and client with isolated demo data."""

import argparse
import functools
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import urllib.request

from flutter_cached import environment

os.environ.update(environment())

import webview

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-number", type=int, default=21)
    args = parser.parse_args()
    game = ROOT / f"build/windows-motion-v{args.build_number}/Clicker"
    output = ROOT / f".cache/windows-package-v{args.build_number}"
    output.mkdir(exist_ok=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        functools.partial(Quiet, directory=str(game / "_internal/client")),
    )
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    stream = (output / "server.log").open("w", encoding="utf-8")
    test_data = output / "data"
    test_data.mkdir(exist_ok=True)
    # An owned robot and no selected egg exercise the actual animated workshop.
    (test_data / "workshop-save-v2.json").write_text(json.dumps({
        "schema": 2, "device_id": "synthetic-package-check", "trusted": True,
        "saved_at": time.time(), "state": {"level": 6, "coin": 370, "food": 35,
        "robot_levels": {"spark": 3}, "active_robot": "spark", "egg_id": "",
        "last_active_at": time.time()},
    }), encoding="utf-8")
    env = dict(os.environ, CLICKER_DEMO="0", FLET_APP_STORAGE_DATA=str(test_data),
               HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9",
               NO_PROXY="127.0.0.1,localhost")
    child = subprocess.Popen([str(game / "Clicker.exe"), "--serve", str(port)], env=env,
                             stdout=stream, stderr=stream, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        started = time.monotonic()
        while time.monotonic() - started < 60:
            if child.poll() is not None:
                raise RuntimeError("Packaged game server stopped")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=.5):
                    break
            except OSError:
                time.sleep(.2)
        window = webview.create_window("Clicker · Package verification",
            f"http://127.0.0.1:{httpd.server_port}/?server=http://127.0.0.1:{port}",
            width=900, height=700, background_color="#F5F7FB")

        def inspect():
            result = {"ok": False}
            started = time.monotonic()
            try:
                if not window.events.loaded.wait(60):
                    raise RuntimeError("Game window did not finish loading")
                while time.monotonic() - started < 60:
                    sample = window.evaluate_js("""JSON.stringify((() => {
                      const roots=[document]; const tags={}; let canvas=0;
                      for(let i=0;i<roots.length;i++) for(const e of roots[i].querySelectorAll('*')) {
                        tags[e.tagName]=(tags[e.tagName]||0)+1;
                        if(e.tagName==='CANVAS')canvas++;
                        if(e.shadowRoot)roots.push(e.shadowRoot);
                      }
                      return {title:document.title,canvas,tags,text:document.body.innerText,
                        resources:performance.getEntriesByType('resource').map(e=>({name:e.name,bytes:e.transferSize}))};
                    })())""")
                    if sample:
                        result.update(json.loads(sample))
                    if result.get("canvas") and any(
                        "game_robot.riv" in r["name"] for r in result.get("resources", [])
                    ):
                        time.sleep(5)
                        result["ok"] = True
                        break
                    time.sleep(.5)
            except Exception as error:
                result["error"] = f"{type(error).__name__}: {error}"
            finally:
                result["seconds"] = round(time.monotonic() - started, 2)
                (output / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                print(json.dumps(result, ensure_ascii=False), flush=True)
                window.destroy()

        webview.start(func=inspect, gui="edgechromium", private_mode=False,
                      storage_path=str(output / "webview"))
    finally:
        child.terminate()
        child.wait(timeout=10)
        httpd.shutdown()
        stream.close()


if __name__ == "__main__":
    main()
