"""Small articulated robot actors: independent head, arms and rolling wheels."""

import math
from dataclasses import dataclass

import flet as ft

from robot_catalog import ROBOT_BY_ID


@dataclass(frozen=True)
class Pose:
    x: float = 0
    y: float = 0
    tilt: float = 0
    head: float = 0
    arm: float = 0
    wheel: float = 0
    eyes: float = 1


def pose_for(motion="idle", now=0, *, facing=1):
    """Absolute transforms, never multiplied by the previous animation state."""
    sway = math.sin(int(now) * 0.65)
    x = 7 * sway
    y, tilt, head, arm = -2 * abs(sway), 0, 0.025 * sway, 0.045 * sway
    if motion in {"attack", "special"}:
        x, y, tilt, head, arm = (
            37 * facing,
            -5,
            -0.06 * facing,
            -0.08 * facing,
            -0.95 * facing,
        )
    elif motion == "hit":
        x, y, tilt, head, arm = -15 * facing, 2, 0.09 * facing, 0.15 * facing, 0.2
    elif motion == "dodge":
        x, y, tilt, head, arm = -28 * facing, -12, -0.13 * facing, 0.1, -0.35
    elif motion == "guard":
        x, y, head, arm = -4 * facing, 0, -0.02, -0.85
    elif motion in {"feed", "happy", "charge"}:
        x, y, head, arm = (
            (13 + 3 * sway) * facing,
            -5 - 2 * sway,
            (-0.08 + 0.05 * sway) * facing,
            -0.65 + 0.12 * sway,
        )
    elif motion == "victory":
        x, y, head, arm = 5 * sway, -10, -0.08, -1.5
    elif motion == "inspect":
        x, y, head, arm = 0, -2, 0.16 * facing, -0.4
    elif motion == "siren":
        x, y, head, arm = 0, -4, -0.1 * sway, -0.8
    # Rolling angle is distance / wheel radius; reverses with the translation.
    return Pose(
        x,
        y,
        tilt,
        head,
        arm,
        x / 21.5,
        0.12 if int(now * 2) % 13 == 0 and motion == "idle" else 1,
    )


def workshop_activity(now, span=42):
    phase = now % 32
    if phase < 10:
        return -span + phase * span / 5, "Исследую мастерскую", "idle", 1
    if phase < 14:
        return span, "Оп! Пора разворачиваться", "hit" if phase < 11 else "inspect", -1
    if phase < 24:
        return span - (phase - 14) * span / 5, "Проверяю, всё ли на месте", "idle", -1
    if phase < 28:
        return -span, "Здесь пригодится фонарик", "inspect", 1
    return -span, "Пиу-пиу! Проверка сигнала", "siren", 1


def robot_actor(
    robot_id, *, size=220, motion="idle", now=0, facing=1, travel=0, opponent=False
):
    if robot_id not in {'spark','volt','flora','forge','nova','glacier','aegis','solar'}:
        # Collection/profile thumbnails are static exports of the actual Rive
        # artboard; only the focused robot consumes an animation ticker.
        return ft.Image(ROBOT_BY_ID[robot_id].image,width=size,height=size,fit=ft.BoxFit.CONTAIN)
    pose = pose_for(motion, now, facing=facing)
    s = size / 240
    mobile = ROBOT_BY_ID[robot_id].mobility == "tracks"
    hover = ROBOT_BY_ID[robot_id].mobility == "hover"
    animation = ft.Animation(270, ft.AnimationCurve.EASE_IN_OUT)
    parts = []
    for left, sign in ((24, 1), (149, -1)):
        parts.append(
            ft.Container(
                ft.Image(f"art/rig/{robot_id}_arm.svg", width=50 * s, height=90 * s),
                left=left * s,
                top=110 * s,
                width=50 * s,
                height=90 * s,
                rotate=ft.Rotate(pose.arm * sign, alignment=ft.Alignment.TOP_CENTER),
                animate_rotation=animation,
            )
        )
    parts.append(
        ft.Container(
            ft.Image(f"art/rig/{robot_id}_body.svg", width=220 * s, height=150 * s),
            left=0,
            top=90 * s,
        )
    )
    if mobile:
        for x in (39, 137):
            parts.append(
                ft.Container(
                    ft.Image("art/rig/wheel.svg", width=43 * s, height=43 * s),
                    left=x * s,
                    top=185 * s,
                    width=43 * s,
                    height=43 * s,
                    rotate=(pose.x + travel) / 21.5,
                    animate_rotation=animation,
                    key=f"wheel-{robot_id}-{x}",
                )
            )
    face = [ft.Image(f"art/rig/{robot_id}_head.svg", width=220 * s, height=110 * s)]
    for x in (77, 127):
        face.append(
            ft.Container(
                left=x * s,
                top=(49 if pose.eyes == 1 else 55) * s,
                width=14 * s,
                height=16 * s * pose.eyes,
                bgcolor="#FFB3CA" if opponent else "#74F3FF",
                border_radius=7 * s,
                animate=ft.Animation(160),
                shadow=ft.BoxShadow(blur_radius=8 * s, color="#704ADCEB"),
            )
        )
    mouth = (
        "oh"
        if motion == "hit"
        else "focus"
        if motion in {"attack", "special", "guard"}
        else "smile"
    )
    face.append(
        ft.Container(
            ft.Image(f"art/rig/mouth_{mouth}.svg", width=25 * s, height=20 * s),
            left=97 * s,
            top=69 * s,
        )
    )
    parts.append(
        ft.Container(
            ft.Stack(face, width=220 * s, height=110 * s),
            top=(-3 if hover else 0) * s,
            left=0,
            rotate=pose.head,
            animate_rotation=animation,
            offset=ft.Offset(0, -0.018 if int(now) % 2 else 0.018),
            animate_offset=700,
        )
    )
    return ft.Container(
        ft.Stack(
            parts, width=220 * s, height=240 * s, clip_behavior=ft.ClipBehavior.NONE
        ),
        width=220 * s,
        height=240 * s,
        offset=ft.Offset(pose.x / 220, pose.y / 240),
        animate_offset=animation,
        rotate=pose.tilt,
        animate_rotation=animation,
        key=f"actor-{robot_id}",
    )
