"""Windows host for the real Flet game + locally bundled Flutter/Rive client.

WebView2 provides the accelerated window; no Visual Studio install is needed.
The server and UI bind to loopback only. No game assets depend on a CDN.
"""

import functools
import json
import http.server
import os
import socket
import secrets
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path


def bundle_root():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def available_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def serve_game(port):
    import flet as ft

    if sys.stdout is None or sys.stderr is None:
        data = Path(
            os.getenv("FLET_APP_STORAGE_DATA", str(Path.home() / ".clicker-runtime"))
        )
        data.mkdir(parents=True, exist_ok=True)
        runtime_log = (data / "windows-runtime.log").open(
            "a", encoding="utf-8", buffering=1
        )
        sys.stdout = sys.stderr = runtime_log

    root = bundle_root()
    if not getattr(sys, "frozen", False):
        sys.path.insert(0, str(root / "src"))
    os.environ["CLICKER_DESKTOP_HOST"] = "1"
    os.environ["FLET_FORCE_WEB_SERVER"] = "1"
    from main import main

    assets = (
        root / "game_assets" if getattr(sys, "frozen", False) else root / "src/assets"
    )
    ft.run(main, view=None, host="127.0.0.1", port=port, assets_dir=str(assets))


def main():
    if "--serve" in sys.argv:
        serve_game(int(sys.argv[sys.argv.index("--serve") + 1]))
        return
    import webview

    self_test = "--self-test" in sys.argv
    test_report = None
    if self_test:
        index = sys.argv.index("--self-test")
        test_report = Path(sys.argv[index + 1]).resolve()
        # A packaged startup check must never open the player's real save.
        if not os.getenv("CLICKER_WINDOWS_DATA"):
            raise RuntimeError("Self-test requires a separate CLICKER_WINDOWS_DATA directory")

    root = bundle_root()
    client = (
        root / "client"
        if getattr(sys, "frozen", False)
        else root / "tools/game_client/build/web"
    )
    if not (client / "index.html").is_file():
        raise RuntimeError(
            "Build the Flutter game client with tools/build_windows_game.py"
        )
    data = Path(os.getenv("CLICKER_WINDOWS_DATA",str(Path(os.getenv("APPDATA", str(Path.home()))) / "Clicker/data")))
    data.mkdir(parents=True, exist_ok=True)
    port = available_port()
    command = (
        [sys.executable]
        + ([] if getattr(sys, "frozen", False) else [str(Path(__file__).resolve())])
        + ["--serve", str(port)]
    )
    env = dict(
        os.environ,
        FLET_APP_STORAGE_DATA=str(data),
        CLICKER_DESKTOP_HOST="1",
        PYTHONUTF8="1",
    )
    if self_test:
        env["CLICKER_DEMO"] = "1"
    log = (data / "windows-runtime.log").open("a", encoding="utf-8")
    host_token = secrets.token_urlsafe(24)

    class Assets(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            if (
                self.path != "/host/scene"
                or self.headers.get("X-Clicker-Host") != host_token
            ):
                self.send_error(403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length < 512:
                    raise ValueError("Invalid message")
                message = json.loads(self.rfile.read(length))
                if webview.windows:
                    webview.windows[0].resize(
                        *((960, 540) if message.get("expanded") else (460, 880))
                    )
                self.send_response(204)
                self.end_headers()
            except (ValueError, KeyError):
                self.send_error(400)

    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Assets, directory=str(client))
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    env.update(
        CLICKER_DESKTOP_HOST_URL=f"http://127.0.0.1:{httpd.server_port}",
        CLICKER_HOST_TOKEN=host_token,
    )
    process = subprocess.Popen(
        command,
        env=env,
        stdout=log,
        stderr=log,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        for _ in range(150):
            if process.poll() is not None:
                raise RuntimeError("Game server stopped; see windows-runtime.log")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=0.5):
                    break
            except OSError:
                time.sleep(0.1)
        address = (
            f"http://127.0.0.1:{httpd.server_port}/?server=http://127.0.0.1:{port}"
        )
        window = webview.create_window(
            "Clicker · Робо-мастерская",
            address,
            width=460,
            height=880,
            min_size=(360, 520),
            background_color="#F5F7FB",
        )

        def check_packaged_game():
            started = time.monotonic()
            result = {"ok": False, "isolated_data": str(data)}
            try:
                if not window.events.loaded.wait(60):
                    raise RuntimeError("Game window did not finish loading")
                while time.monotonic() - started < 90:
                    sample = window.evaluate_js("""JSON.stringify((() => {
                        const roots=[document]; let canvas=false;
                        for(let i=0;i<roots.length;i++) for(const e of roots[i].querySelectorAll('*')) {
                            if(e.tagName==='CANVAS')canvas=true;
                            if(e.shadowRoot)roots.push(e.shadowRoot);
                        }
                        return {title:document.title,canvas};
                    })())""")
                    if sample:
                        result.update(json.loads(sample))
                    if result.get("canvas") and "Preview" in result.get("title", ""):
                        time.sleep(3)
                        result["ok"] = True
                        break
                    time.sleep(0.4)
            except Exception as error:
                result["error"] = f"{type(error).__name__}: {error}"
            finally:
                result["seconds"] = round(time.monotonic() - started, 2)
                test_report.parent.mkdir(parents=True, exist_ok=True)
                test_report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                window.destroy()

        webview.start(
            func=check_packaged_game if self_test else None,
            gui="edgechromium", private_mode=False, storage_path=str(data / "webview")
        )
    finally:
        httpd.shutdown()
        # This is only the child process started above, never another game.
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        log.close()


if __name__ == "__main__":
    main()
