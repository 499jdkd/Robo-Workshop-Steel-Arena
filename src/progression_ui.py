"""Projects, deterministic supply boxes and collectable profile icons."""

import flet as ft

from progression import avatars, daily_goals
from robot_catalog import ROBOTS
from ui_shared import GOLD, GREEN, INK, MUTED, badge, button_style, card, tint


def avatar_picker(session):
    choices = avatars(session.state)
    cells = []
    for avatar in choices:

        async def select(_, identity=avatar.id):
            session.act("avatar", identity)

        cells.append(
            ft.Container(
                ft.Column(
                    [
                        ft.Image(
                            avatar.image,
                            width=53,
                            height=53,
                            opacity=1 if avatar.unlocked else 0.3,
                        ),
                        ft.Text(
                            avatar.title,
                            size=9,
                            color=INK if avatar.unlocked else MUTED,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE_ROUNDED
                            if avatar.id == session.state.avatar_id
                            else ft.Icons.LOCK_OPEN_ROUNDED
                            if avatar.unlocked
                            else ft.Icons.LOCK_ROUNDED,
                            size=14,
                            color=session.state.accent if avatar.unlocked else MUTED,
                        ),
                    ],
                    spacing=4,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                col=3,
                padding=8,
                border_radius=14,
                bgcolor=tint(session.state.accent, 0.84)
                if avatar.id == session.state.avatar_id
                else "#F5F7FB",
                on_click=select if avatar.unlocked else None,
                tooltip=avatar.title if avatar.unlocked else avatar.requirement,
                key=f"avatar-{avatar.id}",
            )
        )
    return card(
        ft.Column(
            [
                ft.Row(
                    [
                        badge("profile", 26),
                        ft.Text(
                            "Иконки профиля",
                            size=15,
                            color=INK,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            f"{sum(item.unlocked for item in choices)}/{len(choices)}",
                            size=11,
                            color=MUTED,
                        ),
                    ],
                    spacing=8,
                ),
                ft.Text(
                    "Открывай роботов и выполняй достижения. Каждая новая иконка остаётся в коллекции",
                    size=11,
                    color=MUTED,
                ),
                ft.ResponsiveRow(cells, spacing=6, run_spacing=7),
            ],
            spacing=10,
        )
    )


def daily_panel(session):
    controls = [
        ft.Row(
            [
                ft.Icon(ft.Icons.WB_SUNNY_ROUNDED, color=GOLD, size=23),
                ft.Text("Цели дня", size=15, color=INK, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        )
    ]
    for goal in daily_goals(session.state, session.clock()):

        async def claim(_, identity=goal["id"]):
            session.act("daily", identity)

        controls.append(
            ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(
                                goal["title"],
                                size=12,
                                color=INK,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                f"{goal['current']}/{goal['target']} · {goal['gold']} золота + {goal['food']} корма + {goal['parts']} детали",
                                size=9,
                                color=MUTED,
                            ),
                            ft.ProgressBar(
                                value=goal["current"] / goal["target"],
                                height=4,
                                color=GREEN
                                if goal["claimed"]
                                else session.state.accent,
                                bgcolor="#E6EBF4",
                            ),
                        ],
                        spacing=5,
                        expand=True,
                    ),
                    ft.IconButton(
                        ft.Icons.CHECK_CIRCLE_ROUNDED
                        if goal["claimed"]
                        else ft.Icons.REDEEM_ROUNDED,
                        key=f"daily-{goal['id']}",
                        on_click=claim,
                        disabled=goal["claimed"] or goal["current"] < goal["target"],
                        icon_color=GREEN if goal["claimed"] else session.state.accent,
                        tooltip="Награда получена"
                        if goal["claimed"]
                        else "Забрать награду",
                    ),
                ],
                spacing=8,
            )
        )
    return card(
        ft.Column(controls, spacing=14), bgcolor=tint(session.state.accent, 0.97)
    )


def supplies_panel(session):
    state = session.state

    async def supplies(_):
        session.act("crate", "supply")

    controls = [
        ft.Row(
            [
                badge("parts", 31),
                ft.Column(
                    [
                        ft.Text(
                            f"Детали: {state.parts}",
                            size=16,
                            color=INK,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            "Проекты, победы и цели пополняют запас",
                            size=10,
                            color=MUTED,
                        ),
                    ],
                    spacing=4,
                    expand=True,
                ),
            ],
            spacing=9,
        ),
        ft.Row(
            [
                ft.Image("art/icons/crate.svg", width=65, height=62),
                ft.Column(
                    [
                        ft.Text(
                            "Бокс припасов",
                            size=14,
                            color=INK,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text("Внутри: 50 золота и 15 корма", size=11, color=MUTED),
                        ft.Text("Содержимое известно заранее", size=9, color=MUTED),
                    ],
                    spacing=5,
                    expand=True,
                ),
            ],
            spacing=9,
        ),
        ft.Button(
            "Открыть · 8 деталей",
            key="crate-supply",
            on_click=supplies,
            disabled=state.parts < 8,
            style=button_style(state.accent),
            width=float("inf"),
        ),
    ]
    for robot in sorted(ROBOTS, key=lambda robot: robot.level):
        if (
            robot.id in state.robot_levels
            or robot.id == state.egg_id
            or state.egg_stock.get(robot.id)
            or robot.level > state.level
        ):
            continue

        async def egg(_, identity=robot.id):
            session.act("crate", "egg", identity)

        controls.append(
            ft.Row(
                [
                    ft.Image(robot.egg_image, width=43, height=45),
                    ft.Column(
                        [
                            ft.Text(
                                f"Бокс: яйцо {robot.name}",
                                size=12,
                                color=INK,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text("Отправится в хранилище яиц", size=10, color=MUTED),
                        ],
                        spacing=4,
                        expand=True,
                    ),
                    ft.Button(
                        "20 деталей",
                        key=f"crate-egg-{robot.id}",
                        on_click=egg,
                        disabled=state.parts < 20,
                        style=button_style(state.accent, secondary=True),
                    ),
                ],
                spacing=8,
            )
        )
    return card(ft.Column(controls, spacing=12), bgcolor="#FFFAEF")


def stored_eggs_panel(session):
    state = session.state
    rows = []
    for robot in ROBOTS:
        if not state.egg_stock.get(robot.id):
            continue

        async def incubate(_, identity=robot.id):
            session.act("stock_egg", identity)

        rows.append(
            ft.Row(
                [
                    ft.Image(robot.egg_image, width=45, height=49),
                    ft.Text(
                        robot.name,
                        size=13,
                        color=INK,
                        weight=ft.FontWeight.BOLD,
                        expand=True,
                    ),
                    ft.Button(
                        "В инкубатор",
                        key=f"stored-egg-{robot.id}",
                        on_click=incubate,
                        disabled=bool(state.egg_id),
                        style=button_style(state.accent, secondary=True),
                    ),
                ],
                spacing=9,
            )
        )
    return card(
        ft.Column(
            [
                ft.Text("Хранилище яиц", size=15, color=INK, weight=ft.FontWeight.BOLD),
                *rows,
                *(
                    []
                    if rows
                    else [
                        ft.Text(
                            "Здесь ждут яйца из боксов. Их можно хранить, пока инкубатор занят",
                            size=11,
                            color=MUTED,
                        )
                    ]
                ),
            ],
            spacing=10,
        )
    )


def project_gallery(session):
    state = session.state
    return card(
        ft.Column(
            [
                ft.Text(
                    "Твои изобретения", size=15, color=INK, weight=ft.FontWeight.BOLD
                ),
                ft.ResponsiveRow(
                    [
                        ft.Container(
                            ft.Column(
                                [
                                    ft.Image(
                                        f"art/projects/{identity}.svg",
                                        width=78,
                                        height=62,
                                        opacity=1
                                        if state.craft_counts.get(identity)
                                        else 0.28,
                                    ),
                                    ft.Text(title, size=10, color=INK),
                                    ft.Text(
                                        f"Собрано: {state.craft_counts.get(identity, 0)}",
                                        size=9,
                                        color=MUTED,
                                    ),
                                ],
                                spacing=3,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            col=4,
                        )
                        for identity, title in (
                            ("lamp", "Фонарик"),
                            ("scooter", "Самокат"),
                            ("robot", "Мини-робот"),
                            ("beacon", "Маяк"),
                            ("solar", "Станция"),
                        )
                    ],
                    run_spacing=12,
                    spacing=6,
                ),
                ft.Text(
                    "Первый собранный фонарик появляется в мастерской — нажми на него, чтобы включить свет",
                    size=11,
                    color=MUTED,
                ),
            ],
            spacing=12,
        )
    )
