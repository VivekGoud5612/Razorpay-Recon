from __future__ import annotations

from dataclasses import dataclass 

from recon.domain.bank.transaction import BankTransaction
from recon.domain.merchant.ledger_entry import LedgerEntry
from recon.domain.merchant.order import MerchantOrder
from recon.domain.pos.transaction import PosTransaction
from recon.domain.gateway.transaction import GatewayTransaction


@dataclass(slots=True, frozen=True, kw_only=True)
class NormalizationResult:
    entity_type: str
    entity_confidence: float
    field_mappings: list[FieldMapping]
    records: list[dict[str, object]]
    warnings: list[str]
    errors: list[str]


@dataclass(slots=True)
class FieldMapping:
    source_column: str
    canonical_field: str
    confidence: float
    reason: str


@dataclass(slots=True)
class DetectedEntity:
    entity_type: str
    confidence: float
    reasons: list[str]


@dataclass(slots=True)
class NormalizedDomainRecords:
    merchant_orders: list[MerchantOrder]
    ledger_entries: list[LedgerEntry]
    bank_transactions: list[BankTransaction]
    pos_transactions: list[PosTransaction]
    gateway_transactions: list[GatewayTransaction]

    def count(self) -> int:
        return (
            len(self.merchant_orders)
            + len(self.ledger_entries)
            + len(self.bank_transactions)
            + len(self.pos_transactions)
            + len(self.gateway_transactions)
        )
    