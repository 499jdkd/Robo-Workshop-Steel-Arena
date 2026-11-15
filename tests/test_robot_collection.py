import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gameplay import (
    GameState,
    advance,
    collect_order,
    hatch_robot,
    incubate_robot,
    offline_income,
    perform,
    start_order,
    tap,
    train_robot,
)
from robot_catalog import MAX_ROBOT_LEVEL, ROBOT_BY_ID, ROBOTS, training_price


class RobotCollectionTests(unittest.TestCase):
    def test_first_egg_is_free_and_opens_after_manual_taps(self):
        state = GameState()
        self.assertEqual((state.coin, state.egg_id), (0, "spark"))
        self.assertFalse(hatch_robot(state, 1000).ok)
        tap(state, 1001, 12)
        self.assertTrue(state.egg_ready)
        self.assertTrue(hatch_robot(state, 1002).ok)
        self.assertEqual(
            (state.coin, state.active_robot, state.robot_levels),
            (12, "spark", {"spark": 1}),
        )
        self.assertEqual(tap(state, 1003).coins, 2)

    def test_auto_income_does_not_charge_an_egg(self):
        state = GameState(base_auto_click_power=50, last_active_at=1000)
        advance(state, 1002)
        self.assertEqual(state.coin, 100)
        self.assertEqual(state.egg_progress, 0)
        self.assertFalse(state.egg_ready)

    def test_one_egg_cannot_be_opened_twice(self):
        state = GameState(manual_taps=12)
        hatch_robot(state, 1000)
        snapshot = state.to_dict()
        self.assertFalse(hatch_robot(state, 1001).ok)
        self.assertEqual(state.to_dict(), snapshot)

    def test_egg_has_known_contents_and_is_charged_only_after_purchase(self):
        state = GameState(
            level=6,
            coin=1000,
            manual_taps=90,
            robot_levels={"spark": 1},
            active_robot="spark",
            egg_id="",
        )
        self.assertTrue(incubate_robot(state, "volt", 1000).ok)
        self.assertEqual(
            (state.egg_id, state.coin, state.egg_progress), ("volt", 820, 0)
        )
        tap(state, 1001, ROBOT_BY_ID["volt"].taps)
        self.assertFalse(hatch_robot(state, 1002).ok)
        self.assertTrue(hatch_robot(state, state.egg_ready_at).ok)
        self.assertEqual(state.robot_levels, {"spark": 1, "volt": 1})
        self.assertEqual(state.active_robot, "volt")

    def test_occupied_incubator_and_duplicate_robot_do_not_spend_coins(self):
        state = GameState(level=25, coin=10000)
        self.assertFalse(incubate_robot(state, "nova", 1000).ok)
        self.assertEqual(state.coin, 10000)
        state.robot_levels = {"spark": 1}
        state.egg_id = ""
        self.assertFalse(incubate_robot(state, "spark", 1000).ok)
        self.assertEqual(state.coin, 10000)

    def test_locked_or_unaffordable_egg_does_not_change_state(self):
        state = GameState(egg_id="", coin=200)
        before = state.to_dict()
        self.assertFalse(incubate_robot(state, "volt", 1000).ok)
        self.assertEqual(state.to_dict(), before)
        state.level = 16
        self.assertFalse(incubate_robot(state, "nova", 1000).ok)
        self.assertEqual(state.coin, 200)

    def test_whole_team_provides_abilities_regardless_of_visible_robot(self):
        state = GameState(
            robot_levels={"spark": 2, "volt": 3, "flora": 2, "nova": 1},
            active_robot="spark",
            egg_id="",
        )
        self.assertEqual(
            (state.click_power(1000), state.auto_power(1000), state.rest_power),
            (6, 5, 4),
        )
        self.assertTrue(perform(state, "select_robot", ["flora"], 1000).ok)
        self.assertEqual(
            (state.click_power(1000), state.auto_power(1000), state.rest_power),
            (6, 5, 4),
        )

    def test_robot_income_works_without_classic_income_upgrades(self):
        state = GameState(robot_levels={"volt": 2, "flora": 1}, last_active_at=1000)
        advance(state, 1002)
        self.assertEqual(state.coin, 4)
        self.assertEqual(offline_income(state, 120, 1122), 4)
        self.assertEqual(state.coin, 8)

    def test_order_bonus_is_fixed_when_order_starts(self):
        state = GameState(coin=10000, robot_levels={"forge": 1})
        self.assertTrue(start_order(state, "lamp", 1000).ok)
        self.assertEqual(state.work_reward, 34)
        train_robot(state, "forge", 1001)
        self.assertEqual(collect_order(state, 1045).coins, 34)
        start_order(state, "lamp", 1046)
        self.assertEqual(state.work_reward, 39)

    def test_training_charges_once_increases_ability_and_stops_at_cap(self):
        budget = sum(
            training_price(ROBOT_BY_ID["spark"], level)
            for level in range(1, MAX_ROBOT_LEVEL)
        )
        state = GameState(coin=budget + 100, robot_levels={"spark": 1}, egg_id="")
        for level in range(1, MAX_ROBOT_LEVEL):
            before = state.coin
            self.assertTrue(train_robot(state, "spark", 1000 + level).ok)
            self.assertEqual(
                before - state.coin, training_price(ROBOT_BY_ID["spark"], level)
            )
        self.assertEqual(state.click_power(1100), 1 + MAX_ROBOT_LEVEL)
        before = state.to_dict()
        self.assertFalse(train_robot(state, "spark", 1200).ok)
        self.assertEqual(state.to_dict(), before)

    def test_robots_and_incubating_egg_survive_json_roundtrip(self):
        state = GameState(
            level=6,
            coin=900,
            manual_taps=100,
            robot_levels={"spark": 3, "volt": 1},
            active_robot="volt",
            egg_id="",
        )
        incubate_robot(state, "flora", 1000)
        tap(state, 1001, 15)
        restored = GameState.from_dict(json.loads(json.dumps(state.to_dict())))
        self.assertEqual(restored.robot_levels, state.robot_levels)
        self.assertEqual(
            (restored.active_robot, restored.egg_id, restored.egg_progress),
            ("volt", "flora", 15),
        )

    def test_legacy_save_gets_first_egg_without_losing_balance_or_upgrades(self):
        state = GameState.from_dict({"coin": 1200, "base_click_power": 8, "level": 12})
        self.assertEqual(
            (state.coin, state.base_click_power, state.level, state.egg_id),
            (1200, 8, 12, "spark"),
        )

    def test_corrupt_collection_is_sanitized(self):
        state = GameState.from_dict(
            {
                "robot_levels": {
                    "spark": 999,
                    "volt": -2,
                    "flora": "bad",
                    "unknown": 8,
                },
                "active_robot": [],
                "egg_id": "unknown",
            }
        )
        self.assertEqual(state.robot_levels, {"spark": MAX_ROBOT_LEVEL})
        self.assertEqual((state.active_robot, state.egg_id), ("spark", ""))

    def test_catalog_has_distinct_roles_and_existing_sprite_references(self):
        self.assertGreaterEqual(len({robot.id for robot in ROBOTS}), 30)
        self.assertEqual(len({robot.role for robot in ROBOTS}), len(ROBOTS))
        for robot in ROBOTS:
            for name in (robot.image, robot.egg_image):
                path = Path(__file__).resolve().parents[1] / "src/assets" / name
                content = path.read_bytes()
                if path.suffix == ".svg":
                    from xml.etree import ElementTree

                    self.assertEqual(
                        ElementTree.fromstring(content).tag,
                        "{http://www.w3.org/2000/svg}svg",
                    )
                else:
                    self.assertEqual(content[:4], b"RIFF", name)
                    self.assertEqual(content[8:12], b"WEBP", name)


if __name__ == "__main__":
    unittest.main()
