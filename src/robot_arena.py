"""Saved, deterministic tactical battles. No random rolls or online dependency."""

from dataclasses import dataclass

from robot_catalog import MAX_ROBOT_LEVEL, ROBOT_BY_ID, ROBOTS
from robot_designs import DESIGNS

BATTLE_ENERGY = 20
INTENTS = ("windup", "heavy", "guard", "attack")
INTENT_NAMES = {
    "attack": "Быстрый удар",
    "guard": "Защитная стойка",
    "windup": "Накапливает энергию",
    "heavy": "Сокрушительный рывок",
    "pulse": "Энергокольцо — нужна защита",
    "pierce": "Точный луч — пробивает щит",
}
SPECIALS = {
    "spark": ("Двойная искра", "Два удара; трать фокус в нужный момент"),
    "volt": ("Электроимпульс", "Урон и остановка ответной атаки"),
    "flora": ("Ремонтный луч", "Восстановление здоровья и лёгкий удар"),
    "forge": ("Стальной купол", "Удар и защита от ответа"),
    "nova": ("Звёздный луч", "Пробивает защитную стойку"),
    "glacier": ("Ледяная волна", "Холодный импульс останавливает ответ соперника"),
    "aegis": ("Крепость", "Удар, щит и небольшой ремонт"),
    "solar": (
        "Солнечная вспышка",
        "Пробивает стойку и восстанавливает немного здоровья",
    ),
}
ELEMENTS = {
    "spark": "steel",
    "forge": "steel",
    "volt": "pulse",
    "flora": "nature",
    "nova": "cosmic",
    "glacier": "pulse",
    "aegis": "steel",
    "solar": "cosmic",
}
ELEMENTS.update({identity: d["element"] for identity, d in DESIGNS.items()})
SPECIALS.update(
    {
        identity: (d["ultimate"], d["strength"])
        for identity, d in DESIGNS.items()
        if identity not in SPECIALS
    }
)
ELEMENT_NAMES = {
    "steel": "Сталь",
    "pulse": "Импульс",
    "nature": "Природа",
    "cosmic": "Космос",
}
ELEMENT_COLORS = {
    "steel": "#F6B95C",
    "pulse": "#66DCFF",
    "nature": "#6CE1BA",
    "cosmic": "#C4A0FF",
}
ADVANTAGE = {"pulse": "steel", "steel": "nature", "nature": "cosmic", "cosmic": "pulse"}
LEAGUES = (
    "Двор мастерской",
    "Неоновый док",
    "Сады механизмов",
    "Стальная станция",
    "Звёздный купол",
)
ACTIONS = {"attack", "guard", "special", "dodge", "charge"}


def element_multiplier(attacker, defender):
    a, d = ELEMENTS[attacker], ELEMENTS[defender]
    return 1.2 if ADVANTAGE[a] == d else 0.85 if ADVANTAGE[d] == a else 1.0


def league_name(stage):
    return LEAGUES[min(len(LEAGUES) - 1, max(0, stage) // 5)]


def robot_stats(robot_id, level):
    from robot_designs import base_stats

    stats = base_stats(robot_id, max(1, min(MAX_ROBOT_LEVEL, level)))
    return stats["health"], stats["attack"]


def _legacy_robot_stats(robot_id, level):
    level = max(1, min(MAX_ROBOT_LEVEL, level))
    health = (
        78
        + 14 * (level - 1)
        + (
            25
            if robot_id == "aegis"
            else 22
            if robot_id == "forge"
            else 12
            if robot_id == "flora"
            else 6
            if robot_id == "glacier"
            else 0
        )
    )
    attack = 12 + 3 * (level - 1) + (2 if robot_id in {"nova", "solar"} else 0)
    return health, attack


def enemy_for(stage):
    stage = max(0, min(10000, int(stage)))
    robot = ROBOTS[stage % len(ROBOTS)]
    boss = stage % 5 == 4
    health = 68 + stage * 11 + (stage // 5) ** 2 * 2
    return {
        "robot_id": robot.id,
        "name": ("Страж " if boss else "Тренер ") + robot.name,
        "health": min(999999, health * 5 // 4 if boss else health),
        "attack": 12 + stage + stage // 5 + (3 if boss else 0),
        "reward": 24 + stage * 10 + (30 if boss else 0),
        "boss": boss,
        "ability": (
            "Броня восстанавливается при защите",
            "Ремонт от нанесённого урона",
            "Перегрузка усиливает импульс",
        )[(stage // 5) % 3]
        if boss
        else "Чередует атаки и защиту",
    }


def new_battle(robot_id, level, stage, serial):
    health, attack = robot_stats(robot_id, level)
    enemy = enemy_for(stage)
    return {
        "id": serial,
        "rules_version": 2,
        "equipment": [],
        "difficulty": "normal",
        "mode": "route",
        "battery": 12,
        "robot_id": robot_id,
        "enemy_id": enemy["robot_id"],
        "stage": stage,
        "turn": 0,
        "player_hp": health,
        "player_max_hp": health,
        "enemy_hp": enemy["health"],
        "enemy_max_hp": enemy["health"],
        "player_attack": attack,
        "enemy_attack": enemy["attack"],
        "player_level": level,
        "reward": enemy["reward"],
        "boss": enemy["boss"],
        "cooldown": 0,
        "focus": 2,
        "heat": 0,
        "dodge_cooldown": 0,
        "precision": 0,
        "result": "active",
        "last_action": "",
        "last_damage": 0,
        "last_incoming": 0,
        "last_heal": 0,
        "last_enemy_heal": 0,
        "last_dodged": False,
        "last_stunned": False,
        "last_counter": 0,
        "last_intent": "",
        "log": ["Читай намерение соперника. Удары подряд перегревают робота."],
    }


def enemy_intent(battle):
    stage, turn = battle.get("stage", 0), battle.get("turn", 0)
    if battle.get("boss"):
        pattern = ("windup", "heavy", "guard", "pierce", "pulse", "attack")
        return pattern[(turn + stage // 5) % len(pattern)]
    pattern = INTENTS if stage % 3 != 2 else ("guard", "attack", "windup", "heavy")
    return pattern[(turn + stage % 2) % len(pattern)]


def suggested_action(battle):
    """Used in the introductory tip and balance simulations, never auto-plays."""
    from armory import equipped_weapon

    if battle.get("rules_version") == 3 and battle.get("combatants"):
        from combat_rules import action_error, allowed, current_actor

        actor = current_actor(battle)
        intent = enemy_intent(battle)
        # Finish a winnable exchange before spending a turn on a defensive tip.
        from copy import deepcopy
        from combat_rules import resolve_action

        for candidate in ("quick", "attack", "special", "pierce", "burst"):
            target = deepcopy(battle["combatants"]["b"])
            target["guard"] = intent == "guard" and not target["emp"]
            target["preparing"] = intent == "windup"
            if candidate in allowed(actor) and not action_error(actor, candidate):
                resolved = resolve_action(
                    deepcopy(actor),
                    target,
                    candidate,
                    seed=battle["id"] + battle["turn"],
                )
                if resolved["ok"] and target["hp"] == 0:
                    return candidate
        preferred = ["ultimate"] if actor["super_charge"] >= 100 else []
        preferred += (
            ["quick"]
            if intent == "windup"
            else ["pierce", "emp", "charge"]
            if intent == "guard"
            else ["dodge", "guard"]
            if intent in {"heavy", "pierce", "pulse"}
            else ["special", "attack", "guard", "charge"]
        )
        return next(
            (
                a
                for a in preferred + ["charge"]
                if a in allowed(actor) and not action_error(actor, a)
            ),
            "charge",
        )

    equipment, _equipment_level = equipped_weapon(battle)
    if equipment and battle.get("battery", 12) < equipment.energy:
        return "charge"
    intent = enemy_intent(battle)
    if intent in {"heavy", "pierce"}:
        if battle.get("focus", 2) and not battle.get("dodge_cooldown", 0):
            return "dodge"
        return "guard"
    if intent == "pulse":
        return "guard"
    if intent == "guard":
        return "charge"
    if battle.get("focus", 2) >= 2 and not battle["cooldown"]:
        return "special"
    return "guard" if battle.get("heat", 0) >= 2 else "attack"


@dataclass(frozen=True)
class TurnResult:
    ok: bool
    message: str = ""
    finished: bool = False


def take_turn(battle, action, battle_id, expected_turn):
    if battle.get("rules_version") == 3 and battle.get("combatants"):
        from combat_rules import local_turn

        return local_turn(battle, action, battle_id, expected_turn)
    if not battle or battle.get("result") != "active":
        return TurnResult(False, "Бой уже завершён")
    if battle_id != battle["id"] or expected_turn != battle["turn"]:
        return TurnResult(False, "Ход уже выполнен")
    if action not in ACTIONS:
        return TurnResult(False, "Выбери действие")
    focus = battle.get("focus", 2)
    if action == "special" and (battle["cooldown"] or focus < 2):
        return TurnResult(False, "Приём требует 2 фокуса и готовую способность")
    if action == "dodge" and (battle.get("dodge_cooldown", 0) or focus < 1):
        return TurnResult(False, "Уклонение требует 1 фокуса и перезарядку")
    from armory import equipped_weapon

    equipment, _equipment_level = equipped_weapon(battle)
    battery = battle.get("battery", 12)
    if equipment and action in {"attack", "special"} and battery < equipment.energy:
        return TurnResult(False, "Батарея оружия разряжена: используй фокус или щит")
    if equipment:
        battle["battery"] = (
            max(0, battery - equipment.energy)
            if action in {"attack", "special"}
            else min(12, battery + (6 if action == "charge" else 3))
        )
    intent = enemy_intent(battle)
    robot_id, attack = battle["robot_id"], battle["player_attack"]
    from armory import equipment_effect

    attack, gear_pierce, gear_shield = equipment_effect(battle, action, attack)
    damage, shield, stun, ignore_guard, healed = 0, False, False, False, 0
    ignore_guard = gear_pierce
    lines = []
    if (
        battle.get("boss")
        and battle["stage"] >= 9
        and intent == "guard"
        and (battle["stage"] // 5) % 3 == 0
    ):
        repaired = min(8, battle["enemy_max_hp"] - battle["enemy_hp"])
        battle["enemy_hp"] += repaired
        if repaired:
            lines.append(f"Страж восстанавливает броню: +{repaired}")
    battle.update(
        last_damage=0,
        last_incoming=0,
        last_heal=0,
        last_dodged=False,
        last_stunned=False,
        last_counter=0,
        last_intent=intent,
    )
    if action == "attack":
        damage = attack if battle.get("heat", 0) < 2 else max(1, attack * 55 // 100)
        battle["heat"] = min(3, battle.get("heat", 0) + 1)
        focus = min(3, focus + 1)
        if battle["heat"] >= 3:
            lines.append("Перегрев: чередуй удары с защитой и приёмами")
    else:
        battle["heat"] = 0
        if action == "charge" and equipment and equipment.id == "drone":
            damage = max(1, attack // 3)
    if action == "guard":
        damage, shield, focus = max(1, attack // 5), True, min(3, focus + 1)
        lines.append("Щит поднят, фокус восстановлен")
        if gear_shield:
            healed = min(4, battle["player_max_hp"] - battle["player_hp"])
            battle["player_hp"] += healed
    elif action == "charge":
        focus, battle["precision"] = min(3, focus + 2), 1
        lines.append("Прицел готов: следующий удар усилен")
    elif action == "dodge":
        focus -= 1
        battle["dodge_cooldown"] = 3
    elif action == "special":
        focus -= 2
        battle["cooldown"] = 3
        lines.append(SPECIALS[robot_id][0])
        if robot_id == "spark":
            damage = attack * 17 // 10
        elif robot_id == "volt":
            damage, stun = attack * 13 // 10, True
        elif robot_id == "flora":
            healed = min(
                battle["player_max_hp"] - battle["player_hp"],
                battle["player_max_hp"] // 3,
            )
            battle["player_hp"] += healed
            damage = max(1, attack // 2)
        elif robot_id == "forge":
            damage, shield = attack * 3 // 2, True
        elif robot_id == "glacier":
            damage, stun = attack * 11 // 10, True
        elif robot_id == "aegis":
            damage, shield = attack * 13 // 10, True
            healed = min(
                battle["player_max_hp"] - battle["player_hp"],
                battle["player_max_hp"] // 8,
            )
            battle["player_hp"] += healed
        elif robot_id == "solar":
            damage, ignore_guard = attack * 19 // 10, True
            healed = min(
                battle["player_max_hp"] - battle["player_hp"],
                battle["player_max_hp"] // 10,
            )
            battle["player_hp"] += healed
        else:
            damage, ignore_guard = attack * 2, True
    if damage and action in {"attack", "special"} and battle.get("precision"):
        damage = damage * 13 // 10
        battle["precision"] = 0
    if damage:
        damage = max(
            1, round(damage * element_multiplier(robot_id, battle["enemy_id"]))
        )
        if intent == "guard" and not ignore_guard:
            damage = max(1, damage * 2 // 5)
    battle["enemy_hp"] = max(0, battle["enemy_hp"] - damage)
    battle["last_damage"], battle["last_heal"] = damage, healed
    if damage:
        lines.append(f"Твой робот: −{damage} здоровья сопернику")
    if healed:
        lines.append(f"Ремонт: +{healed} здоровья")
    if not battle["enemy_hp"]:
        battle["result"] = "win"
    elif stun:
        battle["last_stunned"] = True
        lines.append("Соперник оглушён и пропускает ответ")
    else:
        incoming = battle["enemy_attack"]
        if equipment and equipment.id == "electric" and battle["turn"] % 3 == 2:
            incoming = incoming * 65 // 100
        incoming = (
            0
            if intent == "windup"
            else incoming * 2
            if intent == "heavy"
            else max(1, incoming // 2)
            if intent == "guard"
            else incoming * 6 // 5
            if intent in {"pulse", "pierce"}
            else incoming
        )
        if battle["turn"] >= 18:
            incoming = incoming * (100 + (battle["turn"] - 17) * 8) // 100
        dodged = action == "dodge" and intent in {"attack", "heavy", "pierce"}
        if dodged:
            incoming = 0
            counter = max(1, attack // 2)
            battle["enemy_hp"] = max(0, battle["enemy_hp"] - counter)
            battle["last_damage"] += counter
            battle["last_counter"] = counter
            battle["precision"] = 1
            lines.append(f"Уклонение! Контратака: {counter}")
        elif shield:
            incoming = (
                max(1, incoming * (55 if intent == "pierce" else 28) // 100)
                if incoming
                else 0
            )
        battle["last_dodged"] = dodged
        if battle.get("boss") and battle["stage"] >= 9:
            kind = (battle["stage"] // 5) % 3
            if kind == 1 and incoming:
                repaired = min(
                    7, incoming // 4, battle["enemy_max_hp"] - battle["enemy_hp"]
                )
                battle["enemy_hp"] += repaired
                if repaired:
                    lines.append(f"Страж поглощает энергию: +{repaired}")
            if kind == 2 and intent == "pulse" and incoming:
                incoming = incoming * 115 // 100
        battle["last_incoming"] = incoming
        battle["player_hp"] = max(0, battle["player_hp"] - incoming)
        lines.append(
            "Соперник заряжает мощную атаку"
            if intent == "windup"
            else f"Ответ соперника: {incoming} урона"
        )
        if not battle["enemy_hp"]:
            battle["result"] = "win"
        elif not battle["player_hp"] or battle["turn"] >= 59:
            battle["result"] = "loss"
    battle["focus"] = focus
    battle["cooldown"] = max(0, battle["cooldown"] - 1)
    battle["dodge_cooldown"] = max(0, battle.get("dodge_cooldown", 0) - 1)
    battle["turn"] += 1
    battle["last_action"] = action
    if battle["result"] != "active":
        lines.append(
            "Победа!"
            if battle["result"] == "win"
            else "Попробуй другую тактику или улучши робота"
        )
    battle["log"] = (battle["log"] + lines)[-7:]
    return TurnResult(True, lines[-1], battle["result"] != "active")


def restore_battle(data):
    if not isinstance(data, dict):
        return {}
    if any(
        not isinstance(data.get(k), str) for k in ("robot_id", "enemy_id", "result")
    ):
        return {}
    if data["robot_id"] not in ROBOT_BY_ID or data["enemy_id"] not in ROBOT_BY_ID:
        return {}
    keys = (
        "id",
        "stage",
        "turn",
        "player_hp",
        "player_max_hp",
        "enemy_hp",
        "enemy_max_hp",
        "player_attack",
        "enemy_attack",
        "reward",
        "cooldown",
    )
    if any(
        isinstance(data.get(k), bool)
        or not isinstance(data.get(k), int)
        or not 0 <= data[k] <= 1000000
        for k in keys
    ):
        return {}
    if data["result"] not in {"active", "win", "loss", "left"} or not data["id"]:
        return {}
    if any(
        not data[k]
        for k in ("player_max_hp", "enemy_max_hp", "player_attack", "enemy_attack")
    ):
        return {}
    if (
        data["player_hp"] > data["player_max_hp"]
        or data["enemy_hp"] > data["enemy_max_hp"]
        or data["cooldown"] > 3
    ):
        return {}
    if data["result"] == "active" and (not data["player_hp"] or not data["enemy_hp"]):
        return {}
    result = {k: data[k] for k in keys}
    from armory import BY_ID, DIFFICULTIES, clean_int

    raw_gear = data.get("equipment", [])
    result["equipment"] = (
        [
            {"id": item["id"], "level": min(10, max(1, clean_int(item.get("level"))))}
            for item in raw_gear
            if isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and item.get("id") in BY_ID
        ][:2]
        if isinstance(raw_gear, list)
        else []
    )
    result["difficulty"] = (
        data.get("difficulty")
        if isinstance(data.get("difficulty"), str)
        and data.get("difficulty") in DIFFICULTIES
        else "normal"
    )
    result["mode"] = "tournament" if data.get("mode") == "tournament" else "route"
    for key, default, maximum in (
        ("focus", 2, 3),
        ("battery", 12, 18 if data.get("rules_version") == 3 else 12),
        ("heat", 0, 3),
        ("dodge_cooldown", 0, 3 if data.get("rules_version") == 3 else 2),
        ("precision", 0, 1),
        ("player_level", 1, MAX_ROBOT_LEVEL),
        ("last_damage", 0, 1000000),
        ("last_incoming", 0, 1000000),
        ("last_heal", 0, 1000000),
        ("last_enemy_heal", 0, 1000000),
        ("last_counter", 0, 1000000),
        ("defense", 0, 100),
        ("speed", 100, 500),
        ("crit", 8, 35),
        ("crit_damage", 150, 200),
        ("max_battery", 12, 18),
        ("regen", 3, 6),
        ("super_charge", 0, 100),
        ("weapon_cooldown", 0, 5),
        ("emp_turns", 0, 3),
        ("slow_turns", 0, 3),
        ("skill_level", 1, 5),
    ):
        value = data.get(key, default)
        result[key] = (
            min(maximum, max(0, value))
            if isinstance(value, int) and not isinstance(value, bool)
            else default
        )
    if "insulated" in data:
        result["insulated"] = data["insulated"] is True
    # A legacy standalone battle has none of the v3 fields; keep round trips
    # exact instead of silently introducing statistics into a running fight.
    for key in (
        "defense",
        "speed",
        "crit",
        "crit_damage",
        "max_battery",
        "regen",
        "super_charge",
        "weapon_cooldown",
        "emp_turns",
        "slow_turns",
        "skill_level",
    ):
        if key not in data:
            result.pop(key, None)
    log = data.get("log")
    result.update(
        robot_id=data["robot_id"],
        enemy_id=data["enemy_id"],
        result=data["result"],
        rules_version=2,
        boss=bool(data.get("boss", data["stage"] % 5 == 4)),
        last_action=str(data.get("last_action", ""))[:16],
        last_intent=str(data.get("last_intent", ""))[:16],
        last_dodged=bool(data.get("last_dodged", False)),
        last_stunned=bool(data.get("last_stunned", False)),
        log=[str(line)[:180] for line in log][-7:] if isinstance(log, list) else [],
    )
    if data.get("rules_version") == 3 and isinstance(data.get("combatants"), dict):
        from combat_rules import restore_fighter

        fighters = {
            side: restore_fighter(data["combatants"].get(side)) for side in ("a", "b")
        }
        if not all(fighters.values()):
            return {}
        result["combatants"] = fighters
        result["rules_version"] = 3
        result["enemy_weapon"] = fighters["b"]["weapon"]
        if "enemy_action" in data:
            result["enemy_action"] = str(data["enemy_action"])[:16]
    return result
