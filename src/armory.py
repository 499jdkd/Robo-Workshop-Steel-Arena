"""Deterministic equipment and long-term goals; compatible with old saves."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Weapon:
    id: str
    title: str
    damage: int
    speed: float
    reach: int
    energy: int
    rarity: str
    price: int
    unlock: int
    ability: str
    animation: str = ""
    effect: str = ""
    mass: int = 1


WEAPONS = (
    Weapon(
        "plasma",
        "Плазменная пушка",
        12,
        1.0,
        6,
        2,
        "common",
        120,
        2,
        "Ровный урон и умеренный расход энергии",
    ),
    Weapon(
        "sniper",
        "Снайперская винтовка",
        20,
        0.55,
        10,
        4,
        "rare",
        450,
        5,
        "Подготовленный выстрел пробивает защиту",
    ),
    Weapon(
        "rocket",
        "Ракетная установка",
        23,
        0.5,
        8,
        5,
        "epic",
        950,
        9,
        "Взрыв усиливается после зарядки",
    ),
    Weapon(
        "laser",
        "Лазер",
        14,
        1.3,
        9,
        4,
        "rare",
        520,
        6,
        "Часть урона проходит сквозь защиту",
    ),
    Weapon(
        "electric",
        "Электрическая пушка",
        13,
        0.85,
        5,
        3,
        "rare",
        600,
        7,
        "Каждый третий выстрел ослабляет ответ",
    ),
    Weapon(
        "machinegun",
        "Пулемёт",
        8,
        2.4,
        6,
        2,
        "common",
        280,
        4,
        "Очередь из трёх выстрелов; быстрее греется",
    ),
    Weapon(
        "sword",
        "Энергетический меч",
        18,
        1.1,
        1,
        3,
        "epic",
        850,
        8,
        "Рывок и мощная контратака",
    ),
    Weapon(
        "shield",
        "Энергетический щит",
        5,
        0.7,
        2,
        2,
        "rare",
        350,
        4,
        "Дополнительная защита при блоке",
    ),
    Weapon(
        "flame",
        "Огнемёт",
        11,
        1.4,
        3,
        4,
        "epic",
        1100,
        10,
        "Разогретая струя: урон растёт в серии",
    ),
    Weapon(
        "drone",
        "Боевой дрон",
        10,
        1.2,
        8,
        3,
        "legendary",
        1800,
        13,
        "Поддерживает атакой во время зарядки",
    ),
)
WEAPONS += (
    Weapon(
        "fist",
        "Электрические кулаки",
        15,
        1.25,
        1,
        2,
        "common",
        240,
        3,
        "Быстрый рывок прерывает заряд",
        "fist",
        "interrupt",
        2,
    ),
    Weapon(
        "cryo",
        "Криогенная пушка",
        12,
        0.9,
        7,
        3,
        "rare",
        580,
        7,
        "Холод замедляет следующий ответ",
        "cryo",
        "slow",
        2,
    ),
    Weapon(
        "ion",
        "Ионная пушка",
        22,
        0.55,
        9,
        5,
        "legendary",
        1700,
        16,
        "Ионный импульс частично пробивает броню",
        "ion",
        "pierce",
        4,
    ),
    Weapon(
        "blaster",
        "Импульсный бластер",
        11,
        1.7,
        5,
        2,
        "common",
        200,
        3,
        "Серия импульсов затрудняет уклонение",
        "blaster",
        "burst",
        1,
    ),
    Weapon(
        "magnetic",
        "Магнитная пушка",
        15,
        0.8,
        6,
        4,
        "epic",
        900,
        10,
        "Полярный захват ослабляет ответ после фокуса",
        "magnetic",
        "disrupt",
        3,
    ),
    Weapon(
        "grenade",
        "Гранатомёт",
        19,
        0.65,
        7,
        4,
        "rare",
        650,
        8,
        "Навесной снаряд поражает защитную стойку",
        "grenade",
        "splash",
        3,
    ),
    Weapon(
        "emp",
        "EMP-генератор",
        8,
        0.7,
        6,
        4,
        "epic",
        1000,
        11,
        "Отключает щит противника на два хода",
        "emp",
        "emp",
        2,
    ),
    Weapon(
        "drill",
        "Механический бур",
        21,
        0.75,
        1,
        4,
        "epic",
        1150,
        12,
        "Разрушает броню при пробивающем ударе",
        "drill",
        "shred",
        4,
    ),
    Weapon(
        "disc",
        "Дисковый метатель",
        12,
        1.6,
        6,
        3,
        "rare",
        540,
        7,
        "Два рикошета против быстрого уклонения",
        "disc",
        "burst",
        2,
    ),
    Weapon(
        "repair",
        "Ремонтный луч",
        4,
        0.9,
        5,
        3,
        "rare",
        400,
        5,
        "Восстанавливает здоровье; небольшой урон",
        "repair",
        "heal",
        1,
    ),
)
BY_ID = {weapon.id: weapon for weapon in WEAPONS}
DIFFICULTIES = {
    "training": ("Тренировка · бот", 0.8, 0.7),
    "normal": ("Обычный · бот", 1.0, 1.0),
    "hard": ("Сложный · бот", 1.25, 1.25),
    "expert": ("Эксперт · бот", 1.55, 1.55),
}
WEEKLY = (
    ("taps", "Сделать 500 касаний", "manual_taps", 500, 100, 1),
    ("care", "Угостить роботов 30 раз", "feedings", 30, 180, 2),
    ("battles", "Победить 10 ботов", "arena_wins", 10, 280, 3),
    ("projects", "Завершить 12 заказов", "jobs_done", 12, 250, 3),
    ("armory", "Улучшить оружие 3 раза", "weapon_upgrades", 3, 200, 2),
)


def clean_int(value, maximum=1_000_000):
    return (
        min(maximum, max(0, value))
        if isinstance(value, int) and not isinstance(value, bool)
        else 0
    )


def restore(state, data):
    for field in ("weapon_upgrades", "rare_parts"):
        setattr(state, field, clean_int(data.get(field)))
    raw = data.get("weapon_levels", {})
    state.weapon_levels = (
        {
            key: min(10, max(1, clean_int(value, 10)))
            for key, value in raw.items()
            if key in BY_ID and clean_int(value)
        }
        if isinstance(raw, dict)
        else {}
    )
    raw = data.get("loadouts", {})
    if isinstance(raw, dict):
        state.loadouts = {
            robot: list(
                dict.fromkeys(
                    weapon
                    for weapon in weapons
                    if isinstance(weapon, str) and weapon in state.weapon_levels
                )
            )[:2]
            for robot, weapons in raw.items()
            if robot in state.robot_levels and isinstance(weapons, list)
        }
    state.arena_difficulty = (
        data.get("arena_difficulty", "normal")
        if isinstance(data.get("arena_difficulty", "normal"), str)
        and data.get("arena_difficulty", "normal") in DIFFICULTIES
        else "normal"
    )
    for name in ("weekly", "tournament"):
        raw = data.get(name, {})
        if isinstance(raw, dict) and raw:
            allowed = {"period", "best", "wins", "active", "claimed", "base"}
            clean = {key: value for key, value in raw.items() if key in allowed}
            clean["period"] = clean_int(raw.get("period"))
            clean["wins"] = clean_int(raw.get("wins"), 3)
            clean["best"] = clean_int(raw.get("best"), 3)
            clean["active"] = raw.get("active") is True
            clean["claimed"] = (
                [
                    key
                    for key in raw.get("claimed", [])
                    if isinstance(key, str)
                    and key in {row[0] for row in WEEKLY} | {"cup"}
                ][:6]
                if isinstance(raw.get("claimed", []), list)
                else []
            )
            clean["base"] = (
                {
                    attr: clean_int(
                        raw.get("base", {}).get(attr), 9_000_000_000_000_000
                    )
                    for _, _, attr, *_ in WEEKLY
                }
                if isinstance(raw.get("base"), dict)
                else {}
            )
            if name == "weekly":
                for key in ("wins", "best", "active"):
                    clean.pop(key, None)
            else:
                clean.pop("base", None)
            setattr(state, name, clean)


def refresh_week(state, now):
    period = int((max(0, now) + 259200) // 604800)
    if state.weekly.get("period") != period or not state.weekly.get("base"):
        state.weekly = {
            "period": period,
            "claimed": [],
            "base": {row[2]: getattr(state, row[2]) for row in WEEKLY},
        }
    if state.tournament.get("period") != period:
        state.tournament = {
            "period": period,
            "wins": 0,
            "best": 0,
            "claimed": [],
            "active": False,
        }


def upgrade_cost(weapon, level):
    return weapon.price * (level + 1) * (level + 2) // 3


def perform_armory(state, name, args, now):
    from gameplay import ActionResult

    if name not in {
        "weapon_buy",
        "weapon_upgrade",
        "weapon_equip",
        "weapon_remove",
        "difficulty",
        "weekly_claim",
        "tournament_start",
    }:
        return None
    refresh_week(state, now)
    if name == "difficulty":
        if args and args[0] in DIFFICULTIES and state.battle.get("result") != "active":
            state.arena_difficulty = args[0]
            return ActionResult(True, DIFFICULTIES[args[0]][0])
        return ActionResult(False, "Заверши текущий бой")
    if name == "tournament_start":
        if not state.robot_levels or state.battle.get("result") == "active":
            return ActionResult(False, "Сначала открой робота и заверши текущий бой")
        if state.tournament.get("active"):
            return ActionResult(False, "Турнир уже начат")
        state.tournament.update(active=True, wins=0)
        return ActionResult(
            True, "Кубок ботов: выиграй три боя подряд. Поражение завершает серию"
        )
    if name == "weekly_claim":
        if not args:
            return ActionResult(False)
        spec = next((row for row in WEEKLY if row[0] == args[0]), None)
        if (
            spec is None
            or args[0] in state.weekly.get("claimed", [])
            or getattr(state, spec[2]) - state.weekly["base"].get(spec[2], 0) < spec[3]
        ):
            return ActionResult(False, "Награда уже получена или цель ещё не выполнена")
        state.weekly.setdefault("claimed", []).append(spec[0])
        state.earn(spec[4], 8)
        state.rare_parts += spec[5]
        return ActionResult(True, f"+{spec[4]} золота, +{spec[5]} редких деталей")
    identity = args[0] if args else ""
    weapon = BY_ID.get(identity)
    if weapon is None:
        return ActionResult(False, "Неизвестное оружие")
    if name in {"weapon_equip", "weapon_remove"}:
        robot = args[1] if len(args) > 1 else state.active_robot
        if robot not in state.robot_levels or state.battle.get("result") == "active":
            return ActionResult(False, "Сменить снаряжение можно между боями")
        equipped = state.loadouts.setdefault(robot, [])
        if name == "weapon_remove":
            if identity in equipped:
                equipped.remove(identity)
            return ActionResult(True, "Вернул штатное оснащение")
        if identity not in state.weapon_levels:
            return ActionResult(False, "Сначала купи это оружие")
        from robot_designs import base_stats

        if weapon.mass > base_stats(robot)["capacity"]:
            return ActionResult(False, "Слишком тяжёлое оружие для этой конструкции")
        if identity not in equipped:
            if len(equipped) >= 2:
                return ActionResult(False, "Два слота заняты. Сними один модуль")
            equipped.append(identity)
        return ActionResult(
            True, f"Установлено: {weapon.title}. Два модуля чередуются по ходам"
        )
    level = state.weapon_levels.get(identity, 0)
    if name == "weapon_buy" and level:
        return ActionResult(False, "Оружие уже в инвентаре")
    if name == "weapon_upgrade" and (not level or level >= 10):
        return ActionResult(False, "Сначала купи оружие; максимум 10 уровней")
    price = weapon.price if not level else upgrade_cost(weapon, level)
    rare = 1 + level // 3 if level >= 4 else 0
    if state.level < weapon.unlock or state.coin < price or state.rare_parts < rare:
        return ActionResult(
            False,
            f"Нужно: уровень {weapon.unlock}, {price} золота, {rare} редких деталей",
        )
    state.coin -= price
    state.rare_parts -= rare
    state.weapon_levels[identity] = level + 1
    state.weapon_upgrades += int(level > 0)
    return ActionResult(True, f"{weapon.title}: уровень {level + 1}")


def equip_battle(state, battle):
    equipped = state.loadouts.get(battle["robot_id"], [])
    battle["equipment"] = [
        {"id": weapon, "level": state.weapon_levels[weapon]}
        for weapon in equipped
        if weapon in state.weapon_levels and weapon in BY_ID
    ][:2]
    difficulty = state.arena_difficulty
    multiplier, reward = DIFFICULTIES[difficulty][1:]
    battle["difficulty"] = difficulty
    for key in ("enemy_hp", "enemy_max_hp", "enemy_attack"):
        battle[key] = max(1, round(battle[key] * multiplier))
    battle["reward"] = max(1, round(battle["reward"] * reward))
    battle["mode"] = "tournament" if state.tournament.get("active") else "route"
    from collection_progress import ensure
    from equipment_catalog import effective_stats

    data = ensure(state)
    stats = effective_stats(state, battle["robot_id"])
    # Legacy battles retain their base arithmetic. Individual equipment adds
    # bounded bonuses; normalized online matches do not call this function.
    from robot_designs import base_stats

    baseline = base_stats(battle["robot_id"], state.robot_levels[battle["robot_id"]])
    health_bonus = max(0, stats["health"] - baseline["health"])
    battle["player_hp"] += health_bonus
    battle["player_max_hp"] += health_bonus
    battle["player_attack"] += max(0, stats["attack"] - baseline["attack"])
    if difficulty == "training":
        # Practise counters against a comparable chassis even on a late route.
        battle["enemy_hp"] = battle["enemy_max_hp"] = min(
            battle["enemy_max_hp"], max(65, round(battle["player_max_hp"] * 1.15))
        )
        battle["enemy_attack"] = min(battle["enemy_attack"], max(8, round(battle["player_attack"] * .9)))
    battle.update(
        defense=stats["defense"],
        speed=stats["speed"],
        crit=stats["crit"],
        crit_damage=stats["crit_damage"],
        max_battery=stats["energy"],
        regen=stats["regen"],
        super_charge=0,
        weapon_cooldown=0,
        emp_turns=0,
        slow_turns=0,
        skill_level=data["skills"].get(battle["robot_id"], 1),
        insulated="insulator"
        in data["module_loadouts"].get(battle["robot_id"], {}).values(),
    )
    from combat_rules import prepare_local

    prepare_local(state, battle)


def equipped_weapon(battle):
    gear = battle.get("equipment", [])
    if not gear:
        return None, 0
    item = gear[battle.get("turn", 0) % len(gear)]
    return BY_ID.get(item["id"]), item["level"]


def equipment_effect(battle, action, attack):
    weapon, level = equipped_weapon(battle)
    if not weapon:
        return attack, False, False
    # Effective bonus is capped; upgrading never replaces the robot's base stats.
    bonus = min(18, round(weapon.damage * weapon.speed / 9) + level)
    if action == "attack":
        bonus += min(4, weapon.reach // 3) if battle.get("precision") else 0
        if weapon.id == "machinegun":
            battle["heat"] = min(3, battle.get("heat", 0) + 1)
        if weapon.id == "flame":
            bonus += min(5, battle.get("heat", 0) * 2)
    if weapon.id == "rocket" and battle.get("precision"):
        bonus += 5
    pierce = weapon.id in {"laser", "ion", "drill"} or (
        weapon.id == "sniper" and bool(battle.get("precision"))
    )
    return attack + bonus, pierce, weapon.id == "shield"
