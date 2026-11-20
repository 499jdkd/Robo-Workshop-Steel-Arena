"""Scene-only arena with readable projectiles and one atomic turn commit."""

import asyncio

import flet as ft

from display_mode import set_scene_focus
from game_animation import animated_scene
from robot_arena import (
    ELEMENT_COLORS,
    ELEMENT_NAMES,
    ELEMENTS,
    INTENT_NAMES,
    enemy_intent,
)
from robot_catalog import ROBOT_BY_ID


def health_panel(name, hp, maximum, element, color):
    return ft.Container(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            name,
                            size=13,
                            weight=ft.FontWeight.BOLD,
                            color="white",
                            expand=True,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(f"{hp}/{maximum}", size=11, color="#CAD9EE"),
                    ],
                    spacing=5,
                ),
                ft.ProgressBar(
                    value=hp / max(1, maximum),
                    color=color,
                    bgcolor="#533E5575",
                    height=6,
                    border_radius=7,
                ),
                ft.Text(ELEMENT_NAMES[element], size=11, color=ELEMENT_COLORS[element]),
            ],
            spacing=4,
        ),
        padding=9,
        bgcolor="#BF14243D",
        border_radius=13,
        expand=True,
    )


def battle_scene(
    page, session, battle, *, preview=False, width_override=None, focused=None
):
    focused = (
        session.focus_scene in {"battle", "online-battle"}
        if focused is None
        else focused
    )
    width = max(245, width_override or (getattr(page, "width", None) or 420) - 28)
    page_height = getattr(page, "height", None) or 840
    wide = (getattr(page, "width", None) or 420) >= 650
    height = (
        min(520, max(175, page_height - 110))
        if focused and wide
        else 250
        if preview
        else 270
    )
    visual = (
        session.arena_visual
        if session.arena_visual.get("battle_id") == battle["id"]
        else {}
    )
    phase, action = visual.get("phase", "idle"), visual.get("action", "")
    intent = (
        battle.get("last_intent")
        if visual and phase not in {"approach", "flight"}
        else enemy_intent(battle)
    )
    intent = intent or enemy_intent(battle)
    before_commit = phase in {"approach", "flight"}
    before_reply = phase in {"approach", "flight", "impact", "enemy-flight"}
    hp = (
        visual.get("before_hp", battle["player_hp"])
        if before_reply
        else battle["player_hp"]
    )
    if before_reply and not before_commit:
        hp = min(battle["player_max_hp"], hp + battle.get("last_heal", 0))
    enemy_hp = (
        visual.get("before_enemy_hp", battle["enemy_hp"])
        if before_commit
        else battle["enemy_hp"]
    )
    if before_reply and not before_commit:
        enemy_hp = max(0, enemy_hp - battle.get("last_enemy_heal", 0))
    if phase in {"impact", "enemy-flight", "reply", "counter-flight"}:
        enemy_hp = min(battle["enemy_max_hp"], enemy_hp + battle.get("last_counter", 0))
    player, enemy = ROBOT_BY_ID[battle["robot_id"]], ROBOT_BY_ID[battle["enemy_id"]]

    async def expand(_):
        await set_scene_focus(
            page,
            session,
            ""
            if focused
            else "online-battle"
            if battle.get("kind") == "human-ranked"
            else "battle",
        )

    children = [
        ft.Image(
            f"art/arena/stage_{(battle['stage'] // 5) % 5}.svg",
            width=float("inf"),
            height=height,
            fit=ft.BoxFit.FILL,
        ),
        ft.Container(
            animated_scene(session, arena=True, battle=battle, expanded=focused),
            left=0,
            right=0,
            top=0,
            bottom=0,
        ),
        ft.Container(
            ft.Row(
                [
                    health_panel(
                        battle.get("player_name", player.name),
                        hp,
                        battle["player_max_hp"],
                        ELEMENTS[player.id],
                        "#65E4B4",
                    ),
                    ft.Text("VS", size=12, color="#CCE4FF", weight=ft.FontWeight.BOLD),
                    health_panel(
                        battle.get(
                            "enemy_name",
                            ("Страж-бот " if battle.get("boss") else "Тренер-бот ")
                            + enemy.name,
                        ),
                        enemy_hp,
                        battle["enemy_max_hp"],
                        ELEMENTS[enemy.id],
                        "#C19CFF",
                    ),
                ],
                spacing=7,
            ),
            top=9,
            left=9,
            right=9,
        ),
        ft.Container(
            ft.Text(
                "Предстоящий бой"
                if preview
                else f"PvP · Ход {battle['turn'] + 1}"
                if battle.get("kind") == "human-ranked"
                else f"Ход {battle['turn'] + (phase == 'idle')} · {INTENT_NAMES[intent]}",
                size=10,
                color="white",
                max_lines=2,
                text_align=ft.TextAlign.CENTER,
            ),
            bottom=9,
            left=11,
            right=54,
            padding=7,
            bgcolor="#A51A2947",
            border_radius=10,
        ),
        ft.Container(
            ft.IconButton(
                ft.Icons.CLOSE_FULLSCREEN_ROUNDED
                if focused
                else ft.Icons.OPEN_IN_FULL_ROUNDED,
                key="arena-scene-collapse" if focused else "arena-scene-expand",
                on_click=expand,
                icon_color="white",
                icon_size=21,
                tooltip="Закрыть поле боя" if focused else "Открыть только поле боя",
            ),
            bottom=6,
            right=7,
            bgcolor="#B2192B49",
            border_radius=12,
        ),
    ]
    for x, text, color, visible in (
        (
            0.75,
            f"−{battle.get('last_counter', 0) if phase == 'counter-hit' else max(0, battle.get('last_damage', 0) - battle.get('last_counter', 0))}",
            "#FFE1A2",
            phase in {"impact", "counter-hit"} and bool(battle.get("last_damage")),
        ),
        (
            0.23,
            "МИМО"
            if battle.get("last_dodged")
            else f"−{battle.get('last_incoming', 0)}",
            "#8AF5D5" if battle.get("last_dodged") else "#FFB3BF",
            phase == "reply"
            and bool(battle.get("last_dodged") or battle.get("last_incoming")),
        ),
    ):
        children.append(
            ft.Container(
                ft.Text(text, size=23, color=color, weight=ft.FontWeight.BOLD),
                left=max(5, width * x - 30),
                top=height * 0.33,
                opacity=1 if visible else 0,
                offset=ft.Offset(0, -0.3 if visible else 0.4),
                animate_offset=300,
                animate_opacity=150,
            )
        )
    return ft.Container(
        ft.Stack(children, height=height, clip_behavior=ft.ClipBehavior.HARD_EDGE),
        border_radius=22,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        bgcolor="#152943",
        key="arena-stage",
    )


def turn_timing(choice):
    return {
        "quick": (0.22, 0.42, 0.22),
        "ultimate": (0.72, 1.15, 0.38),
        "special": (0.55, 0.85, 0.30),
        "pierce": (0.55, 0.65, 0.25),
    }.get(choice, (0.40, 0.72, 0.25))


def battle_action_error(battle, choice):
    if battle.get("rules_version") == 3:
        from combat_rules import action_error, current_actor

        return action_error(current_actor(battle), choice)
    if choice == "special" and (battle["cooldown"] or battle.get("focus", 2) < 2):
        return "Нужны 2 фокуса и готовый навык"
    if choice == "dodge" and (battle.get("dodge_cooldown", 0) or battle.get("focus", 2) < 1):
        return "Нужен 1 фокус и готовый уворот"
    from armory import equipped_weapon

    equipment, _ = equipped_weapon(battle)
    if equipment and choice in {"attack", "special"} and battle.get("battery", 12) < equipment.energy:
        return "Батарея разряжена: используй фокус или щит"
    return ""


async def animate_turn(session, choice, identity, expected):
    battle = session.state.battle
    if (
        not session.ui_alive
        or session.arena_animating
        or battle.get("id") != identity
        or battle.get("turn") != expected
        or battle.get("result") != "active"
    ):
        return False
    from combat_rules import ATTACKS

    error = battle_action_error(battle, choice)
    if error:
        session.tell(error)
        session.notify()
        return False
    speed = min(2.0, max(1.0, session.battle_speed))
    prepare_seconds, flight_seconds, impact_seconds = turn_timing(choice)
    session.arena_animation_id += 1
    generation = session.arena_animation_id
    session.arena_animating = True
    session.arena_visual = dict(
        battle_id=identity,
        phase="approach",
        action=choice,
        before_hp=battle["player_hp"],
        before_enemy_hp=battle["enemy_hp"],
        speed=speed,
        flight_seconds=flight_seconds,
        prepare_seconds=prepare_seconds,
        impact_seconds=impact_seconds,
    )

    def valid():
        return (
            session.ui_alive
            and not session._paused
            and generation == session.arena_animation_id
            and session.state.battle.get("id") == identity
        )

    async def frame(phase, duration):
        if not valid():
            return False
        session.arena_visual["phase"] = phase
        session.notify()
        await asyncio.sleep(duration / speed)
        return valid()

    try:
        if not await frame("approach", prepare_seconds):
            return False
        if choice in ATTACKS and not await frame("flight", flight_seconds):
            return False
        result = session.act("battle_turn", choice, identity, expected)
        if not result.ok:
            return False
        if not await frame("impact", impact_seconds):
            return True
        battle = session.state.battle
        own_kill = battle["result"] == "win" and not battle.get("last_counter")
        if not own_kill:
            duration = (
                0.4
                if battle.get("last_stunned") or battle.get("last_intent") == "windup"
                else 0.72
            )
            if not await frame("enemy-flight", duration):
                return True
            if not await frame("reply", 0.25):
                return True
            if battle.get("last_counter"):
                if not await frame("counter-flight", 0.65):
                    return True
                if not await frame("counter-hit", 0.22):
                    return True
        if battle["result"] == "win":
            await frame("victory", 0.4)
        return True
    finally:
        if generation == session.arena_animation_id:
            session.arena_animating = False
            session.arena_visual = {}
            if session.ui_alive:
                session.notify()
