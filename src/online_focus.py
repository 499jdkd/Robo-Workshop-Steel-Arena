"""Expanded human duel; never substitutes a local bot battle."""

import asyncio

import flet as ft

from battle_ui import battle_scene
from display_mode import set_scene_focus
from online_arena import online_for
from ui_shared import INK, MUTED, button_style, card, use_game


@ft.component
def FocusedOnlineBattle(page, session):
    use_game(session)
    online = online_for(session)

    def mounted():
        async def poll():
            while session.ui_alive:
                await asyncio.sleep(2)
                await online.refresh()

        task = page.run_task(poll)
        return lambda: task.cancel() if task is not None else None

    ft.use_effect(mounted, [])

    async def close(_):
        await set_scene_focus(page, session, "")

    match = online.match
    if not match:
        return card(
            ft.Column(
                [
                    ft.Text("Матч ещё не найден", color=INK),
                    ft.Button("Вернуться", on_click=close),
                ]
            )
        )
    side = match["you"]
    other = "b" if side == "a" else "a"
    active = match["result"] == "active"
    your_turn = active and match["state"]["turn"] == side
    controls = [
        ft.Text(
            match["players"][other]["name"],
            size=18,
            color=INK,
            weight=ft.FontWeight.BOLD,
        ),
        ft.Text("Реальный игрок · Равные уровни", size=11, color=MUTED),
        ft.Text(
            "Твой ход" if your_turn else "Ход соперника" if active else "Матч завершён",
            color=session.state.accent,
        ),
        ft.Text(f"Энергия {match['state'][side]['energy']}/10", color=MUTED, size=12),
    ]
    for action, title in [
        ("attack", "Атака"),
        ("guard", "Защита"),
        ("special", "Способность"),
        ("dodge", "Уклонение"),
        ("charge", "Зарядка"),
    ]:

        async def act(_, choice=action):
            await online.command(choice)

        controls.append(
            ft.Button(
                title,
                on_click=act,
                disabled=not your_turn or online.busy,
                style=button_style(session.state.accent, secondary=action != "attack"),
            )
        )
    controls.append(ft.TextButton("Вернуться", on_click=close))
    panel = ft.Column(controls, spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    width = getattr(page, "width", 420) or 420
    if width >= 650:
        return ft.Row(
            [
                ft.Container(
                    battle_scene(
                        page,
                        session,
                        online.view_battle(),
                        focused=True,
                        width_override=width * 0.65,
                    ),
                    expand=2,
                ),
                ft.Container(panel, expand=1),
            ],
            spacing=9,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
    return ft.Column(
        [battle_scene(page, session, online.view_battle(), focused=True), panel],
        spacing=8,
        expand=True,
    )
