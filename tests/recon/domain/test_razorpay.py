from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from recon.domain.razorpay.adjustment import RazorpayAdjustment
from recon.domain.razorpay.order import RazorpayOrder
from recon.domain.razorpay.payment import RazorpayPayment
from recon.domain.razorpay.refund import RazorpayRefund
from recon.domain.razorpay.settlement import RazorpaySettlement
from recon.domain.razorpay.settlement_entry import RazorpaySettlementEntry
from recon.domain.razorpay.transfer import RazorpayTransfer


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def test_razorpay_order():
    order = RazorpayOrder(
        order_id="order_001",
        amount=Decimal("5000.00"),
        currency="INR",
        status="created",
        receipt="receipt_001",
        created_at=NOW,
    )

    assert order.order_id == "order_001"
    assert order.amount == Decimal("5000.00")
    assert order.currency == "INR"
    assert order.status == "created"


def test_razorpay_payment():
    payment = RazorpayPayment(
        payment_id="pay_001",
        order_id="order_001",
        amount=Decimal("5000.00"),
        currency="INR",
        status="captured",
        method="card",
        fee=Decimal("100.00"),
        tax=Decimal("18.00"),
        created_at=NOW,
        captured_at=NOW,
    )

    assert payment.payment_id == "pay_001"
    assert payment.order_id == "order_001"
    assert payment.amount == Decimal("5000.00")
    assert payment.status == "captured"
    assert payment.fee == Decimal("100.00")
    assert payment.tax == Decimal("18.00")


def test_razorpay_refund():
    refund = RazorpayRefund(
        refund_id="rfnd_001",
        payment_id="pay_001",
        amount=Decimal("1000.00"),
        currency="INR",
        status="processed",
        created_at=NOW,
        processed_at=NOW,
    )

    assert refund.refund_id == "rfnd_001"
    assert refund.payment_id == "pay_001"
    assert refund.amount == Decimal("1000.00")
    assert refund.status == "processed"


def test_razorpay_settlement():
    settlement = RazorpaySettlement(
        settlement_id="setl_001",
        amount=Decimal("5000.00"),
        fees=Decimal("100.00"),
        tax=Decimal("18.00"),
        utr="utr_001",
        status="processed",
        created_at=NOW,
        processed_at=NOW,
    )

    assert settlement.settlement_id == "setl_001"
    assert settlement.amount == Decimal("5000.00")
    assert settlement.fees == Decimal("100.00")
    assert settlement.tax == Decimal("18.00")
    assert settlement.utr == "utr_001"


def test_razorpay_settlement_entry():
    entry = RazorpaySettlementEntry(
        entry_id="entry_001",
        settlement_id="setl_001",
        entry_type="payment",
        amount=Decimal("5000.00"),
        debit=Decimal("0.00"),
        credit=Decimal("5000.00"),
        fee=Decimal("100.00"),
        tax=Decimal("18.00"),
        payment_id="pay_001",
        refund_id=None,
        transfer_id=None,
        adjustment_id=None,
        order_id="order_001",
        settlement_utr="utr_001",
        description="Payment settlement",
        created_at=NOW,
        settled_at=NOW,
    )

    assert entry.entry_id == "entry_001"
    assert entry.settlement_id == "setl_001"
    assert entry.entry_type == "payment"
    assert entry.credit == Decimal("5000.00")
    assert entry.payment_id == "pay_001"


def test_razorpay_transfer():
    transfer = RazorpayTransfer(
        transfer_id="trf_001",
        payment_id="pay_001",
        amount=Decimal("500.00"),
        fee=Decimal("10.00"),
        tax=Decimal("1.80"),
        status="processed",
        created_at=NOW,
    )

    assert transfer.transfer_id == "trf_001"
    assert transfer.payment_id == "pay_001"
    assert transfer.amount == Decimal("500.00")
    assert transfer.fee == Decimal("10.00")


def test_razorpay_adjustment():
    adjustment = RazorpayAdjustment(
        adjustment_id="adj_001",
        settlement_id="setl_001",
        amount=Decimal("500.00"),
        description="Settlement correction",
        created_at=NOW,
    )

    assert adjustment.adjustment_id == "adj_001"
    assert adjustment.settlement_id == "setl_001"
    assert adjustment.amount == Decimal("500.00")
    assert adjustment.description == "Settlement correction"