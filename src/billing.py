"""Billing boundary and an explicit, non-persistent season sandbox.

There is no purchase implementation until a store SDK and server receipt
verifier are supplied. Sandbox claims never modify currency or player saves.
"""

from dataclasses import dataclass
import json
from typing import Protocol
from app_paths import asset_path

from season_catalog import LEVEL_XP, LEVELS, reward_at, season_at


@dataclass(frozen=True)
class PurchaseReceipt:
    product_id: str
    token: str
    platform: str


@dataclass(frozen=True)
class VerifiedEntitlement:
    player_id: str
    season_id: int
    expires_at: float
    transaction_id: str


class StoreProvider(Protocol):
    async def purchase(self, product_id: str) -> PurchaseReceipt: ...
    async def restore(self) -> list[PurchaseReceipt]: ...


class ReceiptVerifier(Protocol):
    async def verify(self, receipt: PurchaseReceipt) -> VerifiedEntitlement: ...


def sandbox_available():
    try:
        return (
            json.loads(
                asset_path("config/billing.json").read_text(encoding="utf-8")
            ).get("sandbox")
            is True
        )
    except (OSError, ValueError, AttributeError):
        return False


class SeasonBilling:
    def __init__(
        self,
        session,
        store: StoreProvider | None = None,
        verifier: ReceiptVerifier | None = None,
    ):
        self.session = session
        self.store = store
        self.verifier = verifier
        self.preview = False
        self.claims = set()
        self.rewards = []
        self.season_id = -1

    def toggle_preview(self):
        if not sandbox_available():
            return
        self.preview = not self.preview
        self.session.notify()

    def claim_preview(self, level):
        season = season_at(self.session.clock())
        if season["id"] != self.season_id:
            self.season_id = season["id"]
            self.claims.clear()
            self.rewards = []
        xp = self.session.state.collection.get("season", {}).get("xp", 0)
        if (
            not self.preview
            or not sandbox_available()
            or not 1 <= level <= min(LEVELS, xp // LEVEL_XP)
            or level in self.claims
        ):
            return
        self.claims.add(level)
        self.rewards.append(reward_at(level, True))
        self.session.notify()


def billing_for(session):
    if not hasattr(session, "season_billing"):
        session.season_billing = SeasonBilling(session)
    return session.season_billing
