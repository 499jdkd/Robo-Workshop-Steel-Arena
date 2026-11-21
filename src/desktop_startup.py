"""Choose a client that actually contains the game's Flutter extensions."""

import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

CONTROLS = ("GameRive", "GameCountdown", "GameFactory", "GameMusic")
CLI_TRANSPORT = (
    "FLET_SERVER_PORT",
    "FLET_SERVER_IP",
    "FLET_SERVER_UDS_PATH",
    "FLET_DISPLAY_URL_PREFIX",
    "FLET_WEB_APP_PATH",
    "FLET_WEB_PATH",
    "FLET_FORCE_WEB_SERVER",
    "FLET_HIDE_WINDOW_ON_START",
)


def source_fingerprint(root):
    files = [
        root / "tools/game_client/pubspec.yaml",
        root / "extensions/flet_rive/pubspec.yaml",
    ]
    for folder in ("tools/game_client/lib", "extensions/flet_rive/lib"):
        files.extend((root / folder).rglob("*.dart"))
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(files)
    }


def validate_client(client):
    for relative in ("index.html", "main.dart.js", "rive/wasm/rive_native.wasm"):
        if not (client / relative).is_file():
            raise RuntimeError(f"Game client is incomplete: {relative}")
    javascript = (client / "main.dart.js").read_bytes()
    missing = [name for name in CONTROLS if name.encode() not in javascript]
    if missing:
        raise RuntimeError(
            "This is the stock Flet client; missing: " + ", ".join(missing)
        )


def write_contract(root, client):
    validate_client(client)
    contract = dict(controls=list(CONTROLS), sources=source_fingerprint(root))
    (client / "game-client.json").write_text(
        json.dumps(contract, indent=2), encoding="utf-8"
    )


def ensure_source_client(root):
    client = root / "tools/game_client/build/web"
    try:
        validate_client(client)
        contract = json.loads((client / "game-client.json").read_text(encoding="utf-8"))
        if contract["sources"] == source_fingerprint(root):
            return client
    except (OSError, ValueError, KeyError, RuntimeError):
        pass
    print(
        "Preparing Robo Workshop's animation client (first run or changed Dart files)...",
        flush=True,
    )
    subprocess.run(
        [sys.executable, str(root / "tools/build_game_client.py")], cwd=root, check=True
    )
    validate_client(client)
    return client


def storage_directory(root, *, frozen=False, environ=None):
    env = os.environ if environ is None else environ
    explicit = env.get("CLICKER_WINDOWS_DATA") or env.get("FLET_APP_STORAGE_DATA")
    if explicit:
        return Path(explicit)
    # Source launches keep the same existing progress as `flet run src/main.py`.
    development = root / "src/.flet/storage/data"
    if not frozen and (development / "workshop-save-v2.json").is_file():
        return development
    return Path(env.get("APPDATA", str(Path.home()))) / "Clicker/data"


def worker_environment(data, port, *, environ=None):
    env = dict(os.environ if environ is None else environ)
    # CLI ports belong to the stock client. This host owns its own HTTP port.
    for key in CLI_TRANSPORT:
        env.pop(key, None)
    env.update(
        FLET_APP_STORAGE_DATA=str(data),
        CLICKER_DESKTOP_HOST="1",
        FLET_FORCE_WEB_SERVER="1",
        FLET_SERVER_PORT=str(port),
        FLET_SERVER_IP="127.0.0.1",
        PYTHONUTF8="1",
        PYTHONIOENCODING="utf-8",
    )
    return env


def mode(platform, embedded, environ):
    if platform != "win32" or embedded:
        return "embedded"
    if environ.get("FLET_FORCE_WEB_SERVER", "").lower() in {"1", "true", "yes"}:
        return "web"
    return "desktop"


def run(app):
    import flet as ft
    from flet.utils import is_embedded

    selected = mode(sys.platform, is_embedded(), os.environ)
    root = Path(__file__).resolve().parents[1]
    if selected == "desktop":
        # `flet run` must not hand GameRive to the prebuilt stock desktop client.
        # Our host's worker logs privately, so CLI never opens that stock view.
        runpy.run_path(str(root / "tools/windows_game.py"), run_name="__main__")
    else:
        if selected == "web":
            os.environ["FLET_WEB_PATH"] = str(ensure_source_client(root))
        ft.run(app)
