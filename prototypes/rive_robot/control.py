"""Semantic Flet messages; no per-frame Python loop and no save writes."""

import flet as ft
from flet_rive import Rive

STATES = ("idle", "move", "attack", "defend", "charge", "hit", "victory", "defeat")


@ft.control("RobotRive")
class RobotRive(Rive):
    action: str = "idle"
    command_id: int = 0
    autonomous: bool = True
    arena: bool = False
    paused: bool = False
    reduced_motion: bool = False
    renderer: str = "rive"


def visual_action(motion):
    """Adapter for the existing battle/workshop vocabulary, without mutations."""
    return {
        "guard": "defend",
        "special": "attack",
        "feed": "charge",
        "happy": "victory",
        "dodge": "move",
        "siren": "charge",
        "inspect": "idle",
    }.get(motion, motion if motion in STATES else "idle")
