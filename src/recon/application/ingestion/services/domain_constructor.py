from __future__ import annotations

from recon.domain.bank.transaction import BankTransaction
from recon.domain.merchant.ledger_entry import LedgerEntry
from recon.domain.merchant.order import MerchantOrder
from recon.domain.pos.transaction import PosTransaction
from recon.domain.gateway.transaction import GatewayTransaction


class MerchantDomainConstructor:

    def build(
        self,
        entity_type: str,
        record: dict,
    ):
        builders = {
            "merchant_order": self._build_order,
            "ledger_entry": self._build_ledger_entry,
            "bank_transaction": self._build_bank_transaction,
            "pos_transaction": self._build_pos_transaction,
            "gateway_transaction": self._build_gateway_transaction,
        }

        builder = builders.get(entity_type)

        if builder is None:
            raise ValueError(
                f"Unsupported entity type: {entity_type}"
            )

        return builder(record)

    def _build_order(self, record: dict) -> MerchantOrder:
        return MerchantOrder(
            order_id=record["merchant_order_id"],
            razorpay_order_id=record["razorpay_order_id"],
            amount=record["amount"],
            currency=record["currency"],
            customer_ref=record.get("customer_ref"),
            invoice_id=record.get("invoice_id"),
            status=record["status"],
            created_at=record["created_at"],
        )

    def _build_ledger_entry(self, record: dict) -> LedgerEntry:
        return LedgerEntry(
            entry_id=record["ledger_entry_id"],
            merchant_order_id=record.get("merchant_order_id"),
            account_code=record["account_code"],
            entry_type=record["entry_type"],
            debit=record.get("debit", 0),
            credit=record.get("credit", 0),
            currency=record["currency"],
            posted_at=record["posted_at"],
            reference=record.get("reference"),
            description=record.get("description"),
        )

    def _build_bank_transaction(self, record: dict) -> BankTransaction:
        return BankTransaction(
            transaction_id=record["transaction_id"],
            utr=record.get("utr"),
            transaction_date=record["transaction_date"],
            value_date=record.get("value_date"),
            description=record["description"],
            debit=record.get("debit", 0),
            credit=record.get("credit", 0),
            balance=record.get("balance"),
            reference=record.get("reference"),
        )

    def _build_pos_transaction(self, record: dict) -> PosTransaction:
        return PosTransaction(
            transaction_id=record["pos_transaction_id"],
            merchant_order_id=record["merchant_order_id"],
            razorpay_order_id=record.get("razorpay_order_id"),
            amount=record["amount"],
            currency=record["currency"],
            transaction_date=record["transaction_date"],
            status=record["status"],
            terminal_id=record["terminal_id"],
        )

    def _build_gateway_transaction(
        self,
        record: dict,
    ) -> GatewayTransaction:
        return GatewayTransaction(
            transaction_id=record["gateway_transaction_id"],
            merchant_order_id=record["merchant_order_id"],
            gateway_order_id=record["gateway_order_id"],
            amount=record["amount"],
            currency=record["currency"],
            fee=record.get("fee", 0),
            tax=record.get("tax", 0),
            status=record["status"],
            created_at=record["created_at"],
        )