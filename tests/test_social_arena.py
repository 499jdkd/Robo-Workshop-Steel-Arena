import json
import sqlite3
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
from server.arena_service import ArenaService, RuleError
from server.rules import ROBOTS, WEAPONS


class SocialArenaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = 1000000
        self.path = Path(self.temp.name) / "arena.sqlite"
        self.service = ArenaService(self.path, clock=lambda: self.now)
        self.a, self.b, self.c = [
            self.service.register(name) for name in ("Первый", "Второй", "Третий")
        ]

    def tearDown(self):
        self.temp.cleanup()

    def test_new_catalogs_and_authoritative_bounded_stats(self):
        self.assertEqual(len(ROBOTS), 32)
        self.assertEqual(len(WEAPONS), 20)
        self.service.enqueue(self.a["id"], "arachna", "emp")
        match = self.service.enqueue(self.b["id"], "cyclops", "ion")["match"]
        self.assertEqual(match["state"]["rules_version"], 3)
        for side in ("a", "b"):
            actor = match["state"][side]
            self.assertLessEqual(actor["max_hp"], 150)
            self.assertLessEqual(actor["attack"], 21)
        before = self.service.current(self.a["id"])
        with self.assertRaises(RuleError):
            self.service.turn(self.a["id"], match["id"], 0, "unready-super", "ultimate")
        self.assertEqual(self.service.current(self.a["id"]), before)

    def test_modes_do_not_match_each_other_and_friendly_cannot_farm_rewards(self):
        self.service.enqueue(self.a["id"], "spark", "plasma", "ranked")
        self.assertTrue(
            self.service.enqueue(self.b["id"], "volt", "sniper", "balanced")["waiting"]
        )
        invite = self.service.invite(self.a["id"], "spark", "plasma")
        match = self.service.join_invite(self.b["id"], invite["code"], "volt", "sniper")
        before = [self.service.profile(p["id"]) for p in (self.a, self.b)]
        self.service.turn(self.b["id"], match["id"], 0, "friendly-resign", "resign")
        self.assertEqual(
            before, [self.service.profile(p["id"]) for p in (self.a, self.b)]
        )
        self.assertEqual(self.service.history(self.a["id"])[0]["mode"], "friendly")

    def test_invite_is_atomic_private_single_use_and_expires(self):
        invite = self.service.invite(self.a["id"], "omega", "disc")
        with self.assertRaises(RuleError):
            self.service.join_invite(self.a["id"], invite["code"], "spark", "plasma")

        def enter(player):
            try:
                return self.service.join_invite(
                    player, invite["code"], "volt", "sniper"
                )
            except RuleError:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(enter, [self.b["id"], self.c["id"]]))
        self.assertEqual(sum(item is not None for item in results), 1)
        match = next(item for item in results if item)
        with self.assertRaises(RuleError):
            self.service.invite(self.a["id"], "spark", "plasma")
        self.service.turn(self.a["id"], match["id"], 0, "invite-resign", "resign")
        fresh = self.service.invite(self.a["id"], "spark", "plasma")
        self.now += 601
        with self.assertRaises(RuleError):
            self.service.join_invite(self.b["id"], fresh["code"], "spark", "plasma")

    def test_friend_request_requires_recipient_acceptance(self):
        self.service.friend_action(self.a["id"], "request", self.b["id"])
        with self.assertRaises(RuleError):
            self.service.friend_action(self.a["id"], "accept", self.b["id"])
        with self.assertRaises(RuleError):
            self.service.friend_action(self.c["id"], "accept", self.a["id"])
        records = self.service.friend_action(self.b["id"], "accept", self.a["id"])
        self.assertEqual(records[0]["status"], "accepted")
        self.service.friend_action(self.a["id"], "remove", self.b["id"])
        self.assertEqual(self.service.friends(self.b["id"]), [])

    def test_clan_roles_metadata_search_and_permissions(self):
        clan = self.service.clan_action(self.a["id"], "create", "Мастера")["your_clan"]
        self.service.clan_action(self.b["id"], "join", clan)
        with self.assertRaises(RuleError):
            self.service.clan_action(self.b["id"], "edit", "Подмена|bolt")
        self.service.clan_action(self.a["id"], "edit", "Мирные инженеры|shield")
        self.service.clan_action(self.a["id"], "promote", self.b["id"])
        record = self.service.clans(self.a["id"], "Маст")["clans"][0]
        self.assertEqual(record["description"], "Мирные инженеры")
        self.assertEqual(record["emblem"], "shield")
        self.assertEqual(
            next(p for p in record["roster"] if p["id"] == self.b["id"])["role"],
            "officer",
        )
        self.assertEqual(
            self.service.clans(self.a["id"], "Несуществующий")["clans"], []
        )
        with self.assertRaises(RuleError):
            self.service.clan_action(self.b["id"], "kick", self.a["id"])
        self.service.clan_action(self.a["id"], "leave")
        self.service.clan_action(self.b["id"], "edit", "Новый глава|gear")

    def test_timeout_and_history_are_idempotent(self):
        self.service.enqueue(self.a["id"], "spark", "plasma")
        match = self.service.enqueue(self.b["id"], "volt", "sniper")["match"]
        self.now += 46
        finished = self.service.current(self.a["id"])
        self.assertEqual(finished["state"]["finish_reason"], "disconnect-timeout")
        profile = self.service.profile(self.b["id"])
        for _ in range(3):
            self.service.current(self.a["id"])
        self.assertEqual(profile, self.service.profile(self.b["id"]))
        self.assertEqual(len(self.service.history(self.b["id"])), 1)

    def test_existing_database_is_archived_once_before_migration(self):
        db = sqlite3.connect(self.path)
        try:
            db.execute("PRAGMA user_version=1")
            db.commit()
        finally:
            db.close()
        ArenaService(self.path)
        archive = Path(str(self.path) + ".before-social-v2.backup")
        self.assertTrue(archive.is_file())
        saved = archive.read_bytes()
        ArenaService(self.path)
        self.assertEqual(archive.read_bytes(), saved)
        self.assertEqual(self.service.authenticate(self.a["token"]), self.a["id"])

    def test_ranked_clan_war_contributions_and_claim_are_atomic(self):
        first = self.service.clan_action(self.a["id"], "create", "Синие мастера")["your_clan"]
        second = self.service.clan_action(self.b["id"], "create", "Зелёные мастера")["your_clan"]
        self.service.clan_action(self.a["id"], "war", second)
        self.service.clan_action(self.a["id"], "war", second)
        for number in range(2):
            self.service.enqueue(self.a["id"], "spark", "plasma")
            match = self.service.enqueue(self.b["id"], "volt", "sniper")["match"]
            self.service.turn(self.b["id"], match["id"], 0, f"war-resign-{number}", "resign")
        wars = self.service.clans(self.a["id"])["wars"]
        self.assertEqual(len(wars), 1)
        score = wars[0]["score_a"] if wars[0]["a"] == first else wars[0]["score_b"]
        self.assertEqual(score, 2)
        self.now += 604800
        before = self.service.profile(self.a["id"])["coins"]
        self.service.clan_action(self.a["id"], "war_claim", wars[0]["id"])
        with self.assertRaises(RuleError):
            self.service.clan_action(self.a["id"], "war_claim", wars[0]["id"])
        self.assertEqual(self.service.profile(self.a["id"])["coins"], before + 40)
