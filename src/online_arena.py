"""Authenticated, optional human PvP. The server alone owns rating and results."""

import asyncio
import hashlib
import json
import os
import uuid
from pathlib import Path
from time import monotonic
from urllib.parse import urlparse

import httpx

from robot_catalog import ROBOT_BY_ID
from network_config import arena_url, developer_network
from combat_rules import ACTIONS, ATTACKS
from robot_designs import DESIGNS


class ServerStarting(ValueError):
    """Render may briefly return a gateway error or its HTML startup page."""


class OnlineArena:
    def __init__(self, session):
        self.session = session
        self.root = (
            Path(session.store.directory)
            if hasattr(session.store, "directory")
            else None
        )
        self.url = arena_url()
        if self.root and not self.url and developer_network():
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
        self.friends = []
        self.history = []
        self.invitation = {}
        self.mode = "ranked"
        self.started = False
        self.social_updated = 0

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

    async def request(
        self, method, path, body=None, *, authenticated=True, read_timeout=10
    ):
        if not self.url:
            raise ValueError(
                "Онлайн-сервер пока не подключён к этой сборке. Тренировка с ботами доступна"
            )
        headers = (
            {"Authorization": "Bearer " + self.credentials.get("token", "")}
            if authenticated
            else {}
        )
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(read_timeout, connect=min(8, read_timeout)),
            follow_redirects=False,
        ) as client:
            response = await client.request(
                method, self.url + path, json=body, headers=headers
            )
            warming = method == "GET" and path == "/health"
            if warming and response.status_code in {502, 503, 504}:
                raise ServerStarting("Сервер просыпается")
            if response.status_code >= 400:
                try:
                    detail = response.json().get("detail", "Ошибка игрового сервера")
                except ValueError:
                    detail = "Ответ игрового сервера не распознан"
                raise ValueError(str(detail)[:250])
            try:
                return response.json()
            except ValueError:
                if warming and "text/html" in response.headers.get("content-type", ""):
                    raise ServerStarting("Сервер просыпается") from None
                raise ValueError("Ответ игрового сервера не распознан") from None

    async def warm_up(self):
        """Retry only the read-only liveness probe, never a purchase or a turn."""
        deadline = monotonic() + 75
        while True:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise ValueError(
                    "Сервер ещё просыпается. Попробуй подключиться чуть позже"
                )
            try:
                return await self.request(
                    "GET",
                    "/health",
                    authenticated=False,
                    read_timeout=max(0.1, remaining),
                )
            except (ServerStarting, httpx.TimeoutException):
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise ValueError(
                        "Сервер ещё просыпается. Попробуй подключиться чуть позже"
                    ) from None
                await asyncio.sleep(min(3, remaining))

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
                health = await self.warm_up()
                if (
                    health.get("protocol") != 1
                    or health.get("opponents") != "human-only"
                    or health.get("rules_version") != 3
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
            visual_generation = None
            try:
                own = old["state"][old["you"]]
                self.session.arena_animation_id += 1
                visual_generation = self.session.arena_animation_id
                speed = self.session.battle_speed
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
                    "speed": speed,
                }
                self.notify()
                await asyncio.sleep(0.72 / speed)
                self.session.arena_visual["phase"] = "reply"
                self.notify()
                await asyncio.sleep(0.25 / speed)
            finally:
                if visual_generation == self.session.arena_animation_id:
                    self.session.arena_visual = {}
                self.busy = previous_busy
        if match and match["result"] == "active":
            self.waiting = False
        self.ranking = await self.request("GET", "/ranking")
        self.clans = await self.request("GET", "/clans")
        import time

        if time.monotonic() - self.social_updated > 10:
            self.friends, self.history = await asyncio.gather(
                self.request("GET", "/friends"), self.request("GET", "/history")
            )
            self.social_updated = time.monotonic()

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
            "weapon": gear[0]
            if gear
            else DESIGNS[state.active_robot or "spark"]["weapon"],
            "mode": self.mode,
        }

    async def command(self, name, value=""):
        if self.busy or self.lock.locked() or not self.profile:
            return
        async with self.lock:
            if self.busy or not self.profile:
                return
            self.busy = True
            visual_generation = None
            self.notify()
            try:
                if name == "queue":
                    result = await self.request("POST", "/queue", self.queue_body())
                    self.match = result.get("match", self.match)
                    self.waiting = bool(result.get("waiting"))
                elif name == "cancel":
                    await self.request("DELETE", "/queue")
                    self.waiting = False
                elif name == "duel_create":
                    self.invitation = await self.request(
                        "POST", "/duels", self.queue_body()
                    )
                elif name == "duel_join":
                    self.match = await self.request(
                        "POST", "/duels/join", {**self.queue_body(), "code": value}
                    )
                elif name.startswith("friend_"):
                    self.friends = await self.request(
                        "POST",
                        "/friends/action",
                        {"action": name.removeprefix("friend_"), "player": value},
                    )
                    self.social_updated = 0
                elif name == "clan_search":
                    from urllib.parse import quote

                    self.clans = await self.request(
                        "GET", "/clans?search=" + quote(value)
                    )
                    return
                elif name in ACTIONS | {"resign"}:
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
                    visual_generation = self.session.arena_animation_id
                    from battle_ui import turn_timing

                    prepare_seconds, flight_seconds, impact_seconds = turn_timing(name)
                    speed = self.session.battle_speed
                    self.session.arena_visual = {
                        "battle_id": self.view_battle()["id"],
                        "phase": "approach",
                        "action": name,
                        "speed": speed,
                        "flight_seconds": flight_seconds,
                    }
                    self.notify()
                    await asyncio.sleep(prepare_seconds / speed)
                    if name in ATTACKS:
                        self.session.arena_visual["phase"] = "flight"
                        self.notify()
                        await asyncio.sleep(flight_seconds / speed)
                    self.match = result
                    self.session.arena_visual["phase"] = (
                        "victory"
                        if result["result"] == "finished"
                        and result["state"]["winner"] == result["you"]
                        else "impact"
                    )
                    self.notify()
                    await asyncio.sleep(impact_seconds / speed)
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
                if visual_generation == self.session.arena_animation_id:
                    self.session.arena_visual = {}
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
            "player_max_hp": own.get("max_hp", 120),
            "enemy_hp": enemy["hp"],
            "enemy_max_hp": enemy.get("max_hp", 120),
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
            "rules_version": 3,
            "combatants": {"a": own, "b": enemy},
            "battery": own["energy"],
            "max_battery": own.get("max_energy", 12),
            "focus": own.get("focus", 0),
            "heat": own.get("heat", 0),
            "super_charge": own.get("super_charge", 0),
        }


def online_for(session):
    if not hasattr(session, "online_arena"):
        session.online_arena = OnlineArena(session)
    return session.online_arena
