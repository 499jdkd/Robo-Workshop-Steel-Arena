"""One state, timer and serialized cloud writer per running game page."""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
import uuid

from gameplay import (
    MAX_VALUE,
    ActionResult,
    GameState,
    advance,
    offline_income,
    perform,
    threshold,
)
from local_store import LocalStore, MemoryStore
from progression import DAILY_SPECS, refresh_day

logger = logging.getLogger(__name__)


def default_manager(identity):
    from leaderboard import LeaderboardManager
    return LeaderboardManager(identity)


class GameSession:
    def __init__(
        self,
        page=None,
        *,
        store=None,
        clock=time.time,
        manager_factory=default_manager,
        demo=False,
    ):
        self.page = page
        self.clock = clock
        self.demo = demo
        self.store = (
            store
            if store is not None
            else (
                MemoryStore()
                if demo
                or (
                    getattr(page, "web", False)
                    and os.getenv("CLICKER_DESKTOP_HOST") != "1"
                )
                else LocalStore()
            )
        )
        cached = self.store.load() or {}
        self.state = GameState.from_dict(cached.get("state"))
        from armory import refresh_week

        refresh_week(self.state, self.clock())
        self.device_id = str(cached.get("device_id") or "")
        self.trusted = bool(cached.get("trusted", False))
        self.dirty = bool(cached.get("dirty", False))
        self.started_at = self.clock()
        self._baseline = self.state.clone() if self.trusted else GameState()
        saved_at = cached.get("saved_at")
        self._baseline_at = (
            float(saved_at)
            if self.trusted
            and isinstance(saved_at, (int, float))
            and math.isfinite(saved_at)
            else 0
        )
        pending = cached.get("pending", [])
        self._journal = (
            [op for op in pending if isinstance(op, dict)]
            if not self.trusted and isinstance(pending, list)
            else []
        )
        self._restored_pending = len(self._journal)
        board = cached.get("leaderboard")
        self.board = (
            [row for row in board if isinstance(row, dict)][:5]
            if isinstance(board, list)
            else []
        )
        self.board_loaded = bool(self.board)
        self.board_loading = False
        self.board_error = False
        self.connection = "loading"
        self.cloud_ready = False
        self.manager_factory = manager_factory
        self.manager = None
        self._listeners = []
        self._tasks = []
        self._running = False
        self._closed = False
        self._close_task = None
        self._paused = False
        self._revision = 0
        self._last_save = 0.0
        self._last_upload = 0.0
        self.notice = ""
        self.notice_until = 0.0
        self.notice_id = 0
        self.reveal_until = 0.0
        self.fed_until = 0.0
        self.fed_robot = ""
        self.arena_expanded = False
        self.arena_animating = False
        self.arena_animation_id = 0
        self.arena_visual = {}
        # Transient presentation only; deliberately outside PlayerState/save.
        self.motion_event = 0
        self.motion_action = "idle"
        self.motion_sound = True
        preferences = cached.get("presentation", {})
        preferences = preferences if isinstance(preferences, dict) else {}
        self.motion_sound = preferences.get("motion_sound", True) is not False
        self.battle_speed = preferences.get("battle_speed", 1.5)
        if self.battle_speed not in (1.0, 1.5, 2.0):
            self.battle_speed = 1.5
        self.reduced_effects = preferences.get("reduced_effects") is True
        self.preview_identity = ""
        self.preview_action = "idle"
        self.preview_event = 0
        self.last_auto_feed = -1000000.0
        self.focus_scene = ""
        self.route = ""
        self.robot_detail = ""
        self.robot_detail_return = ""
        self.inspection_id = ""
        self.factory_kind = "normal"
        self.factory_rewards_visible = False
        self._focus_window_size = None
        self._board_reader = None
        board_at = cached.get("board_updated_at")
        self.board_updated_at = (
            float(board_at)
            if isinstance(board_at, (int, float)) and math.isfinite(board_at)
            else 0
        )
        self.board_error_detail = ""
        if self.trusted and self.state.last_active_at:
            gain = offline_income(
                self.state, self.started_at - self.state.last_active_at, self.started_at
            )
            if gain:
                self.tell(f"Пока ты отдыхал, помощники собрали {gain} монет")
                self.dirty = True
        self.state.last_active_at = self.started_at
        if demo:
            self.device_id = "preview-player"
            self.state = GameState(
                level=6,
                coin=370,
                experience=170,
                session_taps=215,
                manual_taps=85,
                purchases=5,
                base_click_power=3,
                base_auto_click_power=2,
                auto_click_price=200,
                offline_income_power=1,
                offline_income_price=200,
                energy=72,
                jobs_done=2,
                last_active_at=self.started_at,
                robot_levels={"spark": 2, "volt": 1},
                active_robot="spark",
                egg_id="flora",
                egg_started_taps=53,
                food=35,
            )
            self.trusted = self.cloud_ready = True
            self.connection = "local"
            self.board = [
                {"username": name, "level": level, "taps": taps}
                for name, level, taps in (
                    ("Лисёнок", 12, 820),
                    ("МастерБот", 9, 510),
                    ("Звёздочка", 7, 300),
                )
            ]
            self.board_loaded = True

    @classmethod
    def preview(cls, page=None, device_id="preview-player"):
        session = cls(page, store=MemoryStore())
        session.device_id = device_id
        session.trusted = True
        session.connection = "local"
        return session

    def subscribe(self, callback):
        if self._closed:
            return lambda: None
        self._listeners.append(callback)

        def unsubscribe():
            if callback in self._listeners:
                self._listeners.remove(callback)

        return unsubscribe

    @property
    def closed(self):
        return self._closed

    @property
    def ui_alive(self):
        return not self._closed and self._page_alive()

    def _page_alive(self):
        try:
            getattr(self.page, "session", None)
            return True
        except RuntimeError as error:
            if "destroyed session" not in str(error).lower():
                raise
            return False

    def notify(self):
        if self._closed or not self._page_alive():
            self._listeners.clear()
            return
        for listener in tuple(self._listeners):
            try:
                listener()
            except RuntimeError as error:
                if "destroyed session" not in str(error).lower():
                    raise
                self._listeners.clear()
                return

    def tell(self, message: str, seconds=4):
        if message:
            self.notice = message
            self.notice_until = self.clock() + seconds
            self.notice_id += 1

    def persist(self):
        try:
            self.store.save(
                {
                    "schema": 2,
                    "device_id": self.device_id,
                    "state": self.state.to_dict(),
                    "trusted": self.trusted,
                    "dirty": self.dirty,
                    "saved_at": self.clock(),
                    "pending": self._journal if not self.trusted else [],
                    "leaderboard": self.board,
                    "board_updated_at": self.board_updated_at,
                    "presentation": {"battle_speed": self.battle_speed, "reduced_effects": self.reduced_effects, "motion_sound": self.motion_sound},
                }
            )
            self._last_save = self.clock()
        except (OSError, ValueError) as error:
            logger.warning("Local save failed: %s", error)
            self.tell("Не удалось сохранить на устройстве. Проверь свободное место", 8)

    def _record(self, name, args, at):
        if self.cloud_ready:
            return
        if not self.trusted:
            # Before the first profile is known only taps are spendable. Keep
            # two bounded counters, even if a device stays offline for days.
            if name not in {"tap", "tick"}:
                return
            kind = "tap" if name == "tap" else "online"
            amount = args[0] if args else 0
            existing = next(
                (op for op in self._journal if op.get("name") == kind), None
            )
            if existing:
                existing["args"][0] += amount
                existing["at"] = at
            else:
                self._journal.append({"name": kind, "args": [amount], "at": at})
            return
        if name == "tap" and self._journal and self._journal[-1].get("name") == "tap":
            self._journal[-1]["args"][0] += args[0] if args else 1
            self._journal[-1]["at"] = at
        else:
            self._journal.append({"name": name, "args": list(args), "at": at})

    def act(self, name: str, *args) -> ActionResult:
        if self._closed:
            return ActionResult(False)
        free_actions = {
            "tap",
            "hatch",
            "feed",
            "battle_start",
            "battle_turn",
            "battle_leave",
            "select_robot",
            "goal",
            "theme",
            "incubate",
            "train_robot",
            "avatar",
            "daily",
            "crate",
            "stock_egg",
            "lamp_toggle",
            "tutorial_done",
            "_video_reward",
            "order",
            "collect",
        }
        if not self.trusted and name not in free_actions:
            result = ActionResult(
                False, "Загружаем прежнее сохранение. Монеты уже можно собирать"
            )
            self.tell(result.message)
            self.notify()
            return result
        now = self.clock()
        daily_before = {spec[2]: getattr(self.state, spec[2]) for spec in DAILY_SPECS}
        previous_level, previous_stage = self.state.level, self.state.stage_index
        result = perform(self.state, name, list(args), now)
        if result.ok:
            if name in {"feed", "hatch", "train_robot", "lamp_toggle", "tap"}:
                self.motion_event += 1
                self.motion_action = {
                    "feed": "feed",
                    "hatch": "surprise",
                    "train_robot": "joy",
                    "lamp_toggle": "surprise",
                    "tap": "joy",
                }[name]
            refresh_day(self.state, now, before=daily_before)
            self._record(name, list(args or (1,)) if name == "tap" else args, now)
            self._revision += 1
            self.dirty = True
            self.persist()
            self.tell(result.message)
            if name == "hatch":
                self.reveal_until = now + 4
            elif name == "feed":
                self.fed_until = now + 2
                self.fed_robot = args[0]
            elif name in {"battle_start", "battle_leave"}:
                self.arena_animation_id += 1
                self.arena_animating = False
                self.arena_visual = {}
            elif self.state.stage_index > previous_stage:
                self.tell(f"Открыта новая мастерская: {self.state.stage.title}!", 6)
            elif self.state.level > previous_level:
                self.tell(
                    f"Уровень {self.state.level}! Ты становишься настоящим мастером"
                )
        else:
            self.tell(result.message)
        self.notify()
        return result

    def claim_video_reward(self, token, offer):
        result = self.act("_video_reward", token, offer)
        if result.ok and offer.get("kind") in {"food", "training"}:
            self.fed_until = self.clock() + 3
            self.fed_robot = (
                offer.get("target")
                if offer.get("kind") == "training"
                else self.state.active_robot
            )
        return result

    def tick(self, now=None):
        if self._paused or self._closed:
            return
        now = self.clock() if now is None else now
        refresh_day(self.state, now)
        elapsed = max(0, now - self.state.last_active_at)
        before = self.state.coin
        advance(self.state, now)
        self._record("tick", [elapsed if elapsed <= 5 else 0], now)
        if self.state.coin != before:
            self.dirty = True
            self._revision += 1
        if self.notice and now >= self.notice_until:
            self.notice = ""
        if now - self._last_save >= 3:
            self.persist()
        self.notify()

    def workshop_tap(self):
        result = self.act("hatch" if self.state.egg_is_ready(self.clock()) else "tap")
        state = self.state
        identity = state.active_robot
        if (
            identity
            and result.coins
            and state.food >= 5
            and self.clock() - self.last_auto_feed >= 0.7
        ):
            from robot_catalog import MAX_ROBOT_LEVEL

            if (
                state.robot_energy.get(identity, 70) < 100
                or state.robot_levels[identity] < MAX_ROBOT_LEVEL
            ):
                self.act("feed", identity)
                self.last_auto_feed = self.clock()
        return result

    def preview_robot(self, identity, action):
        """Only transient renderer intent. Locked and owned robots use this path."""
        from robot_abilities import ABILITIES

        actions = {"attack", "special", "ultimate", "guard", "joy", "idle"}
        if identity in {"volt", "titan"}:
            actions |= {"quick", "dodge", "charge", "jump", "surprise", "anger", "dance", "inspect", "victory", "defeat"}
        if identity not in ABILITIES or action not in actions:
            return False
        self.preview_identity, self.preview_action = identity, action
        self.preview_event += 1
        self.notify()
        return True

    def presentation(self, *, speed=None, reduced=None, sound=None):
        if speed in (1.0, 1.5, 2.0):
            self.battle_speed = float(speed)
        if reduced is not None:
            self.reduced_effects = bool(reduced)
        if sound is not None:
            self.motion_sound = bool(sound)
        self.persist()
        self.notify()

    def pause(self):
        self.tick()
        self._paused = True
        self.persist()
        self.notify()

    def resume(self):
        if not self._paused:
            return
        now = self.clock()
        elapsed = max(0, now - self.state.last_active_at)
        gain = offline_income(self.state, elapsed, now)
        self._record("offline", [elapsed], now)
        if gain:
            self.dirty = True
            self._revision += 1
            self.tell(f"Помощники собрали {gain} монет, пока ты отдыхал")
        self._paused = False
        self.persist()
        self.notify()

    def _merge_profile(self, remote):
        was_trusted = self.trusted
        baseline = self._baseline.clone()
        cloud = GameState.from_dict(remote)
        if remote is not None and (
            not self.trusted or cloud.last_active_at > self._baseline_at
        ):
            if self.trusted:
                for field in (
                    "coin",
                    "session_taps",
                    "base_click_power",
                    "double_click_price",
                    "base_auto_click_power",
                    "auto_click_price",
                    "offline_income_power",
                    "offline_income_price",
                    "boost_level",
                    "boost_price",
                    "username",
                    "play_seconds",
                    "last_active_at",
                ):
                    setattr(baseline, field, getattr(cloud, field))
                baseline.level = max(baseline.level, cloud.level)
                baseline.experience = max(
                    baseline.experience, threshold(baseline.level - 1)
                )
            else:
                baseline = cloud
        if not was_trusted:
            local = self.state.clone()
            online = sum(
                op.get("args", [0])[0]
                for op in self._journal
                if op.get("name") == "online"
            )
            taps = sum(
                op.get("args", [0])[0]
                for op in self._journal
                if op.get("name") == "tap"
            )
            now = self.clock()
            if baseline.last_active_at:
                offline_income(
                    baseline, max(0, now - baseline.last_active_at - online), now
                )
            # Free care/arena progress is already in the local snapshot. Merge
            # it once, then credit the old profile's extra click/auto power.
            # This keeps offline play available without spending an unknown
            # cloud balance or replaying battle rewards twice.
            extra_clicks = (
                max(0, baseline.base_click_power - local.base_click_power) * taps
            )
            passive = int(baseline.base_auto_click_power * online)
            for field in (
                "robot_levels",
                "robot_xp",
                "robot_energy",
                "robot_charge_carry",
                "parts",
                "crates_opened",
                "craft_counts",
                "egg_stock",
                "egg_started_at",
                "egg_ready_at",
                "avatar_id",
                "daily_day",
                "daily_base",
                "daily_claimed",
                "dailies_done",
                "reward_tokens",
                "reward_day",
                "reward_count",
                "reward_last_at",
                "video_boost_end_at",
                "lamp_on",
                "tutorial_seen",
                "energy",
                "work_id",
                "work_started_at",
                "work_end_at",
                "work_reward",
                "jobs_done",
                "robot_trainings",
                "active_robot",
                "egg_id",
                "egg_started_taps",
                "feedings",
                "arena_stage",
                "arena_wins",
                "battles_played",
                "battle_serial",
                "battle",
                "claimed_goals",
                "contracts",
                "manual_taps",
                "purchases",
                "accent",
                "weapon_levels",
                "loadouts",
                "weapon_upgrades",
                "rare_parts",
                "arena_difficulty",
                "weekly",
                "tournament",
                "collection",
            ):
                setattr(baseline, field, getattr(local, field))
            baseline.food = min(MAX_VALUE, local.food + extra_clicks)
            baseline.session_taps = min(
                MAX_VALUE, baseline.session_taps + local.session_taps + passive
            )
            baseline.play_seconds += online
            baseline.earn(
                local.coin + extra_clicks + passive,
                local.experience + min(passive, int(online)),
            )
            baseline.last_active_at = now
        elif baseline.last_active_at:
            gain = offline_income(
                baseline, self.started_at - baseline.last_active_at, self.started_at
            )
            if gain:
                self.tell(f"Пока ты отдыхал, помощники собрали {gain} монет")
        if was_trusted:
            baseline.last_active_at = self.started_at
        for command in self._journal if was_trusted else []:
            name, args, at = (
                command.get("name"),
                command.get("args", []),
                command.get("at", self.started_at),
            )
            if name == "tick":
                advance(baseline, at)
            elif name == "offline":
                offline_income(baseline, args[0], at)
            else:
                perform(baseline, name, args, at)
        self.state = baseline
        self.trusted = self.cloud_ready = True
        self.connection = "online"
        self.dirty = self.dirty or remote is None or bool(self._journal)
        self._journal.clear()
        self._revision += 1
        self.persist()
        self.notify()

    async def bootstrap(self, prefs):
        while self._running:
            try:
                stored_id = await prefs.get("device_id")
                new_identity = not stored_id and not self.device_id
                identity = str(stored_id or self.device_id or uuid.uuid4())
                if not stored_id:
                    await prefs.set("device_id", identity)
                if self.device_id and identity != self.device_id:
                    recent = self._journal[self._restored_pending :]
                    taps = sum(
                        op.get("args", [0])[0]
                        for op in recent
                        if op.get("name") == "tap"
                    )
                    online = sum(
                        op.get("args", [0])[0]
                        for op in recent
                        if op.get("name") in {"online", "tick"}
                    )
                    self.state = GameState(last_active_at=self.clock())
                    if taps:
                        perform(self.state, "tap", [taps], self.clock())
                    self._journal = [
                        {"name": "tap", "args": [taps], "at": self.clock()},
                        {"name": "online", "args": [online], "at": self.clock()},
                    ]
                    self._baseline = GameState()
                    self._baseline_at = 0
                    self.trusted = False
                    self.cloud_ready = False
                self.device_id = identity
                self.manager = self.manager_factory(identity)
                # Both requests start in the background, independently of the UI.
                self._tasks.append(asyncio.create_task(self.refresh_board()))
                if new_identity and not self.trusted:
                    self._merge_profile(None)
                self._tasks.append(asyncio.create_task(self._sync_loop()))
                self.persist()
                self.notify()
                return
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning("Identity initialization failed: %s", error)
                self.connection = "offline"
                self.notify()
                await asyncio.sleep(3)

    async def refresh_board(self, force=False):
        if self.demo or self._closed:
            return
        reader = self.manager or self._board_reader
        if reader is None:
            self._board_reader = reader = self.manager_factory(self.device_id)
        cancelled = False
        self.board_loading = not self.board_loaded
        self.notify()
        try:
            updated = await reader.get_top_5(force=force)
            if self._closed:
                return
            self.board_error = reader.board_error
            self.board_error_detail = getattr(reader, "board_error_message", "")
            if not self.board_error or not self.board:
                self.board = updated
            self.board_loaded = True
            if not self.board_error:
                self.board_updated_at = self.clock()
            self.persist()
        except asyncio.CancelledError:
            cancelled = True
            raise
        finally:
            self.board_loading = False
            if not cancelled and not self._closed:
                self.notify()

    async def _board_loop(self):
        while self._running:
            try:
                await self.refresh_board()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.debug("Leaderboard refresh failed (%s)", type(error).__name__)
                self.board_error = True
                self.board_error_detail = "Не удалось связаться с сервером рейтинга"
                self.notify()
            await asyncio.sleep(30 if self.board_error else 60)

    async def sync_once(self):
        if self.manager is None or self._paused or self._closed:
            return
        if not self.cloud_ready:
            remote = await self.manager.fetch_run()
            if self._closed:
                return
            self._merge_profile(remote)
        if self._paused:
            return
        if not self.dirty and self.clock() - self._last_upload < 30:
            return
        revision = self._revision
        now = self.clock()
        payload = self.state.cloud_payload(self.device_id, now)
        await self.manager.upload_run(payload)
        if self._closed:
            return
        self.dirty = revision != self._revision
        self._last_upload = now
        self.connection = "online"
        self.persist()
        self.notify()

    async def _sync_loop(self):
        retry = 15
        last_error = None
        while self._running:
            try:
                await self.sync_once()
                retry = 15
                last_error = None
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                report = (
                    logger.warning
                    if type(error).__name__ != last_error
                    else logger.debug
                )
                report(
                    "Cloud sync postponed (%s): %s",
                    type(error).__name__,
                    str(error) or "request failed",
                )
                last_error = type(error).__name__
                self.connection = "offline"
                self.cloud_ready = False
                if self.trusted:
                    self._baseline = self.state.clone()
                    self._baseline_at = self.clock()
                    self.started_at = self.clock()
                    self._journal.clear()
                self.persist()
                self.notify()
                await asyncio.sleep(retry)
                retry = min(120, retry * 2)

    async def _ticker(self):
        while self._running:
            await asyncio.sleep(1)
            self.tick()

    def start(self, prefs=None):
        if (
            self._running
            or not self._page_alive()
            or (self._close_task is not None and not self._close_task.done())
        ):
            return
        self._closed = False
        self._close_task = None
        self._running = True
        self._tasks.append(asyncio.create_task(self._ticker()))
        if not self.demo and prefs is not None:
            self._tasks.append(asyncio.create_task(self.bootstrap(prefs)))
        if not self.demo:
            self._tasks.append(asyncio.create_task(self._board_loop()))

    async def close(self):
        if self._close_task is None:
            self._closed = True
            self._running = False
            self._listeners.clear()
            self._close_task = asyncio.create_task(self._finish_close())
        await asyncio.shield(self._close_task)

    async def _finish_close(self):
        self._running = False
        self.persist()
        tasks = [task for task in self._tasks if task is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        if self.manager is not None:
            await self.manager.close()
        if self._board_reader is not None and self._board_reader is not self.manager:
            await self._board_reader.close()


def preview_session(page, device_id):
    """A side-effect-free fallback for isolated screen previews."""
    return GameSession.preview(page, device_id)


def demo_requested():
    return os.getenv("CLICKER_DEMO", "").lower() in {"1", "true", "yes"}
