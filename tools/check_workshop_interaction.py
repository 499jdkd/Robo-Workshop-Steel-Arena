"""Exercise real packaged Flet/Rive pointer events against an isolated save."""

import argparse
import base64
import functools
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import sys
from urllib.request import urlopen

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-number", type=int, required=True)
    parser.add_argument("--robot", default="spark", choices=("spark", "volt"))
    parser.add_argument("--source", action="store_true", help="Use the current game source and its compiled Flutter client")
    parser.add_argument("--tap-x", type=float, default=195,
                        help="Screen X of the visible robot after the floor movement")
    args = parser.parse_args()
    game = ROOT / f"build/windows-motion-v{args.build_number}/Clicker"
    client = ROOT / "tools/game_client/build/web" if args.source else game / "_internal/client"
    out = (ROOT / f".cache/interaction-v27/packaged-input-v{args.build_number}").resolve()
    assert out.is_relative_to((ROOT / ".cache").resolve())
    data = out / "data"
    data.mkdir(parents=True, exist_ok=True)
    save = data / "workshop-save-v2.json"
    now = time.time()
    sys.path.insert(0, str(ROOT / "src"))
    from gameplay import GameState
    fixture = GameState(level=6, coin=100, food=0, robot_levels={args.robot:3},
                        active_robot=args.robot, egg_id="", last_active_at=now)
    save.write_text(json.dumps({"schema": 2, "device_id": "synthetic-pointer-check", "trusted": True,
        "saved_at": now, "state": fixture.to_dict()}), encoding="utf-8")
    (out / "scenes.jsonl").write_text("", encoding="utf-8")
    port, debugging = free_port(), free_port()
    env = dict(os.environ, FLET_APP_STORAGE_DATA=str(data), CLICKER_WINDOWS_DATA=str(data),
               CLICKER_DEMO="0", CLICKER_SCENE_DIAGNOSTICS=str(out / "scenes.jsonl"),
               HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9", NO_PROXY="127.0.0.1,localhost")
    log = (out / "server.log").open("w", encoding="utf-8")
    command = [sys._base_executable, "-c",
        "import site,sys,runpy;site.addsitedir(sys.argv[1]);p=sys.argv[2];sys.argv=sys.argv[2:];runpy.run_path(p,run_name='__main__')",
        str(Path(sys.prefix) / "Lib/site-packages"), str(ROOT / "tools/windows_game.py")] if args.source else [str(game / "Clicker.exe")]
    worker = subprocess.Popen([*command, "--serve", str(port)], env=env,
                              stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
        functools.partial(Quiet, directory=str(client)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    chrome_log = (out / "chrome.log").open("w", encoding="utf-8")
    browser = subprocess.Popen(["C:/Program Files/Google/Chrome/Application/chrome.exe", "--headless=new",
        "--no-first-run", f"--remote-debugging-port={debugging}", "--remote-allow-origins=http://localhost",
        f"--user-data-dir={out / 'chrome-profile'}", "--hide-scrollbars", "about:blank"], stdout=chrome_log, stderr=chrome_log)
    (out / "owned-processes.json").write_text(json.dumps({"server_pid":worker.pid,"browser_pid":browser.pid,"port":port,"source":args.source}),encoding="utf-8")
    try:
        for _ in range(150):
            try:
                urlopen(f"http://127.0.0.1:{port}", timeout=.3).close()
                tabs = json.load(urlopen(f"http://127.0.0.1:{debugging}/json", timeout=.3))
                target = next(t for t in tabs if t["type"] == "page")
                break
            except (OSError, StopIteration):
                time.sleep(.2)
        else:
            raise RuntimeError("Packaged server or isolated browser did not start")
        with connect(target["webSocketDebuggerUrl"], origin="http://localhost", max_size=40_000_000) as ws:
            sequence = 0
            def call(method, params=None):
                nonlocal sequence
                sequence += 1
                ws.send(json.dumps({"id":sequence,"method":method,"params":params or {}}))
                while True:
                    result = json.loads(ws.recv(timeout=30))
                    if result.get("id") == sequence:
                        if "error" in result:
                            raise RuntimeError(result["error"])
                        return result.get("result", {})
            call("Page.enable")
            call("Emulation.setDeviceMetricsOverride", {"width":390,"height":844,"deviceScaleFactor":1,"mobile":False})
            call("Page.navigate", {"url":f"http://127.0.0.1:{server.server_port}/?server=http://127.0.0.1:{port}"})
            for _ in range(150):
                ready = out / "scenes.jsonl"
                if ready.exists() and ready.stat().st_size:
                    break
                time.sleep(.2)
            else:
                raise RuntimeError("Native robot never reported first paint")
            time.sleep(.6)
            def state():
                return json.loads(save.read_text(encoding="utf-8"))["state"]
            def screenshot(name):
                result = call("Page.captureScreenshot", {"format":"png","captureBeyondViewport":False})
                (out / f"{name}.png").write_bytes(base64.b64decode(result["data"]))
            def click(x, y, hold=.06):
                call("Input.dispatchMouseEvent", {"type":"mouseMoved","x":x,"y":y})
                call("Input.dispatchMouseEvent", {"type":"mousePressed","x":x,"y":y,"button":"left","clickCount":1,"buttons":1})
                time.sleep(hold)
                call("Input.dispatchMouseEvent", {"type":"mouseReleased","x":x,"y":y,"button":"left","clickCount":1})
            screenshot("before")
            baseline = state()
            click(90,450)
            time.sleep(1.6)
            assert state()["manual_taps"] == baseline["manual_taps"], "Floor tap awarded resources"
            screenshot("moved")
            click(args.tap_x,405,hold=.9)
            time.sleep(.3)
            assert state()["manual_taps"] == baseline["manual_taps"], "Long press awarded resources"
            time.sleep(1.8)
            for _ in range(5):
                click(args.tap_x,405)
            for _ in range(60):
                if state()["manual_taps"] == baseline["manual_taps"] + 5:
                    break
                time.sleep(.1)
            after = state()
            screenshot("after")
            assert after["manual_taps"] == baseline["manual_taps"] + 5, (baseline["manual_taps"], after["manual_taps"])
            # Volt retains his automatic income, unlike Spark's click bonus.
            # Its recorded automatic taps must be separated from manual reward.
            manual_coins = 5 * GameState.from_dict(baseline).click_power(time.time())
            passive_coins = after["session_taps"] - baseline["session_taps"] - 5
            assert passive_coins >= 0
            assert after["coin"] - baseline["coin"] == manual_coins + passive_coins, (baseline["coin"], after["coin"], manual_coins, passive_coins)
            assert after["purchases"] == baseline["purchases"]
            assert after["feedings"] > baseline["feedings"], "Original automatic feeding stopped working"
            report = {"build":args.build_number,"main_packaged_game":not args.source,"main_game_source":args.source,"robot":args.robot,
                "client":"Current main-game worker and compiled Flutter client, Chrome headless" if args.source else "Windows EXE worker and bundled Flutter/Rive client, Chrome headless",
                "floor_awards":0,"long_press_awards":0,"rapid_robot_taps":5,
                "robot_tap_screen_x":args.tap_x,
                "recorded_taps":after["manual_taps"]-baseline["manual_taps"],
                "coins_from_taps":manual_coins,"passive_coins_preserved":passive_coins,"automatic_feeding_preserved":True,
                "isolated_data":str(data),"real_player_save_opened":False,"android_device":False}
            (out / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report), flush=True)
            call("Browser.close")
    finally:
        for child in (browser, worker):
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=10)
        server.shutdown()
        log.close()
        chrome_log.close()


if __name__ == "__main__":
    main()
