"""Small SQL boundary shared by SQLite and the free hosted PostgreSQL service.

Only internal, parameterized statements pass through this adapter. PostgreSQL
transactions use a transaction-scoped advisory lock: matchmaking, turn revision
checks and reward claims remain atomic across simultaneous HTTP requests.
Connections close after each transaction so an idle Neon database can sleep.
"""

import sqlite3
from contextlib import contextmanager


class StorageUnavailable(RuntimeError):
    """A retryable storage failure, without a connection string in the message."""


def is_postgres(target):
    return str(target).startswith(("postgresql://", "postgres://"))


class SqlRow(dict):
    """Support the named and positional access used by sqlite3.Row callers."""

    def __getitem__(self, key):
        return (
            tuple(self.values())[key]
            if isinstance(key, int)
            else super().__getitem__(key)
        )


def _row_factory(cursor):
    if cursor.description is None:
        return tuple
    names = [column.name for column in cursor.description]
    return lambda values: SqlRow(zip(names, values))


class PostgresConnection:
    def __init__(self, connection, integrity_error):
        self.connection = connection
        self.integrity_error = integrity_error

    def execute(self, sql, params=()):
        try:
            # Queries are project-owned SQL, never user-supplied expressions.
            return self.connection.execute(
                sql.replace("?", "%s"), params, prepare=False
            )
        except self.integrity_error as error:
            # Existing rule handlers turn constraint violations into RuleError;
            # the enclosing transaction then rolls back before the next request.
            raise sqlite3.IntegrityError("Constraint violation") from error

    def executescript(self, sql):
        for statement in sql.split(";"):
            if statement.strip():
                self.execute(statement)


@contextmanager
def transaction(target):
    if is_postgres(target):
        try:
            import psycopg
        except ImportError:
            raise StorageUnavailable(
                "Install server/requirements.txt for PostgreSQL"
            ) from None
        try:
            with psycopg.connect(
                str(target),
                connect_timeout=10,
                row_factory=_row_factory,
                application_name="robo-workshop-arena",
                prepare_threshold=None,
            ) as connection:
                # Transaction pooling is safe: this lock is released by COMMIT
                # or ROLLBACK, rather than being held on a pooled session.
                connection.execute("SET LOCAL lock_timeout = '10s'")
                connection.execute("SET LOCAL statement_timeout = '15s'")
                connection.execute("SELECT pg_advisory_xact_lock(726626279771)")
                yield PostgresConnection(connection, psycopg.IntegrityError)
        except (psycopg.OperationalError, psycopg.InterfaceError):
            raise StorageUnavailable(
                "Database temporarily unavailable; retry shortly"
            ) from None
    else:
        db = sqlite3.connect(str(target), timeout=10)
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


def table_columns(db, table):
    if table not in {"players", "queue", "clans"}:
        raise ValueError("Unknown schema table")
    if isinstance(db, PostgresConnection):
        return {
            row[0]
            for row in db.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=current_schema() AND table_name=?",
                (table,),
            )
        }
    return {row[1] for row in db.execute(f"PRAGMA table_info({table})")}


def record_schema_version(db, version):
    if isinstance(db, PostgresConnection):
        db.execute(
            "CREATE TABLE IF NOT EXISTS arena_schema(id INTEGER PRIMARY KEY, version INTEGER NOT NULL)"
        )
        db.execute(
            "INSERT INTO arena_schema VALUES(1,?) ON CONFLICT(id) DO UPDATE SET version=excluded.version",
            (version,),
        )
    else:
        db.execute(f"PRAGMA user_version={int(version)}")
