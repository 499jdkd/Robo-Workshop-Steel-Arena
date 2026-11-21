"""Application-level semantic music state; no Python animation/audio clock."""

import json
import flet as ft


@ft.control("GameMusic")
class GameMusic(ft.Container):
    payload: str = "{}"
    on_sound_change: ft.ControlEventHandler | None = None


def music_payload(session, selected_index=0):
    return {
        "track": "arena" if selected_index == 2 or session.focus_scene in {"battle", "online-battle"} else "workshop",
        "sound": session.motion_sound,
        "paused": session._paused,
    }


def music_control(session, selected_index=0):
    def sound_change(event):
        data = event.data
        if isinstance(data, str):
            data = json.loads(data)
        if isinstance(data, dict) and isinstance(data.get("enabled"), bool):
            session.presentation(sound=data["enabled"])

    return GameMusic(
        key="application-music", width=0, height=0,
        payload=json.dumps(music_payload(session, selected_index)),
        on_sound_change=sound_change,
    )
