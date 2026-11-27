"""Windows host for the real Flet game + locally bundled Flutter/Rive client.

WebView2 provides the accelerated window; no Visual Studio install is needed.
The server and UI bind to loopback only. No game assets depend on a CDN.
"""

import functools
import base64
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
    os.environ["FLET_SERVER_PORT"] = str(port)
    os.environ["FLET_SERVER_IP"] = "127.0.0.1"
    os.environ.pop("FLET_SERVER_UDS_PATH", None)
    from main import main

    app = main
    scope = os.getenv("CLICKER_WINDOWS_TEST_SCENE", "")
    if scope:
        if os.getenv("CLICKER_DEMO") != "1" or not os.getenv("CLICKER_WINDOWS_DATA"):
            raise RuntimeError("Scene QA requires isolated preview data")

        async def app(page):
            session = await main(page)
            if scope in {"workshop", "battle"}:
                if scope == "battle":
                    session.act("battle_start", "spark")
                from display_mode import set_scene_focus

                await set_scene_focus(page, session, scope)
            elif scope != "normal":
                raise ValueError("Unknown QA scene")

    assets = (
        root / "game_assets" if getattr(sys, "frozen", False) else root / "src/assets"
    )
    ft.run(app, view=None, host="127.0.0.1", port=port, assets_dir=str(assets))


def watch_cli_launcher(window):
    """Close this owned window if Flet hot reload kills its venv launcher."""
    if not os.getenv("FLET_DISPLAY_URL_PREFIX") or getattr(sys, "frozen", False):
        return
    import ctypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x100000, False, os.getppid())
    if not handle:
        return

    def wait():
        try:
            kernel.WaitForSingleObject(handle, 0xFFFFFFFF)
            window.destroy()
        finally:
            kernel.CloseHandle(handle)

    threading.Thread(target=wait, daemon=True).start()


def capture_owned_window(window, destination):
    """Capture our own WebView2 game surface through its supported CDP API."""
    from System import Func, Object

    browser = window.native.webview
    task = browser.Invoke(
        Func[Object](
            lambda: browser.CoreWebView2.CallDevToolsProtocolMethodAsync(
                "Page.captureScreenshot",
                '{"format":"png","captureBeyondViewport":false}',
            )
        )
    )
    destination.write_bytes(base64.b64decode(json.loads(task.Result)["data"]))


def main():
    if "--serve" in sys.argv:
        serve_game(int(sys.argv[sys.argv.index("--serve") + 1]))
        return
    import webview

    self_test = "--self-test" in sys.argv or bool(
        os.getenv("CLICKER_WINDOWS_TEST_REPORT")
    )
    test_report = None
    if self_test:
        test_report = (
            Path(os.environ["CLICKER_WINDOWS_TEST_REPORT"]).resolve()
            if os.getenv("CLICKER_WINDOWS_TEST_REPORT")
            else Path(sys.argv[sys.argv.index("--self-test") + 1]).resolve()
        )
        # A packaged startup check must never open the player's real save.
        if not os.getenv("CLICKER_WINDOWS_DATA"):
            raise RuntimeError(
                "Self-test requires a separate CLICKER_WINDOWS_DATA directory"
            )

    root = bundle_root()
    if not getattr(sys, "frozen", False):
        sys.path.insert(0, str(root / "src"))
    from desktop_startup import (
        ensure_source_client,
        storage_directory,
        validate_client,
        worker_environment,
    )

    client = (
        root / "client" if getattr(sys, "frozen", False) else ensure_source_client(root)
    )
    validate_client(client)
    data = storage_directory(root, frozen=bool(getattr(sys, "frozen", False)))
    data.mkdir(parents=True, exist_ok=True)
    port = available_port()
    command = (
        [sys.executable]
        if getattr(sys, "frozen", False)
        else [
            getattr(sys, "_base_executable", sys.executable),
            "-c",
            "import site,sys,runpy;site.addsitedir(sys.argv[1]);sys.path.insert(0,sys.argv[1]);p=sys.argv[2];sys.argv=sys.argv[2:];runpy.run_path(p,run_name='__main__')",
            str(Path(sys.prefix) / "Lib/site-packages"),
            str(Path(__file__).resolve()),
        ]
    ) + ["--serve", str(port)]
    env = worker_environment(data, port)
    if not getattr(sys, "frozen", False):
        paths = [str(Path(sys.prefix) / "Lib/site-packages"), str(root / "src")]
        if env.get("PYTHONPATH"):
            paths.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(paths)
    if self_test:
        env["CLICKER_DEMO"] = "1"
        scene_report = test_report.with_suffix(".scenes.jsonl")
        scene_report.parent.mkdir(parents=True, exist_ok=True)
        scene_report.write_text("", encoding="utf-8")
        env["CLICKER_SCENE_DIAGNOSTICS"] = str(scene_report)
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
        watch_cli_launcher(window)

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
                    scenes = [
                        json.loads(line)
                        for line in scene_report.read_text(
                            encoding="utf-8"
                        ).splitlines()
                        if line.strip()
                    ]
                    expected = os.getenv("CLICKER_WINDOWS_TEST_SCENE", "normal")
                    matching = [
                        s
                        for s in scenes
                        if s.get("robot")
                        and (expected == "normal" or s.get("expanded"))
                        and (expected != "battle" or s.get("arena") and s.get("enemy"))
                    ]
                    if result.get("canvas") and matching:
                        time.sleep(1)
                        result["painted_scenes"] = matching
                        screenshot = test_report.with_suffix(".png")
                        capture_owned_window(window, screenshot)
                        result["screenshot"] = str(screenshot)
                        result["ok"] = True
                        break
                    time.sleep(0.4)
            except Exception as error:
                result["error"] = f"{type(error).__name__}: {error}"
            finally:
                result["seconds"] = round(time.monotonic() - started, 2)
                test_report.parent.mkdir(parents=True, exist_ok=True)
                test_report.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                window.destroy()

        webview.start(
            func=check_packaged_game if self_test else None,
            gui="edgechromium",
            private_mode=False,
            storage_path=str(data / "webview"),
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
