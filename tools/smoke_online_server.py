"""Run two independent main-game clients against a real loopback HTTP server.

Uses disposable profiles/database; never modifies player saves or deployment.
"""

import argparse
import asyncio
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
import httpx

from combat_rules import action_error
from game_session import GameSession
from gameplay import GameState
from online_arena import OnlineArena


async def check(url):
    sessions = [GameSession.preview(), GameSession.preview()]
    for session, identity in zip(sessions, ("arachna", "cyclops")):
        session.state = GameState(
            coin=777, robot_levels={identity: 5}, active_robot=identity, egg_id=""
        )
    clients = [OnlineArena(s) for s in sessions]
    a, b = clients
    await asyncio.gather(
        a.connect(url, "HTTP клиент А"), b.connect(url, "HTTP клиент Б")
    )
    assert not a.error and not b.error, (a.error, b.error)
    await a.command("friend_request", b.profile["id"])
    await b.command("friend_accept", a.profile["id"])
    await a.command("queue")
    await b.command("queue")
    await a.refresh()
    assert a.match["id"] == b.match["id"]
    turns = 0
    while a.match["result"] == "active" and turns < 120:
        current = next(c for c in clients if c.match["you"] == a.match["state"]["turn"])
        actor = a.match["state"][a.match["state"]["turn"]]
        action = next(
            choice
            for choice in ("ultimate", "special", "attack", "charge")
            if not action_error(actor, choice)
        )
        await current.command(action)
        assert not current.error, current.error
        other = b if current is a else a
        await other.refresh()
        assert a.match["revision"] == b.match["revision"]
        assert a.match["state"] == b.match["state"]
        turns += 1
        print(f"Confirmed turn {turns}: {action}", flush=True)
    assert a.match["result"] == "finished"
    assert all(
        s.state.coin == 777 and s.state.robot_levels in ({"arachna": 5}, {"cyclops": 5})
        for s in sessions
    )
    a.social_updated = b.social_updated = 0
    await asyncio.gather(a.refresh(), b.refresh())
    assert a.history and b.history
    return dict(
        transport="real HTTP loopback",
        clients=2,
        finished=True,
        turns=turns,
        rules_version=3,
        consistent_state=True,
        offline_progress_preserved=True,
        friends=a.friends[0]["status"],
        ratings=[c.profile["rating"] for c in clients],
        public_deployment=False,
    ), clients


@contextmanager
def test_database(directory, postgres):
    if not postgres:
        yield {"CLICKER_ARENA_DB": str(Path(directory) / "arena.sqlite")}, "sqlite"
        return
    import psycopg
    from psycopg import sql

    url = os.getenv("CLICKER_TEST_POSTGRES_URL", "")
    parsed = urlsplit(url)
    if parsed.scheme not in {"postgres", "postgresql"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise ValueError(
            "Set CLICKER_TEST_POSTGRES_URL to a private loopback test database"
        )
    schema = "robo_test_" + secrets.token_hex(8)
    with psycopg.connect(url, autocommit=True) as db:
        db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    query = dict(parse_qsl(parsed.query))
    query["options"] = "-c search_path=" + schema
    # libpq URLs use percent-encoding; '+' is a literal plus, not a space.
    target = urlunsplit(parsed._replace(query=urlencode(query, quote_via=quote)))
    try:
        yield {"CLICKER_ARENA_DATABASE_URL": target}, "postgresql"
    finally:
        with psycopg.connect(url, autocommit=True) as db:
            db.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres-local", action="store_true")
    args = parser.parse_args()
    (ROOT / ".cache/rework-review").mkdir(parents=True, exist_ok=True)
    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        port = reserve.getsockname()[1]
    with (
        tempfile.TemporaryDirectory(dir=ROOT / ".cache") as directory,
        test_database(directory, args.postgres_local) as (storage, backend),
    ):
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        env.pop("CLICKER_ARENA_DATABASE_URL", None)
        env.pop("RENDER", None)
        env.update(storage)
        log = open(Path(directory) / "server.log", "w", encoding="utf-8")

        def stop(process):
            if process is None:
                return
            if os.name == "nt" and process.poll() is None:
                # Windows' venv redirector may own a second Python process.
                # Terminate only this test's known child tree, not other apps.
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            elif process.poll() is None:
                process.terminate()
            process.wait(timeout=15)

        def start():
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "server.app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=log,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            for _ in range(100):
                try:
                    if (
                        httpx.get(
                            f"http://127.0.0.1:{port}/ready", timeout=2
                        ).status_code
                        == 200
                    ):
                        return process
                except httpx.HTTPError:
                    time.sleep(0.1)
                if process.poll() is not None:
                    raise RuntimeError("Test server failed to start")
            stop(process)
            raise RuntimeError("Test server readiness timed out")

        process = None
        try:
            process = start()
            url = f"http://127.0.0.1:{port}"
            report, clients = asyncio.run(check(url))
            # A real process restart exercises external persistence, not just a
            # second Python object retaining a live connection in memory.
            stop(process)
            process = start()
            for client in clients:
                headers = {"Authorization": "Bearer " + client.credentials["token"]}
                with httpx.Client(base_url=url, headers=headers) as direct:
                    assert direct.get("/me").json() == client.profile
                    assert direct.get("/friends").json() == client.friends
                    assert direct.get("/history").json() == client.history
                    assert (
                        direct.get("/match/current").json()["state"]
                        == client.match["state"]
                    )
            report["server_restart_persistence"] = True
            report["storage"] = backend
            suffix = "-postgres" if args.postgres_local else ""
            output = ROOT / f".cache/rework-review/two-client-http{suffix}.json"
            output.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report))
        finally:
            stop(process)
            log.close()


if __name__ == "__main__":
    main()
