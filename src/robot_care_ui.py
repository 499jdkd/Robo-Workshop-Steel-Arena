"""Food and care controls shared by the workshop, collection and arena."""

import flet as ft

from gameplay import compact, feeding_target
from robot_catalog import MAX_ROBOT_LEVEL, ROBOT_BY_ID
from ui_shared import GREEN, INK, MUTED, badge, button_style, card


def food_bar(session):
    return card(
        ft.Row(
            [
                badge("food", 30),
                ft.Text(
                    f"Корм: {compact(session.state.food)}",
                    size=17,
                    color=INK,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(
                    "Собирай касаниями",
                    size=10,
                    color=MUTED,
                    expand=True,
                    text_align=ft.TextAlign.RIGHT,
                ),
            ],
            spacing=9,
        ),
        padding=12,
        bgcolor="#FFF4DB",
    )


def care_actions(session, robot_id, on_arena=None):
    state = session.state
    level = state.robot_levels[robot_id]
    energy = state.robot_energy.get(robot_id, 70)
    xp = state.robot_xp.get(robot_id, 0)

    async def feed(_):
        session.act("feed", robot_id)

    return ft.Column(
        [
            ft.Row(
                [
                    ft.Text(
                        f"Заряд для боёв: {energy} / 100",
                        size=11,
                        color=GREEN,
                        expand=True,
                    ),
                    ft.Text(
                        "Макс. уровень"
                        if level >= MAX_ROBOT_LEVEL
                        else f"Опыт: {xp} / {feeding_target(level)}",
                        size=10,
                        color=MUTED,
                    ),
                ]
            ),
            ft.ProgressBar(
                value=energy / 100,
                color=GREEN,
                bgcolor="#E4F1E9",
                height=6,
                border_radius=4,
            ),
            ft.Row(
                [
                    ft.Button(
                        "Кормить · 5",
                        icon=ft.Icons.RESTAURANT_ROUNDED,
                        key=f"feed-{robot_id}",
                        on_click=feed,
                        disabled=state.food < 5
                        or (energy >= 100 and level >= MAX_ROBOT_LEVEL),
                        style=button_style(GREEN),
                        expand=True,
                    ),
                    *(
                        [
                            ft.Button(
                                "Арена",
                                icon=ft.Icons.SPORTS_MARTIAL_ARTS_ROUNDED,
                                on_click=on_arena,
                                style=button_style(state.accent, secondary=True),
                                expand=True,
                            )
                        ]
                        if on_arena
                        else []
                    ),
                ],
                spacing=8,
            ),
        ],
        spacing=8,
    )


def care_panel(session, on_arena=None):
    state = session.state
    robot = ROBOT_BY_ID.get(state.active_robot)
    if robot is None:
        return ft.Container(height=0)
    return card(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Image(robot.image, width=64, height=68, cache_width=150),
                        ft.Column(
                            [
                                ft.Text(
                                    f"{robot.name} · {state.robot_levels[robot.id]} ур.",
                                    size=16,
                                    color=INK,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Text(
                                    "Порция: +18 заряда, +2 опыта · заряд восстанавливается со временем",
                                    size=11,
                                    color=MUTED,
                                ),
                            ],
                            spacing=5,
                            expand=True,
                        ),
                    ],
                    spacing=9,
                ),
                care_actions(session, robot.id, on_arena),
            ],
            spacing=10,
        ),
        padding=13,
    )
