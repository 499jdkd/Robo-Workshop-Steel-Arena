import asyncio

import flet as ft

from armory_ui import weekly_panel
from game_ui import game_button, resource_hud
from feature_screens import navigate

from game_session import preview_session
from gameplay import (
    ORDERS,
    STAGES,
    active_goals,
    charge_price,
    compact,
    order_reward,
    threshold,
)
from progression_ui import daily_panel, project_gallery
from rewarded_ads import RewardPanel
from robot_care_ui import care_panel, food_bar
from robot_ui import incubator_card, robot_scene
from ui_shared import (
    GOLD,
    GREEN,
    INK,
    MUTED,
    button_style,
    card,
    heading,
    notice,
    saving_status,
    use_game,
    wallet,
)


def goal_card(session, goal):
    state = session.state
    current = min(goal.target, getattr(state, goal.attribute))
    ready = current >= goal.target

    async def claim(_):
        session.act("goal", goal.id)

    return card(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(ft.Icons.FLAG_ROUNDED, color=GOLD, size=20),
                            bgcolor="#FFF4D4",
                            padding=9,
                            border_radius=12,
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    goal.title,
                                    size=13,
                                    weight=ft.FontWeight.BOLD,
                                    color=INK,
                                ),
                                ft.Text(
                                    f"{compact(current)} / {compact(goal.target)}",
                                    size=11,
                                    color=MUTED,
                                ),
                            ],
                            spacing=3,
                            expand=True,
                        ),
                        ft.Button(
                            f"+{compact(goal.reward)}",
                            on_click=claim,
                            disabled=not ready,
                            style=button_style(
                                GREEN if ready else "#91A0B5", secondary=not ready
                            ),
                        ),
                    ],
                    spacing=10,
                ),
                ft.ProgressBar(
                    value=current / goal.target,
                    color=GREEN if ready else state.accent,
                    bgcolor="#EDF1F7",
                    height=5,
                    border_radius=4,
                ),
            ],
            spacing=10,
        ),
        padding=13,
    )


def order_panel(session, now):
    from game_countdown import GameCountdown

    state = session.state

    async def recharge(_):
        session.act("charge")

    energy_row = ft.Row(
        [
            ft.Icon(ft.Icons.BATTERY_CHARGING_FULL_ROUNDED, color=GREEN, size=26),
            ft.Column(
                [
                    ft.Text(
                        f"Заряд помощника · {int(state.energy)}%",
                        size=12,
                        color=INK,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.ProgressBar(
                        value=state.energy / 100,
                        color=GREEN,
                        bgcolor="#E5F3ED",
                        height=6,
                        border_radius=5,
                    ),
                    ft.Text(
                        "Восстанавливается и во время отдыха", size=10, color=MUTED
                    ),
                ],
                spacing=5,
                expand=True,
            ),
            ft.Button(
                f"+40 · {charge_price(state)}",
                on_click=recharge,
                disabled=not session.trusted
                or state.energy >= 100
                or state.coin < charge_price(state),
                style=button_style(GREEN, secondary=True),
            ),
        ],
        spacing=9,
    )
    controls = [energy_row, ft.Divider(color="#EDF0F5", height=18)]
    if state.work_id:
        order = next(item for item in ORDERS if item.id == state.work_id)
        remaining = max(0, int(state.work_end_at - now + 0.99))
        duration = max(1, state.work_end_at - state.work_started_at)

        async def collect(_):
            session.act("collect")

        controls.extend(
            [
                ft.Row(
                    [
                        ft.Image(
                            f"art/projects/{state.work_id}.svg", width=76, height=59
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    order.title,
                                    size=14,
                                    weight=ft.FontWeight.BOLD,
                                    color=INK,
                                ),
                                GameCountdown(
                                    seconds=max(0, state.work_end_at - now),
                                    countdown_id=f"{state.work_id}:{state.work_end_at}",
                                    on_expire=lambda _: session.notify(),
                                    key="work-order-countdown",
                                    size=12,
                                    color=GREEN if not remaining else MUTED,
                                ),
                            ],
                            spacing=4,
                            expand=True,
                        ),
                    ]
                ),
                ft.ProgressBar(
                    value=min(1, max(0, 1 - (state.work_end_at - now) / duration)),
                    color=state.accent,
                    bgcolor="#EDF1F7",
                    height=8,
                    border_radius=6,
                ),
                ft.Button(
                    f"Забрать {compact(state.work_reward)} монет"
                    if not remaining
                    else "Помощник работает…",
                    on_click=collect,
                    disabled=bool(remaining),
                    style=button_style(state.accent),
                    width=float("inf"),
                ),
            ]
        )
    else:
        for order in ORDERS:
            unlocked = state.stage_index >= order.stage
            reward = order_reward(state, order)

            async def start(_, order_id=order.id):
                session.act("order", order_id)

            controls.append(
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(
                                ft.Icons.WORK_ROUNDED
                                if unlocked
                                else ft.Icons.LOCK_ROUNDED,
                                color=state.accent if unlocked else MUTED,
                                size=19,
                            ),
                            bgcolor="#F0F3FA",
                            padding=10,
                            border_radius=12,
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    order.title,
                                    size=13,
                                    color=INK if unlocked else MUTED,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Text(
                                    f"{order.seconds} с · {order.energy} энергии"
                                    if unlocked
                                    else f"Откроется на уровне {STAGES[order.stage].level}",
                                    size=10,
                                    color=MUTED,
                                ),
                            ],
                            spacing=4,
                            expand=True,
                        ),
                        ft.Button(
                            f"+{reward}",
                            on_click=start,
                            disabled=not unlocked or state.energy < order.energy,
                            style=button_style(state.accent, secondary=True),
                        ),
                    ],
                    spacing=9,
                )
            )
    return card(ft.Column(controls, spacing=12), padding=15)


@ft.component
def MainScreen(
    page: ft.Page, device_id: str, session=None, on_collection=None, on_arena=None
):
    session = session or preview_session(page, device_id)
    state = use_game(session)
    pressed, set_pressed = ft.use_state(False)
    gain, set_gain = ft.use_state(0)
    panel, set_panel = ft.use_state(0)
    pulse_running = ft.use_ref(False)
    now = session.clock()

    async def tapped(_):
        if not session.ui_alive:
            return
        result = session.workshop_tap()
        if pulse_running.current:
            return
        pulse_running.current = True
        set_gain(result.coins)
        set_pressed(True)
        try:
            await asyncio.sleep(0.1)
            if session.ui_alive:
                set_pressed(False)
            await asyncio.sleep(0.1)
        finally:
            pulse_running.current = False

    async def show_orders(_):
        set_panel(0)

    async def show_goals(_):
        set_panel(1)

    stage = state.stage_index
    next_stage = STAGES[stage + 1] if stage + 1 < len(STAGES) else None
    scene = robot_scene(session, pressed=pressed, gain=gain, on_tap=tapped)
    stats = ft.Row(
        [
            card(
                ft.Column(
                    [
                        ft.Icon(icon, color=color, size=19),
                        ft.Text(value, size=14, weight=ft.FontWeight.BOLD, color=INK),
                        ft.Text(label, size=10, color=MUTED),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=3,
                ),
                padding=10,
                expand=True,
            )
            for icon, value, label, color in (
                (
                    ft.Icons.BOLT_ROUNDED,
                    f"+{compact(state.click_power(now))}",
                    "касание",
                    GOLD,
                ),
                (
                    ft.Icons.SMART_TOY_ROUNDED,
                    f"+{compact(state.auto_power(now))}",
                    "в секунду",
                    state.accent,
                ),
                (ft.Icons.STAR_ROUNDED, str(state.level), "уровень", "#9B77D4"),
            )
        ],
        spacing=8,
    )
    goals = active_goals(state)
    controls = [
        heading("Robo Workshop", "Мастерская · " + (state.username or "Инженер"), None),
        resource_hud(state),
        saving_status(session),
        ft.Row(
            [
                ft.Text(
                    state.stage.title,
                    size=15,
                    weight=ft.FontWeight.BOLD,
                    color=INK,
                    expand=True,
                ),
                ft.Text(f"Мир {stage + 1} / {len(STAGES)}", size=11, color=MUTED),
            ]
        ),
        ft.ProgressBar(
            value=state.level_progress,
            color=state.accent,
            bgcolor="#E1E8F4",
            height=7,
            border_radius=5,
        ),
        ft.Text(
            f"До уровня {state.level + 1}: {compact(max(0, threshold(state.level) - state.experience))} опыта"
            + (f"  ·  Новый мир на ур. {next_stage.level}" if next_stage else ""),
            size=10,
            color=MUTED,
        ),
        scene,
        ft.Row(
            [
                game_button(
                    "Сезон", navigate(session, "season"), key="open-season", expand=True
                ),
                game_button(
                    "Фабрика",
                    navigate(session, "factory"),
                    kind="blue",
                    key="open-factory",
                    expand=True,
                ),
                game_button(
                    "Магазин",
                    navigate(session, "store"),
                    kind="purple",
                    key="open-store",
                    expand=True,
                ),
            ],
            spacing=7,
        ),
        incubator_card(session, on_collection),
        care_panel(session, on_arena),
        RewardPanel(page=page, session=session, compact=True),
        stats,
        notice(session),
        ft.Text("Ближайшая цель", size=15, weight=ft.FontWeight.BOLD, color=INK),
        goal_card(session, goals[0]),
        daily_panel(session),
        ft.Row(
            [
                ft.Button(
                    "Заказы",
                    icon=ft.Icons.WORK_ROUNDED,
                    on_click=show_orders,
                    expand=True,
                    style=button_style(state.accent, secondary=panel != 0),
                ),
                ft.Button(
                    "Мои планы",
                    icon=ft.Icons.FLAG_ROUNDED,
                    on_click=show_goals,
                    expand=True,
                    style=button_style(state.accent, secondary=panel != 1),
                ),
            ],
            spacing=8,
        ),
    ]
    if panel == 0:
        controls.append(order_panel(session, now))
        controls.append(project_gallery(session))
    else:
        controls.extend(goal_card(session, goal) for goal in goals[1:])
        controls.append(
            card(
                ft.Column(
                    [
                        ft.Icon(
                            ft.Icons.ROCKET_LAUNCH_ROUNDED, color=state.accent, size=28
                        ),
                        ft.Text(
                            next_stage.title if next_stage else "Город идей открыт!",
                            size=17,
                            weight=ft.FontWeight.BOLD,
                            color=INK,
                        ),
                        ft.Text(
                            f"Следующая мастерская откроется на уровне {next_stage.level}"
                            if next_stage
                            else "Новые уровни и мастерские заказы остаются впереди",
                            size=12,
                            color=MUTED,
                        ),
                    ],
                    spacing=8,
                ),
                bgcolor=state.stage.color,
            )
        )
    controls.append(weekly_panel(session))
    return ft.Column(
        controls=controls, spacing=11, scroll=ft.ScrollMode.AUTO, expand=True
    )


def main_screen(
    page: ft.Page, device_id: str, session=None, on_collection=None, on_arena=None
):
    return MainScreen(
        page=page,
        device_id=device_id,
        session=session,
        on_collection=on_collection,
        on_arena=on_arena,
    )
