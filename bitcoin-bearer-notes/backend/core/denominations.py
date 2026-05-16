"""Canonical BTC note denominations.

All values are satoshis. The protocol intentionally supports native 1-sat
internal bearer denominations for microcash use-cases while preserving larger
standard and treasury denominations.

Operational note: tiny denominations are valid inside the protocol, but direct
on-chain BTC redemption should aggregate below the configured dust-safe payout
threshold or route through Lightning/Fedimint-style settlement.
"""
from __future__ import annotations

from dataclasses import dataclass

SATS_PER_BTC = 100_000_000


@dataclass(frozen=True)
class Denomination:
    code: str
    sats: int
    label: str
    tier: str


NATIVE_MICRO_DENOMINATIONS: tuple[Denomination, ...] = (
    Denomination("SAT_1", 1, "1 sat", "native-micro"),
    Denomination("SAT_5", 5, "5 sats", "native-micro"),
    Denomination("SAT_10", 10, "10 sats", "native-micro"),
    Denomination("SAT_25", 25, "25 sats", "native-micro"),
    Denomination("SAT_50", 50, "50 sats", "native-micro"),
    Denomination("SAT_100", 100, "100 sats", "native-micro"),
    Denomination("SAT_250", 250, "250 sats", "native-micro"),
    Denomination("SAT_500", 500, "500 sats", "native-micro"),
)

MICRO_DENOMINATIONS: tuple[Denomination, ...] = (
    Denomination("SAT_1K", 1_000, "1,000 sats", "micro"),
    Denomination("SAT_5K", 5_000, "5,000 sats", "micro"),
    Denomination("SAT_10K", 10_000, "10,000 sats", "micro"),
    Denomination("SAT_25K", 25_000, "25,000 sats", "micro"),
    Denomination("SAT_50K", 50_000, "50,000 sats", "micro"),
    Denomination("SAT_100K", 100_000, "100,000 sats", "micro"),
    Denomination("SAT_250K", 250_000, "250,000 sats", "micro"),
    Denomination("SAT_500K", 500_000, "500,000 sats", "micro"),
    Denomination("BTC_0_01", 1_000_000, "0.01 BTC", "standard"),
    Denomination("BTC_0_05", 5_000_000, "0.05 BTC", "standard"),
    Denomination("BTC_0_10", 10_000_000, "0.10 BTC", "standard"),
    Denomination("BTC_0_25", 25_000_000, "0.25 BTC", "standard"),
    Denomination("BTC_0_50", 50_000_000, "0.50 BTC", "standard"),
    Denomination("BTC_1", 100_000_000, "1 BTC", "standard"),
)

TREASURY_DENOMINATIONS: tuple[Denomination, ...] = (
    Denomination("BTC_10", 10 * SATS_PER_BTC, "10 BTC", "treasury"),
    Denomination("BTC_50", 50 * SATS_PER_BTC, "50 BTC", "treasury"),
    Denomination("BTC_100", 100 * SATS_PER_BTC, "100 BTC", "treasury"),
    Denomination("BTC_500", 500 * SATS_PER_BTC, "500 BTC", "treasury"),
)

ALL_DENOMINATIONS: tuple[Denomination, ...] = (
    NATIVE_MICRO_DENOMINATIONS + MICRO_DENOMINATIONS + TREASURY_DENOMINATIONS
)
VALID_DENOMINATION_SATS: frozenset[int] = frozenset(d.sats for d in ALL_DENOMINATIONS)


def is_valid_denomination(sats: int) -> bool:
    return sats in VALID_DENOMINATION_SATS


def denominations_payload() -> list[dict[str, str | int]]:
    return [
        {"code": d.code, "sats": d.sats, "label": d.label, "tier": d.tier}
        for d in ALL_DENOMINATIONS
    ]
