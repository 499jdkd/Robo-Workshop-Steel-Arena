"""Run the real server contract on a private, disposable local PostgreSQL.

Set CLICKER_TEST_POSTGRES_URL only for a loopback test database. Each test owns a
random schema; no public or production database is accepted or reset.
"""

import os
import secrets
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "src"), str(ROOT)]
import test_social_arena as contracts

from server.arena_service import ArenaService, RuleError
from server.database import PostgresConnection

TEST_URL = os.getenv("CLICKER_TEST_POSTGRES_URL", "")


@unittest.skipUnless(
    TEST_URL, "Local PostgreSQL is optional; use CLICKER_TEST_POSTGRES_URL"
)
class PostgresArenaTests(contracts.SocialArenaTests):
    def setUp(self):
        import psycopg
        from psycopg import sql

        if urlsplit(TEST_URL).hostname not in {"127.0.0.1", "localhost", "::1"}:
            self.fail("PostgreSQL integration tests accept only a local test database")
        self.schema = "robo_test_" + secrets.token_hex(8)
        with psycopg.connect(TEST_URL, autocommit=True) as connection:
            connection.execute(
                sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema))
            )

        def cleanup():
            with psycopg.connect(TEST_URL, autocommit=True) as connection:
                connection.execute(
                    sql.SQL("DROP SCHEMA {} CASCADE").format(
                        sql.Identifier(self.schema)
                    )
                )

        self.addCleanup(cleanup)
        parsed = urlsplit(TEST_URL)
        query = dict(parse_qsl(parsed.query))
        query["options"] = "-c search_path=" + self.schema
        self.path = urlunsplit(parsed._replace(query=urlencode(query, quote_via=quote)))
        self.now = 1794752222.125
        self.service = ArenaService(self.path, clock=lambda: self.now)
        with self.service.tx() as db:
            self.assertIsInstance(db, PostgresConnection)
            self.assertEqual(
                db.execute("SELECT current_schema()").fetchone()[0], self.schema
            )
        self.a, self.b, self.c = [
            self.service.register(name) for name in ("Первый", "Второй", "Третий")
        ]

    def tearDown(self):
        pass

    @unittest.skip(
        "SQLite file backup has its own contract; PostgreSQL uses external storage"
    )
    def test_existing_database_is_archived_once_before_migration(self):
        pass

    def test_recreated_service_keeps_identities_friends_clan_and_timestamp_precision(
        self,
    ):
        self.service.friend_action(self.a["id"], "request", self.b["id"])
        self.service.friend_action(self.b["id"], "accept", self.a["id"])
        clan = self.service.clan_action(self.a["id"], "create", "Постоянный клан")[
            "your_clan"
        ]
        self.service.enqueue(self.a["id"], "spark", "plasma")
        match = self.service.enqueue(self.b["id"], "volt", "sniper")["match"]
        fresh = ArenaService(self.path, clock=lambda: self.now)
        self.assertEqual(fresh.authenticate(self.a["token"]), self.a["id"])
        self.assertEqual(fresh.profile(self.a["id"])["clan"], clan)
        self.assertEqual(fresh.friends(self.a["id"])[0]["status"], "accepted")
        self.assertAlmostEqual(
            fresh.current(self.a["id"])["deadline"], self.now + 45, places=4
        )
        self.now += 44.5
        self.assertEqual(fresh.current(self.a["id"])["result"], "active")
        self.now += 1
        self.assertEqual(fresh.current(self.a["id"])["result"], "finished")
        self.assertEqual(fresh.history(self.a["id"])[0]["id"], match["id"])

    def test_constraint_rollback_duplicate_rewards_and_cross_instance_turn_race(self):
        from concurrent.futures import ThreadPoolExecutor

        clan = self.service.clan_action(self.a["id"], "create", "Один клан")[
            "your_clan"
        ]
        with self.assertRaises(RuleError):
            self.service.clan_action(self.b["id"], "create", "Один клан")
        self.assertEqual(self.service.profile(self.b["id"])["coins"], 100)
        self.service.clan_action(self.b["id"], "join", clan)
        with self.service.tx() as db:
            db.execute(
                "INSERT INTO contributions VALUES(?,?,?,20)",
                (clan, self.a["id"], self.service.week()),
            )
        before = self.service.profile(self.a["id"])["coins"]
        self.service.clan_action(self.a["id"], "mission")
        with self.assertRaises(RuleError):
            self.service.clan_action(self.a["id"], "mission")
        self.assertEqual(self.service.profile(self.a["id"])["coins"], before + 50)
        self.service.enqueue(self.a["id"], "spark", "plasma")
        match = self.service.enqueue(self.b["id"], "volt", "sniper")["match"]
        other = ArenaService(self.path, clock=lambda: self.now)

        def turn(service):
            return service.turn(
                self.a["id"], match["id"], 0, "same-command-twice", "attack"
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(turn, (self.service, other)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.service.current(self.a["id"])["revision"], 1)
