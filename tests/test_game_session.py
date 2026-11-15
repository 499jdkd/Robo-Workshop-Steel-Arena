import asyncio
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from game_session import GameSession
from gameplay import GameState
from local_store import MemoryStore
from robot_arena import suggested_action


class Clock:
    def __init__(self, now=1000):
        self.now = now

    def __call__(self):
        return self.now


class FakeAPI:
    def __init__(self, profile=None, blocked=False):
        self.profile = profile
        self.uploads = []
        self.fetches = 0
        self.fetch_started = asyncio.Event()
        self.release = asyncio.Event()
        if not blocked:
            self.release.set()
        self.error = None
        self.board_error = False
        self.closed = False

    async def fetch_run(self):
        self.fetches += 1
        self.fetch_started.set()
        await self.release.wait()
        if self.error:
            raise self.error
        return self.profile

    async def upload_run(self, payload):
        self.uploads.append(json.loads(json.dumps(payload)))

    async def get_top_5(self, force=False):
        return []

    async def close(self):
        self.closed = True


def cached(state, identity="existing-device", at=1000, dirty=False, board=None):
    return {
        "schema": 2,
        "state": state.to_dict(),
        "device_id": identity,
        "trusted": True,
        "dirty": dirty,
        "saved_at": at,
        "leaderboard": board or [],
    }


class SessionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = Clock()
        self.sessions = []

    def session(self, payload=None, api=None):
        api = api or FakeAPI()
        session = GameSession(
            store=MemoryStore(payload),
            clock=self.clock,
            manager_factory=lambda identity: api,
        )
        session.manager = api
        self.sessions.append(session)
        return session

    async def asyncTearDown(self):
        for session in self.sessions:
            await session.close()

    async def test_cached_game_is_available_without_waiting_for_network(self):
        session = self.session(
            cached(GameState(coin=120, base_click_power=4, last_active_at=1000))
        )
        self.assertEqual(session.state.coin, 120)
        self.assertTrue(session.trusted)
        self.assertEqual(session.act("tap").coins, 4)
        self.assertEqual(session.state.coin, 124)
        self.assertEqual(session.manager.fetches, 0)

    async def test_cancelled_ranking_request_does_not_notify_after_close(self):
        session = self.session()
        started = asyncio.Event()

        async def blocked_board(force=False):
            started.set()
            await asyncio.Event().wait()

        session.manager.get_top_5 = blocked_board
        listener = Mock()
        session.subscribe(listener)
        task = asyncio.create_task(session.refresh_board())
        await started.wait()
        self.assertEqual(listener.call_count, 1)
        await session.close()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        session.notify()
        self.assertEqual(listener.call_count, 1)
        self.assertFalse(session.board_loading)

    async def test_destroyed_page_is_detected_even_before_disconnect_callback(self):
        class DestroyedPage:
            @property
            def session(self):
                raise RuntimeError("An attempt to fetch destroyed session.")

        session = self.session()
        session.page = DestroyedPage()
        listener = Mock()
        session.subscribe(listener)
        session.notify()
        listener.assert_not_called()
        self.assertEqual(session._listeners, [])

    async def test_destroyed_listener_race_is_removed_but_real_errors_are_reported(
        self,
    ):
        session = self.session()
        session.subscribe(
            Mock(side_effect=RuntimeError("An attempt to fetch destroyed session."))
        )
        session.notify()
        self.assertEqual(session._listeners, [])
        session.subscribe(Mock(side_effect=RuntimeError("actual application bug")))
        with self.assertRaisesRegex(RuntimeError, "actual application bug"):
            session.notify()

    async def test_concurrent_close_only_closes_manager_once(self):
        session = self.session()
        session.manager.close = AsyncMock()
        await asyncio.gather(session.close(), session.close())
        session.manager.close.assert_awaited_once()
        session.subscribe(Mock())
        self.assertEqual(session._listeners, [])

    async def test_slow_cloud_load_does_not_erase_early_taps(self):
        api = FakeAPI(
            {"coin": 100, "base_click_power": 4, "last_update": 900}, blocked=True
        )
        session = self.session(api=api)
        task = asyncio.create_task(session.sync_once())
        await api.fetch_started.wait()
        for _ in range(3):
            session.act("tap")
        self.assertEqual((session.state.coin, len(api.uploads)), (3, 0))
        api.release.set()
        await task
        self.assertEqual((session.state.coin, session.state.manual_taps), (112, 3))
        self.assertEqual(api.uploads[0]["coin"], 112)

    async def test_unknown_remote_profile_is_never_overwritten_when_get_fails(self):
        api = FakeAPI()
        api.error = ConnectionError("offline")
        session = self.session(api=api)
        session.act("tap")
        with self.assertRaises(ConnectionError):
            await session.sync_once()
        self.assertEqual(api.uploads, [])
        self.assertFalse(session.cloud_ready)
        self.assertEqual(session.state.coin, 1)

    async def test_unknown_profile_can_be_tapped_but_not_spent(self):
        session = self.session()
        session.act("tap", 100)
        self.assertFalse(session.act("buy", "click").ok)
        self.assertEqual((session.state.coin, session.state.base_click_power), (100, 1))

    async def test_pending_taps_survive_restart_before_first_cloud_response(self):
        first = self.session()
        first.device_id = "existing-device"
        first.act("tap", 5)
        payload = first.store.load()
        second = self.session(payload, FakeAPI({"coin": 80, "base_click_power": 2}))
        second.act("tap", 2)
        await second.sync_once()
        self.assertEqual((second.state.coin, second.state.manual_taps), (94, 7))

    async def test_pending_online_time_is_replayed_without_double_offline_income(self):
        session = self.session(
            api=FakeAPI(
                {
                    "coin": 100,
                    "base_click_power": 4,
                    "base_auto_click_power": 2,
                    "last_update": 900,
                }
            )
        )
        self.clock.now = 1001
        session.tick()
        session.act("tap", 2)
        self.clock.now = 1002
        session.tick()
        session.act("tap")
        await session.sync_once()
        self.assertEqual(session.state.coin, 116)
        self.assertEqual(session.state.play_seconds, 2)

    async def test_untrusted_journal_stays_bounded_when_offline(self):
        session = self.session()
        for _ in range(100):
            session.act("tap")
            self.clock.now += 1
            session.tick()
        self.assertLessEqual(len(session._journal), 2)
        self.assertEqual(
            sum(op["args"][0] for op in session._journal if op["name"] == "tap"), 100
        )

    async def test_newer_remote_save_replays_current_purchase_once(self):
        state = GameState(coin=100, last_active_at=1000)
        session = self.session(
            cached(state, at=900), FakeAPI({"coin": 200, "last_update": 950})
        )
        self.assertTrue(session.act("buy", "auto").ok)
        await session.sync_once()
        self.assertEqual(
            (session.state.coin, session.state.base_auto_click_power), (150, 1)
        )

    async def test_newer_local_save_keeps_offline_purchases(self):
        state = GameState(
            coin=80, base_auto_click_power=2, auto_click_price=200, last_active_at=1000
        )
        session = self.session(
            cached(state, at=990, dirty=True),
            FakeAPI({"coin": 500, "base_auto_click_power": 1, "last_update": 900}),
        )
        await session.sync_once()
        self.assertEqual(
            (session.state.coin, session.state.base_auto_click_power), (80, 2)
        )

    async def test_offline_income_is_not_added_twice_when_cloud_finishes_loading(self):
        self.clock.now = 1125
        state = GameState(coin=10, offline_income_power=2, last_active_at=1000)
        session = self.session(
            cached(state),
            FakeAPI({"coin": 10, "offline_income_power": 2, "last_update": 1000}),
        )
        self.assertEqual(session.state.coin, 14)
        await session.sync_once()
        self.assertEqual(session.state.coin, 14)

    async def test_new_taps_during_upload_keep_the_save_dirty(self):
        session = self.session(cached(GameState(coin=10, last_active_at=1000)))
        session.cloud_ready = True
        session.dirty = True
        started, release = asyncio.Event(), asyncio.Event()

        async def slow_upload(payload):
            started.set()
            await release.wait()

        session.manager.upload_run = slow_upload
        task = asyncio.create_task(session.sync_once())
        await started.wait()
        session.act("tap")
        release.set()
        await task
        self.assertTrue(session.dirty)
        self.assertEqual(session.state.coin, 11)

    async def test_backgrounded_game_does_not_upload_an_active_session(self):
        session = self.session(cached(GameState(coin=10, last_active_at=1000)))
        session.pause()
        await session.sync_once()
        self.assertEqual(session.manager.fetches, 0)
        self.assertEqual(session.manager.uploads, [])

    async def test_cached_leaderboard_survives_network_failure(self):
        board = [{"username": "Player", "level": 3}]
        session = self.session(cached(GameState(), board=board))
        session.manager.board_error = True
        await session.refresh_board()
        self.assertEqual(session.board, board)
        self.assertTrue(session.board_error)

    async def test_ranking_loads_even_when_platform_identity_storage_is_blocked(self):
        api = FakeAPI()
        finished = asyncio.Event()

        async def board(force=False):
            finished.set()
            return [{"username": "Real player", "level": 7, "taps": 340}]

        async def blocked_identity(_):
            await asyncio.Event().wait()

        api.get_top_5 = board
        session = self.session(api=api)
        session.manager = None
        session.start(SimpleNamespace(get=blocked_identity, set=AsyncMock()))
        await asyncio.wait_for(finished.wait(), timeout=1)
        await asyncio.sleep(0)
        self.assertIsNone(session.manager)
        self.assertTrue(session.board_loaded)
        self.assertEqual(session.board[0]["username"], "Real player")
        self.assertEqual(session.state.manual_taps, 0)

    async def test_new_inventory_video_rewards_and_avatar_survive_late_cloud_and_restart(
        self,
    ):
        state = GameState(
            level=8,
            coin=1200,
            parts=8,
            food=5,
            jobs_done=1,
            craft_counts={"lamp": 1},
            robot_levels={"spark": 2},
            active_robot="spark",
            egg_id="",
            last_active_at=1000,
        )
        session = self.session(
            cached(state, at=900),
            FakeAPI({"coin": 1400, "level": 8, "last_update": 950}),
        )
        self.assertTrue(session.act("crate", "supply").ok)
        self.assertTrue(session.act("avatar", "badge:builder").ok)
        self.assertTrue(session.act("incubate", "volt").ok)
        self.assertTrue(
            session.claim_video_reward("confirmed-native-token", {"kind": "food"}).ok
        )
        before = session.state.clone()
        await session.sync_once()
        self.assertEqual(session.state.coin, before.coin + 200)
        resumed = self.session(session.store.load())
        for field in (
            "parts",
            "crates_opened",
            "food",
            "avatar_id",
            "craft_counts",
            "egg_id",
            "egg_started_at",
            "egg_ready_at",
            "reward_tokens",
            "reward_count",
        ):
            self.assertEqual(
                getattr(resumed.state, field), getattr(before, field), field
            )
        self.assertFalse(
            resumed.claim_video_reward("confirmed-native-token", {"kind": "food"}).ok
        )

    async def test_collection_and_incubating_egg_survive_newer_legacy_cloud_profile(
        self,
    ):
        state = GameState(
            level=6,
            coin=1200,
            manual_taps=100,
            last_active_at=1000,
            robot_levels={"spark": 2},
            active_robot="spark",
            egg_id="",
        )
        session = self.session(
            cached(state, at=900),
            FakeAPI({"coin": 1400, "level": 6, "last_update": 950}),
        )
        self.assertTrue(session.act("incubate", "volt").ok)
        session.act("tap", 10)
        await session.sync_once()
        self.assertEqual(session.state.robot_levels, {"spark": 2})
        self.assertEqual(
            (session.state.egg_id, session.state.egg_progress), ("volt", 10)
        )
        self.assertEqual(session.state.coin, 1250)

    async def test_hatched_robot_and_training_survive_local_restart(self):
        session = self.session(
            cached(GameState(coin=300, manual_taps=12, last_active_at=1000))
        )
        self.assertTrue(session.act("hatch").ok)
        self.assertTrue(session.act("train_robot", "spark").ok)
        restarted = self.session(session.store.load())
        self.assertEqual(restarted.state.robot_levels, {"spark": 2})
        self.assertEqual(
            (restarted.state.egg_id, restarted.state.click_power(1000)), ("", 3)
        )

    async def test_feeding_and_battle_rewards_survive_late_cloud_profile(self):
        state = GameState(
            coin=100,
            food=15,
            robot_levels={"spark": 1},
            active_robot="spark",
            egg_id="",
            last_active_at=1000,
        )
        session = self.session(
            cached(state, at=900), FakeAPI({"coin": 140, "last_update": 950})
        )
        session.act("feed", "spark")
        session.act("battle_start", "spark")
        while session.state.battle["result"] == "active":
            battle = session.state.battle
            session.act(
                "battle_turn", suggested_action(battle), battle["id"], battle["turn"]
            )
        await session.sync_once()
        self.assertEqual(
            (session.state.coin, session.state.food, session.state.arena_wins),
            (164, 14, 1),
        )
        self.assertEqual(session.state.robot_xp["spark"], 8)
        self.assertEqual(session.state.battle["result"], "win")

    async def test_unconfirmed_free_care_and_battle_survive_restart_and_merge_once(
        self,
    ):
        first = self.session()
        first.device_id = "old-device"
        first.act("tap", 12)
        self.assertTrue(first.act("hatch").ok)
        self.assertTrue(first.act("feed", "spark").ok)
        self.assertTrue(first.act("battle_start", "spark").ok)
        while first.state.battle["result"] == "active":
            battle = first.state.battle
            first.act(
                "battle_turn", suggested_action(battle), battle["id"], battle["turn"]
            )
        self.assertFalse(first.act("buy", "click").ok)
        resumed = self.session(
            first.store.load(), FakeAPI({"coin": 100, "base_click_power": 4})
        )
        await resumed.sync_once()
        self.assertEqual(
            (resumed.state.coin, resumed.state.food, resumed.state.arena_wins),
            (172, 47, 1),
        )
        self.assertEqual(resumed.state.robot_xp["spark"], 8)
        self.assertEqual(resumed.state.battle["result"], "win")

    async def test_unconfirmed_new_robot_purchases_merge_only_remaining_local_coins(
        self,
    ):
        session = self.session(api=FakeAPI({"coin": 100, "base_click_power": 4}))
        session.act("tap", 200)
        session.act("hatch")
        self.assertTrue(session.act("incubate", "volt").ok)
        session.act("tap", 35)
        self.clock.now = session.state.egg_ready_at
        session.act("hatch")
        self.assertTrue(session.act("train_robot", "spark").ok)
        self.assertEqual(session.state.coin, 30)
        await session.sync_once()
        self.assertEqual(session.state.coin, 835)
        self.assertEqual(session.state.robot_levels, {"spark": 2, "volt": 1})
        self.assertEqual(session.state.purchases, 1)

    async def test_free_goal_reward_is_merged_once_with_unconfirmed_profile(self):
        session = self.session(api=FakeAPI({"coin": 100}))
        session.act("tap", 12)
        session.act("hatch")
        self.assertTrue(session.act("goal", "hatch1").ok)
        await session.sync_once()
        self.assertEqual(session.state.coin, 147)
        self.assertFalse(session.act("goal", "hatch1").ok)
        self.assertEqual(session.state.coin, 147)

    async def test_different_preference_identity_does_not_transfer_cached_balance(self):
        state = GameState(
            coin=900,
            robot_levels={"spark": 3},
            active_robot="spark",
            egg_id="",
            last_active_at=1000,
        )
        api = FakeAPI(blocked=True)
        session = self.session(cached(state, identity="previous-player"), api)
        session.act("tap", 2)
        prefs = SimpleNamespace(
            get=AsyncMock(return_value="different-player"), set=AsyncMock()
        )
        session.start(prefs)
        await api.fetch_started.wait()
        self.assertEqual(session.state.coin, 2)
        self.assertEqual(session.state.robot_levels, {})

    async def test_start_is_idempotent_and_preserves_existing_device_id(self):
        api = FakeAPI(blocked=True)
        session = self.session(api=api)
        prefs = SimpleNamespace(
            get=AsyncMock(return_value="old-device"), set=AsyncMock()
        )
        session.start(prefs)
        session.start(prefs)
        await api.fetch_started.wait()
        self.assertEqual(session.device_id, "old-device")
        prefs.set.assert_not_awaited()
        self.assertEqual(api.fetches, 1)

    async def test_cleared_preferences_reuse_cached_identity_without_assuming_new_player(
        self,
    ):
        session = self.session()
        session.device_id = "old-device"
        session.manager = None
        api = FakeAPI(blocked=True)
        session.manager_factory = lambda identity: api
        prefs = SimpleNamespace(get=AsyncMock(return_value=None), set=AsyncMock())
        session.start(prefs)
        await api.fetch_started.wait()
        self.assertEqual(session.device_id, "old-device")
        prefs.set.assert_awaited_once_with("device_id", "old-device")
        self.assertEqual(api.uploads, [])


if __name__ == "__main__":
    unittest.main()
