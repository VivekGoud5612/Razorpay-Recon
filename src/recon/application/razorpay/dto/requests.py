from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreateOrderRequest:
    amount: int
    currency: str
    receipt: str


@dataclass(frozen=True, slots=True)
class CapturePaymentRequest:
    amount: int


@dataclass(frozen=True, slots=True)
class FetchSettlementReconRequest:
    year: int
    month: int
    day: int | None = None
    count: int = 100
    skip: int = 0