"""Semantic presentation bridge. No damage, inventory or save state lives here."""

import json
import os
from pathlib import Path

import flet as ft
from flet_rive import Rive

from robot_catalog import ROBOT_BY_ID
from robot_designs import DESIGNS
from cosmetic_catalog import animation_name
from robot_abilities import ABILITIES

# Ordinary attacks showcase the robot's built-in equipment. Specials retain
# their existing effects (healing/stun/shield/piercing) and combat arithmetic.
WEAPONS = {
    "spark": ("plasma", "plasma"),
    "volt": ("fist", "fist"),
    "flora": ("plasma", "repair"),
    "forge": ("rocket", "shield"),
    "nova": ("sniper", "sniper"),
    "glacier": ("sniper", "plasma"),
    "aegis": ("rocket", "shield"),
    "solar": ("plasma", "rocket"),
}
WEAPON_NAMES = {
    "plasma": "Плазменная пушка",
    "sniper": "Снайперская винтовка",
    "fist": "Электрический кулак",
    "rocket": "Ракетная установка",
    "shield": "Энергетический щит",
    "repair": "Ремонтный луч",
}


for _id, _design in DESIGNS.items():
    WEAPONS[_id] = (_design["weapon"], _design["weapon"])


def weapon_for(robot_id, action="attack", state=None, battle=None):
    if action == "emp":
        return "emp"
    if action == "guard":
        return "shield"
    if action in {"charge", "dodge"}:
        return action
    if action == "ultimate":
        return DESIGNS[robot_id]["weapon"]
    if state is not None:
        gear = (battle or {}).get("equipment")
        if gear:
            turn = (battle or {}).get("turn", 0)
            return gear[turn % len(gear)]["id"]
        loadout = state.loadouts.get(robot_id, [])
        if loadout:
            return loadout[0]
    return WEAPONS.get(robot_id, WEAPONS["spark"])[action == "special"]


@ft.control("GameRive")
class GameRive(Rive):
    payload: str = "{}"
    renderer: str = "auto"
    report_ready: bool = False
    on_ready: ft.ControlEventHandler | None = None
    on_robot_tap: ft.ControlEventHandler | None = None


def animated_scene(session, *, arena=False, battle=None, expanded=False, identity=None, on_robot_tap=None):
    state = session.state
    visual = session.arena_visual if arena else {}
    battle = battle or {}
    if visual.get("battle_id") != battle.get("id"):
        visual = {}
    robot_id = battle.get("robot_id") if arena else identity or state.active_robot
    enemy_id = battle.get("enemy_id", "flora")
    robot = ROBOT_BY_ID.get(robot_id, ROBOT_BY_ID["spark"])
    enemy = ROBOT_BY_ID.get(enemy_id, ROBOT_BY_ID["flora"])
    action = visual.get("action", "idle") if arena else session.motion_action
    demonstration = identity is not None and not arena
    if demonstration:
        action = session.preview_action if session.preview_identity == robot.id else "idle"
    actual_action = action
    action = {
        "quick": "attack",
        "pierce": "attack",
        "burst": "attack",
        "emp": "attack",
        "ultimate": "special",
    }.get(action, action)
    phase = visual.get("phase", "idle") if arena else "workshop"
    if arena:
        from battle_ui import turn_timing
        prepare_seconds, _, impact_seconds = turn_timing(actual_action)
    else:
        prepare_seconds, impact_seconds = 0.4, 0.25
    if phase in {"counter-flight", "counter-hit"}:
        action = "attack"
    animation_battle = dict(battle)
    if phase not in {"idle", "approach", "flight"}:
        animation_battle["turn"] = max(0, battle.get("turn", 0) - 1)
    visible_equipment = state.loadouts.get(robot.id, [])[:2]
    if arena and robot.id == "volt":
        visible_equipment = [item["id"] for item in battle.get("equipment", []) if isinstance(item, dict) and "id" in item][:2]
    enemy_equipment = [item["id"] for item in battle.get("enemy_equipment", []) if isinstance(item, dict) and "id" in item][:2]
    if battle.get("kind") == "human-ranked" and battle.get("enemy_weapon"):
        enemy_equipment = [battle["enemy_weapon"]]
    payload = {
        "arena": arena,
        "demonstration": demonstration,
        "expanded": expanded,
        "robot": robot.id,
        "enemy": enemy.id,
        "accent": robot.color,
        "enemyAccent": enemy.color,
        "mobility": robot.mobility,
        "enemyMobility": enemy.mobility,
        "enemyAction": {
            "quick": "attack",
            "pierce": "attack",
            "burst": "attack",
            "emp": "attack",
            "ultimate": "special",
        }.get(battle.get("enemy_action"), battle.get("enemy_action", "attack")),
        "level": state.robot_levels.get(robot.id, 1),
        "weapon": weapon_for(
            robot.id,
            actual_action if actual_action in {"emp", "ultimate"} else action,
            state,
            animation_battle,
        ),
        "combatAction": actual_action,
        "enemyCombatAction": battle.get("enemy_action", "attack"),
        "signature": ABILITIES[robot.id].title,
        "reactions": list(ABILITIES[robot.id].reactions),
        "animationSpeed": visual.get("speed", session.battle_speed) if arena else 1,
        "flightSeconds": visual.get("flight_seconds", 0.72),
        "prepareSeconds": visual.get("prepare_seconds", prepare_seconds),
        "impactSeconds": visual.get("impact_seconds", impact_seconds),
        "reducedEffects": session.reduced_effects,
        "equipped": visible_equipment,
        "enemyEquipped": enemy_equipment,
        "modules": list(
            state.collection.get("module_loadouts", {}).get(robot.id, {}).values()
        ),
        "skin": state.collection.get("skin_loadouts", {}).get(robot.id, ""),
        "idleEmotion": animation_name(
            state.collection.get("animation_loadouts", {}).get(robot.id, "")
        )[1]
        if state.collection.get("animation_loadouts", {}).get(robot.id)
        else "joy",
        "workshopLevel": state.stage_index,
        "inventions": state.craft_counts,
        "enemyWeapon": battle.get("enemy_weapon")
        or weapon_for(
            enemy.id,
            "special" if battle.get("last_intent") in {"pulse", "pierce"} else "attack",
        ),
        "phase": phase,
        "action": action,
        "event": f"{battle.get('id')}:{session.arena_animation_id}:{battle.get('turn', 0)}:{phase}"
        if arena
        else f"preview:{robot.id}:{session.preview_event}"
        if demonstration
        else str(session.motion_event),
        "result": battle.get("result", "active"),
        "damage": max(0, battle.get("last_damage", 0) - battle.get("last_counter", 0)),
        "incoming": battle.get("last_incoming", 0),
        "dodged": battle.get("last_dodged", False),
        "stunned": battle.get("last_stunned", False),
        "counter": battle.get("last_counter", 0),
        "intent": battle.get("last_intent", ""),
        "sound": session.motion_sound,
        "paused": session._paused,
    }
    diagnostic_path = os.getenv("CLICKER_SCENE_DIAGNOSTICS")

    def ready(event):
        if not diagnostic_path:
            return
        data = event.data if isinstance(event.data, dict) else json.loads(event.data) if event.data else {"robot": robot.id, "renderer": "unknown"}
        path = Path(diagnostic_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps({**data, "arena": arena, "expanded": expanded}) + "\n"
            )

    return GameRive(
        src="animation/game_robot.riv",
        payload=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        renderer=os.environ.get("CLICKER_RIVE_RENDERER", "auto"),
        report_ready=bool(diagnostic_path),
        on_ready=ready if diagnostic_path else None,
        on_robot_tap=on_robot_tap,
        key="game-rive-arena" if arena else f"game-rive-preview-{robot.id}" if demonstration else "game-rive-workshop",
        expand=True,
    )
