"""Reported 1/12-energy stall, input recovery, showroom isolation and bot tactics."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import flet as ft
from flet.controls.context import _context_page
from flet.components.component import Renderer
import battle_ui
from arena_screen import action_panel
from combat_info import action_info
from combat_rules import action_cost, action_error, allowed, fighter, resolve_action
from game_animation import animated_scene, weapon_for
from game_session import GameSession
from gameplay import GameState
from local_store import MemoryStore
from robot_abilities import ABILITIES
from robot_arena import enemy_intent
from robot_designs import DESIGNS
from robot_preview import preview_controls
from test_robot_ui import render_controls


@ft.component
def Panel(session):
    return action_panel(session)


class EnergySafetyTests(unittest.TestCase):
    def test_all_32_robots_have_a_free_recovery_with_zero_energy_and_statuses(self):
        for identity, design in DESIGNS.items():
            with self.subTest(robot=identity):
                actor = fighter(identity, design["weapon"])
                actor.update(energy=0, focus=0, super_charge=100, cooldown=3,
                             weapon_cooldown=2, dodge_cooldown=3, root=2, emp=2)
                target = fighter("titan", "fist")
                for action in ("guard", "charge"):
                    copy = deepcopy(actor)
                    self.assertEqual(action_cost(copy, action), 0)
                    self.assertFalse(action_error(copy, action))
                    self.assertTrue(resolve_action(copy, deepcopy(target), action)["ok"])
                    self.assertGreater(copy["energy"], 0)

    def test_full_supercharge_at_one_energy_is_rejected_without_any_mutation(self):
        a, b = fighter("volt", "electric"), fighter("arachna", "laser")
        a.update(energy=1, super_charge=100)
        before = deepcopy((a, b))
        result = resolve_action(a, b, "ultimate")
        self.assertFalse(result["ok"])
        self.assertIn("4 энергии", result["error"])
        self.assertIn("есть 1", result["error"])
        self.assertEqual((a, b), before)
        self.assertTrue(resolve_action(a, b, "guard")["ok"])
        self.assertEqual(a["energy"], 4)
        self.assertTrue(resolve_action(a, b, "ultimate")["ok"])
        self.assertEqual((a["energy"], a["super_charge"]), (0, 0))

    def test_every_weapon_uses_the_same_cost_in_validation_and_deduction(self):
        from armory import WEAPONS
        for weapon in WEAPONS:
            for action in allowed(fighter("volt", weapon.id)) - {"guard", "charge"}:
                actor, target = fighter("volt", weapon.id), fighter("titan", "fist")
                actor.update(super_charge=100, energy=12)
                cost = action_cost(actor, action)
                self.assertTrue(resolve_action(actor, target, action)["ok"])
                self.assertEqual(actor["energy"], 12 - cost)

    def test_cards_show_actual_recovery_and_exact_missing_resources(self):
        actor = fighter("volt", "electric")
        actor.update(energy=1, super_charge=100, focus=0)
        self.assertEqual(action_info(actor, "charge")["effect"], "+6 энергии · +2 фокуса")
        self.assertEqual(action_info(actor, "guard")["effect"], "+3 энергии · +1 фокуса")
        info = action_info(actor, "ultimate")
        self.assertFalse(info["ready"])
        self.assertIn("есть 1", info["reason"])
        self.assertIn("100% заряда", info["detail"])
        before = deepcopy(actor)
        action_info(actor, "ultimate", fighter("titan", "fist"))
        self.assertEqual(actor, before)


class InteractionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        page = SimpleNamespace(width=390, height=844, run_task=Mock(),
                               _dialogs=SimpleNamespace(controls=[]), session=SimpleNamespace(components_mode=True))
        self.session = GameSession.preview(page)
        token = _context_page.set(page)
        self.addCleanup(_context_page.reset, token)
        self.session.state = GameState(robot_levels={"volt": 4}, active_robot="volt", egg_id="")
        self.session.act("battle_start", "volt")

    async def asyncTearDown(self):
        await self.session.close()

    async def test_reported_battle_buttons_disable_paid_attacks_but_leave_recovery(self):
        battle = self.session.state.battle
        battle["combatants"]["a"].update(energy=1, super_charge=100)
        controls = render_controls(Renderer().render(Panel, session=self.session))
        buttons = {c.key: c for c in controls if isinstance(c, ft.Button)}
        for action in ("attack", "quick", "special", "ultimate"):
            self.assertTrue(buttons[f"arena-{action}"].disabled)
        for action in ("guard", "charge"):
            self.assertFalse(buttons[f"arena-{action}"].disabled)
        self.assertTrue(any("Нужно 4 энергии, есть 1" in (c.value or "")
                            for c in controls if isinstance(c, ft.Text)))
        before = deepcopy(battle)
        self.assertFalse(await battle_ui.animate_turn(self.session, "ultimate", battle["id"], 0))
        self.assertEqual(battle, before)
        self.assertFalse(self.session.arena_animating)

    async def test_zero_energy_focus_commits_and_unblocks_the_next_attack(self):
        battle = self.session.state.battle
        battle["combatants"]["a"].update(energy=0, focus=0)
        with patch.object(battle_ui.asyncio, "sleep", new=AsyncMock()):
            self.assertTrue(await battle_ui.animate_turn(self.session, "charge", battle["id"], 0))
        self.assertGreaterEqual(battle["combatants"]["a"]["energy"], 4)
        self.assertEqual(battle["turn"], 1)
        self.assertFalse(self.session.arena_animating)

    async def test_v3_dodge_needs_energy_and_cooldown_but_not_legacy_focus(self):
        battle = self.session.state.battle
        battle["combatants"]["a"]["focus"] = battle["focus"] = 0
        with patch.object(battle_ui.asyncio, "sleep", new=AsyncMock()):
            self.assertTrue(await battle_ui.animate_turn(self.session, "dodge", battle["id"], 0))

    async def test_failed_animation_unlocks_controls_without_committing_a_turn(self):
        battle = self.session.state.battle
        before = deepcopy(battle)
        with patch.object(battle_ui.asyncio, "sleep", new=AsyncMock(side_effect=RuntimeError("renderer disconnected"))):
            with self.assertRaises(RuntimeError):
                await battle_ui.animate_turn(self.session, "attack", battle["id"], 0)
        self.assertEqual(battle, before)
        self.assertFalse(self.session.arena_animating)
        self.assertFalse(self.session.arena_visual)

    async def test_cancellation_releases_the_input_lock(self):
        entered = asyncio.Event()
        async def wait(_):
            entered.set()
            await asyncio.Event().wait()
        battle = self.session.state.battle
        with patch.object(battle_ui.asyncio, "sleep", side_effect=wait):
            task = asyncio.create_task(battle_ui.animate_turn(self.session, "attack", battle["id"], 0))
            await entered.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertFalse(self.session.arena_animating)
        self.assertEqual(battle["turn"], 0)

    async def test_pause_during_windup_does_not_spend_a_turn_and_resume_allows_input(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def wait(_):
            entered.set()
            await release.wait()
        battle = self.session.state.battle
        with patch.object(battle_ui.asyncio, "sleep", side_effect=wait):
            task = asyncio.create_task(battle_ui.animate_turn(self.session, "attack", battle["id"], 0))
            await entered.wait()
            self.session.pause()
            release.set()
            self.assertFalse(await task)
        self.session.resume()
        with patch.object(battle_ui.asyncio, "sleep", new=AsyncMock()):
            self.assertTrue(await battle_ui.animate_turn(self.session, "charge", battle["id"], 0))

    async def test_owned_and_locked_showrooms_cannot_change_save_or_equipment(self):
        self.session.act("battle_leave")
        self.session.persist()
        before = self.session.state.to_dict()
        saved = deepcopy(self.session.store.load())
        for identity in DESIGNS:
            controls = render_controls(preview_controls(self.session, identity))
            for control in controls:
                if isinstance(control, ft.Button) and str(control.key).startswith("preview-"):
                    self.assertFalse(control.disabled)
                    await control.on_click(None)
                    payload = json.loads(animated_scene(self.session, identity=identity).payload)
                    self.assertTrue(payload["demonstration"])
                    self.assertEqual(payload["robot"], identity)
                    self.assertEqual(payload["combatAction"], self.session.preview_action)
        self.assertEqual(self.session.state.to_dict(), before)
        self.assertEqual(self.session.store.load(), saved)

    async def test_equipped_alternating_mounts_match_renderer_and_rules(self):
        battle = self.session.state.battle
        self.session.state.weapon_levels = {"laser": 2, "sniper": 2}
        self.session.state.loadouts = {"volt": ["laser", "sniper"]}
        battle["equipment"] = [{"id": "laser", "level": 2}, {"id": "sniper", "level": 2}]
        for turn, expected in enumerate(("laser", "sniper", "laser")):
            battle["turn"] = turn
            self.assertEqual(weapon_for("volt", "attack", self.session.state, battle), expected)

    async def test_presentation_preferences_survive_reload_without_changing_progress(self):
        before = self.session.state.to_dict()
        self.session.presentation(speed=2.0, reduced=True)
        restored = GameSession(store=self.session.store)
        self.assertEqual((restored.battle_speed, restored.reduced_effects), (2.0, True))
        self.assertEqual(self.session.state.to_dict(), before)
        await restored.close()


class IdentityAndTacticsTests(unittest.TestCase):
    def test_every_existing_identity_has_authored_showroom_and_counter_description(self):
        self.assertEqual(set(ABILITIES), set(DESIGNS))
        self.assertEqual(len({a.choreography for a in ABILITIES.values()}), 32)
        for ability in ABILITIES.values():
            self.assertGreaterEqual(len(set(ability.reactions)), 3)
            self.assertTrue(ability.title and ability.effect)

    def test_difficult_bots_interrupt_preparation_while_training_remains_predictable(self):
        session = GameSession.preview()
        session.state = GameState(robot_levels={"spark": 3}, active_robot="spark", egg_id="")
        session.act("battle_start", "spark")
        battle = session.state.battle
        battle["combatants"]["a"]["preparing"] = True
        battle["difficulty"] = "training"
        self.assertEqual(enemy_intent(battle), "windup")
        battle["difficulty"] = "hard"
        self.assertEqual(enemy_intent(battle), "quick")

    def test_training_opponent_stats_stay_comparable_on_late_route(self):
        session = GameSession.preview()
        session.state = GameState(robot_levels={"volt": 4}, active_robot="volt", egg_id="",
                                  arena_stage=20, arena_difficulty="training")
        session.act("battle_start", "volt")
        battle = session.state.battle
        self.assertLessEqual(battle["enemy_max_hp"], round(battle["player_max_hp"] * 1.15))
        self.assertLessEqual(battle["enemy_attack"], battle["player_attack"])


if __name__ == "__main__":
    unittest.main()
