import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gameplay import (
    GameState,
    advance,
    buy,
    charge,
    claim_goal,
    collect_order,
    offline_income,
    start_order,
    tap,
    threshold,
)
from local_store import LocalStore


class GameRulesTests(unittest.TestCase):
    def test_legacy_save_keeps_progress_and_restores_upgrade_prices(self):
        state = GameState.from_dict(
            {
                "level": 6,
                "coin": 17,
                "taps": 95,
                "base_click_power": 4,
                "base_auto_click_power": 2,
                "offline_income_power": 3,
                "username": "Player",
            }
        )
        self.assertEqual((state.level, state.coin, state.session_taps), (6, 17, 95))
        self.assertEqual(
            (state.auto_click_price, state.offline_income_price), (200, 800)
        )
        self.assertGreaterEqual(state.experience, threshold(5))

    def test_taps_credit_coins_score_and_experience(self):
        state = GameState(base_click_power=4)
        result = tap(state, 1000, 3)
        self.assertEqual(
            (result.coins, state.coin, state.manual_taps, state.session_taps),
            (12, 12, 3, 3),
        )
        self.assertEqual(state.experience, 3)

    def test_buying_does_not_reduce_level_or_xp(self):
        state = GameState(level=4, coin=100, experience=85)
        result = buy(state, "auto", 1000)
        self.assertTrue(result.ok)
        self.assertEqual(
            (state.coin, state.base_auto_click_power, state.auto_click_price),
            (50, 1, 100),
        )
        self.assertEqual((state.level, state.experience), (4, 85))

    def test_unaffordable_purchase_does_not_modify_state(self):
        state = GameState(coin=5)
        before = state.to_dict()
        self.assertFalse(buy(state, "auto", 1000).ok)
        self.assertEqual(state.to_dict(), before)

    def test_large_reward_advances_multiple_levels_without_spending_balance(self):
        state = GameState()
        state.earn(500)
        self.assertEqual((state.coin, state.level, state.stage_index), (500, 10, 3))
        self.assertGreaterEqual(state.level_progress, 0)
        self.assertLessEqual(state.level_progress, 1)

    def test_boost_expires_and_cannot_be_purchased_twice_while_active(self):
        state = GameState(coin=1000, base_click_power=10, base_auto_click_power=10)
        self.assertTrue(buy(state, "boost", 1000).ok)
        self.assertGreater(state.click_power(1001), 10)
        self.assertFalse(buy(state, "boost", 1001).ok)
        self.assertEqual(state.click_power(1021), 10)

    def test_auto_income_runs_once_per_elapsed_time(self):
        state = GameState(base_auto_click_power=3, last_active_at=1000)
        advance(state, 1002)
        self.assertEqual((state.coin, state.session_taps), (6, 6))
        advance(state, 1002)
        advance(state, 999)
        self.assertEqual(state.coin, 6)
        self.assertEqual(state.last_active_at, 1002)

    def test_fractional_timer_intervals_do_not_lose_auto_income(self):
        state = GameState(base_auto_click_power=1, last_active_at=1000)
        for step in range(1, 21):
            advance(state, 1000 + step * 0.5)
        self.assertEqual(state.coin, 10)
        self.assertAlmostEqual(state.auto_carry, 0)

    def test_first_boost_has_a_visible_effect_at_base_power_one(self):
        state = GameState(coin=20)
        buy(state, "boost", 1000)
        self.assertEqual(tap(state, 1001).coins, 2)

    def test_offline_income_is_capped_and_does_not_reduce_energy(self):
        state = GameState(offline_income_power=2, energy=10)
        self.assertEqual(offline_income(state, 3 * 24 * 3600, 1000000), 2880)
        self.assertEqual(state.energy, 100)
        self.assertEqual(offline_income(state, -100, 1000001), 0)

    def test_order_can_only_be_collected_once_after_finishing(self):
        state = GameState()
        self.assertTrue(start_order(state, "lamp", 1000).ok)
        self.assertEqual(state.energy, 85)
        self.assertFalse(collect_order(state, 1014).ok)
        self.assertFalse(start_order(state, "lamp", 1001).ok)
        self.assertFalse(collect_order(state, 1044).ok)
        self.assertEqual(collect_order(state, 1045).coins, 30)
        self.assertFalse(collect_order(state, 1046).ok)
        self.assertEqual((state.coin, state.jobs_done), (30, 1))

    def test_order_survives_restart_and_completes_while_away(self):
        state = GameState(level=6, experience=150)
        start_order(state, "robot", 1000)
        restored = GameState.from_dict(json.loads(json.dumps(state.to_dict())))
        self.assertTrue(collect_order(restored, 2000).ok)
        self.assertEqual(restored.jobs_done, 1)

    def test_charging_is_optional_and_clicking_works_without_energy(self):
        state = GameState(coin=100, energy=0)
        self.assertEqual(tap(state, 1000).coins, 1)
        self.assertTrue(charge(state, 1001).ok)
        self.assertEqual((state.energy, state.charges), (40, 1))

    def test_goal_reward_is_not_duplicated(self):
        state = GameState(manual_taps=20)
        self.assertTrue(claim_goal(state, "tap20", 1000).ok)
        self.assertFalse(claim_goal(state, "tap20", 1001).ok)
        self.assertEqual(state.coin, 25)

    def test_future_goals_cannot_be_claimed_early(self):
        state = GameState()
        self.assertFalse(claim_goal(state, "level10", 1000).ok)
        self.assertEqual(state.coin, 0)

    def test_corrupt_numbers_do_not_create_negative_or_non_finite_balances(self):
        state = GameState.from_dict(
            {
                "coin": float("nan"),
                "level": -20,
                "energy": 500,
                "base_click_power": -1,
                "claimed_goals": None,
            }
        )
        self.assertEqual(
            (state.coin, state.level, state.base_click_power, state.energy),
            (0, 1, 1, 100),
        )


class AtomicSaveTests(unittest.TestCase):
    def test_save_restores_and_has_valid_backup_after_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(directory)
            store.save({"schema": 2, "state": {"coin": 10}})
            self.assertEqual(store.load()["state"]["coin"], 10)
            store.save({"schema": 2, "state": {"coin": 20}})
            Path(store.path).write_text("broken json", encoding="utf-8")
            self.assertEqual(store.load()["state"]["coin"], 10)


if __name__ == "__main__":
    unittest.main()
