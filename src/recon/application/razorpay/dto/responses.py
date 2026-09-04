from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreateOrderResponse:
    order_id: str
    amount: int
    amount_paid: int
    amount_due: int
    currency: str
    receipt: str | None
    status: str
    attempts: int
    created_at: int


@dataclass(frozen=True, slots=True)
class PaymentResponse:
    payment_id: str
    order_id: str | None
    amount: int
    currency: str
    status: str
    method: str | None
    captured: bool
    fee: int | None
    tax: int | None
    created_at: int
    captured_at: int | None


@dataclass(frozen=True, slots=True)
class RefundResponse:
    refund_id: str
    payment_id: str
    amount: int
    currency: str
    status: str
    created_at: int
    processed_at: int | None


@dataclass(frozen=True, slots=True)
class TransferResponse:
    transfer_id: str
    payment_id: str
    amount: int
    fee: int
    tax: int
    status: str
    created_at: int


@dataclass(frozen=True, slots=True)
class AdjustmentResponse:
    adjustment_id: str
    settlement_id: str
    amount: int
    description: str | None
    created_at: int


@dataclass(frozen=True, slots=True)
class SettlementResponse:
    settlement_id: str
    amount: int
    fees: int
    tax: int
    utr: str | None
    status: str
    created_at: int
    processed_at: int | None


@dataclass(frozen=True, slots=True)
class SettlementReconResponse:
    entity_id: str
    entity_type: str
    debit: int
    credit: int
    amount: int
    currency: str
    fee: int
    tax: int
    settled: bool
    settlement_id: str
    settlement_utr: str | None
    order_id: str | None
    payment_id: str | None
    created_at: int
    settled_at: int | None
    description: str | None