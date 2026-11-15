"""Authenticated, optional human PvP. The server alone owns rating and results."""

import asyncio
import hashlib
import json
import os
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx

from robot_catalog import ROBOT_BY_ID


class OnlineArena:
    def __init__(self, session):
        self.session = session
        self.root = (
            Path(session.store.directory)
            if hasattr(session.store, "directory")
            else None
        )
        self.url = os.getenv("CLICKER_ARENA_URL", "").rstrip("/")
        if self.root:
            try:
                self.url = json.loads(
                    (self.root / "arena-server.json").read_text(encoding="utf-8")
                ).get("url", self.url)
            except (OSError, ValueError, AttributeError):
                pass
        self.credentials = {}
        self.profile = {}
        self.match = None
        self.ranking = []
        self.clans = {}
        self.waiting = False
        self.busy = False
        self.error = ""
        self.lock = asyncio.Lock()

    def notify(self):
        if self.session.ui_alive:
            self.session.notify()

    def credentials_path(self):
        if not self.root:
            return None
        return (
            self.root
            / f"arena-identity-{hashlib.sha256(self.url.encode()).hexdigest()[:16]}.json"
        )

    async def request(self, method, path, body=None, *, authenticated=True):
        if not self.url:
            raise ValueError("Укажи адрес игрового сервера")
        headers = (
            {"Authorization": "Bearer " + self.credentials.get("token", "")}
            if authenticated
            else {}
        )
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10, connect=4), follow_redirects=False
        ) as client:
            response = await client.request(
                method, self.url + path, json=body, headers=headers
            )
            if response.status_code >= 400:
                try:
                    detail = response.json().get("detail", "Ошибка игрового сервера")
                except ValueError:
                    detail = "Ответ игрового сервера не распознан"
                raise ValueError(str(detail)[:250])
            return response.json()

    async def connect(self, url, name):
        async with self.lock:
            self.busy = True
            self.notify()
            try:
                parsed = urlparse(url.strip())
                if (
                    parsed.scheme not in {"https", "http"}
                    or not parsed.hostname
                    or parsed.username
                    or parsed.password
                    or parsed.query
                    or parsed.fragment
                ):
                    raise ValueError(
                        "Укажи адрес http:// или https:// без логина и пароля"
                    )
                self.url = url.strip().rstrip("/")
                health = await self.request("GET", "/health", authenticated=False)
                if (
                    health.get("protocol") != 1
                    or health.get("opponents") != "human-only"
                ):
                    raise ValueError("Это не сервер сетевой арены Clicker")
                path = self.credentials_path()
                self.credentials = {}
                if path:
                    try:
                        self.credentials = json.loads(path.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        pass
                if not self.credentials.get("token"):
                    self.credentials = await self.request(
                        "POST",
                        "/register",
                        {"name": name or "Исследователь"},
                        authenticated=False,
                    )
                    if path:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(json.dumps(self.credentials), encoding="utf-8")
                self.profile = await self.request("GET", "/me")
                if self.root:
                    (self.root / "arena-server.json").write_text(
                        json.dumps({"url": self.url}), encoding="utf-8"
                    )
                self.error = ""
                await self._refresh()
            except (httpx.HTTPError, ValueError, OSError) as error:
                self.error = str(error)[:250] or "Сервер недоступен"
            finally:
                self.busy = False
                self.notify()

    async def _refresh(self):
        self.profile = await self.request("GET", "/me")
        match = await self.request("GET", "/match/current")
        old = self.match
        before = self.view_battle()
        self.match = match
        if (
            old
            and match
            and old["id"] == match["id"]
            and match["revision"] > old["revision"]
            and match["state"].get("last", {}).get("actor") != match["you"]
        ):
            previous_busy = self.busy
            self.busy = True
            try:
                own = old["state"][old["you"]]
                self.session.arena_animation_id += 1
                self.session.arena_visual = {
                    "battle_id": self.view_battle()["id"],
                    "phase": "enemy-flight",
                    "action": "guard"
                    if own.get("guard")
                    else "dodge"
                    if own.get("dodge")
                    else "idle",
                    "before_hp": before["player_hp"],
                    "before_enemy_hp": before["enemy_hp"],
                }
                self.notify()
                await asyncio.sleep(0.95)
                self.session.arena_visual["phase"] = "reply"
                self.notify()
                await asyncio.sleep(0.5)
            finally:
                self.session.arena_visual = {}
                self.busy = previous_busy
        if match and match["result"] == "active":
            self.waiting = False
        self.ranking = await self.request("GET", "/ranking")
        self.clans = await self.request("GET", "/clans")

    async def refresh(self):
        if self.busy or not self.profile or self.session._paused:
            return
        async with self.lock:
            try:
                await self._refresh()
                if self.waiting:
                    result = await self.request("POST", "/queue", self.queue_body())
                    if result.get("match"):
                        self.match = result["match"]
                        self.waiting = False
                self.error = ""
            except (httpx.HTTPError, ValueError) as error:
                self.error = (
                    str(error)[:250] or "Сервер недоступен; локальные бои работают"
                )
            self.notify()

    def queue_body(self):
        state = self.session.state
        gear = state.loadouts.get(state.active_robot, [])
        # Ranked play uses equal level/equipment; the server never trusts local
        # damage, save currency, reported wins or inventory levels.
        return {
            "robot": state.active_robot or "spark",
            "weapon": gear[0] if gear else "plasma",
        }

    async def command(self, name, value=""):
        async with self.lock:
            if self.busy or not self.profile:
                return
            self.busy = True
            self.notify()
            try:
                if name == "queue":
                    result = await self.request("POST", "/queue", self.queue_body())
                    self.match = result.get("match", self.match)
                    self.waiting = bool(result.get("waiting"))
                elif name == "cancel":
                    await self.request("DELETE", "/queue")
                    self.waiting = False
                elif name in {
                    "attack",
                    "guard",
                    "special",
                    "dodge",
                    "charge",
                    "resign",
                }:
                    if not self.match:
                        raise ValueError("Бой ещё не найден")
                    result = await self.request(
                        "POST",
                        f"/match/{self.match['id']}/turn",
                        {
                            "revision": self.match["revision"],
                            "command": uuid.uuid4().hex,
                            "action": name,
                        },
                    )
                    self.session.arena_animation_id += 1
                    self.session.arena_visual = {
                        "battle_id": self.view_battle()["id"],
                        "phase": "approach",
                        "action": name,
                    }
                    self.notify()
                    await asyncio.sleep(0.6)
                    if name in {"attack", "special"}:
                        self.session.arena_visual["phase"] = "flight"
                        self.notify()
                        await asyncio.sleep(0.95)
                    self.match = result
                    self.session.arena_visual["phase"] = (
                        "victory"
                        if result["result"] == "finished"
                        and result["state"]["winner"] == result["you"]
                        else "impact"
                    )
                    self.notify()
                    await asyncio.sleep(0.5)
                    self.session.arena_visual = {}
                else:
                    await self.request(
                        "POST", "/clans/action", {"action": name, "value": value}
                    )
                await self._refresh()
                self.error = ""
            except (httpx.HTTPError, ValueError) as error:
                self.error = str(error)[:250] or "Не удалось выполнить действие"
            finally:
                self.busy = False
                self.notify()

    def view_battle(self):
        if not self.match:
            return {}
        match = self.match
        side = match["you"]
        other = "b" if side == "a" else "a"
        state = match["state"]
        own, enemy, last = state[side], state[other], state.get("last", {})
        return {
            "id": int(match["id"][:8], 16),
            "robot_id": own["robot"],
            "enemy_id": enemy["robot"],
            "stage": 0,
            "turn": match["revision"],
            "player_hp": own["hp"],
            "player_max_hp": 120,
            "enemy_hp": enemy["hp"],
            "enemy_max_hp": 120,
            "last_damage": last.get("damage", 0) if last.get("actor") == side else 0,
            "last_incoming": last.get("damage", 0) if last.get("actor") == other else 0,
            "last_heal": last.get("heal", 0),
            "last_counter": 0,
            "last_dodged": bool(last.get("dodged") and last.get("actor") == other),
            "last_intent": "attack",
            "result": "active"
            if match["result"] == "active"
            else "win"
            if state["winner"] == side
            else "loss",
            "equipment": [{"id": own["weapon"], "level": 1}],
            "cooldown": own["cooldown"],
            "enemy_name": match["players"][other]["name"],
            "player_name": match["players"][side]["name"],
            "kind": "human-ranked",
            "enemy_weapon": enemy["weapon"],
            "enemy_action": last.get("action", "idle")
            if last.get("actor") == other
            else "idle",
        }


def online_for(session):
    if not hasattr(session, "online_arena"):
        session.online_arena = OnlineArena(session)
    return session.online_arena
