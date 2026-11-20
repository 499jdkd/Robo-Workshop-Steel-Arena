"""Reproduce Volt training balance on synthetic states, without player saves."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from armory import equip_battle
from gameplay import GameState
from robot_arena import new_battle, suggested_action, take_turn


def simulate():
    rows = []
    for level in (1, 4, 10, 20):
        for stage in range(50):
            for sample in range(3):
                state = GameState(
                    robot_levels={"volt": level}, active_robot="volt", egg_id="",
                    arena_stage=stage, arena_difficulty="training",
                )
                battle = new_battle("volt", level, stage, 1000 + sample)
                equip_battle(state, battle)
                before = {key: battle[key] for key in (
                    "player_max_hp", "player_attack", "enemy_max_hp", "enemy_attack",
                )}
                while battle["result"] == "active" and battle["turn"] < 70:
                    action = suggested_action(battle)
                    result = take_turn(battle, action, battle["id"], battle["turn"])
                    if not result.ok:
                        raise AssertionError((stage, level, action, result.message))
                rows.append({
                    "level": level, "stage": stage, "sample": sample,
                    "enemy": battle["enemy_id"], "boss": battle["boss"],
                    "initial": before, "result": battle["result"],
                    "turns": battle["turn"], "remaining_hp": battle["player_hp"],
                    "enemy_remaining_hp": battle["enemy_hp"],
                })
    summaries = []
    for level in (1, 4, 10, 20):
        cases = [row for row in rows if row["level"] == level]
        summaries.append({
            "level": level, "cases": len(cases),
            "wins": sum(row["result"] == "win" for row in cases),
            "losses": sum(row["result"] == "loss" for row in cases),
            "stalled": sum(row["result"] == "active" for row in cases),
            "max_turns": max(row["turns"] for row in cases),
        })
    return {
        "scenario": "Volt training route stages 0-49 at levels 1,4,10,20",
        "cases": len(rows), "strategy": "existing suggested_action, deterministic seeds",
        "real_player_state_used": False, "server_touched": False,
        "balance_changed": False,
        "limitations": [
            "Synthetic strategy benchmark; not a human playtest or PvP result.",
            "Late-route boss mechanics and the 60-turn limit remain enabled in training.",
        ],
        "summary": summaries, "details": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / ".cache/volt-refinement/qa/training-balance.json")
    args = parser.parse_args()
    report = simulate()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "details"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
