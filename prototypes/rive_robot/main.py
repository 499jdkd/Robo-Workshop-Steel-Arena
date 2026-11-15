"""Isolated visual lab: never imports GameSession, LocalStore or AdMob."""

import flet as ft
from control import STATES, RobotRive


def main(page: ft.Page):
    page.title = "Clicker · Rive prototype"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0A1525"
    page.padding = 16
    page.window.width, page.window.height = 1000, 760
    actor = RobotRive(src="spark.riv", expand=True, key="spark-rive-prototype")
    caption = ft.Text(
        "Прототип Искры · сохранение игры не используется", color="#AAC4D8", size=12
    )

    def action(name):
        def handler(_):
            actor.action, actor.command_id = name, actor.command_id + 1
            actor.update()

        return handler

    def arena(event):
        actor.arena = event.control.value
        actor.action, actor.command_id = "idle", actor.command_id + 1
        actor.update()

    def auto(event):
        actor.autonomous = event.control.value
        actor.update()

    page.add(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            "Искра / Motion Lab", size=24, weight=ft.FontWeight.BOLD
                        ),
                        caption,
                    ],
                    wrap=True,
                ),
                ft.Container(
                    actor,
                    expand=True,
                    border_radius=22,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                ),
                ft.Row(
                    [
                        ft.Button(
                            name.capitalize(),
                            on_click=action(name),
                            key="motion-" + name,
                        )
                        for name in STATES
                    ],
                    wrap=True,
                ),
                ft.Row(
                    [
                        ft.Switch("Арена", on_change=arena),
                        ft.Switch(
                            "Самостоятельное движение", value=True, on_change=auto
                        ),
                    ],
                    wrap=True,
                ),
                ft.Text(
                    "Осмотр: двойное нажатие, перетаскивание и щипок. На компьютере — также колесо мыши.",
                    size=11,
                    color="#AAC4D8",
                ),
            ],
            expand=True,
            spacing=12,
        )
    )


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
