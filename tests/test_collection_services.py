import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
from billing import SeasonBilling
from collection_progress import ensure, refresh_season
from combat_rules import allowed, current_actor
from gameplay import GameState, perform


class CollectionServiceTests(unittest.TestCase):
    def test_capsule_robot_duplicates_turn_into_fragments_and_new_robot_persists(self):
        from collection_progress import grant, roll_container

        state = GameState(robot_levels={"spark": 4}, active_robot="spark", egg_id="")
        duplicate = {"kind": "robot", "id": "spark", "amount": 1, "rarity": "common"}
        grant(state, duplicate)
        self.assertEqual(duplicate["kind"], "fragments")
        self.assertEqual(state.collection["fragments"]["spark"], 10)
        self.assertEqual(state.robot_levels["spark"], 4)
        grant(state, {"kind": "robot", "id": "arachna", "amount": 1, "rarity": "epic"})
        self.assertEqual(
            GameState.from_dict(state.to_dict()).robot_levels["arachna"], 1
        )
        state.egg_id = "titan"
        state.egg_ready_at = 2000000
        grant(state, {"kind": "robot", "id": "titan", "amount": 1, "rarity": "rare"})
        self.assertEqual(state.egg_id, "titan")
        self.assertNotIn("titan", state.robot_levels)
        self.assertGreater(state.collection["fragments"]["titan"], 0)
        self.assertTrue(
            any(
                roll_container("capsule", n)[0]["kind"] == "robot"
                for n in range(1, 100)
            )
        )

    def test_skin_purchase_is_cosmetic_and_duplicate_click_does_not_spend(self):
        from equipment_catalog import effective_stats

        state = GameState(
            coin=500, robot_levels={"spark": 1}, active_robot="spark", egg_id=""
        )
        stats = effective_stats(state, "spark")
        self.assertTrue(perform(state, "skin_buy", ["steel-0"], 1000000).ok)
        self.assertEqual(state.coin, 0)
        before = state.to_dict()
        self.assertFalse(perform(state, "skin_buy", ["steel-0"], 1000001).ok)
        self.assertEqual(state.to_dict(), before)
        self.assertEqual(effective_stats(state, "spark"), stats)

    def test_malformed_receipts_and_nested_fighters_do_not_block_legacy_save(self):
        from combat_rules import restore_fighter

        state = GameState.from_dict(
            {
                "coin": 813,
                "collection": {
                    "factory_rewards": [
                        {"kind": []},
                        {"kind": "module", "id": [], "amount": 1},
                        {"kind": "gold", "amount": 12, "rarity": []},
                    ]
                },
            }
        )
        self.assertEqual(state.coin, 813)
        self.assertEqual(
            state.collection["factory_rewards"],
            [{"kind": "gold", "amount": 12, "rarity": "common"}],
        )
        self.assertIsNone(restore_fighter({"robot": [], "weapon": "plasma"}))
        self.assertIsNone(restore_fighter({"robot": "spark", "weapon": {}}))

    def test_route_boss_keeps_existing_energy_drain_repair(self):
        from unittest.mock import patch

        state = GameState(
            robot_levels={"titan": 10}, active_robot="titan", egg_id="", arena_stage=9
        )
        self.assertTrue(perform(state, "battle_start", ["titan"], 1000000).ok)
        battle = state.battle
        b = battle["combatants"]["b"]
        b["hp"] = 20
        battle["enemy_hp"] = 20
        with patch("robot_arena.enemy_intent", return_value="attack"):
            self.assertTrue(
                perform(state, "battle_turn", ["charge", battle["id"], 0], 1000001).ok
            )
        self.assertGreater(battle["enemy_hp"], 20)
        self.assertGreater(battle["last_enemy_heal"], 0)
        self.assertEqual(GameState.from_dict(state.to_dict()).battle, battle)

    def test_sandbox_claims_are_explicit_temporary_and_never_change_save(self):
        state = GameState(
            coin=500, robot_levels={"spark": 1}, active_robot="spark", egg_id=""
        )
        refresh_season(state, 1000000)["xp"] = 2000
        session = SimpleNamespace(state=state, clock=lambda: 1000000, notify=Mock())
        billing = SeasonBilling(session)
        before = state.to_dict()
        billing.toggle_preview()
        self.assertFalse(billing.preview)
        with patch("billing.sandbox_available", return_value=True):
            billing.toggle_preview()
            self.assertTrue(billing.preview)
            billing.claim_preview(1)
            billing.claim_preview(1)
            billing.claim_preview(50)
            self.assertEqual(len(billing.rewards), 1)
            self.assertEqual(billing.claims, {1})
        self.assertEqual(before, state.to_dict())
        self.assertFalse(SeasonBilling(session).preview)

    def test_cosmetics_persist_but_do_not_change_combat_stats(self):
        from equipment_catalog import effective_stats

        state = GameState(
            coin=10000, robot_levels={"spark": 3}, active_robot="spark", egg_id=""
        )
        data = ensure(state)
        data["skins"] = ["steel-1"]
        data["animations"] = ["salute"]
        data["emblems"] = ["steel-crest"]
        stats = effective_stats(state, "spark")
        for action, item in [
            ("skin_equip", "steel-1"),
            ("animation_equip", "salute"),
            ("emblem_equip", "steel-crest"),
        ]:
            self.assertTrue(perform(state, action, [item], 1000000).ok)
        restored = GameState.from_dict(state.to_dict())
        self.assertEqual(restored.collection["animation_loadouts"], {"spark": "salute"})
        self.assertEqual(restored.collection["selected_emblem"], "steel-crest")
        self.assertEqual(effective_stats(restored, "spark"), stats)
        snapshot = restored.to_dict()
        self.assertFalse(perform(restored, "skin_equip", ["not-owned"], 1000000).ok)
        self.assertEqual(snapshot, restored.to_dict())

    def test_alternating_weapon_actions_match_the_next_mount(self):
        state = GameState(
            coin=10000,
            robot_levels={"spark": 3},
            active_robot="spark",
            egg_id="",
            weapon_levels={"plasma": 1, "emp": 1},
            loadouts={"spark": ["plasma", "emp"]},
        )
        self.assertTrue(perform(state, "battle_start", ["spark"], 1000000).ok)
        battle = state.battle
        self.assertNotIn("emp", allowed(current_actor(battle)))
        self.assertTrue(
            perform(state, "battle_turn", ["guard", battle["id"], 0], 1000001).ok
        )
        self.assertEqual(current_actor(battle)["weapon"], "emp")
        self.assertIn("emp", allowed(current_actor(battle)))
        self.assertTrue(
            perform(state, "battle_turn", ["emp", battle["id"], 1], 1000002).ok
        )

    def test_material_packs_spend_gold_once_per_success_and_restore(self):
        state = GameState(coin=180)
        self.assertTrue(perform(state, "materials_buy", ["parts"], 1000000).ok)
        self.assertEqual((state.coin, state.parts), (0, 12))
        snapshot = state.to_dict()
        self.assertFalse(perform(state, "materials_buy", ["parts"], 1000001).ok)
        self.assertEqual(state.to_dict(), snapshot)
        self.assertEqual(GameState.from_dict(snapshot).parts, 12)
