"""Authoritative human PvP/clans. SQLite transactions; no seeded/fake players.

Run one process with a persistent disk. Shared SQL/Postgres is the upgrade path
for multiple workers; never put a separate SQLite file on each replica.
"""

import hashlib
import json
import math
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

WEAPONS = {
    "plasma": (15, 2),
    "sniper": (23, 4),
    "rocket": (26, 5),
    "laser": (17, 4),
    "electric": (16, 3),
    "machinegun": (16, 2),
    "sword": (20, 3),
    "shield": (9, 2),
    "flame": (18, 4),
    "drone": (14, 3),
}
ROBOTS = {"spark", "volt", "flora", "forge", "nova", "glacier", "aegis", "solar"}


class RuleError(ValueError):
    pass


class ArenaService:
    def __init__(self, path, clock=time.time):
        self.path, self.clock = str(path), clock
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.tx() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS players(id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL,
              name TEXT NOT NULL, rating INTEGER NOT NULL DEFAULT 1000, coins INTEGER NOT NULL DEFAULT 100,
              wins INTEGER NOT NULL DEFAULT 0, clan TEXT, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS queue(player TEXT PRIMARY KEY, robot TEXT NOT NULL, weapon TEXT NOT NULL, joined REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS matches(id TEXT PRIMARY KEY, a TEXT NOT NULL, b TEXT NOT NULL,
              state TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, result TEXT NOT NULL DEFAULT 'active', updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS commands(match_id TEXT, command TEXT, player TEXT, response TEXT,
              PRIMARY KEY(match_id, command, player));
            CREATE TABLE IF NOT EXISTS clans(id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, owner TEXT NOT NULL,
              xp INTEGER NOT NULL DEFAULT 0, rating INTEGER NOT NULL DEFAULT 1000);
            CREATE TABLE IF NOT EXISTS contributions(clan TEXT, player TEXT, week INTEGER, wins INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY(clan,player,week));
            CREATE TABLE IF NOT EXISTS claims(player TEXT, reward TEXT, PRIMARY KEY(player,reward));
            CREATE TABLE IF NOT EXISTS wars(id TEXT PRIMARY KEY, a TEXT NOT NULL, b TEXT NOT NULL, week INTEGER NOT NULL,
              score_a INTEGER NOT NULL DEFAULT 0, score_b INTEGER NOT NULL DEFAULT 0,
              UNIQUE(a,b,week));
            """)

    @contextmanager
    def tx(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def week(self):
        return int((self.clock() + 259200) // 604800)

    def register(self, name):
        name = str(name).strip()[:24]
        if len(name) < 2:
            raise RuleError("Имя: от 2 до 24 символов")
        identity, token = secrets.token_hex(12), secrets.token_urlsafe(32)
        with self.tx() as db:
            db.execute(
                "INSERT INTO players(id,token_hash,name,created) VALUES(?,?,?,?)",
                (
                    identity,
                    hashlib.sha256(token.encode()).hexdigest(),
                    name,
                    self.clock(),
                ),
            )
        return {"id": identity, "token": token}

    def authenticate(self, token):
        with self.tx() as db:
            row = db.execute(
                "SELECT id FROM players WHERE token_hash=?",
                (hashlib.sha256(token.encode()).hexdigest(),),
            ).fetchone()
        if not row:
            raise RuleError("Требуется вход в соревновательный профиль")
        return row[0]

    def profile(self, player):
        with self.tx() as db:
            row = db.execute(
                "SELECT id,name,rating,coins,wins,clan FROM players WHERE id=?",
                (player,),
            ).fetchone()
            if not row:
                raise RuleError("Профиль не найден")
            return dict(row)

    def ranking(self):
        with self.tx() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,name,rating,wins FROM players ORDER BY rating DESC,wins DESC,id LIMIT 50"
                )
            ]

    def _public(self, db, row, player):
        state = json.loads(row["state"])
        if row["result"] == "active" and self.clock() - row["updated"] > 45:
            self._finish(db, row, state, "b" if state["turn"] == "a" else "a")
            row = db.execute(
                "SELECT * FROM matches WHERE id=?", (row["id"],)
            ).fetchone()
            state = json.loads(row["state"])
        names = {
            side: dict(
                db.execute(
                    "SELECT id,name,rating FROM players WHERE id=?", (row[side],)
                ).fetchone()
            )
            for side in ("a", "b")
        }
        return {
            "id": row["id"],
            "revision": row["revision"],
            "result": row["result"],
            "state": state,
            "players": names,
            "you": "a" if row["a"] == player else "b",
            "deadline": row["updated"] + 45,
            "kind": "human-ranked",
        }

    def current(self, player):
        with self.tx() as db:
            row = db.execute(
                "SELECT * FROM matches WHERE (a=? OR b=?) ORDER BY updated DESC LIMIT 1",
                (player, player),
            ).fetchone()
            if row:
                return self._public(db, row, player)
            return None

    def enqueue(self, player, robot, weapon):
        if robot not in ROBOTS or weapon not in WEAPONS:
            raise RuleError("Неизвестный робот или оружие")
        with self.tx() as db:
            active = db.execute(
                "SELECT * FROM matches WHERE (a=? OR b=?) AND result='active' LIMIT 1",
                (player, player),
            ).fetchone()
            if active:
                value = self._public(db, active, player)
                if value["result"] == "active":
                    return {"match": value}
            db.execute("DELETE FROM queue WHERE joined<?", (self.clock() - 65,))
            me = db.execute(
                "SELECT rating FROM players WHERE id=?", (player,)
            ).fetchone()
            opponent = db.execute(
                "SELECT q.*,p.rating FROM queue q JOIN players p ON p.id=q.player WHERE q.player!=? AND ABS(p.rating-?)<=400 ORDER BY joined LIMIT 1",
                (player, me["rating"]),
            ).fetchone()
            if not opponent:
                db.execute(
                    "INSERT INTO queue VALUES(?,?,?,?) ON CONFLICT(player) DO UPDATE SET robot=excluded.robot,weapon=excluded.weapon,joined=excluded.joined",
                    (player, robot, weapon, self.clock()),
                )
                return {
                    "waiting": True,
                    "message": "Ищем реального игрока. Боты не участвуют в рейтинге PvP",
                }
            a, b = opponent["player"], player
            identity = secrets.token_hex(12)
            state = {
                "turn": "a",
                "winner": None,
                "a": {
                    "hp": 120,
                    "energy": 8,
                    "guard": False,
                    "dodge": False,
                    "cooldown": 0,
                    "robot": opponent["robot"],
                    "weapon": opponent["weapon"],
                },
                "b": {
                    "hp": 120,
                    "energy": 8,
                    "guard": False,
                    "dodge": False,
                    "cooldown": 0,
                    "robot": robot,
                    "weapon": weapon,
                },
                "last": {},
            }
            db.execute(
                "INSERT INTO matches VALUES(?,?,?,?,0,'active',?)",
                (identity, a, b, json.dumps(state), self.clock()),
            )
            db.execute("DELETE FROM queue WHERE player IN (?,?)", (a, b))
            row = db.execute("SELECT * FROM matches WHERE id=?", (identity,)).fetchone()
            return {"match": self._public(db, row, player)}

    def cancel_queue(self, player):
        with self.tx() as db:
            db.execute("DELETE FROM queue WHERE player=?", (player,))
        return {"waiting": False}

    def _finish(self, db, row, state, winner):
        if row["result"] != "active":
            return
        loser = "b" if winner == "a" else "a"
        state["winner"] = winner
        db.execute(
            "UPDATE players SET rating=rating+16,coins=coins+25,wins=wins+1 WHERE id=?",
            (row[winner],),
        )
        db.execute(
            "UPDATE players SET rating=MAX(100,rating-16),coins=coins+5 WHERE id=?",
            (row[loser],),
        )
        clans = {
            side: db.execute(
                "SELECT clan FROM players WHERE id=?", (row[side],)
            ).fetchone()[0]
            for side in ("a", "b")
        }
        clan = clans[winner]
        if clan:
            db.execute("UPDATE clans SET xp=xp+20 WHERE id=?", (clan,))
            db.execute(
                "INSERT INTO contributions VALUES(?,?,?,1) ON CONFLICT(clan,player,week) DO UPDATE SET wins=wins+1",
                (clan, row[winner], self.week()),
            )
        if clan and clans[loser] and clan != clans[loser]:
            first, second = sorted((clan, clans[loser]))
            field = "score_a" if clan == first else "score_b"
            db.execute(
                f"UPDATE wars SET {field}={field}+1 WHERE a=? AND b=? AND week=?",
                (first, second, self.week()),
            )
        db.execute(
            "UPDATE matches SET state=?,result='finished',revision=revision+1,updated=? WHERE id=?",
            (json.dumps(state), self.clock(), row["id"]),
        )

    def turn(self, player, identity, revision, command, action):
        if (
            action not in {"attack", "guard", "charge", "special", "dodge", "resign"}
            or not 8 <= len(command) <= 80
        ):
            raise RuleError("Некорректная команда")
        with self.tx() as db:
            row = db.execute(
                "SELECT * FROM matches WHERE id=? AND (a=? OR b=?)",
                (identity, player, player),
            ).fetchone()
            if not row:
                raise RuleError("Этот бой недоступен")
            duplicate = db.execute(
                "SELECT response FROM commands WHERE match_id=? AND command=? AND player=?",
                (identity, command, player),
            ).fetchone()
            if duplicate:
                return json.loads(duplicate[0])
            current = self._public(db, row, player)
            if current["result"] != "active" or current["revision"] != revision:
                raise RuleError("Ход уже выполнен: обнови бой")
            state = current["state"]
            side = current["you"]
            other = "b" if side == "a" else "a"
            if action != "resign" and state["turn"] != side:
                raise RuleError("Сейчас ход соперника")
            actor, target = state[side], state[other]
            target_dodged = target.get("dodge", False)
            damage, heal = 0, 0
            actor["guard"] = actor["dodge"] = False
            base, cost = WEAPONS[actor["weapon"]]
            if action in {"attack", "special"}:
                needed = cost + (2 if action == "special" else 0)
                if actor["energy"] < needed or (
                    action == "special" and actor["cooldown"]
                ):
                    raise RuleError("Нужна зарядка или перезарядка способности")
                actor["energy"] -= needed
                damage = base
                if action == "special":
                    damage = round(base * 1.5)
                    actor["cooldown"] = 3
                    if actor["robot"] == "flora":
                        damage = max(1, base // 2)
                        heal = min(28, 120 - actor["hp"])
                        actor["hp"] += heal
                    if actor["robot"] in {"aegis", "forge"}:
                        actor["guard"] = True
                    if actor["robot"] == "spark":
                        damage = round(base * 1.65)
                    if actor["robot"] == "glacier":
                        target["energy"] = max(0, target["energy"] - 3)
                    if actor["robot"] == "aegis":
                        heal = min(12, 120 - actor["hp"])
                        actor["hp"] += heal
                        damage = base
                    if actor["robot"] == "solar":
                        heal = min(10, 120 - actor["hp"])
                        actor["hp"] += heal
                if target["dodge"]:
                    damage = 0
                    target["dodge"] = False
                elif target["guard"] and not (
                    action == "special" and actor["robot"] in {"nova", "solar"}
                ):
                    damage = round(
                        damage
                        * (0.65 if actor["weapon"] in {"laser", "sniper"} else 0.35)
                    )
                target["hp"] = max(0, target["hp"] - damage)
            elif action == "guard":
                actor["guard"] = True
                actor["energy"] = min(10, actor["energy"] + 2)
            elif action == "charge":
                actor["energy"] = min(10, actor["energy"] + 5)
            elif action == "dodge":
                if actor["energy"] < 2:
                    raise RuleError("Нужно 2 энергии")
                actor["dodge"] = True
                actor["energy"] -= 2
            actor["cooldown"] = max(0, actor["cooldown"] - 1)
            state["last"] = {
                "dodged": bool(target_dodged and action in {"attack", "special"}),
                "actor": side,
                "action": action,
                "damage": damage,
                "heal": heal,
                "weapon": actor["weapon"],
            }
            state["turn"] = other
            if action == "special" and actor["robot"] == "volt" and target["hp"]:
                state["turn"] = side
            if action == "resign" or not target["hp"]:
                self._finish(db, row, state, other if action == "resign" else side)
            else:
                db.execute(
                    "UPDATE matches SET state=?,revision=revision+1,updated=? WHERE id=?",
                    (json.dumps(state), self.clock(), identity),
                )
            result = self._public(
                db,
                db.execute("SELECT * FROM matches WHERE id=?", (identity,)).fetchone(),
                player,
            )
            db.execute(
                "INSERT INTO commands VALUES(?,?,?,?)",
                (identity, command, player, json.dumps(result)),
            )
            return result

    def clans(self, player):
        with self.tx() as db:
            profile = db.execute(
                "SELECT clan FROM players WHERE id=?", (player,)
            ).fetchone()
            result = []
            for row in db.execute(
                "SELECT c.*,COUNT(p.id) members FROM clans c LEFT JOIN players p ON p.clan=c.id GROUP BY c.id ORDER BY c.xp DESC,c.id LIMIT 50"
            ):
                entry = dict(row)
                entry["level"] = 1 + math.isqrt(entry["xp"] // 50)
                entry["mission_wins"] = db.execute(
                    "SELECT COALESCE(SUM(wins),0) FROM contributions WHERE clan=? AND week=?",
                    (entry["id"], self.week()),
                ).fetchone()[0]
                result.append(entry)
            wars = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM wars WHERE week>=? ORDER BY week DESC,id",
                    (self.week() - 1,),
                )
            ]
            return {
                "clans": result,
                "your_clan": profile[0],
                "wars": wars,
                "week": self.week(),
            }

    def clan_action(self, player, action, value=""):
        with self.tx() as db:
            me = db.execute("SELECT * FROM players WHERE id=?", (player,)).fetchone()
            clan = me["clan"]
            if action == "create":
                name = value.strip()[:24]
                if clan or me["coins"] < 50 or len(name) < 3:
                    raise RuleError(
                        "Создание: 50 жетонов, имя от 3 символов, без текущего клана"
                    )
                identity = secrets.token_hex(8)
                try:
                    db.execute(
                        "INSERT INTO clans(id,name,owner) VALUES(?,?,?)",
                        (identity, name, player),
                    )
                except sqlite3.IntegrityError:
                    raise RuleError("Это имя клана занято") from None
                db.execute(
                    "UPDATE players SET clan=?,coins=coins-50 WHERE id=?",
                    (identity, player),
                )
            elif action == "join":
                if (
                    clan
                    or not db.execute(
                        "SELECT id FROM clans WHERE id=?", (value,)
                    ).fetchone()
                ):
                    raise RuleError(
                        "Сначала выйди из текущего клана или выбери существующий"
                    )
                if (
                    db.execute(
                        "SELECT COUNT(*) FROM players WHERE clan=?", (value,)
                    ).fetchone()[0]
                    >= 30
                ):
                    raise RuleError("Клан заполнен")
                db.execute("UPDATE players SET clan=? WHERE id=?", (value, player))
            elif action == "leave":
                owner = db.execute(
                    "SELECT owner FROM clans WHERE id=?", (clan,)
                ).fetchone()
                if owner and owner[0] == player:
                    successor = db.execute(
                        "SELECT id FROM players WHERE clan=? AND id!=? ORDER BY id LIMIT 1",
                        (clan, player),
                    ).fetchone()
                    if successor:
                        db.execute(
                            "UPDATE clans SET owner=? WHERE id=?", (successor[0], clan)
                        )
                    else:
                        db.execute("DELETE FROM clans WHERE id=?", (clan,))
                db.execute("UPDATE players SET clan=NULL WHERE id=?", (player,))
            elif action == "donate":
                if not clan or me["coins"] < 10:
                    raise RuleError("Нужно 10 PvP-жетонов и членство в клане")
                db.execute("UPDATE players SET coins=coins-10 WHERE id=?", (player,))
                db.execute("UPDATE clans SET xp=xp+10 WHERE id=?", (clan,))
            elif action == "mission":
                total = db.execute(
                    "SELECT COALESCE(SUM(wins),0) FROM contributions WHERE clan=? AND week=?",
                    (clan, self.week()),
                ).fetchone()[0]
                own = db.execute(
                    "SELECT wins FROM contributions WHERE clan=? AND player=? AND week=?",
                    (clan, player, self.week()),
                ).fetchone()
                if not clan or total < 20 or not own or own[0] < 1:
                    raise RuleError(
                        "Нужно 20 общих побед недели и хотя бы одна твоя победа"
                    )
                try:
                    db.execute(
                        "INSERT INTO claims VALUES(?,?)",
                        (player, f"mission:{clan}:{self.week()}"),
                    )
                except sqlite3.IntegrityError:
                    raise RuleError("Награда уже получена") from None
                db.execute("UPDATE players SET coins=coins+50 WHERE id=?", (player,))
            elif action == "war_claim":
                war = db.execute("SELECT * FROM wars WHERE id=?", (value,)).fetchone()
                if (
                    not war
                    or war["week"] >= self.week()
                    or war["score_a"] == war["score_b"]
                ):
                    raise RuleError("Война ещё идёт или закончилась вничью")
                winner = war["a"] if war["score_a"] > war["score_b"] else war["b"]
                own = db.execute(
                    "SELECT wins FROM contributions WHERE clan=? AND player=? AND week=?",
                    (winner, player, war["week"]),
                ).fetchone()
                if clan != winner or not own or own[0] < 1:
                    raise RuleError("Награда участникам победившего клана")
                try:
                    db.execute(
                        "INSERT INTO claims VALUES(?,?)", (player, "war:" + value)
                    )
                except sqlite3.IntegrityError:
                    raise RuleError("Награда войны уже получена") from None
                db.execute("UPDATE players SET coins=coins+40 WHERE id=?", (player,))
                settled = db.execute(
                    "INSERT OR IGNORE INTO claims VALUES(?,?)",
                    ("clan:" + winner, "war:" + value),
                ).rowcount
                if settled:
                    db.execute(
                        "UPDATE clans SET rating=rating+30,xp=xp+100 WHERE id=?",
                        (winner,),
                    )
            elif action == "war":
                if (
                    not clan
                    or clan == value
                    or not db.execute(
                        "SELECT id FROM clans WHERE id=?", (value,)
                    ).fetchone()
                ):
                    raise RuleError("Выбери другой существующий клан")
                if (
                    db.execute(
                        "SELECT owner FROM clans WHERE id=?", (clan,)
                    ).fetchone()[0]
                    != player
                ):
                    raise RuleError("Войну объявляет глава клана")
                a, b = sorted((clan, value))
                db.execute(
                    "INSERT OR IGNORE INTO wars(id,a,b,week) VALUES(?,?,?,?)",
                    (secrets.token_hex(8), a, b, self.week()),
                )
            else:
                raise RuleError("Неизвестное действие клана")
        return self.clans(player)
