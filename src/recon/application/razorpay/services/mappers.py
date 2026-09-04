from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from recon.application.razorpay.dto.responses import (
    AdjustmentResponse,
    CreateOrderResponse,
    PaymentResponse,
    RefundResponse,
    SettlementReconResponse,
    SettlementResponse,
    TransferResponse,
)

from recon.domain.razorpay.adjustment import RazorpayAdjustment
from recon.domain.razorpay.order import RazorpayOrder
from recon.domain.razorpay.payment import RazorpayPayment
from recon.domain.razorpay.refund import RazorpayRefund
from recon.domain.razorpay.settlement import RazorpaySettlement
from recon.domain.razorpay.settlement_entry import RazorpaySettlementEntry
from recon.domain.razorpay.transfer import RazorpayTransfer


def map_order_response_to_domain(
    response: CreateOrderResponse,
) -> RazorpayOrder:
    return RazorpayOrder(
        order_id=response.order_id,
        amount=Decimal(response.amount) / Decimal("100"),
        currency=response.currency,
        status=response.status,
        receipt=response.receipt,
        created_at=datetime.fromtimestamp(response.created_at, tz=timezone.utc),
    )


def map_payment_response_to_domain(
    response: PaymentResponse,
) -> RazorpayPayment:
    return RazorpayPayment(
        payment_id=response.payment_id,
        order_id=response.order_id,
        amount=Decimal(response.amount) / Decimal("100"),
        currency=response.currency,
        status=response.status,
        method=response.method,
        fee=Decimal(response.fee or 0) / Decimal("100"),
        tax=Decimal(response.tax or 0) / Decimal("100"),
        created_at=datetime.fromtimestamp(response.created_at, tz=timezone.utc),
        captured_at=(
            datetime.fromtimestamp(response.captured_at, tz=timezone.utc)
            if response.captured_at is not None
            else None
        ),
    )


def map_settlement_response_to_domain(
    response: SettlementResponse,
) -> RazorpaySettlement:
    return RazorpaySettlement(
        settlement_id=response.settlement_id,
        amount=Decimal(response.amount) / Decimal("100"),
        fees=Decimal(response.fees) / Decimal("100"),
        tax=Decimal(response.tax) / Decimal("100"),
        utr=response.utr,
        status=response.status,
        created_at=datetime.fromtimestamp(response.created_at, tz=timezone.utc),
        processed_at=(
            datetime.fromtimestamp(response.processed_at, tz=timezone.utc)
            if response.processed_at is not None
            else None
        ),
    )


def map_settlement_recon_to_domain(
    response: SettlementReconResponse,
) -> RazorpaySettlementEntry:
    return RazorpaySettlementEntry(
        entry_id=response.entity_id,
        settlement_id=response.settlement_id,
        entry_type=response.entity_type,
        amount=Decimal(response.amount) / Decimal("100"),
        debit=Decimal(response.debit) / Decimal("100"),
        credit=Decimal(response.credit) / Decimal("100"),
        fee=Decimal(response.fee) / Decimal("100"),
        tax=Decimal(response.tax) / Decimal("100"),
        payment_id=response.payment_id,
        refund_id=response.entity_id if response.entity_type == "refund" else None,
        transfer_id=response.entity_id if response.entity_type == "transfer" else None,
        adjustment_id=response.entity_id if response.entity_type == "adjustment" else None,
        order_id=response.order_id,
        settlement_utr=response.settlement_utr,
        description=response.description,
        created_at=datetime.fromtimestamp(response.created_at, tz=timezone.utc),
        settled_at=(
            datetime.fromtimestamp(response.settled_at, tz=timezone.utc)
            if response.settled_at is not None
            else None
        ),
    )


def map_refund_response_to_domain(
    response: RefundResponse,
) -> RazorpayRefund:
    return RazorpayRefund(
        refund_id=response.refund_id,
        payment_id=response.payment_id,
        amount=Decimal(response.amount) / Decimal("100"),
        currency=response.currency,
        status=response.status,
        created_at=datetime.fromtimestamp(response.created_at, tz=timezone.utc),
        processed_at=(
            datetime.fromtimestamp(response.processed_at, tz=timezone.utc)
            if response.processed_at is not None
            else None
        ),
    )


def map_transfer_response_to_domain(
    response: TransferResponse,
) -> RazorpayTransfer:
    return RazorpayTransfer(
        transfer_id=response.transfer_id,
        payment_id=response.payment_id,
        amount=Decimal(response.amount) / Decimal("100"),
        fee=Decimal(response.fee) / Decimal("100"),
        tax=Decimal(response.tax) / Decimal("100"),
        status=response.status,
        created_at=datetime.fromtimestamp(response.created_at, tz=timezone.utc),
    )


def map_adjustment_response_to_domain(
    response: AdjustmentResponse,
) -> RazorpayAdjustment:
    return RazorpayAdjustment(
        adjustment_id=response.adjustment_id,
        settlement_id=response.settlement_id,
        amount=Decimal(response.amount) / Decimal("100"),
        description=response.description,
        created_at=datetime.fromtimestamp(response.created_at, tz=timezone.utc),
    )