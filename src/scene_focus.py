"""Only the workshop or battle scene is opened in landscape, with its controls."""

import asyncio

import flet as ft

from arena_screen import action_panel
from battle_ui import battle_scene
from display_mode import set_scene_focus
from robot_arena import BATTLE_ENERGY, enemy_for, new_battle
from robot_ui import robot_scene
from ui_shared import GREEN, INK, MUTED, button_style, card, use_game


@ft.component
def FocusedScene(page, session):
    state = use_game(session)
    pressed, set_pressed = ft.use_state(False)
    gain, set_gain = ft.use_state(0)
    pulse = ft.use_ref(False)
    width, height = (
        getattr(page, "width", None) or 420,
        getattr(page, "height", None) or 840,
    )

    async def tapped(_):
        if not session.ui_alive:
            return
        result = session.workshop_tap()
        if pulse.current:
            return
        pulse.current = True
        set_gain(result.coins)
        set_pressed(True)
        try:
            await asyncio.sleep(0.15)
            if session.ui_alive:
                set_pressed(False)
        finally:
            pulse.current = False

    async def close(_):
        await set_scene_focus(page, session, "")

    if session.focus_scene == "robot":
        from robot_preview import preview_controls, preview_stage

        identity = session.inspection_id
        scene = preview_stage(session, identity, expanded=True, on_expand=close,
                              height=max(210, height - 40) if width >= 650 else min(400, height * .55))
        controls = preview_controls(session, identity)
        if width >= 650:
            return ft.Row([
                ft.Container(scene, expand=2),
                ft.Container(ft.Column([controls], scroll=ft.ScrollMode.AUTO), expand=1),
            ], expand=True, spacing=10, vertical_alignment=ft.CrossAxisAlignment.START)
        return ft.Column([scene, controls], expand=True, spacing=10, scroll=ft.ScrollMode.AUTO)
    if session.focus_scene == "workshop":
        return ft.Container(
            robot_scene(
                session,
                pressed=pressed,
                gain=gain,
                on_tap=tapped,
                expanded=True,
                width=max(260, width - 10),
                height=max(200, height - 92),
            ),
            expand=True,
        )
    if session.focus_scene == "online-battle":
        from online_focus import FocusedOnlineBattle

        return FocusedOnlineBattle(page=page, session=session)
    battle = state.battle
    identity = state.active_robot or next(iter(state.robot_levels), None)
    if not identity:
        return card(
            ft.Column(
                [
                    ft.Text("Сначала открой первого робота", color=INK),
                    ft.Button("Вернуться", on_click=close),
                ]
            )
        )
    if not battle:
        battle = new_battle(
            identity, state.robot_levels[identity], state.arena_stage, 0
        )
        from armory import equip_battle

        equip_battle(state, battle)
    active = battle.get("result") == "active" and battle.get("id", 0) > 0
    animating = session.arena_animating and session.arena_visual.get(
        "battle_id"
    ) == battle.get("id")

    async def start(_):
        session.act("battle_start", identity)

    async def leave(_):
        session.act("battle_leave")

    if active or animating:
        panel = ft.Column(
            [
                action_panel(session, wide=width >= 650),
                ft.TextButton(
                    "Завершить бой", on_click=leave, key="focused-arena-leave"
                ),
            ],
            spacing=5,
            scroll=ft.ScrollMode.AUTO,
        )
    else:
        enemy = enemy_for(state.arena_stage)
        panel = ft.Column(
            [
                card(
                    ft.Column(
                        [
                            ft.Text(
                                "Победа!"
                                if battle.get("result") == "win"
                                else "Следующий соперник",
                                size=19,
                                color=INK,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(enemy["name"], size=13, color=MUTED),
                            ft.Text(
                                f"Награда: {enemy['reward']} золота + 4 корма + детали",
                                size=11,
                                color=GREEN,
                            ),
                            ft.Button(
                                "На арену · 20 заряда",
                                on_click=start,
                                key="focused-arena-start",
                                disabled=state.robot_energy.get(identity, 70)
                                < BATTLE_ENERGY,
                                style=button_style(state.accent),
                                width=float("inf"),
                            ),
                            ft.TextButton("Вернуться в лигу", on_click=close),
                        ],
                        spacing=11,
                    )
                ),
            ],
            spacing=6,
            scroll=ft.ScrollMode.AUTO,
        )
    if width >= 650:
        scene_width = max(280, width * 0.67 - 22)
        return ft.Row(
            [
                ft.Container(
                    battle_scene(
                        page,
                        session,
                        battle,
                        preview=not active and not animating,
                        width_override=scene_width,
                        focused=True,
                    ),
                    expand=2,
                ),
                ft.Container(panel, expand=1),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START,
            expand=True,
        )
    return ft.Column(
        [
            battle_scene(
                page,
                session,
                battle,
                preview=not active and not animating,
                focused=True,
            ),
            panel,
        ],
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
