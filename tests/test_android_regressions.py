"""Offline regression checks: python -m unittest discover -s tests -v."""

import ast
import asyncio
import importlib
import json
import sys
import unittest
import uuid
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import flet as ft
import httpx
import tomllib
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import config  # noqa: E402
import leaderboard  # noqa: E402
import main  # noqa: E402
from game_session import GameSession  # noqa: E402
from gameplay import GameState  # noqa: E402
from local_store import MemoryStore  # noqa: E402


class PackagingTests(unittest.TestCase):
    def test_runtime_dependencies_are_declared(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        dependencies = {
            requirement.name: requirement
            for requirement in map(Requirement, project["project"]["dependencies"])
        }
        local_modules = {path.stem for path in (ROOT / "src").glob("*.py")}
        imports = set()
        for path in (ROOT / "src").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module.split(".")[0])
        external_imports = imports - sys.stdlib_module_names - local_modules
        dependency_imports = {name.replace("-", "_") for name in dependencies}
        self.assertFalse(
            external_imports - dependency_imports,
            "An app import is missing from APK dependencies",
        )
        for dependency in dependencies.values():
            self.assertIn(version(dependency.name), dependency.specifier)
        self.assertEqual(project["tool"]["flet"]["app"]["path"], "src")

    def test_app_sources_compile_and_do_not_import_aiohttp(self):
        for path in (ROOT / "src").glob("*.py"):
            with self.subTest(path=path.name):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        self.assertNotIn(
                            "aiohttp", [alias.name for alias in node.names]
                        )
                    elif isinstance(node, ast.ImportFrom):
                        self.assertNotEqual(node.module, "aiohttp")


class NetworkTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.requests = []
        self.status = 200
        self.body = "null"
        self.error = None
        self.client_type = httpx.AsyncClient
        self.transport = httpx.MockTransport(self.handle_request)
        self.client_patch = patch.object(
            leaderboard.httpx,
            "AsyncClient",
            side_effect=lambda **kwargs: self.client_type(
                transport=self.transport, **kwargs
            ),
        )
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)
        logger_patch = patch.object(leaderboard, "logger")
        logger_patch.start()
        self.addCleanup(logger_patch.stop)
        self.manager = leaderboard.LeaderboardManager(
            "existing-device", db_url="https://example.test/leaderboard"
        )

    async def asyncTearDown(self):
        await self.manager.close()

    def handle_request(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return httpx.Response(self.status, text=self.body)

    async def test_loads_existing_progress(self):
        progress = {
            "id": "existing-device",
            "level": 7,
            "coin": 123,
            "username": "Player",
        }
        self.body = json.dumps(progress)
        self.assertEqual(await self.manager.get_run(), progress)
        self.assertEqual(
            str(self.requests[0].url), "https://example.test/user/existing-device"
        )

    async def test_missing_or_invalid_progress_does_not_block_startup(self):
        for body in ("", "null", "[]", "broken json"):
            with self.subTest(body=body):
                self.body = body
                self.assertIsNone(await self.manager.get_run())

    async def test_offline_startup_and_leaderboard(self):
        self.error = httpx.ConnectError("offline")
        self.assertIsNone(await self.manager.get_run())
        self.assertEqual(await self.manager.get_top_5(), [])

    async def test_server_errors_do_not_become_player_progress(self):
        self.status = 503
        self.body = '{"detail": "unavailable"}'
        self.assertIsNone(await self.manager.get_run())
        self.assertEqual(await self.manager.get_top_5(), [])

    async def test_leaderboard_orders_and_limits_players(self):
        players = [
            {"id": "low", "level": 1, "taps": 999, "time": 1},
            {"id": "slow", "level": 4, "taps": 20, "time": 30},
            {"id": "fast", "level": 4, "taps": 20, "time": 10},
            {"id": "more-taps", "level": 4, "taps": 21, "time": 100},
            {"id": "highest", "level": 5, "taps": 1, "time": 100},
            {"id": "middle", "level": 2, "taps": 1, "time": 1},
            None,
        ]
        self.body = json.dumps(players)
        top = await self.manager.get_top_5()
        self.assertEqual(
            [p["id"] for p in top], ["highest", "more-taps", "fast", "slow", "middle"]
        )

    async def test_leaderboard_accepts_dictionary_response(self):
        self.body = '{"a": {"id": "a", "level": 2}, "b": null}'
        self.assertEqual(await self.manager.get_top_5(), [{"id": "a", "level": 2}])

    async def test_empty_or_invalid_leaderboard_is_a_list(self):
        for body in ("", "null", "[]", "broken json", '"unexpected"'):
            with self.subTest(body=body):
                self.body = body
                self.assertEqual(await self.manager.get_top_5(force=True), [])

    async def test_failed_profile_lookup_is_distinct_from_a_new_player(self):
        self.status = 503
        with self.assertRaises(httpx.HTTPStatusError):
            await self.manager.fetch_run()
        self.status = 200
        self.body = "null"
        self.assertIsNone(await self.manager.fetch_run())

    async def test_leaderboard_shares_concurrent_requests_and_uses_cache(self):
        started, release = asyncio.Event(), asyncio.Event()

        async def slow_request(request):
            self.requests.append(request)
            started.set()
            await release.wait()
            return httpx.Response(200, json=[{"id": "a", "level": 3}])

        self.transport = httpx.MockTransport(slow_request)
        first = asyncio.create_task(self.manager.get_top_5())
        await started.wait()
        second = asyncio.create_task(self.manager.get_top_5(force=True))
        await asyncio.sleep(0)
        release.set()
        self.assertEqual(await first, await second)
        self.assertEqual(await self.manager.get_top_5(), [{"id": "a", "level": 3}])
        self.assertEqual(len(self.requests), 1)

    async def test_failed_refresh_keeps_last_leaderboard(self):
        self.body = '[{"id": "a", "level": 3}]'
        await self.manager.get_top_5()
        self.error = httpx.ConnectError("offline")
        self.assertEqual(
            await self.manager.get_top_5(force=True), [{"id": "a", "level": 3}]
        )
        self.assertTrue(self.manager.board_error)

    async def test_timeout_keeps_cached_board_and_throttles_automatic_retries(self):
        with patch.object(leaderboard.time, "monotonic", return_value=100) as clock:
            self.body = '[{"id": "cached", "level": 3}]'
            expected = await self.manager.get_top_5()
            self.error = httpx.ReadTimeout("")
            self.assertEqual(await self.manager.get_top_5(force=True), expected)
            for _ in range(20):
                self.assertEqual(await self.manager.get_top_5(), expected)
            self.assertEqual(len(self.requests), 2)
            clock.return_value = 131
            self.assertEqual(await self.manager.get_top_5(), expected)
            self.assertEqual(len(self.requests), 3)
            self.assertEqual(self.manager._board_retry_after, 161)
            self.error = None
            self.body = '[{"id": "new", "level": 4}]'
            self.assertEqual(
                await self.manager.get_top_5(force=True), [{"id": "new", "level": 4}]
            )
            self.assertFalse(self.manager.board_error)
            self.assertEqual(self.manager._board_failures, 0)

    async def test_background_server_requests_have_a_bounded_read_timeout(self):
        timeout = self.manager._http().timeout
        self.assertEqual((timeout.read, timeout.connect, timeout.pool), (30, 5, 5))

    async def test_save_preserves_progress_payload(self):
        self.body = '{"status": 200}'
        self.manager.save_run(
            level=7,
            taps=50,
            username="Player",
            base_auto_click_power=2,
            offline_income_power=3,
            coin=123,
            base_click_power=4,
            double_click_price=80,
            boost_level=2,
            boost_price=40,
        )
        await asyncio.sleep(0)
        self.assertEqual(len(self.requests), 1)
        request = self.requests[0]
        self.assertEqual(request.method, "PUT")
        payload = json.loads(request.content)
        for key, expected in {
            "id": "existing-device",
            "level": 7,
            "taps": 50,
            "coin": 123,
            "username": "Player",
            "base_auto_click_power": 2,
            "offline_income_power": 3,
            "base_click_power": 4,
            "double_click_price": 80,
            "boost_level": 2,
            "boost_price": 40,
        }.items():
            self.assertEqual(payload[key], expected, key)
        self.manager.save_run(level=7)
        await asyncio.sleep(0)
        self.assertEqual(len(self.requests), 1, "Saves must still be throttled")


class StartupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = SimpleNamespace(window=SimpleNamespace(), render=Mock())
        self.prefs = SimpleNamespace(
            get=AsyncMock(return_value="existing-device"), set=AsyncMock()
        )
        self.api = SimpleNamespace(
            fetch_run=AsyncMock(return_value=None),
            upload_run=AsyncMock(),
            get_top_5=AsyncMock(return_value=[]),
            close=AsyncMock(),
            board_error=False,
        )
        self.session = GameSession(
            self.page, store=MemoryStore(), manager_factory=lambda identity: self.api
        )
        for patcher in (
            patch.object(main, "GameSession", return_value=self.session),
            patch.object(main, "demo_requested", return_value=False),
            patch.object(main.ft, "SharedPreferences", return_value=self.prefs),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    async def asyncTearDown(self):
        await self.session.close()

    async def test_first_render_does_not_wait_for_identity_or_blocked_server(self):
        started, release = asyncio.Event(), asyncio.Event()

        async def slow_profile():
            self.assertTrue(self.page.render.called)
            started.set()
            await release.wait()
            return {"coin": 50, "base_click_power": 3}

        self.api.fetch_run.side_effect = slow_profile
        returned = await main.main(self.page)
        self.assertIs(returned, self.session)
        self.page.render.assert_called_once_with(
            main.App, page=self.page, device_id="", session=self.session
        )
        self.prefs.get.assert_not_awaited()
        await asyncio.wait_for(started.wait(), timeout=1)
        self.session.act("tap", 2)
        self.assertEqual(self.session.state.coin, 2)
        self.assertEqual(self.session.device_id, "existing-device")
        self.prefs.set.assert_not_awaited()
        release.set()
        for _ in range(4):
            await asyncio.sleep(0)
        self.assertEqual(self.session.state.coin, 56)
        self.assertEqual(self.api.upload_run.await_args.args[0]["coin"], 56)

    async def test_new_identity_is_saved_after_first_render(self):
        self.prefs.get.return_value = None

        async def save_identity(key, identity):
            self.assertTrue(self.page.render.called)
            self.assertEqual(key, "device_id")
            self.assertEqual(str(uuid.UUID(identity)), identity)

        self.prefs.set.side_effect = save_identity
        await main.main(self.page)
        for _ in range(4):
            await asyncio.sleep(0)
        self.prefs.set.assert_awaited_once_with("device_id", self.session.device_id)
        self.api.fetch_run.assert_not_awaited()

    async def test_cached_progress_and_offline_income_are_available_at_first_render(
        self,
    ):
        state = GameState(
            coin=100, level=3, offline_income_power=3, last_active_at=1000
        )
        self.session = GameSession(
            self.page,
            store=MemoryStore(
                {
                    "schema": 2,
                    "state": state.to_dict(),
                    "trusted": True,
                    "device_id": "existing-device",
                    "saved_at": 1000,
                }
            ),
            clock=lambda: 1125,
            manager_factory=lambda identity: self.api,
        )
        with patch.object(main, "GameSession", return_value=self.session):
            await main.main(self.page)
        self.assertEqual((self.session.state.coin, self.session.state.level), (106, 3))
        self.assertEqual(
            self.page.render.call_args.kwargs["device_id"], "existing-device"
        )
        self.api.fetch_run.assert_not_awaited()


class ScreenConstructionTests(unittest.TestCase):
    def setUp(self):
        importlib.reload(config)
        self.addCleanup(importlib.reload, config)
        self.page = SimpleNamespace(
            run_task=Mock(), show_dialog=Mock(), window=SimpleNamespace(close=Mock())
        )

    def test_all_four_screens_construct_flet_controls(self):
        # Stub renderer hooks while using real Flet control constructors.
        for module_name, component_name in (
            ("main_screen", "MainScreen"),
            ("shop_screen", "ShopScreen"),
            ("leaderboard_screen", "LeaderboardScreen"),
            ("profile_screen", "ProfileScreen"),
            ("arena_screen", "ArenaBattles"),
        ):
            with self.subTest(screen=module_name):
                module = importlib.import_module(module_name)
                with (
                    patch.object(
                        ft, "use_state", side_effect=lambda value: (value, Mock())
                    ),
                    patch.object(ft, "use_effect"),
                    patch.object(
                        ft,
                        "use_ref",
                        side_effect=lambda value: SimpleNamespace(current=value),
                    ),
                    patch.object(ft, "use_dialog"),
                ):
                    if module_name == "shop_screen":
                        import collection_ui
                        with (
                            patch.object(collection_ui,'CollectionPanel',return_value=ft.Container()),
                            patch.object(
                                module, "ShopCard", module.ShopCard.__wrapped__
                            ),
                            patch.object(
                                module, "RewardPanel", module.RewardPanel.__wrapped__
                            ),
                        ):
                            result = getattr(module, component_name).__wrapped__(
                                self.page, "existing-device"
                            )
                    elif module_name == "profile_screen":
                        with patch.object(
                            module, "AdDiagnostics", module.AdDiagnostics.__wrapped__
                        ):
                            result = getattr(module, component_name).__wrapped__(
                                self.page, "existing-device"
                            )
                    elif module_name == "main_screen":
                        with patch.object(
                            module, "RewardPanel", module.RewardPanel.__wrapped__
                        ):
                            result = getattr(module, component_name).__wrapped__(
                                self.page, "existing-device"
                            )
                    else:
                        result = getattr(module, component_name).__wrapped__(
                            self.page, "existing-device"
                        )
                self.assertIsInstance(result, ft.Control)

    def test_loaded_leaderboard_and_error_retry_construct(self):
        module = importlib.import_module("leaderboard_screen")
        for error, players in (
            (False, [{"id": "player", "level": 3, "taps": 20, "username": "Player"}]),
            (True, []),
            (True, [{"id": "cached", "username": "Cached player", "level": 2}]),
        ):
            with self.subTest(error=error, cached=bool(players)):
                session = GameSession.preview(self.page, "existing-device")
                session.board_error, session.board = error, players
                session.refresh_board = AsyncMock()
                with (
                    patch.object(
                        ft, "use_state", side_effect=lambda value: (value, Mock())
                    ),
                    patch.object(ft, "use_effect"),
                    patch.object(
                        ft,
                        "use_ref",
                        side_effect=lambda value: SimpleNamespace(current=value),
                    ),
                ):
                    result = module.LeaderboardScreen.__wrapped__(
                        self.page, "existing-device", session=session
                    )
                self.assertIsInstance(result, ft.Control)
                refresh = result.controls[2].controls[1]
                self.assertEqual(refresh.key, "leaderboard-refresh")
                asyncio.run(refresh.on_click(None))
                session.refresh_board.assert_awaited_once_with(force=True)


if __name__ == "__main__":
    unittest.main()
