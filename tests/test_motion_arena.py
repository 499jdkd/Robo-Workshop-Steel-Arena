"""Tactical balance, saved state, animation races and reversible display mode."""

import asyncio
import copy
import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import flet as ft
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import battle_ui
import game_session
from display_mode import set_arena_expanded
from game_session import GameSession
from gameplay import GameState, advance, offline_income, recharge_robots
from robot_arena import (
    enemy_for,
    enemy_intent,
    new_battle,
    restore_battle,
    suggested_action,
    take_turn,
)
from robot_motion import pose_for


class TacticalRulesTests(unittest.TestCase):
    def fight(self, action, *, level=1, stage=0):
        battle = new_battle("spark", level, stage, 1)
        for _ in range(60):
            if battle["result"] != "active":
                break
            move = action(battle) if callable(action) else action
            self.assertTrue(take_turn(battle, move, 1, battle["turn"]).ok)
        return battle

    def test_first_fight_rewards_tactics_instead_of_repeated_attacks(self):
        tactical = self.fight(suggested_action)
        repeated = self.fight("attack")
        self.assertEqual(tactical["result"], "win")
        self.assertEqual(repeated["result"], "loss")
        self.assertGreater(tactical["player_hp"], 0)
        self.assertGreater(tactical["turn"], 3)

    def test_difficulty_keeps_growing_after_the_old_eighth_stage_cap(self):
        for lower, higher in ((0, 1), (8, 12), (12, 20), (25, 50)):
            self.assertLess(enemy_for(lower)["health"], enemy_for(higher)["health"])
            self.assertLess(enemy_for(lower)["attack"], enemy_for(higher)["attack"])
        self.assertTrue(enemy_for(4)["boss"])
        self.assertFalse(enemy_for(5)["boss"])
        self.assertEqual(self.fight(suggested_action, stage=8)["result"], "loss")
        self.assertEqual(
            self.fight(suggested_action, level=8, stage=8)["result"], "win"
        )

    def test_heavy_attack_can_be_dodged_but_pulse_requires_guard(self):
        heavy = new_battle("spark", 3, 0, 1)
        heavy["turn"] = 1
        self.assertEqual(enemy_intent(heavy), "heavy")
        before = heavy["player_hp"]
        take_turn(heavy, "dodge", 1, 1)
        self.assertEqual(heavy["player_hp"], before)
        self.assertTrue(heavy["last_dodged"])
        self.assertEqual((heavy["focus"], heavy["dodge_cooldown"]), (1, 2))
        pulse = new_battle("spark", 3, 4, 1)
        pulse["turn"] = 4
        self.assertEqual(enemy_intent(pulse), "pulse")
        guarded = copy.deepcopy(pulse)
        take_turn(pulse, "dodge", 1, 4)
        take_turn(guarded, "guard", 1, 4)
        self.assertFalse(pulse["last_dodged"])
        self.assertGreater(guarded["player_hp"], pulse["player_hp"])

    def test_focus_and_cooldown_rejections_leave_battle_unchanged(self):
        for action, field, value in (
            ("special", "focus", 1),
            ("dodge", "focus", 0),
            ("dodge", "dodge_cooldown", 1),
        ):
            battle = new_battle("spark", 1, 0, 1)
            battle[field] = value
            before = copy.deepcopy(battle)
            self.assertFalse(take_turn(battle, action, 1, 0).ok)
            self.assertEqual(battle, before)

    def test_overheat_reduces_repeated_hits_and_guard_cools_the_motor(self):
        battle = new_battle("spark", 1, 20, 1)
        take_turn(battle, "attack", 1, 0)
        first = battle["last_damage"]
        battle["turn"] = 4  # Compare against the same enemy stance.
        battle["heat"] = 2
        take_turn(battle, "attack", 1, 4)
        self.assertLess(battle["last_damage"], first)
        take_turn(battle, "guard", 1, 5)
        self.assertEqual(battle["heat"], 0)

    def test_old_in_progress_battle_keeps_health_damage_and_reward(self):
        legacy = new_battle("spark", 5, 8, 17)
        legacy["player_hp"] = 35
        legacy["turn"] = 3
        for key in (
            "focus",
            "heat",
            "dodge_cooldown",
            "precision",
            "rules_version",
            "player_level",
            "boss",
        ):
            legacy.pop(key)
        restored = restore_battle(legacy)
        for key in (
            "id",
            "player_hp",
            "player_attack",
            "enemy_hp",
            "enemy_attack",
            "reward",
            "turn",
        ):
            self.assertEqual(restored[key], legacy[key])
        self.assertEqual((restored["focus"], restored["heat"]), (2, 0))
        self.assertTrue(take_turn(restored, "guard", 17, 3).ok)


class MotionAndRestTests(unittest.TestCase):
    def test_absolute_poses_stay_bounded_and_wheels_follow_distance(self):
        for motion in (
            "idle",
            "attack",
            "special",
            "hit",
            "dodge",
            "guard",
            "feed",
            "happy",
            "charge",
            "victory",
        ):
            for now in (0, 1, 20, 50000):
                for facing in (-1, 1):
                    pose = pose_for(motion, now, facing=facing)
                    self.assertLessEqual(abs(pose.x), 37)
                    self.assertLessEqual(abs(pose.y), 12)
                    self.assertAlmostEqual(pose.wheel * 21.5, pose.x)
                    self.assertTrue(
                        all(math.isfinite(value) for value in vars(pose).values())
                    )
                    self.assertEqual(pose, pose_for(motion, now, facing=facing))

    def test_fractional_rest_preserves_charge_across_a_save(self):
        state = GameState(
            robot_levels={"spark": 2, "volt": 1}, robot_energy={"spark": 40, "volt": 99}
        )
        for _ in range(89):
            recharge_robots(state, 0.5)
        self.assertEqual(state.robot_energy["spark"], 40)
        restored = GameState.from_dict(state.to_dict())
        recharge_robots(restored, 0.5)
        self.assertEqual(restored.robot_energy, {"spark": 41, "volt": 100})
        self.assertEqual(restored.robot_charge_carry, 0)
        restored.robot_energy = {"spark": 0, "volt": 0}
        offline_income(restored, 100000, 100000)
        self.assertEqual(restored.robot_energy, {"spark": 100, "volt": 100})

    def test_high_click_power_does_not_multiply_level_experience(self):
        from gameplay import tap

        state = GameState(base_click_power=1000)
        tap(state, 1000, 10)
        self.assertEqual((state.coin, state.food, state.experience), (10000, 10000, 10))

    def test_robot_charge_uses_time_even_without_income(self):
        state = GameState(
            robot_levels={"spark": 1}, robot_energy={"spark": 20}, last_active_at=1000
        )
        for tick in range(1, 46):
            advance(state, 1000 + tick)
        self.assertEqual((state.coin, state.robot_energy["spark"]), (0, 21))
        self.assertEqual(state.play_seconds, 45)

    def test_fractional_timer_ticks_do_not_lose_passive_experience(self):
        state = GameState(base_auto_click_power=5, last_active_at=1000)
        for tick in range(1, 41):
            advance(state, 1000 + tick / 4)
        self.assertEqual((state.coin, state.experience), (50, 10))
        self.assertAlmostEqual(state.auto_xp_carry, 0)


class AnimatedTurnTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = GameSession.preview()
        self.session.state = GameState(
            robot_levels={"spark": 1}, active_robot="spark", egg_id=""
        )
        self.session.act("battle_start", "spark")
        self.started, self.release = asyncio.Event(), asyncio.Event()
        self.calls = 0

    async def blocked_first_frame(self, seconds):
        self.calls += 1
        if self.calls == 1:
            self.started.set()
            await self.release.wait()

    async def asyncTearDown(self):
        await self.session.close()

    async def test_simultaneous_actions_commit_one_turn(self):
        identity = self.session.state.battle["id"]
        with patch.object(
            battle_ui.asyncio, "sleep", side_effect=self.blocked_first_frame
        ):
            first = asyncio.create_task(
                battle_ui.animate_turn(self.session, "attack", identity, 0)
            )
            await self.started.wait()
            self.assertFalse(
                await battle_ui.animate_turn(self.session, "special", identity, 0)
            )
            self.assertTrue(self.session.arena_animating)
            self.assertEqual(self.session.state.battle["turn"], 0)
            self.release.set()
            self.assertTrue(await first)
        self.assertEqual(self.session.state.battle["turn"], 1)
        self.assertFalse(self.session.arena_animating)

    async def test_leaving_during_windup_cannot_attack_a_new_battle(self):
        identity = self.session.state.battle["id"]
        with patch.object(
            battle_ui.asyncio, "sleep", side_effect=self.blocked_first_frame
        ):
            first = asyncio.create_task(
                battle_ui.animate_turn(self.session, "attack", identity, 0)
            )
            await self.started.wait()
            self.session.act("battle_leave")
            self.session.act("battle_start", "spark")
            before = self.session.state.to_dict()
            self.release.set()
            self.assertFalse(await first)
        self.assertEqual(self.session.state.to_dict(), before)
        self.assertFalse(self.session.arena_animating)

    async def test_close_during_windup_never_notifies_destroyed_ui(self):
        listener = Mock()
        self.session.subscribe(listener)
        identity = self.session.state.battle["id"]
        with patch.object(
            battle_ui.asyncio, "sleep", side_effect=self.blocked_first_frame
        ):
            first = asyncio.create_task(
                battle_ui.animate_turn(self.session, "attack", identity, 0)
            )
            await self.started.wait()
            await self.session.close()
            count = listener.call_count
            self.release.set()
            self.assertFalse(await first)
        self.assertEqual(listener.call_count, count)
        self.assertEqual(self.session.state.battle["turn"], 0)


class DisplayAndRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_android_fullscreen_requests_landscape_and_restores_portrait(self):
        page = SimpleNamespace(
            web=False,
            platform=ft.PagePlatform.ANDROID,
            set_allowed_device_orientations=AsyncMock(),
        )
        session = GameSession.preview(page)
        await set_arena_expanded(page, session, True)
        self.assertTrue(session.arena_expanded)
        page.set_allowed_device_orientations.assert_awaited_with(
            [ft.DeviceOrientation.LANDSCAPE_LEFT, ft.DeviceOrientation.LANDSCAPE_RIGHT]
        )
        await set_arena_expanded(page, session, False)
        self.assertFalse(session.arena_expanded)
        page.set_allowed_device_orientations.assert_awaited_with(
            [ft.DeviceOrientation.PORTRAIT_UP]
        )

    async def test_desktop_fullscreen_toggle_is_reversible(self):
        page = SimpleNamespace(
            web=False,
            platform=ft.PagePlatform.WINDOWS,
            window=SimpleNamespace(full_screen=False),
            update=Mock(),
        )
        session = GameSession.preview(page)
        await set_arena_expanded(page, session, True)
        self.assertFalse(page.window.full_screen)
        self.assertEqual((page.window.width, page.window.height), (960, 540))
        await set_arena_expanded(page, session, False)
        self.assertFalse(page.window.full_screen)
        self.assertEqual((page.window.width, page.window.height), (420, 840))

    async def test_unsupported_rotation_keeps_the_battle_playable(self):
        page = SimpleNamespace(
            web=False,
            platform=ft.PagePlatform.ANDROID,
            set_allowed_device_orientations=AsyncMock(
                side_effect=RuntimeError("unavailable")
            ),
        )
        session = GameSession.preview(page)
        await set_arena_expanded(page, session, True)
        self.assertTrue(session.arena_expanded)
        self.assertIn("поворот экрана недоступен", session.notice)

    async def test_sync_backoff_stops_log_spam_and_resets_after_recovery(self):
        session = GameSession.preview()
        session._running = True
        session.sync_once = AsyncMock(
            side_effect=[
                httpx.ReadTimeout(""),
                httpx.ReadTimeout(""),
                None,
                httpx.ReadTimeout(""),
            ]
        )
        delays = []

        async def next_attempt(seconds):
            delays.append(seconds)
            if len(delays) == 4:
                session._running = False

        with (
            patch.object(game_session.asyncio, "sleep", side_effect=next_attempt),
            patch.object(game_session, "logger") as logger,
        ):
            await session._sync_loop()
        self.assertEqual(delays, [15, 30, 5, 15])
        self.assertEqual(logger.warning.call_count, 2)
        self.assertEqual(logger.debug.call_count, 1)
        await session.close()


if __name__ == "__main__":
    unittest.main()
