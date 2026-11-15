"""Robot collection controls; all actions use the shared saved game session."""

import flet as ft

from asset_layout import SPRITE_BOUNDS
from display_mode import set_scene_focus
from game_animation import animated_scene
from gameplay import compact
from progression import egg_remaining
from robot_care_ui import care_actions
from robot_catalog import MAX_ROBOT_LEVEL, RARITIES, ROBOT_BY_ID, ROBOTS, training_price
from robot_motion import robot_actor, workshop_activity
from ui_shared import GREEN, INK, MUTED, button_style, card, tint


def robot_scene(
    session,
    *,
    pressed=False,
    gain=0,
    on_tap=None,
    expanded=False,
    width=None,
    height=None,
):
    state = session.state
    egg = ROBOT_BY_ID.get(state.egg_id)
    robot = ROBOT_BY_ID.get(state.active_robot)
    if robot is not None:
        egg=None  # An incubating second robot must not hide the selected one.
    image = egg.egg_image if egg else robot.image if robot else "art/egg_starter.webp"
    phase = int(session.clock()) % 2
    width = width or max(280, (getattr(session.page, "width", None) or 420) - 28)
    scene_height = height or 294
    robot_size = min(270, scene_height * 0.77) if expanded else 222
    span = min(
        250 if expanded else 42, max(0, (width - robot_size * 220 / 240) / 2 - 18)
    )
    roam_x, activity, idle_motion, facing = workshop_activity(session.clock(), span)
    reveal = session.clock() < session.reveal_until
    fed = (
        session.clock() < session.fed_until
        and session.fed_robot == state.active_robot
        and not egg
    )
    sprite_w, sprite_h, _left, top, _right, bottom = SPRITE_BOUNDS.get(
        image, (220, 240, 0, 0, 220, 240)
    )
    size = min(280, 168 / max(0.4, (bottom - top) / sprite_h))
    position = 197 - size * bottom / sprite_h
    label = (
        f"{egg.name} ждёт внутри"
        if egg
        else f"{robot.name} · {state.robot_levels[robot.id]} ур."
        if robot
        else "Твой первый робот"
    )
    caption = (
        ("Нажми, чтобы открыть яйцо!")
        if state.egg_is_ready(session.clock())
        else f"Касайся · +{compact(state.click_power(session.clock()))} корма"
        if egg
        else "Нажимай — корми и развивай робота"
    )

    async def expand(_):
        await set_scene_focus(session.page, session, "" if expanded else "workshop")

    async def lamp(_):
        session.act("lamp_toggle")

    return card(
        ft.Stack(
            [
                ft.Container(
                    ft.AnimatedSwitcher(
                        ft.Image(
                            'art/workshop-future-v1.png' if state.stage_index>=1 else f"art/room_{state.stage_index}.webp",
                            key=f"room-{state.stage_index}",
                            fit=ft.BoxFit.COVER,
                            width=float("inf"),
                            height=scene_height,
                            cache_width=900,
                        ),
                        duration=450,
                        transition=ft.AnimatedSwitcherTransition.FADE,
                    )
                    if not expanded
                    else None,
                    image=ft.DecorationImage(
                        src='art/workshop-future-v1.png' if state.stage_index>=1 else f"art/room_{state.stage_index}.webp",
                        fit=ft.BoxFit.COVER,
                        alignment=ft.Alignment.BOTTOM_CENTER,
                    )
                    if expanded
                    else None,
                    top=0,
                    left=0,
                    right=0,
                    bottom=0,
                ),
                ft.Container(
                    ft.Image(
                        image,
                        key=image,
                        width=size,
                        height=size,
                        cache_width=560,
                        fit=ft.BoxFit.CONTAIN,
                    )
                    if egg or not robot
                    else None,
                    top=(scene_height - size) / 2
                    if egg and expanded
                    else position + 10
                    if egg
                    else scene_height - robot_size - scene_height * 0.14,
                    left=0,
                    right=0,
                    height=size if egg else robot_size,
                    alignment=ft.Alignment.CENTER,
                    scale=1,
                    rotate=(0.04 if pressed else -0.009 if phase else 0.009)
                    if egg
                    else 0,
                    animate_rotation=ft.Animation(150 if pressed else 1000),
                    offset=ft.Offset(
                        0 if egg else roam_x / width, -0.012 if phase and egg else 0
                    ),
                    animate_offset=ft.Animation(900, ft.AnimationCurve.LINEAR),
                ),
                *(
                    [
                        ft.Container(
                            animated_scene(session, expanded=expanded),
                            left=0,
                            right=0,
                            top=0,
                            bottom=0,
                        )
                    ]
                    if robot and not egg
                    else []
                ),
                *(
                    [
                        ft.Container(
                            ft.Image(
                                "art/projects/lamp.svg",
                                width=110 if expanded else 72,
                                height=70 if expanded else 46,
                            ),
                            left=14,
                            bottom=52,
                            opacity=1 if state.lamp_on else 0.55,
                            on_click=lamp,
                            key="workshop-lamp",
                        )
                    ]
                    if state.craft_counts.get("lamp")
                    else []
                ),
                *(
                    [
                        ft.Container(
                            ft.Icon(
                                ft.Icons.NOTIFICATIONS_ACTIVE_ROUNDED,
                                color="#B8F3FF",
                                size=24,
                            ),
                            top=18,
                            left=width * 0.5 - 12,
                            shadow=ft.BoxShadow(blur_radius=22, color="#B558DAFF"),
                        )
                    ]
                    if not egg and idle_motion == "siren"
                    else []
                ),
                *(
                    [
                        ft.Container(
                            ft.Row(
                                [
                                    ft.Image("art/icons/food.svg", width=27, height=27),
                                    ft.Text(
                                        (
                                            "Спасибо, мастер!",
                                            "Мотор готов к приключениям!",
                                            "М-м, энергия!",
                                            "Шестерёнки довольны!",
                                        )[state.feedings % 4],
                                        size=11,
                                        color=INK,
                                        expand=True,
                                    ),
                                ],
                                spacing=6,
                            ),
                            top=12,
                            right=10,
                            width=177,
                            padding=8,
                            bgcolor="#EEFFFFFF",
                            border_radius=13,
                            animate_opacity=200,
                        )
                    ]
                    if fed
                    else []
                ),
                *[
                    ft.Container(
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=color, size=22),
                        top=y,
                        left=x,
                        opacity=1 if reveal else 0,
                        animate_opacity=350,
                        rotate=0.3 if phase else -0.2,
                        animate_rotation=700,
                    )
                    for x, y, color in (
                        (24, 70, "#FFD775"),
                        (63, 32, "#ABF3FF"),
                        (260, 67, "#FFD775"),
                        (278, 142, "#BDB0FF"),
                    )
                ],
                ft.Container(
                    ft.Text(
                        "Новый друг!" if reveal else "Вкусно!" if fed else label,
                        size=11,
                        color="white",
                        weight=ft.FontWeight.BOLD,
                    ),
                    top=12,
                    left=12,
                    bgcolor="#AA33304F",
                    padding=ft.Padding.symmetric(horizontal=11, vertical=7),
                    border_radius=12,
                ),
                ft.Container(
                    ft.Text(
                        f"+{compact(gain)} корма",
                        size=19,
                        weight=ft.FontWeight.BOLD,
                        color="#FFF1AF",
                    ),
                    top=45,
                    right=28,
                    opacity=1 if pressed else 0,
                    offset=ft.Offset(0, 0 if pressed else -0.6),
                    animate_opacity=220,
                    animate_offset=220,
                ),
                ft.Container(
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.TOUCH_APP_ROUNDED, size=15, color="white"),
                            ft.Text(
                                activity
                                if not egg
                                and not pressed
                                and idle_motion in {"siren", "inspect", "hit"}
                                else caption,
                                size=11,
                                color="white",
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        tight=True,
                        spacing=5,
                    ),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    bgcolor="#B333304F",
                    border_radius=16,
                    bottom=11,
                    left=12,
                    right=58,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Container(
                    ft.IconButton(
                        ft.Icons.CLOSE_FULLSCREEN_ROUNDED
                        if expanded
                        else ft.Icons.OPEN_IN_FULL_ROUNDED,
                        key="workshop-collapse" if expanded else "workshop-expand",
                        on_click=expand,
                        icon_color="white",
                        icon_size=21,
                        tooltip="Закрыть сцену"
                        if expanded
                        else "Открыть только мастерскую",
                    ),
                    right=9,
                    bottom=7,
                    bgcolor="#A533304F",
                    border_radius=13,
                ),
            ],
            height=scene_height,
        ),
        key="robot-tap-scene",
        padding=0,
        on_click=on_tap,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )


def incubator_card(session, on_collection=None):
    state = session.state
    egg = ROBOT_BY_ID.get(state.egg_id)

    async def hatch(_):
        session.act("hatch")

    if egg:
        ready = state.egg_is_ready(session.clock())
        remaining = egg_remaining(state, session.clock())
        timed = bool(state.egg_ready_at)
        duration = max(30, egg.hatch_seconds)
        return card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Image(
                                egg.egg_image, width=52, height=58, cache_width=116
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        f"Внутри — {egg.name}",
                                        size=14,
                                        color=INK,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    ft.Text(egg.ability(), size=11, color=MUTED),
                                    ft.Text(
                                        "Готово к открытию!"
                                        if ready
                                        else f"Инкубация: {remaining // 60:02d}:{remaining % 60:02d}"
                                        if timed
                                        else f"Заряд: {state.egg_progress} / {egg.taps} касаний",
                                        size=11,
                                        color=GREEN if ready else state.accent,
                                    ),
                                ],
                                spacing=5,
                                expand=True,
                            ),
                        ],
                        spacing=9,
                    ),
                    ft.ProgressBar(
                        value=max(0, min(1, 1 - remaining / duration))
                        if timed
                        else state.egg_progress / egg.taps,
                        color=GREEN if ready else state.accent,
                        bgcolor="#E8E8F7",
                        height=7,
                        border_radius=5,
                    ),
                    ft.Button(
                        "Открыть яйцо"
                        if ready
                        else "Касания ускоряют таймер"
                        if timed
                        else "Заряжай яйцо касаниями",
                        key="hatch-egg",
                        icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                        on_click=hatch,
                        disabled=not ready,
                        style=button_style(
                            GREEN if ready else state.accent, secondary=not ready
                        ),
                        width=float("inf"),
                    ),
                ],
                spacing=10,
            ),
            padding=13,
        )
    return card(
        ft.Row(
            [
                ft.Icon(ft.Icons.SMART_TOY_ROUNDED, color=state.accent, size=28),
                ft.Column(
                    [
                        ft.Text(
                            f"Твоя команда: {state.robot_count} / {len(ROBOTS)}",
                            size=14,
                            color=INK,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            "Выбирай яйца и развивай способности друзей",
                            size=11,
                            color=MUTED,
                        ),
                    ],
                    spacing=5,
                    expand=True,
                ),
                *(
                    [
                        ft.IconButton(
                            icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                            on_click=on_collection,
                            tooltip="Открыть коллекцию",
                            icon_color=state.accent,
                        )
                    ]
                    if on_collection
                    else []
                ),
            ],
            spacing=10,
        ),
        padding=13,
    )


def team_summary(session):
    state = session.state
    bonuses = [
        (ft.Icons.BOLT_ROUNDED, f"+{state.robot_bonus('click')}", "за касание"),
        (ft.Icons.SMART_TOY_ROUNDED, f"+{state.robot_bonus('auto')}", "монет/с"),
        (
            ft.Icons.NIGHTS_STAY_ROUNDED,
            f"+{state.robot_bonus('offline')}",
            "за минуту отдыха",
        ),
        (ft.Icons.WORK_ROUNDED, f"+{state.robot_bonus('orders')}%", "к заказам"),
    ]
    return card(
        ft.Column(
            [
                ft.Text(
                    "Вся команда помогает вместе",
                    size=14,
                    color=INK,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.ResponsiveRow(
                    [
                        ft.Container(
                            ft.Row(
                                [
                                    ft.Icon(icon, color=state.accent, size=18),
                                    ft.Column(
                                        [
                                            ft.Text(
                                                value,
                                                size=15,
                                                color=INK,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Text(label, size=10, color=MUTED),
                                        ],
                                        spacing=2,
                                        expand=True,
                                    ),
                                ],
                                spacing=7,
                            ),
                            col=6,
                        )
                        for icon, value, label in bonuses
                    ],
                    spacing=8,
                    run_spacing=12,
                ),
                ft.Text(
                    "Выбор персонажа в мастерской не отключает остальных друзей",
                    size=10,
                    color=MUTED,
                ),
            ],
            spacing=13,
        ),
        bgcolor="#EEF0FC",
    )


def robot_card(session, robot, on_home=None):
    state = session.state
    level = state.robot_levels.get(robot.id, 0)
    selected = state.active_robot == robot.id
    incubating = state.egg_id == robot.id
    unlocked = state.level >= robot.level
    maxed = level >= MAX_ROBOT_LEVEL
    price = training_price(robot, level) if level else robot.egg_price
    rarity_name, rarity_color = RARITIES[robot.rarity]
    stored = bool(state.egg_stock.get(robot.id))

    async def choose(_):
        result = session.act("select_robot", robot.id)
        if result.ok and on_home:
            on_home(None)

    async def purchase(_):
        session.act(
            "train_robot" if level else "stock_egg" if stored else "incubate", robot.id
        )

    async def open_workshop(_):
        if on_home:
            on_home(None)

    content = [
        ft.Row(
            [
                ft.Container(
                    robot_actor(
                        robot.id,
                        size=112,
                        motion="feed"
                        if session.fed_robot == robot.id
                        and session.clock() < session.fed_until
                        else "idle",
                        now=session.clock(),
                    )
                    if level
                    else ft.Image(robot.image, width=105, height=112, cache_width=240),
                    bgcolor=tint(rarity_color, 0.83),
                    border_radius=18,
                    opacity=1 if level else 0.8,
                ),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    robot.name,
                                    size=20,
                                    color=INK,
                                    weight=ft.FontWeight.BOLD,
                                    expand=True,
                                ),
                                ft.Icon(
                                    ft.Icons.CHECK_CIRCLE_ROUNDED
                                    if level
                                    else ft.Icons.LOCK_OPEN_ROUNDED
                                    if unlocked
                                    else ft.Icons.LOCK_ROUNDED,
                                    size=18,
                                    color=GREEN if level else MUTED,
                                ),
                            ]
                        ),
                        ft.Text(
                            robot.role,
                            size=11,
                            color=robot.color,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Container(
                            ft.Text(
                                rarity_name,
                                size=10,
                                color=rarity_color,
                                weight=ft.FontWeight.BOLD,
                            ),
                            bgcolor="#CCFFFFFF",
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            border_radius=8,
                        ),
                        ft.Text(robot.ability(level or 1), size=12, color=INK),
                        ft.Text(
                            f"Уровень {level} / {MAX_ROBOT_LEVEL}"
                            if level
                            else f"Яйцо · {robot.hatch_seconds // 60} мин · касания ускоряют"
                            if unlocked
                            else f"С уровня {robot.level}",
                            size=10,
                            color=MUTED,
                        ),
                    ],
                    spacing=6,
                    expand=True,
                ),
            ],
            spacing=12,
        ),
        ft.Text(robot.story, size=11, color=MUTED),
    ]
    if level:
        content.append(care_actions(session, robot.id))
        if not maxed:
            content.append(
                ft.Text(
                    f"Следующий уровень: {robot.ability(level + 1)}",
                    size=11,
                    color=state.accent,
                )
            )
        content.append(
            ft.Row(
                [
                    ft.Button(
                        "Макс. уровень" if maxed else f"Улучшить · {compact(price)}",
                        on_click=purchase,
                        key=f"robot-train-{robot.id}",
                        disabled=maxed or state.coin < price,
                        style=button_style(state.accent, secondary=maxed),
                        expand=True,
                    ),
                    ft.TextButton(
                        "В мастерской" if selected else "Выбрать",
                        key=f"robot-select-{robot.id}",
                        on_click=choose,
                        style=ft.ButtonStyle(color=state.accent),
                    ),
                ],
                spacing=7,
            )
        )
    elif incubating:
        content.append(
            ft.Button(
                "К яйцу в мастерскую",
                on_click=open_workshop,
                style=button_style(state.accent),
                width=float("inf"),
            )
        )
    else:
        label = (
            "В инкубатор из хранилища"
            if stored
            else f"Яйцо · {compact(price)} золота"
            if price
            else "Первое яйцо бесплатно"
        )
        if not unlocked:
            label = f"Откроется на уровне {robot.level}"
        elif state.egg_id:
            label = "Сначала открой текущее яйцо"
        content.append(
            ft.Button(
                label,
                key=f"robot-egg-{robot.id}",
                on_click=purchase,
                disabled=not unlocked
                or bool(state.egg_id)
                or (not stored and state.coin < price),
                style=button_style(state.accent, secondary=not unlocked),
                width=float("inf"),
            )
        )
    return card(
        ft.Column(content, spacing=12),
        padding=15,
        gradient=ft.LinearGradient(
            colors=[tint(rarity_color, 0.72), tint(rarity_color, 0.95), "#FFFFFF"],
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
        ),
        border=ft.Border.all(1.3, tint(rarity_color, 0.45)),
        key=f"robot-card-{robot.id}",
        shadow=ft.BoxShadow(
            blur_radius=18, spread_radius=1, color="#28" + rarity_color[1:]
        ),
    )
