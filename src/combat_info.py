"""Read-only ability cards derived from the same rules used to commit a turn."""

from copy import deepcopy

import flet as ft

from armory import BY_ID
from combat_rules import action_cost, action_error, resolve_action
from robot_abilities import ABILITIES
from ui_shared import GOLD, INK, MUTED, button_style

ACTION_TITLES = {
    "attack": "Удар", "guard": "Щит", "special": "Навык", "dodge": "Уворот",
    "charge": "Фокус", "quick": "Быстрый удар", "pierce": "Пробитие",
    "burst": "Серия", "emp": "EMP · импульс", "ultimate": "Супер",
}
ACTION_ICONS = {
    "attack": ft.Icons.FLASH_ON_ROUNDED, "guard": ft.Icons.SHIELD_ROUNDED,
    "special": ft.Icons.AUTO_FIX_HIGH_ROUNDED, "dodge": ft.Icons.DOUBLE_ARROW_ROUNDED,
    "charge": ft.Icons.BATTERY_CHARGING_FULL_ROUNDED, "quick": ft.Icons.SPEED_ROUNDED,
    "pierce": ft.Icons.GPS_FIXED_ROUNDED, "burst": ft.Icons.GRAIN_ROUNDED,
    "emp": ft.Icons.SENSORS_OFF_ROUNDED, "ultimate": ft.Icons.AUTO_AWESOME_ROUNDED,
}
TACTICS = {
    "attack": ("+1 фокус; установленное оружие", "Щит уменьшает урон; нагрев ослабляет удар"),
    "quick": ("+1 фокус; прерывает подготовку", "Урон ниже обычной атаки; нагревает корпус"),
    "pierce": ("Разрушает щит и игнорирует броню", "4 энергии; модуль перезаряжается 2 хода"),
    "burst": ("Три попадания против одиночного уворота", "Расходует 4 энергии и повышает нагрев"),
    "emp": ("Электромагнитный импульс отключает щит на 2 хода", "Небольшой урон; изоляция сокращает эффект до 1 хода"),
    "guard": ("Снижает урон на 72%; +1 фокус, охлаждение", "Пробитие разрушает стойку; EMP отключает щит"),
    "dodge": ("Избегает одного попадания", "Серия сохраняет остальные попадания; захват запрещает уворот"),
    "charge": ("+2 фокуса; охлаждение; следующий удар сильнее на 20%", "Подготовка повышает входящий урон на 25%; быстрый удар её прерывает"),
}


def action_info(actor, action, target=None, *, blocked=""):
    """No player state, RNG state, energy or inventory is modified by a preview."""
    cost = action_cost(actor, action)
    reason = blocked or action_error(actor, action)
    cooldown = 3 if action in {"special", "dodge"} else 2 if action in {"pierce", "burst", "emp"} else 0
    strength, weakness = TACTICS.get(action, (ABILITIES[actor["robot"]].effect, "Учитывай щит, уворот и запас энергии"))
    if action in {"guard", "charge"}:
        recovery = min(actor["max_energy"] - actor["energy"], actor["regen"] + (3 if action == "charge" else 0))
        effect = f"+{recovery} энергии · +{min(3 - actor['focus'], 2 if action == 'charge' else 1)} фокуса"
        if actor.get("stun"):
            effect = "Пропустить оглушение · без восстановления"
    elif action == "dodge":
        effect = "Уворот от 1 попадания"
    elif target:
        sample, victim = deepcopy(actor), deepcopy(target)
        sample.update(energy=max(cost, sample["energy"]), focus=3, cooldown=0,
                      dodge_cooldown=0, weapon_cooldown=0, super_charge=100, crit=0, stun=0, root=0)
        event = resolve_action(sample, victim, action)
        effect = f"≈{event.get('damage', 0)} урона"
        if event.get("heal"):
            effect += f" · +{event['heal']} HP"
    else:
        effect = strength
    requirements = f"{cost} энергии"
    if action == "special":
        requirements += ", 2 фокуса, готовый навык"
    if action == "ultimate":
        requirements += ", 100% суперзаряда"
    cycle = "Накопи 100% заряда" if action == "ultimate" else f"Перезарядка: {cooldown} хода" if cooldown else "Доступно каждый ход"
    return {
        "title": ACTION_TITLES[action], "cost": cost, "effect": effect,
        "reason": reason, "ready": not reason, "cooldown": cooldown,
        "cycle": cycle,
        "detail": f"{ACTION_TITLES[action]} · {BY_ID[actor['weapon']].title}\n{effect}\n"
                  f"Требования: {requirements}. {cycle}.\n"
                  f"{strength}.\n{weakness}." + (f"\nСейчас: {reason}" if reason else ""),
    }


def action_control(actor, action, on_click, accent, *, target=None, blocked="", key=None):
    info = action_info(actor, action, target, blocked=blocked)
    ready = info["ready"]
    super_ready = action == "ultimate" and ready
    style = button_style(GOLD if super_ready else accent, secondary=action in {"guard", "charge"})
    style.bgcolor = {
        ft.ControlState.DISABLED: "#18263C",
        ft.ControlState.DEFAULT: GOLD if super_ready else "#25466B" if action in {"guard", "charge"} else "#284E80",
    }
    style.side = {
        ft.ControlState.DISABLED: ft.BorderSide(1, "#3A4B64"),
        ft.ControlState.DEFAULT: ft.BorderSide(2 if super_ready else 1, GOLD if super_ready else "#75A8DA"),
    }
    style.padding = ft.Padding.symmetric(horizontal=9, vertical=10)
    color = "#14243D" if super_ready else INK if ready else "#899AB2"
    return ft.Container(
        ft.Column([
            ft.Button(
                ft.Column([
                    ft.Row([
                        ft.Icon(ACTION_ICONS[action], size=21, color=color),
                        ft.Text(info["title"], size=13, color=color, weight=ft.FontWeight.BOLD, expand=True),
                        ft.Row([
                            ft.Text(str(info["cost"]), size=12, color=color),
                            ft.Icon(ft.Icons.BOLT_ROUNDED, size=15, color=color),
                        ], spacing=0, tight=True),
                    ], spacing=5),
                    ft.Text(info["effect"], size=11, color=color, max_lines=2),
                    ft.Text(info["cycle"], size=11, color=color),
                ], spacing=5, horizontal_alignment=ft.CrossAxisAlignment.START, tight=True),
                on_click=on_click, disabled=not ready, tooltip=info["detail"],
                style=style, width=float("inf"), key=key or f"arena-{action}",
            ),
            *([ft.Text(info["reason"], size=11, color="#D4B2A8", max_lines=3)]
              if info["reason"] and blocked not in {"Роботы выполняют ход…", "Бой завершён", "Ход соперника"} else []),
        ], spacing=4, tight=True),
        col=6,
        shadow=ft.BoxShadow(blur_radius=15, color="#66FFD05A") if super_ready else None,
    )
