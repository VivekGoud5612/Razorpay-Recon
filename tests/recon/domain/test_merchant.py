from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from recon.domain.merchant.invoice import Invoice
from recon.domain.merchant.ledger_entry import LedgerEntry
from recon.domain.merchant.order import MerchantOrder


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def test_merchant_order():
    order = MerchantOrder(
        order_id="merchant_order_001",
        amount=Decimal("5000.00"),
        currency="INR",
        customer_ref="customer_001",
        invoice_id="invoice_001",
        status="paid",
        created_at=NOW,
    )

    assert order.order_id == "merchant_order_001"
    assert order.amount == Decimal("5000.00")
    assert order.currency == "INR"
    assert order.customer_ref == "customer_001"
    assert order.invoice_id == "invoice_001"
    assert order.status == "paid"


def test_invoice():
    invoice = Invoice(
        invoice_id="invoice_001",
        merchant_order_id="merchant_order_001",
        amount=Decimal("5000.00"),
        currency="INR",
        status="paid",
        issued_at=NOW,
        due_at=None,
    )

    assert invoice.invoice_id == "invoice_001"
    assert invoice.merchant_order_id == "merchant_order_001"
    assert invoice.amount == Decimal("5000.00")
    assert invoice.status == "paid"


def test_ledger_entry():
    entry = LedgerEntry(
        entry_id="ledger_001",
        merchant_order_id="merchant_order_001",
        account_code="REVENUE",
        entry_type="credit",
        debit=Decimal("0.00"),
        credit=Decimal("5000.00"),
        currency="INR",
        posted_at=NOW,
        reference="INV-001",
        description="Revenue recognition",
    )

    assert entry.entry_id == "ledger_001"
    assert entry.merchant_order_id == "merchant_order_001"
    assert entry.account_code == "REVENUE"
    assert entry.credit == Decimal("5000.00")
    assert entry.debit == Decimal("0.00")