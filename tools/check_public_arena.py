"""Check an owned public server with two clearly named, isolated QA profiles.

Uses friendly invitations, never the public matchmaking queue. Credentials stay
in .cache. Player saves, real opponents and ranked rewards are untouched.
"""

import argparse
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from combat_rules import action_error
from game_session import GameSession
from gameplay import GameState
from online_arena import OnlineArena


class ObservedArena(OnlineArena):
    last_turn = None

    async def request(self, method, path, body=None, **kwargs):
        if method == "POST" and path.endswith("/turn"):
            self.last_turn = (path, deepcopy(body))
        return await super().request(method, path, body, **kwargs)


async def command(client, name, value=""):
    await client.command(name, value)
    assert not client.error, client.error


async def run(url, *, check_disconnect, report_path=None):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError(
            "Use the owned server's plain HTTPS origin, without query parameters"
        )
    url = url.rstrip("/")
    private = (
        ROOT / ".cache/public-arena" / hashlib.sha256(url.encode()).hexdigest()[:16]
    )
    sessions, clients = [], []
    for side, robot in (("A", "arachna"), ("B", "cyclops")):
        session = GameSession.preview()
        session.state = GameState(
            coin=777, robot_levels={robot: 5}, active_robot=robot, egg_id=""
        )
        # MemoryStore still owns only synthetic game data. The directory is
        # used solely for the two QA identities' private authentication files.
        session.store.directory = private / side
        sessions.append(session)
        client = ObservedArena(session)
        clients.append(client)
        await client.connect(url, "QA-Net-" + side)
        assert not client.error, client.error
        assert client.profile["name"] == "QA-Net-" + side, (
            "Refusing to use a non-QA profile"
        )
    a, b = clients
    offline = [s.state.to_dict() for s in sessions]
    await command(a, "friend_request", b.profile["id"])
    await command(b, "friend_accept", a.profile["id"])

    clan_checked = False
    if (
        a.profile["coins"] >= 50
        and not a.profile.get("clan")
        and not b.profile.get("clan")
    ):
        await command(a, "create", "QA-Net-" + a.profile["id"][:8])
        clan = a.clans["your_clan"]
        await command(b, "join", clan)
        await command(a, "edit", "Temporary deployment check|gear")
        await command(a, "promote", b.profile["id"])
        await command(b, "leave")
        await command(a, "leave")
        clan_checked = True

    await command(a, "duel_create")
    await command(b, "duel_join", a.invitation["code"])
    await a.refresh()
    assert a.match["id"] == b.match["id"]
    assert a.match["state"]["mode"] == "friendly"
    profiles_before = [deepcopy(c.profile) for c in clients]
    turns = 0
    duplicate_checked = False
    while a.match["result"] == "active" and turns < 120:
        current = next(c for c in clients if c.match["you"] == a.match["state"]["turn"])
        actor = a.match["state"][a.match["state"]["turn"]]
        action = next(
            choice
            for choice in ("ultimate", "special", "attack", "charge")
            if not action_error(actor, choice)
        )
        await command(current, action)
        if turns == 0:
            path, body = current.last_turn
            duplicate = await current.request("POST", path, body)
            assert duplicate == current.match
            duplicate_checked = True
        await (b if current is a else a).refresh()
        assert not a.error and not b.error, (a.error, b.error)
        assert a.match["revision"] == b.match["revision"]
        assert a.match["state"] == b.match["state"]
        turns += 1
        print(f"Public friendly duel: confirmed turn {turns}", flush=True)
    assert a.match["result"] == "finished"
    assert [c.profile for c in clients] == profiles_before, (
        "Friendly battle changed ratings or currency"
    )

    # Reconnect from disk-backed QA identities through fresh main-game clients.
    for old, side in zip(clients, ("A", "B")):
        session = GameSession.preview()
        session.store.directory = private / side
        fresh = OnlineArena(session)
        await fresh.connect(url, "QA-Net-" + side)
        assert not fresh.error, fresh.error
        assert fresh.profile == old.profile
        assert fresh.history and fresh.history[0]["id"] == a.match["id"]
        assert any(f["status"] == "accepted" for f in fresh.friends)

    timeout_checked = False
    if check_disconnect:
        await command(a, "duel_create")
        await command(b, "duel_join", a.invitation["code"])
        await a.refresh()
        print("Checking server turn timeout (46 seconds)", flush=True)
        await asyncio.sleep(46)
        await a.refresh()
        await b.refresh()
        assert a.match["result"] == b.match["result"] == "finished"
        assert a.match["state"]["finish_reason"] == "disconnect-timeout"
        await a.refresh()
        assert [c.profile for c in clients] == profiles_before
        timeout_checked = True

    assert [s.state.to_dict() for s in sessions] == offline
    await command(a, "friend_remove", b.profile["id"])
    report = dict(
        server=url,
        public_https=True,
        clients=2,
        profiles="explicit QA profiles",
        mode="friendly, no ranked matchmaking",
        turns=turns,
        consistent_state=True,
        duplicate_command_idempotent=duplicate_checked,
        identities_reused=True,
        history_and_friends_persisted=True,
        clan_create_edit_join_roles_leave=clan_checked,
        disconnect_timeout=timeout_checked,
        ranked_rewards_unchanged=True,
        offline_progress_preserved=True,
        two_physical_devices=False,
    )
    out = report_path or ROOT / ".cache/rework-review/public-arena-v26.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--check-disconnect", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.url, check_disconnect=args.check_disconnect, report_path=args.report))
