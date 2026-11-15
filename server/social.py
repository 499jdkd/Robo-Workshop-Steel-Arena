"""Real persistent friends, invite duels, match history and clan metadata."""

import json
import secrets

from server.database import record_schema_version, table_columns


class SocialService:
    def social_schema(self, db):
        additions = {
            "players": {"clan_role": "TEXT NOT NULL DEFAULT 'member'"},
            "queue": {
                "mode": "TEXT NOT NULL DEFAULT 'ranked'",
                "power": "INTEGER NOT NULL DEFAULT 0",
            },
            "clans": {
                "description": "TEXT NOT NULL DEFAULT ''",
                "emblem": "TEXT NOT NULL DEFAULT 'gear'",
            },
        }
        for table, columns in additions.items():
            present = table_columns(db, table)
            for column, definition in columns.items():
                if column not in present:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        db.executescript("""
          CREATE TABLE IF NOT EXISTS friendships(a TEXT,b TEXT,status TEXT NOT NULL,requester TEXT NOT NULL,
            PRIMARY KEY(a,b));
          CREATE TABLE IF NOT EXISTS duels(code TEXT PRIMARY KEY,host TEXT NOT NULL,robot TEXT NOT NULL,
            weapon TEXT NOT NULL,expires DOUBLE PRECISION NOT NULL,match_id TEXT);
        """)
        record_schema_version(db, 2)

    def history(self, player):
        with self.tx() as db:
            rows = db.execute(
                "SELECT * FROM matches WHERE (a=? OR b=?) AND result!='active' ORDER BY updated DESC LIMIT 30",
                (player, player),
            ).fetchall()
            result = []
            for row in rows:
                state = json.loads(row["state"])
                side = "a" if row["a"] == player else "b"
                other = "b" if side == "a" else "a"
                opponent = db.execute(
                    "SELECT name FROM players WHERE id=?", (row[other],)
                ).fetchone()
                result.append(
                    dict(
                        id=row["id"],
                        opponent=opponent[0],
                        won=state.get("winner") == side,
                        draw=state.get("winner") is None,
                        mode=state.get("mode", "ranked"),
                        finished=row["updated"],
                        robot=state[side]["robot"],
                        turns=row["revision"],
                        reason=state.get("finish_reason", "battle"),
                    )
                )
            return result

    def friends(self, player):
        with self.tx() as db:
            return [
                dict(row)
                for row in db.execute(
                    """SELECT p.id,p.name,p.rating,f.status,f.requester
                FROM friendships f JOIN players p ON p.id=CASE WHEN f.a=? THEN f.b ELSE f.a END
                WHERE f.a=? OR f.b=? ORDER BY p.name LIMIT 100""",
                    (player, player, player),
                )
            ]

    def friend_action(self, player, action, other):
        from server.arena_service import RuleError

        if action not in {"request", "accept", "remove"} or player == other:
            raise RuleError("Выбери другого игрока")
        a, b = sorted((player, other))
        with self.tx() as db:
            if not db.execute("SELECT id FROM players WHERE id=?", (other,)).fetchone():
                raise RuleError("Игрок не найден")
            record = db.execute(
                "SELECT * FROM friendships WHERE a=? AND b=?", (a, b)
            ).fetchone()
            if action == "remove":
                db.execute("DELETE FROM friendships WHERE a=? AND b=?", (a, b))
            elif action == "accept":
                if (
                    not record
                    or record["requester"] == player
                    or record["status"] != "pending"
                ):
                    raise RuleError("Нет входящего приглашения")
                db.execute(
                    "UPDATE friendships SET status='accepted' WHERE a=? AND b=?", (a, b)
                )
            else:
                count = db.execute(
                    "SELECT COUNT(*) FROM friendships WHERE a=? OR b=?",
                    (player, player),
                ).fetchone()[0]
                if count >= 100:
                    raise RuleError("Список друзей заполнен")
                db.execute(
                    "INSERT INTO friendships VALUES(?,?,'pending',?) ON CONFLICT DO NOTHING",
                    (a, b, player),
                )
        return self.friends(player)

    def invite(self, player, robot, weapon):
        from server.arena_service import RuleError
        from server.rules import ROBOTS, WEAPONS

        if robot not in ROBOTS or weapon not in WEAPONS:
            raise RuleError("Неизвестная сборка")
        with self.tx() as db:
            if db.execute(
                "SELECT id FROM matches WHERE (a=? OR b=?) AND result='active'",
                (player, player),
            ).fetchone():
                raise RuleError("Сначала заверши текущий бой")
            db.execute(
                "DELETE FROM duels WHERE expires<? OR (host=? AND match_id IS NULL)",
                (self.clock(), player),
            )
            code = secrets.token_hex(4).upper()
            db.execute(
                "INSERT INTO duels VALUES(?,?,?,?,?,NULL)",
                (code, player, robot, weapon, self.clock() + 600),
            )
            return dict(code=code, expires=self.clock() + 600)

    def join_invite(self, player, code, robot, weapon):
        from server.arena_service import RuleError
        from server.rules import ROBOTS, WEAPONS

        if robot not in ROBOTS or weapon not in WEAPONS:
            raise RuleError("Неизвестная сборка")
        with self.tx() as db:
            record = db.execute(
                "SELECT * FROM duels WHERE code=?", (code.strip().upper(),)
            ).fetchone()
            if (
                not record
                or record["expires"] < self.clock()
                or record["host"] == player
            ):
                raise RuleError("Код недействителен или истёк")
            if record["match_id"]:
                match = db.execute(
                    "SELECT * FROM matches WHERE id=?", (record["match_id"],)
                ).fetchone()
                if player not in {match["a"], match["b"]}:
                    raise RuleError("Приглашение уже использовано")
                return self._public(db, match, player)
            if db.execute(
                "SELECT id FROM matches WHERE (a IN (?,?) OR b IN (?,?)) AND result='active'",
                (player, record["host"], player, record["host"]),
            ).fetchone():
                raise RuleError("Один из игроков уже в бою")
            row = self._create_match(
                db,
                record["host"],
                player,
                record["robot"],
                record["weapon"],
                robot,
                weapon,
                "friendly",
            )
            db.execute(
                "UPDATE duels SET match_id=? WHERE code=?", (row["id"], record["code"])
            )
            return self._public(db, row, player)

    def clan_edit(self, player, action, value):
        from server.arena_service import RuleError

        with self.tx() as db:
            me = db.execute(
                "SELECT clan,clan_role FROM players WHERE id=?", (player,)
            ).fetchone()
            clan = db.execute(
                "SELECT * FROM clans WHERE id=?", (me["clan"],)
            ).fetchone()
            if not clan:
                raise RuleError("Сначала вступи в клан")
            owner = clan["owner"] == player
            if action == "edit":
                if not owner:
                    raise RuleError("Описание меняет глава клана")
                description, _, emblem = value.partition("|")
                if emblem not in {"gear", "shield", "bolt", "star", "leaf"}:
                    raise RuleError("Неизвестная эмблема")
                db.execute(
                    "UPDATE clans SET description=?,emblem=? WHERE id=?",
                    (description[:160], emblem, clan["id"]),
                )
            elif action in {"promote", "demote", "kick"}:
                if not owner or value == player:
                    raise RuleError("Действие доступно главе для другого участника")
                target = db.execute(
                    "SELECT clan FROM players WHERE id=?", (value,)
                ).fetchone()
                if not target or target["clan"] != clan["id"]:
                    raise RuleError("Участник не найден")
                if action == "kick":
                    db.execute(
                        "UPDATE players SET clan=NULL,clan_role='member' WHERE id=?",
                        (value,),
                    )
                else:
                    db.execute(
                        "UPDATE players SET clan_role=? WHERE id=?",
                        ("officer" if action == "promote" else "member", value),
                    )
            else:
                raise RuleError("Неизвестное действие")
        return self.clans(player)
