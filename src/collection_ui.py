"""The collection grid and full robot profiles inside the main Flet application."""

import flet as ft

from armory import BY_ID, WEAPONS, upgrade_cost
from collection_progress import ensure
from display_mode import set_scene_focus
from equipment_catalog import MODULES, MODULE_BY_ID, SLOTS, effective_stats, module_cost
from game_animation import animated_scene
from game_ui import game_button, resource_hud, section_title, stat_chip, tabs
from gameplay import compact, feeding_target
from robot_catalog import MAX_ROBOT_LEVEL, RARITIES, ROBOT_BY_ID, ROBOTS, training_price
from robot_designs import CLASSES, DESIGNS, RARITY_FRAGMENTS, STAR_COSTS
from ui_shared import (
    GOLD,
    GREEN,
    INK,
    MUTED,
    button_style,
    card,
    notice,
    tint,
    use_game,
)

CLASS_ICONS = {
    "tank": ft.Icons.SHIELD_ROUNDED,
    "striker": ft.Icons.GPS_FIXED_ROUNDED,
    "support": ft.Icons.ADD_CIRCLE_ROUNDED,
    "scout": ft.Icons.FLIGHT_ROUNDED,
    "special": ft.Icons.AUTO_AWESOME_ROUNDED,
}


def stars(rank, size=11):
    return ft.Row(
        [
            ft.Icon(
                ft.Icons.STAR_ROUNDED if n < rank else ft.Icons.STAR_OUTLINE_ROUNDED,
                size=size,
                color=GOLD if n < rank else MUTED,
            )
            for n in range(5)
        ],
        spacing=0,
        tight=True,
    )


def power(state, identity):
    stats = effective_stats(state, identity)
    return (
        stats["health"]
        + stats["attack"] * 8
        + stats["defense"] * 5
        + stats["speed"] // 3
    )


def robot_tile(session, robot):
    state = session.state
    data = ensure(state)
    owned = robot.id in state.robot_levels
    design = DESIGNS[robot.id]
    color = RARITIES[robot.rarity][1]
    level = state.robot_levels.get(robot.id, 0)
    rank = data["stars"].get(robot.id, 1)
    fragments = data["fragments"].get(robot.id, 0)
    cost = RARITY_FRAGMENTS[robot.rarity]
    ready = (owned and rank < 5 and fragments >= STAR_COSTS[rank - 1]) or (
        not owned and fragments >= cost
    )

    async def open_robot(_):
        session.robot_detail = robot.id
        session.robot_detail_return = ""
        session.notify()

    return ft.Container(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(CLASS_ICONS[design["class"]], size=15, color=INK),
                        ft.Icon(
                            ft.Icons.UPGRADE_ROUNDED
                            if ready
                            else ft.Icons.STAR_ROUNDED
                            if owned
                            else ft.Icons.LOCK_ROUNDED,
                            color=GREEN if ready else GOLD if owned else MUTED,
                            size=14,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Image(
                    robot.image,
                    width=float("inf"),
                    height=122,
                    fit=ft.BoxFit.CONTAIN,
                    opacity=1 if owned else 0.75,
                ),
                ft.Text(
                    robot.name,
                    color=INK if owned else MUTED,
                    size=13,
                    weight=ft.FontWeight.BOLD,
                    max_lines=2,
                ),
                ft.Row(
                    [ft.Text(f"Ур. {level}", size=9, color=GOLD), stars(rank, 9)],
                    spacing=3,
                )
                if owned
                else ft.Text(
                    f"Фрагменты {fragments}/{cost}",
                    size=9,
                    color="#C2D3EA",
                    max_lines=1,
                ),
            ],
            spacing=3,
        ),
        key=f"robot-open-{robot.id}",
        on_click=open_robot,
        padding=7,
        col={"xs": 6, "sm": 4, "md": 3, "lg": 2},
        border_radius=12,
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[tint(color, 0.1), "#172942"],
        ),
        border=ft.Border.all(2, color if owned else "#43536E"),
        shadow=ft.BoxShadow(blur_radius=7, color="#66020C20", offset=ft.Offset(0, 3)),
    )


@ft.component
def CollectionPanel(page, session, on_home=None):
    state = use_game(session)
    data = ensure(state)
    tab, set_tab = ft.use_state(0)
    role, set_role = ft.use_state("all")
    sort, set_sort = ft.use_state("power")
    rarity, set_rarity = ft.use_state("all")
    if session.robot_detail:
        return RobotDetail(
            page=page, session=session, identity=session.robot_detail, on_home=on_home
        )
    robots = list(ROBOTS)
    if role != "all":
        robots = [r for r in robots if DESIGNS[r.id]["class"] == role]
    if rarity != "all":
        robots = [r for r in robots if r.rarity == rarity]
    rank = {name: i for i, name in enumerate(RARITIES)}
    robots.sort(
        key=lambda r: (
            power(state, r.id)
            if sort == "power"
            else state.robot_levels.get(r.id, 0)
            if sort == "level"
            else rank[r.rarity]
            if sort == "rarity"
            else DESIGNS[r.id]["class"],
            r.id,
        ),
        reverse=sort != "class",
    )
    rows = [
        resource_hud(state),
        section_title(
            "Коллекция роботов", f"{len(state.robot_levels)} / {len(ROBOTS)} открыто"
        ),
        tabs(["Коллекция", "Отряд", "Энциклопедия"], tab, set_tab),
    ]
    if tab == 1:
        rows += [
            card(
                ft.Text(
                    "В отряде до трёх роботов. Выбери активного бойца в его профиле; мастерской помогает вся открытая команда.",
                    size=12,
                    color=MUTED,
                )
            )
        ]
        chosen = [ROBOT_BY_ID[r] for r in data["team"]]
        rows.append(
            ft.ResponsiveRow(
                [robot_tile(session, r) for r in chosen], spacing=7, run_spacing=8
            )
        )
        if not chosen:
            rows.append(
                ft.Text("Открой профиль робота и нажми «В отряд».", size=12, color=INK)
            )
        rows.append(ft.Text("Доступные бойцы", color=INK, weight=ft.FontWeight.BOLD))
        rows.append(
            ft.ResponsiveRow(
                [robot_tile(session, r) for r in ROBOTS if r.id in state.robot_levels],
                spacing=7,
                run_spacing=8,
            )
        )
    else:
        rows.append(
            ft.Row(
                [
                    ft.Dropdown(
                        value=role,
                        options=[ft.DropdownOption("all", "Все классы")]
                        + [ft.DropdownOption(k, v) for k, v in CLASSES.items()],
                        on_select=lambda e: set_role(e.control.value),
                        text_size=10,
                        expand=True,
                        bgcolor="#183454",
                        content_padding=8,
                    ),
                    ft.Dropdown(
                        value=sort,
                        options=[
                            ft.DropdownOption(k, v)
                            for k, v in [
                                ("power", "Сила"),
                                ("level", "Уровень"),
                                ("rarity", "Редкость"),
                                ("class", "Класс"),
                            ]
                        ],
                        on_select=lambda e: set_sort(e.control.value),
                        text_size=10,
                        expand=True,
                        bgcolor="#183454",
                        content_padding=8,
                    ),
                ],
                spacing=7,
            )
        )
        rows.append(
            ft.Dropdown(
                value=rarity,
                options=[ft.DropdownOption("all", "Все редкости")]
                + [ft.DropdownOption(k, v[0]) for k, v in RARITIES.items()],
                on_select=lambda e: set_rarity(e.control.value),
                text_size=11,
                bgcolor="#183454",
                content_padding=8,
            )
        )
        if tab == 0:
            rows.append(
                ft.ResponsiveRow(
                    [robot_tile(session, r) for r in robots], spacing=7, run_spacing=9
                )
            )
        else:
            for r in robots:
                d = DESIGNS[r.id]
                rows.append(
                    card(
                        ft.Row(
                            [
                                ft.Image(r.image, width=74, height=92),
                                ft.Column(
                                    [
                                        ft.Text(
                                            r.name + " · " + CLASSES[d["class"]],
                                            color=INK,
                                            weight=ft.FontWeight.BOLD,
                                            size=13,
                                        ),
                                        ft.Text(d["strength"], color=GREEN, size=11),
                                        ft.Text(
                                            "Слабость: " + d["weakness"],
                                            color=MUTED,
                                            size=10,
                                        ),
                                        ft.Text(
                                            "Передвижение: " + d["mobility"],
                                            color=MUTED,
                                            size=10,
                                        ),
                                    ],
                                    spacing=5,
                                    expand=True,
                                ),
                            ],
                            spacing=10,
                        )
                    )
                )
    return ft.Column(rows, spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)


@ft.component
def RobotDetail(page, session, identity, on_home=None):
    state = use_game(session)
    data = ensure(state)
    robot = ROBOT_BY_ID[identity]
    design = DESIGNS[identity]
    tab, set_tab = ft.use_state(0)
    owned = identity in state.robot_levels
    level = state.robot_levels.get(identity, 0)
    rank = data["stars"].get(identity, 1)
    stats = effective_stats(state, identity)
    fragments = data["fragments"].get(identity, 0)
    rarity_color = RARITIES[robot.rarity][1]

    async def back(_):
        session.robot_detail = ""
        session.route = session.robot_detail_return
        session.robot_detail_return = ""
        session.notify()

    def command(name, *args):
        async def run(_):
            session.act(name, *args)

        return run

    async def inspect(_):
        session.inspection_id = identity
        await set_scene_focus(page, session, "robot")

    rows = [
        ft.Row(
            [
                ft.IconButton(
                    ft.Icons.ARROW_BACK_ROUNDED,
                    on_click=back,
                    icon_color="#8DE7FF",
                    key="robot-detail-back",
                ),
                ft.Column(
                    [
                        ft.Text(
                            robot.name, color=INK, size=24, weight=ft.FontWeight.BOLD
                        ),
                        ft.Text(
                            CLASSES[design["class"]]
                            + " · "
                            + RARITIES[robot.rarity][0],
                            color=rarity_color,
                            size=11,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
                stars(rank, 14),
            ]
        ),
        resource_hud(state),
    ]
    from robot_preview import preview_stage, preview_controls

    rows.append(preview_stage(session, identity, on_expand=inspect))
    rows.append(preview_controls(session, identity))
    if owned:
        rows.append(
            ft.Row(
                [
                    game_button(
                        "Выбран" if state.active_robot == identity else "В мастерскую",
                        command("select_robot", identity),
                        key=f"select-{identity}",
                        disabled=state.active_robot == identity,
                        expand=True,
                    ),
                    game_button(
                        "Убрать из отряда" if identity in data["team"] else "В отряд",
                        command("team_toggle", identity),
                        kind="blue",
                        expand=True,
                    ),
                ],
                spacing=8,
            )
        )
        rows.append(
            ft.Row(
                [
                    game_button(
                        "Кормить · 5",
                        command("feed", identity),
                        key=f"feed-{identity}",
                        kind="green",
                        disabled=state.food < 5,
                        expand=True,
                    ),
                    game_button(
                        f"Улучшить · {compact(training_price(robot, level))}",
                        command("train_robot", identity),
                        key=f"train-{identity}",
                        disabled=level >= MAX_ROBOT_LEVEL
                        or state.coin < training_price(robot, level),
                        expand=True,
                    ),
                ],
                spacing=8,
            )
        )
    else:
        cost = RARITY_FRAGMENTS[robot.rarity]
        rows.append(
            game_button(
                f"Открыть · {fragments}/{cost} фрагментов",
                command("fragment_unlock", identity),
                key=f"fragment-unlock-{identity}",
                disabled=fragments < cost,
            )
        )
        if (
            not state.egg_id
            and robot.level <= state.level
            and state.coin >= robot.egg_price
        ):
            rows.append(
                game_button(
                    f"Яйцо · {compact(robot.egg_price)} золота",
                    command("incubate", identity),
                    key=f"robot-egg-{identity}",
                    kind="blue",
                )
            )
    rows.append(notice(session))
    if state.egg_id == identity:
        from robot_ui import incubator_card

        rows.append(incubator_card(session))
    labels = {
        "health": "Здоровье",
        "attack": "Урон",
        "defense": "Броня",
        "speed": "Скорость",
        "crit": "Крит. шанс %",
        "crit_damage": "Крит. урон %",
        "energy": "Энергия",
        "regen": "Восстановление",
    }
    rows.append(
        ft.ResponsiveRow(
            [stat_chip(title, stats[key]) for key, title in labels.items()],
            spacing=7,
            run_spacing=7,
        )
    )
    # Seven persisted equipment slots: two weapon mounts plus five modules.
    mounts = state.loadouts.get(identity, [])
    slots = [
        (
            "Основное",
            BY_ID[mounts[0]].title if mounts else "Штатное",
            ft.Icons.FLASH_ON_ROUNDED,
            0,
        ),
        (
            "Дополнительное",
            BY_ID[mounts[1]].title if len(mounts) > 1 else "Свободно",
            ft.Icons.GPS_FIXED_ROUNDED,
            0,
        ),
    ]
    for key, title in SLOTS.items():
        item = data["module_loadouts"].get(identity, {}).get(key)
        slots.append(
            (
                title,
                MODULE_BY_ID[item].title if item else "Свободно",
                ft.Icons.SETTINGS_ROUNDED,
                1,
            )
        )
    rows.append(
        ft.ResponsiveRow(
            [
                ft.Container(
                    ft.Column(
                        [
                            ft.Icon(icon, color="#90DFFF", size=23),
                            ft.Text(
                                title, color=INK, size=10, weight=ft.FontWeight.BOLD
                            ),
                            ft.Text(value, color=MUTED, size=9, max_lines=2),
                        ],
                        spacing=4,
                    ),
                    on_click=lambda _, t=t: set_tab(t),
                    col=4,
                    padding=8,
                    bgcolor="#172E50",
                    border_radius=9,
                    border=ft.Border.all(1, "#5376A3"),
                )
                for title, value, icon, t in slots
            ],
            spacing=6,
            run_spacing=6,
        )
    )
    rows.append(
        tabs(["Оружие", "Модули", "Навыки", "Внешний вид", "Развитие"], tab, set_tab)
    )
    if tab == 0:
        for weapon in WEAPONS:
            lv = state.weapon_levels.get(weapon.id, 0)
            equipped = weapon.id in mounts
            compatible = weapon.mass <= stats["capacity"]
            price = upgrade_cost(weapon, lv) if lv else weapon.price
            current = BY_ID[mounts[0]] if mounts else BY_ID[design["weapon"]]
            rows.append(
                card(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Image(
                                        f"art/weapons/{weapon.id}.svg",
                                        width=52,
                                        height=52,
                                    ),
                                    ft.Column(
                                        [
                                            ft.Text(
                                                weapon.title,
                                                color=INK,
                                                size=13,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Text(
                                                f"{RARITIES[weapon.rarity][0]} · {lv}/10 ур. · "
                                                + (
                                                    "Совместимо"
                                                    if compatible
                                                    else "Тяжёлое крепление"
                                                ),
                                                color=RARITIES[weapon.rarity][1],
                                                size=10,
                                            ),
                                        ],
                                        expand=True,
                                        spacing=3,
                                    ),
                                ],
                                spacing=9,
                            ),
                            ft.Text(
                                f"Урон {weapon.damage + lv * 2} · Темп {weapon.speed} · Дальность {weapon.reach} · Энергия {weapon.energy}",
                                color=MUTED,
                                size=10,
                            ),
                            ft.Text(weapon.ability, color=INK, size=11),
                            ft.Text(
                                f"Сравнение с {current.title}: базовый урон {weapon.damage - current.damage:+d}, энергия {weapon.energy - current.energy:+d}",
                                color="#98D8FF",
                                size=10,
                            ),
                            ft.Text(
                                f"Чертежи: {data['blueprints'].get(weapon.id, 0)}/10",
                                color=MUTED,
                                size=10,
                            ),
                            ft.Row(
                                [
                                    game_button(
                                        f"{'Улучшить' if lv else 'Купить'} · {compact(price)}",
                                        command(
                                            "weapon_upgrade" if lv else "weapon_buy",
                                            weapon.id,
                                        ),
                                        key=f"weapon-buy-{weapon.id}",
                                        kind="green",
                                        disabled=lv >= 10
                                        or state.coin < price
                                        or state.level < weapon.unlock,
                                        expand=True,
                                    ),
                                    game_button(
                                        "Снять" if equipped else "Установить",
                                        command(
                                            "weapon_remove"
                                            if equipped
                                            else "weapon_equip",
                                            weapon.id,
                                            identity,
                                        ),
                                        key=f"weapon-equip-{weapon.id}",
                                        kind="blue",
                                        disabled=not owned
                                        or not lv
                                        or not compatible
                                        or state.battle.get("result") == "active",
                                        expand=True,
                                    ),
                                ],
                                spacing=7,
                            ),
                            *(
                                [
                                    game_button(
                                        "Создать по чертежам",
                                        command("blueprint_craft", weapon.id),
                                        kind="purple",
                                    )
                                ]
                                if not lv and data["blueprints"].get(weapon.id, 0) >= 10
                                else []
                            ),
                        ],
                        spacing=8,
                    ),
                    padding=12,
                    border=ft.Border.all(1, RARITIES[weapon.rarity][1]),
                )
            )
    elif tab == 1:
        for module in MODULES:
            lv = data["modules"].get(module.id, 0)
            installed = (
                data["module_loadouts"].get(identity, {}).get(module.slot) == module.id
            )
            price = module_cost(module, lv)
            rows.append(
                card(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Image(
                                        f"art/modules/{module.id}.svg",
                                        width=46,
                                        height=46,
                                    ),
                                    ft.Column(
                                        [
                                            ft.Text(
                                                module.title,
                                                color=INK,
                                                size=13,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Text(
                                                f"{SLOTS[module.slot]} · {lv}/10 ур. · +{module.bonus * max(1, lv)} {labels.get(module.attribute, module.attribute)}",
                                                color=MUTED,
                                                size=10,
                                            ),
                                        ],
                                        expand=True,
                                    ),
                                ],
                                spacing=9,
                            ),
                            ft.Text(module.description, color=MUTED, size=11),
                            ft.Row(
                                [
                                    game_button(
                                        f"{'Улучшить' if lv else 'Купить'} · {compact(price)}",
                                        command(
                                            "module_upgrade" if lv else "module_buy",
                                            module.id,
                                        ),
                                        kind="green",
                                        key=f"module-buy-{module.id}",
                                        disabled=lv >= 10 or state.coin < price,
                                        expand=True,
                                    ),
                                    game_button(
                                        "Снять" if installed else "Установить",
                                        command(
                                            "module_remove"
                                            if installed
                                            else "module_equip",
                                            module.id,
                                            identity,
                                        ),
                                        kind="blue",
                                        key=f"module-equip-{module.id}",
                                        disabled=not lv or not owned,
                                        expand=True,
                                    ),
                                ],
                                spacing=7,
                            ),
                        ],
                        spacing=9,
                    ),
                    padding=12,
                )
            )
    elif tab == 2:
        lv = data["skills"].get(identity, 1)
        rows.append(
            card(
                ft.Column(
                    [
                        section_title(design["ultimate"], f"Уровень навыка {lv}/5"),
                        ft.Text(design["strength"], color=INK, size=12),
                        ft.Text(
                            "Заряд суперспособности растёт от атак, защиты и полученного урона. Нужны 100% заряда и 4 энергии.",
                            color=MUTED,
                            size=11,
                        ),
                        ft.Text(
                            "Слабость: " + design["weakness"], color="#FFC0B1", size=11
                        ),
                        game_button(
                            f"Навык ↑ · {250 * lv} золота, {max(0, lv - 1)} ядер",
                            command("skill_up", identity),
                            disabled=not owned or lv >= 5,
                            key="robot-skill-up",
                        ),
                    ],
                    spacing=10,
                )
            )
        )
    elif tab == 3:
        from cosmetic_catalog import cosmetic_name

        rows.append(
            ft.Text(
                "Окраски и эмоции открываются в сезоне. Они не меняют боевые характеристики.",
                color=MUTED,
                size=12,
            )
        )
        for skin in data["skins"]:
            rows.append(
                game_button(
                    cosmetic_name("skin", skin) + " · Применить",
                    command("skin_equip", skin, identity),
                    kind="purple",
                    disabled=not owned,
                )
            )
        for animation in data["animations"]:
            rows.append(
                game_button(
                    cosmetic_name("animation", animation) + " · Выбрать эмоцию",
                    command("animation_equip", animation, identity),
                    kind="blue",
                    disabled=not owned,
                )
            )
        if not data["skins"]:
            rows.append(
                card(
                    ft.Text(
                        "Первые окраски доступны в бесплатной линии сезона.",
                        color=INK,
                        size=12,
                    )
                )
            )
    else:
        cost = STAR_COSTS[rank - 1] if rank < 5 else 0
        rows.append(
            card(
                ft.Column(
                    [
                        section_title(
                            "Звёздный ранг",
                            f"{rank}/5 · Каждая звезда даёт +7% к базовым здоровью и урону",
                        ),
                        ft.Text(
                            f"Фрагменты: {fragments}/{cost}"
                            if cost
                            else "Максимальный ранг",
                            color=GOLD,
                            size=13,
                        ),
                        game_button(
                            "Повысить звезду",
                            command("star_up", identity),
                            disabled=not owned or rank >= 5 or fragments < cost,
                            key="robot-star-up",
                        ),
                    ],
                    spacing=10,
                )
            )
        )
    return ft.Column(rows, spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
