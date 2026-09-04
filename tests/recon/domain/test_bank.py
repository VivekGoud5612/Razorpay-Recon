from __future__ import annotations

from datetime import date
from decimal import Decimal

from recon.domain.bank.transaction import BankTransaction


def test_bank_transaction():
    transaction = BankTransaction(
        transaction_id="bank_tx_001",
        utr="UTR001",
        transaction_date=date(2026, 8, 25),
        value_date=date(2026, 8, 25),
        description="Razorpay settlement",
        debit=Decimal("0.00"),
        credit=Decimal("4882.00"),
        balance=Decimal("104882.00"),
        reference="setl_001",
    )

    assert transaction.transaction_id == "bank_tx_001"
    assert transaction.utr == "UTR001"
    assert transaction.credit == Decimal("4882.00")
    assert transaction.debit == Decimal("0.00")
    assert transaction.reference == "setl_001"