from __future__ import annotations

from dataclasses import dataclass

from recon.domain.bank.transaction import BankTransaction
from recon.domain.merchant.ledger_entry import LedgerEntry
from recon.domain.merchant.order import MerchantOrder
from recon.domain.razorpay.adjustment import RazorpayAdjustment
from recon.domain.razorpay.payment import RazorpayPayment
from recon.domain.razorpay.refund import RazorpayRefund
from recon.domain.razorpay.settlement import RazorpaySettlement
from recon.domain.razorpay.settlement_entry import RazorpaySettlementEntry
from recon.domain.razorpay.transfer import RazorpayTransfer
from recon.domain.razorpay.order import RazorpayOrder 
from recon.domain.pos.transaction import PosTransaction
from recon.domain.gateway.transaction import GatewayTransaction
from recon.domain.reconciliation.finding import ReconciliationFinding


@dataclass(slots=True)
class SettlementReconciliationData:
    settlement: RazorpaySettlement
    settlement_entries: list[RazorpaySettlementEntry]

    orders: list[RazorpayOrder]
    payments: list[RazorpayPayment]
    refunds: list[RazorpayRefund]
    transfers: list[RazorpayTransfer]
    adjustments: list[RazorpayAdjustment]

    merchant_orders: list[MerchantOrder]
    ledger_entries: list[LedgerEntry]
    bank_transactions: list[BankTransaction]
    pos_transactions: list[PosTransaction]
    gateway_transactions: list[GatewayTransaction]

    entity_imports: dict[tuple[str, str], str]  # (entity_type, entity_id) -> import_id
    object_keys: dict[str, str]     # import_id -> object_key
