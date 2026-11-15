"""Async API access with one reusable client and a shared leaderboard cache."""

import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)


class LeaderboardManager:
    def __init__(
        self,
        device_id: str,
        username: str = "",
        db_url="https://microservice-a2vk.onrender.com/leaderboard",
        *,
        client=None,
    ):
        self.db_url = db_url
        self.device_id = self.session_id = device_id
        self.username = username
        self.start_time = time.time()
        self._last_upload = 0.0
        self._client = client
        self._board = []
        self._board_time = 0.0
        self._board_loaded = False
        self._board_task = None
        self.board_error = False
        self.board_error_message = ""
        self._board_retry_after = 0.0
        self._board_failures = 0

    def _http(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30, connect=5, pool=5)
            )
        return self._client

    async def fetch_run(self):
        """None means an actual 200/null profile, never a connection failure."""
        base = self.db_url.rsplit("/leaderboard", 1)[0]
        response = await self._http().get(f"{base}/user/{self.device_id}")
        response.raise_for_status()
        if not response.text.strip():
            raise ValueError("Empty player response")
        data = response.json()
        if data is None:
            return None
        if not isinstance(data, dict):
            raise ValueError("Invalid player response")
        return data

    async def get_run(self):
        """Compatibility helper for old callers that only display data."""
        try:
            return await self.fetch_run()
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("Could not load player progress: %s", error)
            return None

    async def upload_run(self, data):
        response = await self._http().put(self.db_url, json=data)
        response.raise_for_status()

    async def _upload_score(self, data):
        try:
            await self.upload_run(data)
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("Could not save player progress: %s", error)

    def save_run(
        self,
        level,
        taps=0,
        username=None,
        base_auto_click_power=0,
        offline_income_power=0,
        coin=0,
        base_click_power=1,
        double_click_price=10,
        boost_level=0,
        boost_price=20,
    ):
        now = time.time()
        if now - self._last_upload <= 5:
            return
        self._last_upload = now
        data = {
            "level": level,
            "time": int(now - self.start_time),
            "taps": taps,
            "id": self.device_id,
            "last_update": now,
            "username": self.username if username is None else username,
            "base_auto_click_power": base_auto_click_power,
            "offline_income_power": offline_income_power,
            "coin": coin,
            "base_click_power": base_click_power,
            "double_click_price": double_click_price,
            "boost_level": boost_level,
            "boost_price": boost_price,
        }
        try:
            asyncio.get_running_loop().create_task(self._upload_score(data))
        except RuntimeError:
            return

    async def _fetch_board(self):
        try:
            response = await self._http().get(
                self.db_url, timeout=httpx.Timeout(8, connect=5)
            )
            response.raise_for_status()
            data = response.json() if response.text.strip() else []
            if isinstance(data, dict):
                data = list(data.values())
            if not isinstance(data, list):
                data = []
            board = [row for row in data if isinstance(row, dict)]

            def numeric(row, key, default=0):
                value = row.get(key, default)
                return value if isinstance(value, (int, float)) else default

            board.sort(
                key=lambda row: (
                    -numeric(row, "level"),
                    -numeric(row, "taps"),
                    numeric(row, "time", 999999),
                )
            )
            self._board = board[:5]
            self._board_time = time.monotonic()
            self._board_loaded = True
            self.board_error = response.headers.get("X-Leaderboard-Stale") == "1"
            self.board_error_message = (
                "Сервер показывает сохранённый рейтинг" if self.board_error else ""
            )
            self._board_failures = 0
            self._board_retry_after = 0.0
        except (httpx.HTTPError, ValueError) as error:
            self.board_error = True
            self.board_error_message = (
                "Сервер рейтинга ещё не подключён к базе"
                if isinstance(error, httpx.HTTPStatusError)
                and error.response.status_code == 503
                else "Сервер рейтинга не ответил. Результаты на устройстве сохранены"
            )
            self._board_failures += 1
            self._board_retry_after = time.monotonic() + min(
                120, 15 * 2 ** min(3, self._board_failures - 1)
            )
            report = logger.warning if self._board_failures == 1 else logger.debug
            report(
                "Could not update leaderboard (%s): %s",
                type(error).__name__,
                str(error) or "request failed",
            )
        return list(self._board)

    async def get_top_5(self, force=False):
        if not force and time.monotonic() < self._board_retry_after:
            return list(self._board)
        if (
            not force
            and self._board_loaded
            and time.monotonic() - self._board_time < 30
        ):
            return list(self._board)
        if self._board_task is None or self._board_task.done():
            self._board_task = asyncio.create_task(self._fetch_board())
        return await asyncio.shield(self._board_task)

    async def close(self):
        if self._board_task is not None and not self._board_task.done():
            self._board_task.cancel()
            await asyncio.gather(self._board_task, return_exceptions=True)
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
