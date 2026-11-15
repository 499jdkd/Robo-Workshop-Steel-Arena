"""The new loop earns real local rewards without forced ads or lost saves."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gameplay import (
    GameState,
    collect_order,
    feeding_target,
    hatch_robot,
    incubate_robot,
    perform,
    start_order,
    tap,
)
from progression import (
    DAY,
    avatars,
    daily_goals,
    grant_video,
    selected_avatar,
    video_available,
    video_offer,
)
from robot_arena import new_battle, take_turn
from robot_catalog import ROBOTS


class ProgressionTests(unittest.TestCase):
    def test_project_produces_a_visible_invention_parts_and_profile_icon_once(self):
        state = GameState()
        self.assertTrue(start_order(state, "lamp", 1000).ok)
        self.assertFalse(collect_order(state, 1044).ok)
        self.assertTrue(collect_order(state, 1045).ok)
        self.assertEqual((state.craft_counts, state.parts), ({"lamp": 1}, 2))
        self.assertTrue(
            next(item for item in avatars(state) if item.id == "badge:builder").unlocked
        )
        self.assertTrue(perform(state, "lamp_toggle", [], 1046).ok)
        self.assertFalse(state.lamp_on)
        before = state.to_dict()
        self.assertFalse(collect_order(state, 1046).ok)
        self.assertEqual(state.to_dict(), before)

    def test_daily_rewards_cannot_be_claimed_twice_or_reused_next_day(self):
        state = GameState()
        tap(state, 1000, 100)
        self.assertEqual(daily_goals(state, 1000)[0]["current"], 100)
        self.assertTrue(perform(state, "daily", ["taps"], 1001).ok)
        self.assertEqual(
            (state.coin, state.food, state.parts, state.dailies_done), (135, 108, 2, 1)
        )
        before = state.to_dict()
        self.assertFalse(perform(state, "daily", ["taps"], 1002).ok)
        self.assertEqual(state.to_dict(), before)
        self.assertEqual(daily_goals(state, DAY + 1)[0]["current"], 0)
        tap(state, DAY + 1, 99)
        self.assertFalse(perform(state, "daily", ["taps"], DAY + 2).ok)
        tap(state, DAY + 3)
        self.assertTrue(perform(state, "daily", ["taps"], DAY + 3).ok)

    def test_supply_box_contents_are_fixed_and_parts_cannot_go_negative(self):
        state = GameState(parts=8)
        self.assertTrue(perform(state, "crate", ["supply"], 1000).ok)
        self.assertEqual(
            (state.parts, state.coin, state.food, state.crates_opened), (0, 50, 15, 1)
        )
        before = state.to_dict()
        self.assertFalse(perform(state, "crate", ["supply"], 1001).ok)
        self.assertEqual(state.to_dict(), before)

    def test_egg_box_goes_to_storage_then_one_incubator_without_double_spending(self):
        state = GameState(level=3, parts=20)
        self.assertTrue(perform(state, "crate", ["egg", "volt"], 1000).ok)
        self.assertEqual(state.egg_stock, {"volt": 1})
        before = state.to_dict()
        self.assertFalse(perform(state, "stock_egg", ["volt"], 1000).ok)
        self.assertEqual(state.to_dict(), before)
        tap(state, 1001, 12)
        hatch_robot(state, 1001)
        gold = state.coin
        self.assertTrue(perform(state, "stock_egg", ["volt"], 1002).ok)
        self.assertEqual(
            (state.coin, state.egg_stock, state.egg_ready_at), (gold, {}, 1122)
        )
        self.assertFalse(perform(state, "stock_egg", ["volt"], 1002).ok)
        tap(state, 1003, 10)
        self.assertEqual(state.egg_ready_at, 1102)
        self.assertFalse(hatch_robot(state, 1101).ok)
        self.assertTrue(hatch_robot(state, 1102).ok)
        self.assertIn("volt", state.robot_levels)

    def test_locked_or_duplicate_egg_box_never_consumes_parts(self):
        state = GameState(level=3, parts=100, robot_levels={"spark": 1}, egg_id="")
        for identity in ("solar", "spark", "unknown"):
            before = state.to_dict()
            self.assertFalse(perform(state, "crate", ["egg", identity], 1000).ok)
            self.assertEqual(state.to_dict(), before)

    def test_legacy_egg_keeps_manual_progress_and_does_not_acquire_a_new_wait(self):
        state = GameState.from_dict(
            {"level": 3, "egg_id": "volt", "manual_taps": 40, "egg_started_taps": 5}
        )
        self.assertEqual(state.egg_ready_at, 0)
        self.assertTrue(hatch_robot(state, 1000).ok)

    def test_selected_icon_and_all_new_inventory_fields_survive_restart(self):
        state = GameState(
            level=8,
            parts=55,
            jobs_done=3,
            craft_counts={"lamp": 3},
            egg_stock={"glacier": 1},
            robot_levels={"spark": 2},
            active_robot="spark",
            egg_id="",
            crates_opened=3,
        )
        self.assertTrue(perform(state, "avatar", ["badge:builder"], 1000).ok)
        restored = GameState.from_dict(json.loads(json.dumps(state.to_dict())))
        self.assertEqual(
            (restored.parts, restored.craft_counts, restored.egg_stock),
            (55, {"lamp": 3}, {"glacier": 1}),
        )
        self.assertEqual(selected_avatar(restored).id, "badge:builder")
        before = restored.to_dict()
        self.assertFalse(perform(restored, "avatar", ["robot:solar"], 1000).ok)
        self.assertEqual(restored.to_dict(), before)

    def test_first_hatch_gives_a_robot_profile_icon_automatically(self):
        state = GameState()
        tap(state, 1000, 12)
        hatch_robot(state, 1000)
        self.assertEqual(state.avatar_id, "robot:spark")

    def test_new_robots_all_have_working_skills(self):
        self.assertGreaterEqual(len(ROBOTS), 30)
        for robot in ROBOTS:
            with self.subTest(robot=robot.id):
                battle = new_battle(robot.id, 3, 0, 1)
                self.assertTrue(take_turn(battle, "special", 1, 0).ok)
                self.assertLess(battle["enemy_hp"], battle["enemy_max_hp"])

    def test_corrupt_optional_collections_do_not_crash_save_restore(self):
        state = GameState.from_dict(
            {
                "daily_claimed": [{}, [], True, "taps"],
                "egg_stock": {"unknown": 1},
                "avatar_id": {},
                "reward_tokens": [{}, "valid"],
            }
        )
        self.assertEqual(state.daily_claimed, ["taps"])
        self.assertEqual(
            (state.egg_stock, state.avatar_id, state.reward_tokens),
            ({}, "starter", ["valid"]),
        )


class VideoRewardRulesTests(unittest.TestCase):
    def test_reward_is_once_even_after_restart_and_has_a_daily_limit(self):
        state = GameState()
        for index in range(4):
            self.assertTrue(
                grant_video(
                    state, f"token-{index}", {"kind": "food"}, 1000 + index * 60
                ).ok
            )
        self.assertEqual((state.food, state.reward_count), (60, 4))
        restored = GameState.from_dict(state.to_dict())
        before = restored.to_dict()
        self.assertFalse(grant_video(restored, "token-0", {"kind": "food"}, 2000).ok)
        self.assertFalse(grant_video(restored, "token-5", {"kind": "food"}, 2000).ok)
        self.assertEqual(restored.to_dict(), before)
        self.assertTrue(
            grant_video(restored, "next-day", {"kind": "food"}, DAY + 2000).ok
        )
        self.assertEqual(
            (restored.reward_count, video_available(restored, DAY + 2000)), (1, (3, 60))
        )

    def test_boost_doubles_only_manual_gold_and_food_and_expires(self):
        state = GameState(base_click_power=3)
        grant_video(state, "boost", {"kind": "boost"}, 1000)
        tap(state, 1001)
        self.assertEqual((state.coin, state.food, state.experience), (6, 6, 1))
        self.assertIsNone(video_offer(state, "boost", now=1001))
        tap(state, 1121)
        self.assertEqual((state.coin, state.food, state.experience), (9, 9, 2))

    def test_training_offer_finishes_at_most_one_level(self):
        state = GameState(
            robot_levels={"spark": 1}, robot_xp={"spark": feeding_target(1) - 8}
        )
        offer = video_offer(state, "training", "spark", 1000)
        self.assertEqual(offer["amount"], 8)
        self.assertTrue(grant_video(state, "train", offer, 1000).ok)
        self.assertEqual((state.robot_levels["spark"], state.robot_xp["spark"]), (2, 0))

    def test_incubator_reward_survives_integer_to_float_time_restore(self):
        state = GameState(level=3, coin=500, robot_levels={"spark": 1}, egg_id="")
        incubate_robot(state, "volt", 1000)
        offer = video_offer(state, "incubator", now=1000)
        restored = GameState.from_dict(state.to_dict())
        self.assertTrue(grant_video(restored, "skip", offer, 1001).ok)
        self.assertTrue(restored.egg_is_ready(1001))
        self.assertEqual(restored.food, 0)

    def test_completed_egg_gives_promised_replacement_instead_of_losing_video(self):
        state = GameState()
        self.assertTrue(
            grant_video(
                state, "late", {"kind": "incubator", "target": "volt:1.000000"}, 1000
            ).ok
        )
        self.assertEqual(state.food, 15)


if __name__ == "__main__":
    unittest.main()
