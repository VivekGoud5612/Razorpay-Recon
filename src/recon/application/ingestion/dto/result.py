from __future__ import annotations

from dataclasses import dataclass, field

from recon.domain.bank.transaction import BankTransaction
from recon.domain.merchant.ledger_entry import LedgerEntry
from recon.domain.merchant.order import MerchantOrder


@dataclass(slots=True, frozen=True, kw_only=True)
class IngestionResult:
    merchant_orders: list[MerchantOrder] = field(default_factory=list)
    invoices: list[Invoice] = field(default_factory=list)
    ledger_entries: list[LedgerEntry] = field(default_factory=list)
    bank_transactions: list[BankTransaction] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

