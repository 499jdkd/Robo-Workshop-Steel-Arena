"""Equipment inventory and weekly activities inside the existing game screens."""

import flet as ft

from armory import BY_ID, DIFFICULTIES, WEAPONS, WEEKLY, refresh_week, upgrade_cost
from robot_catalog import RARITIES, ROBOT_BY_ID
from ui_shared import INK, MUTED, button_style, card

ICONS = {
    "plasma": ft.Icons.FLASH_ON_ROUNDED,
    "sniper": ft.Icons.GPS_FIXED_ROUNDED,
    "rocket": ft.Icons.ROCKET_LAUNCH_ROUNDED,
    "laser": ft.Icons.FLARE_ROUNDED,
    "electric": ft.Icons.BOLT_ROUNDED,
    "machinegun": ft.Icons.GRAIN_ROUNDED,
    "sword": ft.Icons.AUTO_FIX_HIGH_ROUNDED,
    "shield": ft.Icons.SHIELD_ROUNDED,
    "flame": ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED,
    "drone": ft.Icons.FLIGHT_ROUNDED,
}


def armory_panel(session):
    state = session.state
    robot = state.active_robot
    gear = state.loadouts.get(robot, [])
    controls = [
        card(
            ft.Column(
                [
                    ft.Text("Арсенал", size=21, weight=ft.FontWeight.BOLD, color=INK),
                    ft.Text(
                        f"Редкие детали: {state.rare_parts} · Золото: {state.coin}",
                        color=MUTED,
                        size=12,
                    ),
                    ft.Text(
                        f"{ROBOT_BY_ID[robot].name if robot in ROBOT_BY_ID else 'Выбери робота'} · 2 слота",
                        color=state.accent,
                        size=13,
                    ),
                    ft.Text(
                        " + ".join(BY_ID[item].title for item in gear)
                        or "Штатное оружие робота",
                        color=INK,
                        size=12,
                    ),
                    ft.Text(
                        "Модули чередуются по ходам. Способность робота сохраняется. Снаряжение меняется между боями.",
                        color=MUTED,
                        size=11,
                    ),
                ],
                spacing=8,
            )
        ),
    ]
    for weapon in WEAPONS:
        level = state.weapon_levels.get(weapon.id, 0)
        equipped = weapon.id in gear
        color = RARITIES[weapon.rarity][1]

        async def buy(_, item=weapon.id, owned=level):
            session.act("weapon_upgrade" if owned else "weapon_buy", item)

        async def equip(_, item=weapon.id, installed=equipped):
            session.act("weapon_remove" if installed else "weapon_equip", item, robot)

        price = upgrade_cost(weapon, level) if level else weapon.price
        controls.append(
            card(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Container(
                                    ft.Icon(ICONS[weapon.id], size=30, color=color),
                                    padding=12,
                                    bgcolor="#F0F4FC",
                                    border_radius=14,
                                ),
                                ft.Column(
                                    [
                                        ft.Text(
                                            weapon.title,
                                            color=INK,
                                            size=15,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        ft.Text(
                                            f"{RARITIES[weapon.rarity][0]} · {f'{level} / 10 ур.' if level else f'Доступ с ур. {weapon.unlock}'}",
                                            color=color,
                                            size=11,
                                        ),
                                    ],
                                    expand=True,
                                    spacing=4,
                                ),
                            ],
                            spacing=10,
                        ),
                        ft.Text(
                            f"Урон {weapon.damage + level * 2} · Скорость {weapon.speed}/с · Дальность {weapon.reach} · Энергия {weapon.energy}",
                            color=MUTED,
                            size=11,
                        ),
                        ft.Text(weapon.ability, color=MUTED, size=12),
                        ft.Text(
                            f"Следующее улучшение: {price} золота"
                            + (
                                f" + {1 + level // 3} редких деталей"
                                if level >= 4
                                else ""
                            ),
                            color=MUTED,
                            size=10,
                        ),
                        ft.Row(
                            [
                                ft.Button(
                                    "Макс. уровень"
                                    if level >= 10
                                    else ("Улучшить" if level else "Купить"),
                                    key=f"weapon-buy-{weapon.id}",
                                    on_click=buy,
                                    disabled=level >= 10
                                    or state.coin < price
                                    or state.level < weapon.unlock,
                                    style=button_style(state.accent),
                                    expand=True,
                                ),
                                *(
                                    [
                                        ft.Button(
                                            "Снять" if equipped else "Установить",
                                            key=f"weapon-equip-{weapon.id}",
                                            on_click=equip,
                                            disabled=not robot
                                            or state.battle.get("result") == "active",
                                            style=button_style(
                                                state.accent, secondary=True
                                            ),
                                            expand=True,
                                        )
                                    ]
                                    if level
                                    else []
                                ),
                            ],
                            spacing=8,
                        ),
                    ],
                    spacing=9,
                )
            )
        )
    return controls


def weekly_panel(session):
    state = session.state
    refresh_week(state, session.clock())
    rows = [
        ft.Row(
            [
                ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, color=state.accent),
                ft.Text("Цели недели", color=INK, weight=ft.FontWeight.BOLD, size=17),
            ],
            spacing=9,
        )
    ]
    for key, title, attr, target, gold, rare in WEEKLY:
        progress = max(0, getattr(state, attr) - state.weekly["base"].get(attr, 0))
        claimed = key in state.weekly.get("claimed", [])

        async def claim(_, identity=key):
            session.act("weekly_claim", identity)

        rows.extend(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(title, size=12, color=INK),
                                ft.Text(
                                    f"{min(target, progress)}/{target} · {gold} золота + {rare} редких деталей",
                                    size=10,
                                    color=MUTED,
                                ),
                            ],
                            expand=True,
                            spacing=4,
                        ),
                        ft.IconButton(
                            ft.Icons.CHECK_CIRCLE_ROUNDED
                            if claimed
                            else ft.Icons.CARD_GIFTCARD_ROUNDED,
                            key=f"weekly-{key}",
                            on_click=claim,
                            disabled=claimed or progress < target,
                            icon_color=state.accent,
                        ),
                    ],
                    spacing=6,
                ),
                ft.ProgressBar(
                    value=min(1, progress / target),
                    color=state.accent,
                    bgcolor="#E7ECF7",
                    height=4,
                    border_radius=5,
                ),
            ]
        )
    return card(ft.Column(rows, spacing=9))


def arena_options(session):
    state = session.state
    refresh_week(state, session.clock())
    choices = []
    for key, (title, _strength, _reward) in DIFFICULTIES.items():

        async def choose(_, identity=key):
            session.act("difficulty", identity)

        choices.append(
            ft.Button(
                title,
                key=f"difficulty-{key}",
                on_click=choose,
                style=button_style(
                    state.accent, secondary=state.arena_difficulty != key
                ),
                col={"xs": 6, "sm": 3},
            )
        )

    async def cup(_):
        session.act("tournament_start")

    return card(
        ft.Column(
            [
                ft.Text(
                    "Тактические бои с ботами",
                    color=INK,
                    size=16,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.ResponsiveRow(choices, spacing=6, run_spacing=7),
                ft.Text(
                    "Чем выше сложность, тем больше здоровье, урон и награда. Это компьютерные соперники.",
                    size=11,
                    color=MUTED,
                ),
                ft.Divider(height=8),
                ft.Text(
                    f"Кубок ботов · серия {state.tournament.get('wins', 0)}/3 · рекорд {state.tournament.get('best', 0)}/3",
                    size=13,
                    color=INK,
                ),
                ft.Text(
                    "Три победы подряд. Награда недели: 350 золота и 4 редких детали. Одна награда за неделю.",
                    color=MUTED,
                    size=11,
                ),
                ft.Button(
                    "Кубок начат: следующий бой — турнирный"
                    if state.tournament.get("active")
                    else "Начать кубок ботов",
                    on_click=cup,
                    disabled=state.tournament.get("active", False),
                    style=button_style(state.accent, secondary=True),
                ),
            ],
            spacing=9,
        )
    )
