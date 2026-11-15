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

from server.rules import ACTIONS, ROBOTS, WEAPONS, arena_actor, combat_power, league, resolve_action
from server.social import SocialService

class RuleError(ValueError):
    pass


class ArenaService(SocialService):
    def __init__(self, path, clock=time.time):
        self.path, self.clock = str(path), clock
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        if Path(path).exists():
            # SQLite backup includes WAL; preserve the pre-social schema once.
            original=sqlite3.connect(self.path)
            try:
                version=original.execute('PRAGMA user_version').fetchone()[0]
                archive=Path(self.path+'.before-social-v2.backup')
                if version<2 and not archive.exists():
                    target=sqlite3.connect(str(archive))
                    try:original.backup(target)
                    finally:target.close()
            finally:original.close()
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
            self.social_schema(db)

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
                "SELECT id,name,rating,coins,wins,clan,clan_role FROM players WHERE id=?",
                (player,),
            ).fetchone()
            if not row:
                raise RuleError("Профиль не найден")
            result=dict(row);result['league']=league(row['rating']);result['friend_code']=row['id']
            return result

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
            state['finish_reason']='disconnect-timeout'
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

    def _create_match(self,db,a,b,robot_a,weapon_a,robot_b,weapon_b,mode):
        identity=secrets.token_hex(12)
        state=dict(turn='a',winner=None,a=arena_actor(robot_a,weapon_a),b=arena_actor(robot_b,weapon_b),
                   last={},rules_version=3,mode=mode)
        db.execute("INSERT INTO matches VALUES(?,?,?,?,0,'active',?)",(identity,a,b,json.dumps(state),self.clock()))
        db.execute('DELETE FROM queue WHERE player IN (?,?)',(a,b))
        return db.execute('SELECT * FROM matches WHERE id=?',(identity,)).fetchone()

    def enqueue(self, player, robot, weapon, mode='ranked'):
        if robot not in ROBOTS or weapon not in WEAPONS or mode not in {'ranked','balanced'}:
            raise RuleError('??????????? ?????, ?????? ??? ?????')
        power=combat_power(robot,weapon)
        with self.tx() as db:
            active=db.execute("SELECT * FROM matches WHERE (a=? OR b=?) AND result='active' LIMIT 1",(player,player)).fetchone()
            if active:
                value=self._public(db,active,player)
                if value['result']=='active':return {'match':value}
            db.execute('DELETE FROM queue WHERE joined<?',(self.clock()-65,))
            me=db.execute('SELECT rating FROM players WHERE id=?',(player,)).fetchone()
            if not me:raise RuleError('??????? ?? ??????')
            opponent=db.execute("""SELECT q.*,p.rating FROM queue q JOIN players p ON p.id=q.player
                WHERE q.player!=? AND q.mode=? AND ABS(p.rating-?)<=400 AND ABS(q.power-?)<=100 ORDER BY joined LIMIT 1""",(player,mode,me['rating'],power)).fetchone()
            if not opponent:
                db.execute("""INSERT INTO queue(player,robot,weapon,joined,mode,power) VALUES(?,?,?,?,?,?)
                    ON CONFLICT(player) DO UPDATE SET robot=excluded.robot,weapon=excluded.weapon,
                    joined=excluded.joined,mode=excluded.mode,power=excluded.power""",(player,robot,weapon,self.clock(),mode,power))
                return {'waiting':True,'message':'???? ????????? ??????. ???? ?? ????????? ? PvP'}
            row=self._create_match(db,opponent['player'],player,opponent['robot'],opponent['weapon'],robot,weapon,mode)
            return {'match':self._public(db,row,player)}

    def cancel_queue(self, player):
        with self.tx() as db:
            db.execute("DELETE FROM queue WHERE player=?", (player,))
        return {"waiting": False}

    def _finish(self, db, row, state, winner):
        if row["result"] != "active":
            return
        loser = "b" if winner == "a" else "a"
        state["winner"] = winner
        if winner is not None and state.get('mode','ranked')=='ranked':
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
            action not in ACTIONS|{"resign"}
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
            actor,target=state[side],state[other]
            # Upgrade an in-progress legacy match without touching its HP/energy.
            if state.get('rules_version')!=3:
                for key in ('a','b'):
                    previous=state[key];fresh=arena_actor(previous['robot'],previous['weapon'])
                    fresh.update({k:v for k,v in previous.items() if k in fresh});state[key]=fresh
                state['rules_version']=3
                actor,target=state[side],state[other]
            if action!='resign':
                event=resolve_action(actor,target,action,seed=int(identity[:8],16)+revision)
                if not event['ok']:raise RuleError(event['error'])
                state['last']={**event,'actor':side}
            else:state['last']=dict(actor=side,action=action,damage=0,heal=0,weapon=actor['weapon'])
            state['turn']=other
            if action=='resign':state['finish_reason']='resign'
            if action == "resign" or not target["hp"]:
                self._finish(db, row, state, other if action == "resign" else side)
            elif revision>=119:
                state['finish_reason']='turn-limit'
                score={key:state[key]['hp']/state[key]['max_hp'] for key in ('a','b')}
                self._finish(db,row,state,None if score['a']==score['b'] else max(score,key=score.get))
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

    def clans(self, player, search=""):
        with self.tx() as db:
            profile = db.execute(
                "SELECT clan FROM players WHERE id=?", (player,)
            ).fetchone()
            result = []
            for row in db.execute(
                "SELECT c.*,COUNT(p.id) members FROM clans c LEFT JOIN players p ON p.clan=c.id WHERE c.name LIKE ? GROUP BY c.id ORDER BY c.rating DESC,c.xp DESC,c.id LIMIT 50",
                ("%"+search[:24]+"%",)
            ):
                entry = dict(row)
                entry["level"] = 1 + math.isqrt(entry["xp"] // 50)
                entry["mission_wins"] = db.execute(
                    "SELECT COALESCE(SUM(wins),0) FROM contributions WHERE clan=? AND week=?",
                    (entry["id"], self.week()),
                ).fetchone()[0]
                entry['roster']=[{**dict(member),'role':'owner' if member['id']==entry['owner'] else member['clan_role']}
                    for member in db.execute('SELECT id,name,rating,clan_role FROM players WHERE clan=? ORDER BY rating DESC',(entry['id'],))] if entry['id']==profile[0] else []
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
        if action in {'edit','promote','demote','kick'}:return self.clan_edit(player,action,value)
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
                db.execute("UPDATE players SET clan=NULL,clan_role='member' WHERE id=?", (player,))
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
