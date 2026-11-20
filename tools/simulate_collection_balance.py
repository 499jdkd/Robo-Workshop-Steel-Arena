"""Bounded and reproducible strategy-vs-spam simulations; no player data."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gameplay import GameState, perform
from robot_designs import DESIGNS
from robot_arena import suggested_action
from combat_rules import action_error


def run(robot, stage, level, policy, serial):
    state = GameState(
        level=30,
        robot_levels={robot: level},
        active_robot=robot,
        egg_id="",
        arena_stage=stage,
        battle_serial=serial,
        robot_energy={robot: 100},
    )
    assert perform(state, "battle_start", [robot], 1_800_000_000).ok
    for _ in range(60):
        battle = state.battle
        if battle["result"] != "active":
            break
        choice = suggested_action(battle) if policy == "tactical" else "attack"
        if action_error(battle["combatants"]["a"], choice):
            choice = "charge"
        result = perform(
            state, "battle_turn", [choice, battle["id"], battle["turn"]], 1_800_000_001
        )
        assert result.ok, (robot, stage, choice, result.message)
    return state.battle["result"] == "win", state.battle["turn"]


def main():
    rows = []
    for stage, level in [(0, 1), (4, 3), (8, 5), (12, 6), (19, 10)]:
        for policy in ("spam", "tactical"):
            wins = turns = count = 0
            for robot in DESIGNS:
                for seed in range(4):
                    won, t = run(robot, stage, level, policy, seed * 17)
                    wins += won
                    turns += t
                    count += 1
            rows.append(
                dict(
                    stage=stage,
                    robot_level=level,
                    policy=policy,
                    battles=count,
                    win_rate=round(wins / count, 3),
                    average_turns=round(turns / count, 1),
                )
            )
    out = ROOT / ".cache/rework-review/balance.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
