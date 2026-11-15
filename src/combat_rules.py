"""Shared deterministic counter system for local bots and authoritative PvP.

An actor is a plain validated dictionary. resolve_action is transactional: an
invalid action changes neither fighter. Animations consume the returned event.
"""

from copy import deepcopy
from armory import BY_ID
from robot_designs import DESIGNS

ATTACKS = {"attack", "quick", "pierce", "burst", "emp", "special", "ultimate"}
ACTIONS = ATTACKS | {"guard", "dodge", "charge"}
INTERACTIONS = (
    ("Щит", "Обычный удар", "Снижает урон на 72%; EMP временно отключает щит"),
    ("Пробитие", "Щит", "Разрушает стойку, но расходует 4 энергии"),
    ("Быстрая атака", "Подготовка", "Слабее обычного удара; прерывает подготовку"),
    ("Уворот", "Сильная одиночная атака", "Избегает одного попадания"),
    ("Серия", "Уворот", "Уворот спасает только от первого из трёх попаданий"),
    ("EMP", "Энергетический щит", "Отключает на 2 хода, небольшой прямой урон"),
    ("Фокус", "Энергия", "Восстанавливает энергию, но входящий урон выше на 25%"),
)
SUPER_EFFECTS = {
    "spark": ("burst", 1.7),
    "volt": ("stun", 1.2),
    "flora": ("heal", 0.7),
    "forge": ("shred", 1.4),
    "nova": ("pierce", 1.8),
    "glacier": ("slow", 1.15),
    "aegis": ("fortify", 1.1),
    "solar": ("renew", 1.5),
    "titan": ("reflect", 1.1),
    "arachna": ("trap", 1.15),
    "phantom": ("evade", 1.4),
    "falcon": ("aerial", 1.4),
    "cyclops": ("critical", 1.65),
    "medic": ("restore", 0.6),
    "atlas": ("shatter", 1.55),
    "cerberus": ("rush", 1.65),
    "cobra": ("root", 1.3),
    "phoenix": ("rebirth", 1.3),
    "driller": ("drill", 1.5),
    "ninja": ("counter", 1.4),
    "specter": ("decoy", 1.2),
    "magneto": ("drain", 1.3),
    "rocketeer": ("salvo", 1.7),
    "octopus": ("repair_swarm", 1.1),
    "scarab": ("carapace", 1.1),
    "orbit": ("wave", 1.5),
    "guardian": ("aegis", 1.0),
    "goliath": ("siege", 1.85),
    "chronos": ("time", 1.05),
    "omega": ("convert", 1.45),
    "storm": ("storm", 1.35),
    "chameleon": ("adapt", 1.25),
}


def fighter(
    robot,
    weapon="plasma",
    *,
    health=120,
    attack=18,
    defense=6,
    speed=100,
    energy=12,
    regen=3,
    crit=8,
    skill=1,
):
    if weapon not in BY_ID:
        weapon = "plasma"
    return dict(
        robot=robot,
        weapon=weapon,
        hp=health,
        max_hp=health,
        attack=attack,
        defense=defense,
        speed=speed,
        energy=energy,
        max_energy=energy,
        regen=regen,
        crit=crit,
        skill=skill,
        focus=2,
        heat=0,
        super_charge=0,
        cooldown=0,
        weapon_cooldown=0,
        dodge_cooldown=0,
        guard=False,
        dodge=False,
        preparing=False,
        emp=0,
        slow=0,
        stun=0,
        root=0,
        burn=0,
        reflect=0,
        adapt=False,
        precision=False,
        form=0,
        turns=0,
        insulated=False,
    )


def allowed(actor):
    weapon = BY_ID[actor["weapon"]]
    choices = {"attack", "quick", "guard", "dodge", "charge", "special", "ultimate"}
    if weapon.id in {"sniper", "laser", "ion", "drill", "sword", "fist", "grenade"}:
        choices.add("pierce")
    if weapon.id in {"machinegun", "blaster", "disc", "rocket", "drone"}:
        choices.add("burst")
    if weapon.id == "emp" or actor["robot"] in {"volt", "storm", "chronos"}:
        choices.add("emp")
    return choices


def action_error(actor, action):
    if action not in allowed(actor):
        return "Это действие не поддерживает выбранное оружие"
    weapon = BY_ID[actor["weapon"]]
    cost = (
        weapon.energy
        if action == "attack"
        else 2
        if action in {"quick", "dodge"}
        else 4
        if action in {"pierce", "burst", "emp", "ultimate"}
        else min(7, weapon.energy + 1)
        if action == "special"
        else 0
    )
    if actor["energy"] < cost:
        return "Не хватает энергии. Используй фокус или защиту"
    if action == "special" and (actor["cooldown"] or actor["focus"] < 2):
        return "Нужны 2 фокуса и готовый навык"
    if action == "ultimate" and actor["super_charge"] < 100:
        return "Суперспособность ещё не заряжена"
    if action in {"pierce", "burst", "emp"} and actor["weapon_cooldown"]:
        return "Боевой модуль перезаряжается"
    if action == "dodge" and (actor["dodge_cooldown"] or actor["root"]):
        return "Уворот недоступен: перезарядка или захват"
    return ""


def resolve_action(actor, target, action, *, seed=0):
    """Resolve one human/server turn; bots use the same resolver for the reply."""
    error = action_error(actor, action)
    if error:
        return {"ok": False, "error": error}
    a, b = deepcopy(actor), deepcopy(target)
    weapon = BY_ID[a["weapon"]]
    event = dict(
        ok=True,
        action=action,
        weapon=weapon.id,
        damage=0,
        heal=0,
        critical=False,
        interrupted=False,
        dodged=False,
        hits=0,
        shield_broken=False,
    )
    # Status durations count the affected fighter's own turns.
    for key in ("cooldown", "weapon_cooldown", "dodge_cooldown", "emp", "slow", "root"):
        a[key] = max(0, a.get(key, 0) - 1)
    a["guard"] = a["dodge"] = a["preparing"] = False
    if a.get("stun"):
        a["stun"] -= 1
        action = "stunned"
        event.update(action=action, interrupted=True)
    if a.get("burn"):
        a["hp"] = max(1, a["hp"] - 4)
        a["burn"] -= 1
    if action == "guard":
        a["guard"] = not bool(a["emp"])
        a["energy"] = min(a["max_energy"], a["energy"] + a["regen"])
        a["focus"] = min(3, a["focus"] + 1)
        a["heat"] = 0
    elif action == "charge":
        a["energy"] = min(a["max_energy"], a["energy"] + a["regen"] + 3)
        a["focus"] = min(3, a["focus"] + 2)
        a["heat"] = 0
        a["preparing"] = True
        a["precision"] = True
    elif action == "dodge":
        a["energy"] -= 2
        a["focus"] = max(0, a["focus"] - 1)
        a["dodge"] = True
        a["dodge_cooldown"] = 3
        a["heat"] = 0
    elif action in ATTACKS:
        cost = (
            weapon.energy
            if action == "attack"
            else 2
            if action == "quick"
            else min(7, weapon.energy + 1)
            if action == "special"
            else 4
        )
        a["energy"] -= cost
        a["heat"] = (
            min(3, a["heat"] + 1) if action in {"attack", "quick", "burst"} else 0
        )
        mult = {
            "attack": 1,
            "quick": 0.62,
            "pierce": 1.05,
            "burst": 1.2,
            "emp": 0.35,
            "special": 1.15,
            "ultimate": 1.5,
        }[action]
        if action == "quick":
            mult += max(-0.15, min(0.15, (a["speed"] - 100) * 0.003))
        hits = 3 if action == "burst" else 1
        piercing = action == "pierce" or weapon.id in {"ion", "laser", "drill"}
        effect = ""
        if action in {"special", "ultimate"}:
            effect, power = SUPER_EFFECTS[a["robot"]]
            mult = (
                power
                * (0.72 if action == "special" else 1)
                * (1 + 0.04 * (a["skill"] - 1))
            )
            if action == "special":
                a["focus"] -= 2
                a["cooldown"] = 3
            else:
                a["super_charge"] = 0
                a["cooldown"] = max(a["cooldown"], 2)
            if effect in {"burst", "rush", "salvo", "storm"}:
                hits = 3
            if effect in {"pierce", "shatter", "drill", "critical", "siege"}:
                piercing = True
            if effect in {
                "heal",
                "restore",
                "renew",
                "fortify",
                "rebirth",
                "repair_swarm",
            }:
                fraction = {
                    "heal": 0.28,
                    "restore": 0.35,
                    "renew": 0.16,
                    "fortify": 0.12,
                    "rebirth": 0.22,
                    "repair_swarm": 0.18,
                }[effect]
                healed = min(a["max_hp"] - a["hp"], round(a["max_hp"] * fraction))
                a["hp"] += healed
                event["heal"] = healed
            if effect in {"stun", "trap", "time"}:
                b["stun"] = min(1, b["stun"] + 1)
            if effect in {"slow", "time"}:
                b["slow"] = 2
                b["energy"] = max(0, b["energy"] - 2)
            if effect in {"fortify", "aegis", "reflect", "carapace", "wave"}:
                a["guard"] = not bool(a["emp"])
            if effect in {"reflect", "carapace"}:
                a["reflect"] = 1
            if effect in {"shred", "shatter", "drill", "siege"}:
                b["defense"] = max(0, b["defense"] - 3)
            if effect in {"evade", "aerial", "counter", "decoy"}:
                a["dodge"] = not bool(a["root"])
            if effect == "root":
                b["root"] = 2
            if effect == "rebirth":
                b["burn"] = 2
            if effect == "drain":
                b["energy"] = max(0, b["energy"] - 3)
                a["energy"] = min(a["max_energy"], a["energy"] + 2)
            if effect == "restore":
                a["energy"] = min(a["max_energy"], a["energy"] + 3)
                a["heat"] = 0
            if effect == "repair_swarm":
                a["cooldown"] = max(0, a["cooldown"] - 1)
            if effect == "convert":
                a["form"] = 1 - a["form"]
                a["guard"] = a["form"] == 1
                mult += 0.2 if not a["form"] else 0
            if effect == "adapt":
                a["adapt"] = True
        if action == "emp" or effect == "storm":
            b["emp"] = 1 if b.get("insulated") else 2
            b["guard"] = False
            event["shield_broken"] = True
        if action == "quick" and b.get("preparing"):
            b["stun"] = 1
            b["preparing"] = False
            b["precision"] = False
            event["interrupted"] = True
        if action == "pierce":
            b["guard"] = False
            event["shield_broken"] = True
        if action in {"pierce", "emp", "burst"}:
            a["weapon_cooldown"] = 2
        base = a["attack"] + min(10, round(weapon.damage * weapon.speed / 8))
        if a["heat"] >= 3:
            mult *= 0.58
        if a["slow"]:
            mult *= 0.85
        if a.get("precision"):
            mult *= 1.2
            a["precision"] = False
        if b.get("preparing"):
            mult *= 1.25
        critical = (
            effect == "critical"
            or (seed * 37 + a["turns"] * 23 + len(a["robot"]) * 11) % 100 < a["crit"]
        )
        if critical:
            mult *= 1.5
            event["critical"] = True
        per_hit = max(
            1, round(base * mult / hits) - (0 if piercing else b["defense"] // 2)
        )
        damage = per_hit * hits
        if b["dodge"]:
            damage = per_hit * max(0, hits - 1)
            event["dodged"] = hits == 1
            b["dodge"] = False
        if b["guard"] and not piercing and not b["emp"]:
            damage = round(damage * 0.28)
        if b.get("adapt"):
            damage = round(damage * 0.7)
            b["adapt"] = False
        if weapon.id == "repair":
            healed = min(10, a["max_hp"] - a["hp"])
            a["hp"] += healed
            event["heal"] += healed
            damage = round(damage * 0.35)
        if weapon.id == "cryo":
            b["slow"] = max(b["slow"], 1)
        if weapon.id == "magnetic" and action in {"pierce", "special", "ultimate"}:
            b["energy"] = max(0, b["energy"] - 1)
        if weapon.id == "flame" and action in {"attack", "burst"}:
            b["burn"] = 1
        b["hp"] = max(0, b["hp"] - damage)
        event.update(damage=damage, hits=hits, effect=effect)
        if b.get("reflect") and damage:
            a["hp"] = max(1, a["hp"] - round(damage * 0.25))
            b["reflect"] = 0
        a["focus"] = (
            min(3, a["focus"] + 1) if action in {"attack", "quick"} else a["focus"]
        )
        b["super_charge"] = min(100, b["super_charge"] + (12 if damage else 5))
    a["turns"] += 1
    if action != "ultimate":
        a["super_charge"] = min(
            100, a["super_charge"] + (18 if action in ATTACKS else 16)
        )
    actor.clear()
    actor.update(a)
    target.clear()
    target.update(b)
    return event


def prepare_local(state, battle):
    from equipment_catalog import effective_stats

    stats = effective_stats(state, battle["robot_id"])
    data = state.collection
    weapon = (
        battle.get("equipment") or [{"id": DESIGNS[battle["robot_id"]]["weapon"]}]
    )[0]["id"]
    a = fighter(
        battle["robot_id"],
        weapon,
        health=battle["player_max_hp"],
        attack=battle["player_attack"],
        defense=stats["defense"],
        speed=stats["speed"],
        energy=stats["energy"],
        regen=stats["regen"],
        crit=stats["crit"],
        skill=data["skills"].get(battle["robot_id"], 1),
    )
    a["insulated"] = battle.get("insulated", False)
    b = fighter(
        battle["enemy_id"],
        DESIGNS[battle["enemy_id"]]["weapon"],
        health=battle["enemy_max_hp"],
        attack=battle["enemy_attack"],
        defense=min(12, 2 + battle["stage"] // 3),
        crit=4,
    )
    battle.update(
        rules_version=3,
        combatants={"a": a, "b": b},
        enemy_weapon=b["weapon"],
        enemy_action="",
    )


def current_actor(battle):
    """Project the next alternating mount before displaying or validating actions."""
    actor = deepcopy(battle["combatants"]["a"])
    gear = battle.get("equipment", [])
    if gear:
        actor["weapon"] = gear[battle["turn"] % len(gear)]["id"]
    return actor


def local_turn(battle, action, identity, expected_turn):
    from robot_arena import TurnResult, enemy_intent

    if (
        battle.get("id") != identity
        or battle.get("turn") != expected_turn
        or battle.get("result") != "active"
    ):
        return TurnResult(False, "Ход уже выполнен или бой завершён")
    trial = deepcopy(battle)
    a = current_actor(trial)
    trial["combatants"]["a"] = a
    b = trial["combatants"]["b"]
    intent = enemy_intent(trial)
    b["guard"] = intent == "guard" and not b["emp"]
    b["preparing"] = intent == "windup"
    boss_kind = (
        (trial["stage"] // 5) % 3 if trial.get("boss") and trial["stage"] >= 9 else -1
    )
    if boss_kind == 0 and intent == "guard":
        b["hp"] = min(b["max_hp"], b["hp"] + 8)
    event = resolve_action(a, b, action, seed=trial["id"] + trial["turn"])
    if not event["ok"]:
        return TurnResult(False, event["error"])
    reply = {"damage": 0, "heal": 0, "dodged": False, "interrupted": False}
    if b["hp"]:
        enemy_action = (
            "charge"
            if intent == "windup"
            else "guard"
            if intent == "guard"
            else "pierce"
            if intent in {"heavy", "pierce"} and "pierce" in allowed(b)
            else "burst"
            if intent == "pulse" and "burst" in allowed(b)
            else "special"
            if intent == "heavy"
            else "attack"
        )
        if action_error(b, enemy_action):
            enemy_action = "charge"
        reply = resolve_action(b, a, enemy_action, seed=trial["id"] + trial["turn"] + 7)
        if boss_kind == 1 and reply.get("damage"):
            repaired = min(7, reply["damage"] // 4, b["max_hp"] - b["hp"])
            b["hp"] += repaired
            reply["heal"] = reply.get("heal", 0) + repaired
        if boss_kind == 2 and intent == "pulse" and reply.get("damage"):
            extra = reply["damage"] * 115 // 100 - reply["damage"]
            a["hp"] = max(0, a["hp"] - extra)
            reply["damage"] += extra
    result = (
        "win"
        if not b["hp"]
        else "loss"
        if not a["hp"] or trial["turn"] >= 59
        else "active"
    )
    trial.update(
        player_hp=a["hp"],
        enemy_hp=b["hp"],
        last_damage=event["damage"],
        last_heal=event["heal"],
        last_enemy_heal=reply.get("heal", 0),
        last_incoming=reply.get("damage", 0),
        last_dodged=reply.get("dodged", False),
        last_stunned=reply.get("interrupted", False),
        last_counter=0,
        last_intent=intent,
        cooldown=a["cooldown"],
        focus=a["focus"],
        heat=a["heat"],
        battery=a["energy"],
        max_battery=a["max_energy"],
        dodge_cooldown=a["dodge_cooldown"],
        precision=int(a["precision"]),
        super_charge=a["super_charge"],
        weapon_cooldown=a["weapon_cooldown"],
        enemy_weapon=b["weapon"],
        enemy_action=enemy_action if b["hp"] else "",
        last_action=action,
        result=result,
    )
    lines = [
        f"{action}: {event['damage']} урона"
        + (" · Критический!" if event["critical"] else ""),
        f"Ответ: {reply.get('damage', 0)} урона",
    ]
    if event["interrupted"]:
        lines.append("Подготовка противника прервана")
    if event["shield_broken"]:
        lines.append("Защитная стойка отключена")
    if result != "active":
        lines.append(
            "Победа!" if result == "win" else "Поражение. Попробуй другой контрприём"
        )
    trial["log"] = (trial.get("log", []) + lines)[-7:]
    trial["turn"] += 1
    battle.clear()
    battle.update(trial)
    return TurnResult(True, lines[-1], result != "active")


def restore_fighter(raw):
    if (
        not isinstance(raw, dict)
        or not isinstance(raw.get("robot"), str)
        or not isinstance(raw.get("weapon"), str)
        or raw.get("robot") not in DESIGNS
        or raw.get("weapon") not in BY_ID
    ):
        return None
    clean = fighter(raw["robot"], raw["weapon"])
    for key, value in clean.items():
        if isinstance(value, bool):
            clean[key] = raw.get(key) is True
        elif isinstance(value, int):
            v = raw.get(key, value)
            clean[key] = (
                min(1000000, max(0, v))
                if isinstance(v, int) and not isinstance(v, bool)
                else value
            )
    clean["max_hp"] = max(1, clean["max_hp"])
    clean["hp"] = min(clean["hp"], clean["max_hp"])
    clean["max_energy"] = max(1, min(18, clean["max_energy"]))
    clean["energy"] = min(clean["energy"], clean["max_energy"])
    for key, maximum in {
        "cooldown": 3,
        "weapon_cooldown": 2,
        "dodge_cooldown": 3,
        "emp": 2,
        "slow": 2,
        "stun": 1,
        "root": 2,
        "burn": 2,
        "reflect": 1,
        "heat": 3,
        "focus": 3,
        "skill": 5,
        "super_charge": 100,
        "crit": 35,
    }.items():
        clean[key] = min(clean[key], maximum)
    return clean
