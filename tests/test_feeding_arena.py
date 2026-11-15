import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gameplay import (
    GameState,
    advance,
    battle_turn,
    feed_robot,
    feeding_target,
    perform,
    start_battle,
    tap,
)
from robot_arena import new_battle, restore_battle, suggested_action, take_turn
from robot_catalog import MAX_ROBOT_LEVEL


class FeedingTests(unittest.TestCase):
    def test_taps_create_food_but_auto_income_does_not(self):
        state = GameState(
            base_click_power=3, base_auto_click_power=10, last_active_at=1000
        )
        tap(state, 1000, 2)
        self.assertEqual((state.food, state.coin), (6, 6))
        advance(state, 1001)
        self.assertEqual((state.food, state.coin), (6, 16))

    def test_feeding_consumes_food_restores_charge_and_levels_robot(self):
        state = GameState(
            food=15, coin=250, robot_levels={"spark": 1}, robot_energy={"spark": 10}
        )
        for _ in range(3):
            self.assertTrue(feed_robot(state, "spark", 1000).ok)
        self.assertEqual(
            (state.food, state.coin, state.robot_levels["spark"]), (0, 250, 1)
        )
        self.assertEqual(
            (state.robot_energy["spark"], state.robot_xp["spark"], state.feedings),
            (64, 6, 3),
        )
        self.assertEqual(state.click_power(1000), 2)
        remaining = (feeding_target(1) - state.robot_xp["spark"]) // 2
        state.food = remaining * 5
        for _ in range(remaining):
            self.assertTrue(feed_robot(state, "spark", 1001).ok)
        self.assertEqual((state.robot_levels["spark"], state.robot_xp["spark"]), (2, 0))
        self.assertEqual(state.click_power(1001), 3)

    def test_full_charge_still_allows_growth_but_maxed_full_robot_does_not_spend(self):
        state = GameState(
            food=20, robot_levels={"spark": 1}, robot_energy={"spark": 100}
        )
        self.assertTrue(feed_robot(state, "spark", 1000).ok)
        state.robot_levels["spark"] = MAX_ROBOT_LEVEL
        before = state.to_dict()
        self.assertFalse(feed_robot(state, "spark", 1001).ok)
        self.assertEqual(state.to_dict(), before)

    def test_insufficient_food_and_unknown_robot_do_not_mutate_state(self):
        state = GameState(food=4, robot_levels={"spark": 1})
        before = state.to_dict()
        self.assertFalse(feed_robot(state, "spark", 1000).ok)
        self.assertFalse(feed_robot(state, "nova", 1000).ok)
        self.assertEqual(state.to_dict(), before)

    def test_old_collection_migrates_with_charge_without_erasing_upgrades(self):
        state = GameState.from_dict(
            {
                "coin": 110,
                "robot_levels": {"spark": 3},
                "active_robot": "spark",
                "egg_id": "",
            }
        )
        self.assertEqual(
            (state.coin, state.robot_levels["spark"], state.robot_energy["spark"]),
            (110, 3, 70),
        )

    def test_rest_does_not_reduce_robot_charge(self):
        state = GameState.from_dict(
            {
                "robot_levels": {"spark": 2},
                "robot_energy": {"spark": 45},
                "last_active_at": 1000,
            }
        )
        advance(state, 100000)
        self.assertEqual(state.robot_energy["spark"], 100)


class ArenaTests(unittest.TestCase):
    def state(self, robot="spark", level=1, stage=0):
        return GameState(
            robot_levels={robot: level},
            active_robot=robot,
            robot_energy={robot: 70},
            egg_id="",
            arena_stage=stage,
        )

    def test_start_charges_energy_once_and_rejects_second_active_battle(self):
        state = self.state()
        self.assertTrue(start_battle(state, "spark", 1000).ok)
        self.assertEqual((state.robot_energy["spark"], state.battles_played), (50, 1))
        self.assertFalse(start_battle(state, "spark", 1001).ok)
        self.assertEqual(state.robot_energy["spark"], 50)

    def test_unowned_or_tired_robot_cannot_start(self):
        state = self.state()
        state.robot_energy["spark"] = 19
        self.assertFalse(start_battle(state, "spark", 1000).ok)
        self.assertFalse(start_battle(state, "nova", 1000).ok)
        self.assertEqual((state.battle, state.battles_played), ({}, 0))

    def test_stale_double_click_cannot_take_two_turns(self):
        battle = new_battle("spark", 1, 0, 5)
        self.assertTrue(take_turn(battle, "attack", 5, 0).ok)
        before = json.loads(json.dumps(battle))
        self.assertFalse(take_turn(battle, "attack", 5, 0).ok)
        self.assertEqual(battle, before)

    def test_ability_has_two_intervening_turns_of_cooldown(self):
        battle = new_battle("flora", 1, 8, 5)
        self.assertTrue(take_turn(battle, "special", 5, 0).ok)
        before = json.loads(json.dumps(battle))
        self.assertFalse(take_turn(battle, "special", 5, 1).ok)
        self.assertEqual(battle, before)
        take_turn(battle, "guard", 5, 1)
        take_turn(battle, "guard", 5, 2)
        self.assertEqual(battle["cooldown"], 0)

    def test_volt_special_prevents_enemy_reply(self):
        battle = new_battle("volt", 1, 0, 1)
        before = battle["player_hp"]
        take_turn(battle, "special", 1, 0)
        self.assertEqual(battle["player_hp"], before)
        self.assertLess(battle["enemy_hp"], battle["enemy_max_hp"])

    def test_flora_special_repairs_while_nova_ignores_guard(self):
        flora = new_battle("flora", 1, 0, 1)
        flora["player_hp"] = 20
        take_turn(flora, "special", 1, 0)
        self.assertGreater(flora["player_hp"], 20)
        nova = new_battle("nova", 1, 0, 1)
        nova["turn"] = 2  # The opponent is guarding; this skill ignores that guard.
        take_turn(nova, "special", 1, 2)
        self.assertEqual(
            nova["enemy_max_hp"] - nova["enemy_hp"], nova["player_attack"] * 2
        )

    def test_guard_reduces_heavy_reply(self):
        attack = new_battle("spark", 1, 2, 1)
        guard = new_battle("spark", 1, 2, 1)
        take_turn(attack, "attack", 1, 0)
        take_turn(guard, "guard", 1, 0)
        self.assertGreater(guard["player_hp"], attack["player_hp"])

    def test_first_robot_can_win_and_rewards_cannot_be_repeated(self):
        state = self.state()
        start_battle(state, "spark", 1000)
        reward = state.battle["reward"]
        for _ in range(20):
            if state.battle["result"] != "active":
                break
            battle_turn(
                state,
                suggested_action(state.battle),
                state.battle["id"],
                state.battle["turn"],
                1001,
            )
        self.assertEqual(
            (
                state.battle["result"],
                state.coin,
                state.food,
                state.arena_wins,
                state.arena_stage,
            ),
            ("win", reward, 4, 1, 1),
        )
        before = state.to_dict()
        self.assertFalse(
            battle_turn(
                state, "attack", state.battle["id"], state.battle["turn"], 1002
            ).ok
        )
        self.assertEqual(state.to_dict(), before)

    def test_loss_does_not_remove_robot_or_balance(self):
        state = self.state(stage=8)
        state.coin = 75
        start_battle(state, "spark", 1000)
        for _ in range(60):
            if state.battle['result']!='active':break
            from combat_rules import action_error
            move='charge' if action_error(state.battle['combatants']['a'],'attack') else 'attack'
            battle_turn(state, move, state.battle["id"], state.battle["turn"], 1001)
        self.assertEqual(
            (state.battle["result"], state.coin, state.arena_stage), ("loss", 75, 8)
        )
        self.assertIn("spark", state.robot_levels)

    def test_battle_snapshot_and_food_survive_restart(self):
        state = self.state()
        state.food = 20
        start_battle(state, "spark", 1000)
        battle_turn(state, "guard", state.battle["id"], 0, 1001)
        restored = GameState.from_dict(json.loads(json.dumps(state.to_dict())))
        self.assertEqual(restored.battle, state.battle)
        self.assertEqual((restored.food, restored.robot_energy), (20, {"spark": 50}))

    def test_leaving_and_restarting_never_accepts_old_handlers(self):
        state = self.state()
        start_battle(state, "spark", 1000)
        previous = state.battle["id"]
        perform(state, "battle_leave", [], 1001)
        start_battle(state, "spark", 1002)
        before = state.to_dict()
        self.assertFalse(battle_turn(state, "special", previous, 0, 1003).ok)
        self.assertEqual(state.to_dict(), before)

    def test_corrupt_saved_battle_is_discarded(self):
        for data in (
            None,
            {},
            {"robot_id": []},
            {"robot_id": "spark", "enemy_id": "volt"},
            {**new_battle("spark", 1, 0, 1), "player_hp": -1},
        ):
            self.assertEqual(restore_battle(data), {})


if __name__ == "__main__":
    unittest.main()
