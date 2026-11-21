import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desktop_startup import mode, storage_directory, validate_client, worker_environment
from gameplay import GameState
from local_store import LocalStore


class DesktopStartupTests(unittest.TestCase):
    def test_flet_native_cli_uses_the_custom_host_even_with_an_assigned_port(self):
        self.assertEqual(mode("win32", False, {"FLET_SERVER_PORT": "60484"}), "desktop")
        self.assertEqual(mode("win32", False, {"FLET_FORCE_WEB_SERVER": "true"}), "web")
        self.assertEqual(mode("win32", True, {"FLET_SERVER_PORT": "60484"}), "embedded")
        self.assertEqual(mode("android", True, {}), "embedded")

    def test_private_worker_does_not_reuse_the_cli_transport(self):
        env = worker_environment(
            Path("private-save"),
            12345,
            environ={
                "FLET_SERVER_PORT": "60484",
                "FLET_SERVER_UDS_PATH": "old.sock",
                "FLET_DISPLAY_URL_PREFIX": "PAGE_URL_old",
                "FLET_WEB_APP_PATH": "old",
                "FLET_APP_STORAGE_CACHE": "keep-cache",
                "FLET_APP_STORAGE_TEMP": "keep-temp",
            },
        )
        self.assertEqual(env["FLET_SERVER_PORT"], "12345")
        self.assertEqual(env["FLET_APP_STORAGE_DATA"], "private-save")
        self.assertNotIn("FLET_SERVER_UDS_PATH", env)
        self.assertNotIn("FLET_DISPLAY_URL_PREFIX", env)
        self.assertNotIn("FLET_WEB_APP_PATH", env)
        self.assertEqual(env["FLET_APP_STORAGE_CACHE"], "keep-cache")
        self.assertEqual(env["FLET_APP_STORAGE_TEMP"], "keep-temp")

    def test_source_launch_restores_existing_flet_progress_without_moving_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "src/.flet/storage/data"
            LocalStore(source).save(
                {
                    "schema": 2,
                    "state": {
                        "coin": 917,
                        "robot_levels": {"spark": 5},
                        "active_robot": "spark",
                    },
                }
            )
            before = (source / "workshop-save-v2.json").read_bytes()
            chosen = storage_directory(root, environ={"APPDATA": str(root / "appdata")})
            restored = GameState.from_dict(LocalStore(chosen).load()["state"])
            self.assertEqual(chosen, source)
            self.assertEqual(restored.coin, 917)
            self.assertEqual(restored.robot_levels["spark"], 5)
            self.assertEqual((source / "workshop-save-v2.json").read_bytes(), before)
            self.assertEqual(
                storage_directory(
                    root, frozen=True, environ={"APPDATA": str(root / "appdata")}
                ),
                root / "appdata/Clicker/data",
            )
            self.assertEqual(
                storage_directory(root, environ={"FLET_APP_STORAGE_DATA": "cli-save"}),
                Path("cli-save"),
            )

    def test_stock_client_is_rejected_before_any_game_control_is_sent(self):
        with tempfile.TemporaryDirectory() as directory:
            client = Path(directory)
            (client / "rive/wasm").mkdir(parents=True)
            (client / "index.html").write_text("<html></html>")
            (client / "rive/wasm/rive_native.wasm").write_bytes(b"test")
            (client / "main.dart.js").write_text('controls = ["Rive", "Text"]')
            with self.assertRaisesRegex(RuntimeError, "stock Flet client"):
                validate_client(client)
            (client / "main.dart.js").write_text(
                json.dumps(["GameRive", "GameCountdown", "GameFactory", "GameMusic"])
            )
            validate_client(client)
