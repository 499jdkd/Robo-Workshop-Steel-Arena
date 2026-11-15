"""Semantic presentation bridge. No damage, inventory or save state lives here."""

import json
import os

import flet as ft
from flet_rive import Rive

from robot_catalog import ROBOT_BY_ID

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


def weapon_for(robot_id, action="attack", state=None, battle=None):
    if action == "guard":
        return "shield"
    if action in {"charge", "dodge"}:
        return action
    if state is not None and action != "special":
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


def animated_scene(session, *, arena=False, battle=None, expanded=False):
    state = session.state
    visual = session.arena_visual if arena else {}
    battle = battle or {}
    if visual.get("battle_id") != battle.get("id"):
        visual = {}
    robot_id = battle.get("robot_id") if arena else state.active_robot
    enemy_id = battle.get("enemy_id", "flora")
    robot = ROBOT_BY_ID.get(robot_id, ROBOT_BY_ID["spark"])
    enemy = ROBOT_BY_ID.get(enemy_id, ROBOT_BY_ID["flora"])
    action = visual.get("action", "idle") if arena else session.motion_action
    phase = visual.get("phase", "idle") if arena else "workshop"
    if phase in {"counter-flight", "counter-hit"}:
        action = "attack"
    animation_battle = dict(battle)
    if phase not in {"idle", "approach", "flight"}:
        animation_battle["turn"] = max(0, battle.get("turn", 0) - 1)
    payload = {
        "arena": arena,
        "expanded": expanded,
        "robot": robot.id,
        "enemy": enemy.id,
        "accent": robot.color,
        "enemyAccent": enemy.color,
        "mobility": robot.mobility,
        "enemyMobility": enemy.mobility,
        "enemyAction": battle.get("enemy_action", "attack"),
        "level": state.robot_levels.get(robot.id, 1),
        "weapon": weapon_for(robot.id, action, state, animation_battle),
        "equipped": state.loadouts.get(robot.id, [])[:2],
        "enemyWeapon": battle.get("enemy_weapon")
        or weapon_for(
            enemy.id,
            "special" if battle.get("last_intent") in {"pulse", "pierce"} else "attack",
        ),
        "phase": phase,
        "action": action,
        "event": f"{battle.get('id')}:{session.arena_animation_id}:{battle.get('turn', 0)}:{phase}"
        if arena
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
    return GameRive(
        src="animation/game_robot.riv",
        payload=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        renderer=os.environ.get("CLICKER_RIVE_RENDERER", "auto"),
        key="game-rive-arena" if arena else "game-rive-workshop",
        expand=True,
    )
