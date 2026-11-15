"""HTTPS reverse proxy should terminate TLS; bind locally unless deployed."""

import os
from pathlib import Path
from threading import Lock
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from server.arena_service import ArenaService, RuleError
from server.database import StorageUnavailable, is_postgres


def storage_target():
    url = os.getenv("CLICKER_ARENA_DATABASE_URL", "").strip()
    if url:
        if not is_postgres(url):
            raise StorageUnavailable(
                "CLICKER_ARENA_DATABASE_URL must be a PostgreSQL URL"
            )
        return url
    if os.getenv("RENDER") == "true":
        # Render Free's local filesystem is disposable. Never quietly create a
        # fresh ranking database there if the Neon secret was not configured.
        raise StorageUnavailable("Configure CLICKER_ARENA_DATABASE_URL in Render")
    return os.getenv(
        "CLICKER_ARENA_DB", str(Path.home() / ".clicker-arena/arena.sqlite3")
    )


class LazyService:
    instance = None

    def __init__(self):
        self.lock = Lock()

    def __getattr__(self, name):
        if self.instance is None:
            with self.lock:
                if self.instance is None:
                    self.instance = ArenaService(storage_target())
        return getattr(self.instance, name)


service = LazyService()
app = FastAPI(title="Clicker Arena", version="1.0")


@app.exception_handler(StorageUnavailable)
async def unavailable(_request, _error):
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Server storage temporarily unavailable. Please retry shortly."
        },
        headers={"Retry-After": "15"},
    )


def player(authorization: Annotated[str, Header()] = ""):
    try:
        return service.authenticate(authorization.removeprefix("Bearer "))
    except RuleError as error:
        raise HTTPException(401, str(error)) from None


PlayerId = Annotated[str, Depends(player)]


def call(function, *args):
    try:
        return function(*args)
    except RuleError as error:
        raise HTTPException(409, str(error)) from None


class Register(BaseModel):
    name: str = Field(min_length=2, max_length=24)


class Queue(BaseModel):
    robot: str = Field(max_length=20)
    weapon: str = Field(max_length=20)
    mode: str = Field(default="ranked", pattern="^(ranked|balanced)$")


class Turn(BaseModel):
    revision: int = Field(ge=0)
    command: str = Field(min_length=8, max_length=80)
    action: str = Field(max_length=16)


class ClanAction(BaseModel):
    action: str = Field(max_length=16)
    value: str = Field(default="", max_length=190)


class FriendAction(BaseModel):
    action: str = Field(pattern="^(request|accept|remove)$")
    player: str = Field(min_length=24, max_length=24)


class Duel(Queue):
    code: str = Field(default="", max_length=8)


@app.get("/health")
def health():
    # Render polls this endpoint frequently. A DB query here would keep Neon
    # awake and needlessly consume its free compute quota. /ready tests storage.
    target = storage_target()
    return {
        "service": "clicker-arena",
        "protocol": 1,
        "rules_version": 3,
        "features": ["friends", "duel-codes", "balanced", "clan-roles", "history"],
        "opponents": "human-only",
        "storage": "postgresql" if is_postgres(target) else "transactional-sqlite",
        "database_checked": False,
    }


@app.get("/ready")
def ready():
    if not service.ready():
        raise HTTPException(503, "Database unavailable")
    return {"ready": True, "storage": health()["storage"]}


@app.post("/register")
def register(body: Register):
    return call(service.register, body.name)


@app.get("/me")
def me(uid: PlayerId):
    return service.profile(uid)


@app.get("/ranking")
def ranking(uid: PlayerId):
    return service.ranking()


@app.get("/match/current")
def current(uid: PlayerId):
    return service.current(uid)


@app.post("/queue")
def queue(body: Queue, uid: PlayerId):
    return call(service.enqueue, uid, body.robot, body.weapon, body.mode)


@app.delete("/queue")
def cancel(uid: PlayerId):
    return service.cancel_queue(uid)


@app.post("/match/{identity}/turn")
def turn(identity: str, body: Turn, uid: PlayerId):
    return call(service.turn, uid, identity, body.revision, body.command, body.action)


@app.get("/clans")
def clans(uid: PlayerId, search: str = ""):
    return service.clans(uid, search)


@app.post("/clans/action")
def clan_action(body: ClanAction, uid: PlayerId):
    return call(service.clan_action, uid, body.action, body.value)


@app.get("/friends")
def friends(uid: PlayerId):
    return service.friends(uid)


@app.post("/friends/action")
def friend_action(body: FriendAction, uid: PlayerId):
    return call(service.friend_action, uid, body.action, body.player)


@app.get("/history")
def history(uid: PlayerId):
    return service.history(uid)


@app.post("/duels")
def invite(body: Duel, uid: PlayerId):
    return call(service.invite, uid, body.robot, body.weapon)


@app.post("/duels/join")
def join_duel(body: Duel, uid: PlayerId):
    return call(service.join_invite, uid, body.code, body.robot, body.weapon)
