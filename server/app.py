"""HTTPS reverse proxy should terminate TLS; bind locally unless deployed."""

import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from server.arena_service import ArenaService, RuleError


class LazyService:
    instance = None

    def __getattr__(self, name):
        if self.instance is None:
            self.instance = ArenaService(
                os.getenv(
                    "CLICKER_ARENA_DB",
                    str(Path.home() / ".clicker-arena/arena.sqlite3"),
                )
            )
        return getattr(self.instance, name)


service = LazyService()
app = FastAPI(title="Clicker Arena", version="1.0")


def player(authorization: Annotated[str, Header()] = ""):
    try:
        return service.authenticate(authorization.removeprefix("Bearer "))
    except RuleError as error:
        raise HTTPException(401, str(error)) from None


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
    mode: str = Field(default='ranked', pattern='^(ranked|balanced)$')


class Turn(BaseModel):
    revision: int = Field(ge=0)
    command: str = Field(min_length=8, max_length=80)
    action: str = Field(max_length=16)


class ClanAction(BaseModel):
    action: str = Field(max_length=16)
    value: str = Field(default="", max_length=190)


class FriendAction(BaseModel):
    action: str = Field(pattern='^(request|accept|remove)$')
    player: str = Field(min_length=24,max_length=24)


class Duel(Queue):
    code: str = Field(default='',max_length=8)


@app.get("/health")
def health():
    return {
        "service": "clicker-arena",
        "protocol": 1,
        "rules_version": 3,
        "features": ['friends','duel-codes','balanced','clan-roles','history'],
        "opponents": "human-only",
        "storage": "transactional-sqlite",
    }


@app.post("/register")
def register(body: Register):
    return call(service.register, body.name)


@app.get("/me")
def me(uid=Depends(player)):
    return service.profile(uid)


@app.get("/ranking")
def ranking(uid=Depends(player)):
    return service.ranking()


@app.get("/match/current")
def current(uid=Depends(player)):
    return service.current(uid)


@app.post("/queue")
def queue(body: Queue, uid=Depends(player)):
    return call(service.enqueue, uid, body.robot, body.weapon, body.mode)


@app.delete("/queue")
def cancel(uid=Depends(player)):
    return service.cancel_queue(uid)


@app.post("/match/{identity}/turn")
def turn(identity: str, body: Turn, uid=Depends(player)):
    return call(service.turn, uid, identity, body.revision, body.command, body.action)


@app.get("/clans")
def clans(search: str='',uid=Depends(player)):
    return service.clans(uid,search)


@app.post("/clans/action")
def clan_action(body: ClanAction, uid=Depends(player)):
    return call(service.clan_action, uid, body.action, body.value)


@app.get('/friends')
def friends(uid=Depends(player)):
    return service.friends(uid)


@app.post('/friends/action')
def friend_action(body:FriendAction,uid=Depends(player)):
    return call(service.friend_action,uid,body.action,body.player)


@app.get('/history')
def history(uid=Depends(player)):
    return service.history(uid)


@app.post('/duels')
def invite(body:Duel,uid=Depends(player)):
    return call(service.invite,uid,body.robot,body.weapon)


@app.post('/duels/join')
def join_duel(body:Duel,uid=Depends(player)):
    return call(service.join_invite,uid,body.code,body.robot,body.weapon)
