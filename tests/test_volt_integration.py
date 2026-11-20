"""Volt input races and native-scene intent stability on isolated game state."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import battle_ui
import flet as ft
from combat_rules import current_actor, resolve_action
from game_animation import animated_scene
from game_session import GameSession
from gameplay import GameState
from robot_arena import enemy_intent
from robot_designs import DESIGNS
from robot_preview import preview_controls
from test_robot_ui import render_controls


class VoltInputRaceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = SimpleNamespace(width=390, height=844, run_task=Mock())
        self.session = GameSession.preview(self.page)
        self.session.state = GameState(
            robot_levels={"volt": 4}, active_robot="volt", egg_id="",
            arena_difficulty="training",
        )
        self.assertTrue(self.session.act("battle_start", "volt").ok)

    async def asyncTearDown(self):
        await self.session.close()

    async def test_double_click_does_not_queue_another_turn(self):
        entered, release = asyncio.Event(), asyncio.Event()
        real_sleep = asyncio.sleep
        waits = 0

        async def gate(_):
            nonlocal waits
            waits += 1
            if waits == 1:
                entered.set()
                await release.wait()
            else:
                await real_sleep(0)

        battle = self.session.state.battle
        identity = battle["id"]
        with patch.object(battle_ui.asyncio, "sleep", side_effect=gate):
            first = asyncio.create_task(battle_ui.animate_turn(self.session, "attack", identity, 0))
            await entered.wait()
            self.assertFalse(await battle_ui.animate_turn(self.session, "attack", identity, 0))
            release.set()
            self.assertTrue(await first)
            self.assertFalse(await battle_ui.animate_turn(self.session, "attack", identity, 0))
        self.assertEqual(battle["turn"], 1)
        self.assertFalse(self.session.arena_animating)
        self.assertFalse(self.session.arena_visual)

    async def test_old_scene_cannot_erase_new_battle_animation(self):
        entered = {name: asyncio.Event() for name in ("old", "new")}
        release = {name: asyncio.Event() for name in ("old", "new")}
        real_sleep = asyncio.sleep
        seen = set()

        async def gate(_):
            name = asyncio.current_task().get_name()
            if name not in seen:
                seen.add(name)
                entered[name].set()
                await release[name].wait()
            else:
                await real_sleep(0)

        original = self.session.state.battle
        with patch.object(battle_ui.asyncio, "sleep", side_effect=gate):
            old = asyncio.create_task(
                battle_ui.animate_turn(self.session, "attack", original["id"], 0), name="old")
            await entered["old"].wait()
            self.assertTrue(self.session.act("battle_leave").ok)
            self.assertTrue(self.session.act("battle_start", "volt").ok)
            replacement = self.session.state.battle
            new = asyncio.create_task(
                battle_ui.animate_turn(self.session, "charge", replacement["id"], 0), name="new")
            await entered["new"].wait()
            active_visual = deepcopy(self.session.arena_visual)
            release["old"].set()
            self.assertFalse(await old)
            self.assertTrue(self.session.arena_animating)
            self.assertEqual(self.session.arena_visual, active_visual)
            self.assertEqual(replacement["turn"], 0)
            release["new"].set()
            self.assertTrue(await new)
        self.assertEqual(replacement["turn"], 1)
        self.assertFalse(self.session.arena_animating)

    async def test_cancellation_after_commit_keeps_one_committed_turn(self):
        entered = asyncio.Event()
        real_sleep = asyncio.sleep

        async def gate(_):
            if self.session.arena_visual.get("phase") == "impact":
                entered.set()
                await asyncio.Event().wait()
            await real_sleep(0)

        battle = self.session.state.battle
        with patch.object(battle_ui.asyncio, "sleep", side_effect=gate):
            task = asyncio.create_task(battle_ui.animate_turn(self.session, "attack", battle["id"], 0))
            await entered.wait()
            committed = deepcopy(battle)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(battle, committed)
        self.assertEqual(battle["turn"], 1)
        self.assertFalse(self.session.arena_animating)
        self.assertFalse(self.session.arena_visual)
        with patch.object(battle_ui.asyncio, "sleep", new=AsyncMock()):
            self.assertTrue(await battle_ui.animate_turn(self.session, "charge", battle["id"], 1))

    async def test_background_tick_does_not_restart_workshop_motion(self):
        self.assertTrue(self.session.act("battle_leave").ok)
        before = json.loads(animated_scene(self.session).payload)
        for offset in range(1, 6):
            self.session.tick(self.session.state.last_active_at + offset)
            current = json.loads(animated_scene(self.session).payload)
            self.assertEqual(current["event"], before["event"])
            self.assertEqual(current["combatAction"], before["combatAction"])
        self.assertEqual(before["robot"], "volt")

    async def test_actual_equipped_mount_matches_every_animation_phase_and_damage(self):
        self.session.act("battle_leave")
        self.session.state.weapon_levels = {"laser": 2, "sniper": 2}
        self.session.state.loadouts = {"volt": ["laser", "sniper"]}
        self.assertTrue(self.session.act("battle_start", "volt").ok)
        battle = self.session.state.battle
        for turn, selected in enumerate(("laser", "sniper")):
            actor, victim = current_actor(battle), deepcopy(battle["combatants"]["b"])
            intent = enemy_intent(battle)
            victim["guard"] = intent == "guard" and not victim["emp"]
            victim["preparing"] = intent == "windup"
            expected = resolve_action(actor, victim, "attack", seed=battle["id"] + turn)
            self.assertTrue(expected["ok"])
            payloads = []

            async def sample(_):
                payloads.append(json.loads(animated_scene(self.session, arena=True, battle=battle).payload))

            with patch.object(battle_ui.asyncio, "sleep", side_effect=sample):
                self.assertTrue(await battle_ui.animate_turn(self.session, "attack", battle["id"], turn))
            own_phases = [payload for payload in payloads if payload["phase"] in {"approach", "flight", "impact"}]
            self.assertEqual({payload["phase"] for payload in own_phases}, {"approach", "flight", "impact"})
            self.assertEqual({payload["weapon"] for payload in own_phases}, {selected})
            self.assertTrue(all(payload["equipped"] == ["laser", "sniper"] for payload in own_phases))
            self.assertTrue(all(payload["combatAction"] == "attack" for payload in own_phases))
            self.assertTrue(all(payload["prepareSeconds"] > 0 and payload["impactSeconds"] > 0 for payload in own_phases))
            self.assertEqual(battle["combatants"]["a"]["weapon"], selected)
            self.assertEqual(battle["last_damage"], expected["damage"])

    async def test_human_pvp_uses_server_equipment_without_local_loadout_or_resolver_mutation(self):
        battle = deepcopy(self.session.state.battle)
        battle.update(kind="human-ranked", robot_id="volt", enemy_id="volt",
                      equipment=[{"id": "laser", "level": 1}], enemy_equipment=[],
                      enemy_weapon="rocket", enemy_action="attack")
        battle["combatants"]["a"]["weapon"] = "laser"
        battle["combatants"]["b"].update(robot="volt", weapon="rocket")
        self.session.arena_visual = {"battle_id": battle["id"], "phase": "flight", "action": "attack"}
        for local_gear in ([], ["sniper"]):
            with self.subTest(local_loadout=local_gear):
                self.session.state.loadouts = {"volt": local_gear} if local_gear else {}
                before_battle, before_state = deepcopy(battle), self.session.state.to_dict()
                payload = json.loads(animated_scene(self.session, arena=True, battle=battle).payload)
                self.assertEqual(payload["weapon"], "laser")
                self.assertEqual(payload["equipped"], ["laser"])
                self.assertEqual(payload["enemy"], "volt")
                self.assertEqual(payload["enemyWeapon"], "rocket")
                self.assertEqual(payload["enemyEquipped"], ["rocket"])
                self.assertEqual(payload["combatAction"], "attack")
                self.assertEqual(battle, before_battle)
                self.assertEqual(self.session.state.to_dict(), before_state)


class VoltPreviewIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_ten_owned_and_locked_volt_preview_buttons_never_change_progress(self):
        expected = {"attack", "special", "ultimate", "guard", "quick", "dodge", "charge", "dance", "victory", "defeat"}
        for owned in (False, True):
            with self.subTest(owned=owned):
                session = GameSession.preview()
                session.state = GameState(
                    level=10, coin=1234, food=32,
                    robot_levels={"spark": 3, **({"volt": 4} if owned else {})},
                    active_robot="volt" if owned else "spark", egg_id="",
                    weapon_levels={"laser": 2}, loadouts={"volt" if owned else "spark": ["laser"]},
                )
                session.persist()
                before, saved = session.state.to_dict(), deepcopy(session.store.load())
                try:
                    controls = render_controls(preview_controls(session, "volt"))
                    buttons = {control.key.removeprefix("preview-").removesuffix("-volt"): control
                               for control in controls if isinstance(control, ft.Button)
                               and str(control.key).startswith("preview-")}
                    self.assertEqual(set(buttons), expected)
                    previous_event = session.preview_event
                    for action, button in buttons.items():
                        self.assertFalse(button.disabled)
                        await button.on_click(None)
                        payload = json.loads(animated_scene(session, identity="volt").payload)
                        self.assertEqual(payload["robot"], "volt")
                        self.assertTrue(payload["demonstration"])
                        self.assertEqual(payload["combatAction"], action)
                        self.assertEqual(session.preview_event, previous_event + 1)
                        previous_event += 1
                        self.assertEqual(session.state.to_dict(), before)
                        self.assertEqual(session.store.load(), saved)
                finally:
                    await session.close()

    async def test_volt_reactions_are_transient_and_other_robots_keep_their_existing_actions(self):
        session = GameSession.preview()
        session.persist()
        before, saved = session.state.to_dict(), deepcopy(session.store.load())
        extended = {"quick", "dodge", "charge", "jump", "surprise", "anger", "dance", "inspect", "victory", "defeat"}
        try:
            for action in extended:
                self.assertTrue(session.preview_robot("volt", action))
                snapshot = (session.preview_identity, session.preview_action, session.preview_event)
                for identity in set(DESIGNS) - {"volt"}:
                    self.assertFalse(session.preview_robot(identity, action), (identity, action))
                    self.assertEqual((session.preview_identity, session.preview_action, session.preview_event), snapshot)
            for identity in set(DESIGNS) - {"volt"}:
                controls = render_controls(preview_controls(session, identity))
                self.assertEqual(sum(isinstance(control, ft.Button) and str(control.key).startswith("preview-")
                                     for control in controls), 4)
            self.assertEqual(session.state.to_dict(), before)
            self.assertEqual(session.store.load(), saved)
        finally:
            await session.close()


if __name__ == "__main__":
    unittest.main()
