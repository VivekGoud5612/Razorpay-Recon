from __future__ import annotations

import asyncpg

from recon.domain.bank.transaction import BankTransaction
from recon.domain.gateway.transaction import GatewayTransaction
from recon.domain.merchant.ledger_entry import LedgerEntry
from recon.domain.merchant.order import MerchantOrder
from recon.domain.pos.transaction import PosTransaction
from recon.domain.razorpay.adjustment import RazorpayAdjustment
from recon.domain.razorpay.order import RazorpayOrder
from recon.domain.razorpay.payment import RazorpayPayment
from recon.domain.razorpay.refund import RazorpayRefund
from recon.domain.razorpay.settlement import RazorpaySettlement
from recon.domain.razorpay.settlement_entry import RazorpaySettlementEntry
from recon.domain.razorpay.transfer import RazorpayTransfer


def map_razorpay_order(row: asyncpg.Record) -> RazorpayOrder:
    return RazorpayOrder(
        order_id=row["order_id"],
        amount=row["amount"],
        currency=row["currency"],
        status=row["status"],
        receipt=row["receipt"],
        created_at=row["created_at"],
    )


def map_razorpay_payment(row: asyncpg.Record) -> RazorpayPayment:
    return RazorpayPayment(
        payment_id=row["payment_id"],
        order_id=row["order_id"],
        amount=row["amount"],
        currency=row["currency"],
        status=row["status"],
        method=row["method"],
        fee=row["fee"],
        tax=row["tax"],
        created_at=row["created_at"],
        captured_at=row["captured_at"],
    )


def map_razorpay_refund(row: asyncpg.Record) -> RazorpayRefund:
    return RazorpayRefund(
        refund_id=row["refund_id"],
        payment_id=row["payment_id"],
        amount=row["amount"],
        currency=row["currency"],
        status=row["status"],
        created_at=row["created_at"],
        processed_at=row["processed_at"],
    )


def map_razorpay_settlement(row: asyncpg.Record) -> RazorpaySettlement:
    return RazorpaySettlement(
        settlement_id=row["settlement_id"],
        amount=row["amount"],
        fees=row["fees"],
        tax=row["tax"],
        utr=row["utr"],
        status=row["status"],
        created_at=row["created_at"],
        processed_at=row["processed_at"],
    )


def map_settlement_entry(
    row: asyncpg.Record,
) -> RazorpaySettlementEntry:
    return RazorpaySettlementEntry(
        entry_id=row["entry_id"],
        settlement_id=row["settlement_id"],
        entry_type=row["entry_type"],
        amount=row["amount"],
        debit=row["debit"],
        credit=row["credit"],
        fee=row["fee"],
        tax=row["tax"],
        payment_id=row["payment_id"],
        refund_id=row["refund_id"],
        transfer_id=row["transfer_id"],
        adjustment_id=row["adjustment_id"],
        order_id=row["order_id"],
        settlement_utr=row["settlement_utr"],
        description=row["description"],
        created_at=row["created_at"],
        settled_at=row["settled_at"],
    )


def map_razorpay_transfer(row: asyncpg.Record) -> RazorpayTransfer:
    return RazorpayTransfer(
        transfer_id=row["transfer_id"],
        payment_id=row["payment_id"],
        amount=row["amount"],
        fee=row["fee"],
        tax=row["tax"],
        status=row["status"],
        created_at=row["created_at"],
    )


def map_razorpay_adjustment(row: asyncpg.Record) -> RazorpayAdjustment:
    return RazorpayAdjustment(
        adjustment_id=row["adjustment_id"],
        settlement_id=row["settlement_id"],
        amount=row["amount"],
        description=row["description"],
        created_at=row["created_at"],
    )


def map_merchant_order(row: asyncpg.Record) -> MerchantOrder:
    return MerchantOrder(
        order_id=row["merchant_order_id"],
        amount=row["amount"],
        currency=row["currency"],
        customer_ref=row["customer_ref"],
        invoice_id=row["invoice_id"],
        razorpay_order_id=row["razorpay_order_id"],
        status=row["status"],
        created_at=row["created_at"],
    )


def map_ledger_entry(row: asyncpg.Record) -> LedgerEntry:
    return LedgerEntry(
        entry_id=row["entry_id"],
        merchant_order_id=row["merchant_order_id"],
        account_code=row["account_code"],
        entry_type=row["entry_type"],
        debit=row["debit"],
        credit=row["credit"],
        currency=row["currency"],
        posted_at=row["posted_at"],
        reference=row["reference"],
        description=row["description"],
    )


def map_bank_transaction(row: asyncpg.Record) -> BankTransaction:
    return BankTransaction(
        transaction_id=row["transaction_id"],
        utr=row["utr"],
        transaction_date=row["transaction_date"],
        value_date=row["value_date"],
        description=row["description"],
        debit=row["debit"],
        credit=row["credit"],
        balance=row["balance"],
        reference=row["reference"],
    )


def map_pos_transaction(row: asyncpg.Record) -> PosTransaction:
    return PosTransaction(
        transaction_id=row["transaction_id"],
        merchant_order_id=row["merchant_order_id"],
        razorpay_order_id=row["razorpay_order_id"],
        amount=row["amount"],
        currency=row["currency"],
        transaction_date=row["transaction_date"],
        status=row["status"],
        terminal_id=row["terminal_id"],
    )


def map_gateway_transaction(row: asyncpg.Record) -> GatewayTransaction:
    return GatewayTransaction(
        transaction_id=row["transaction_id"],
        merchant_order_id=row["merchant_order_id"],
        gateway_order_id=row["gateway_order_id"],
        amount=row["amount"],
        currency=row["currency"],
        fee=row["fee"],
        tax=row["tax"],
        status=row["status"],
        created_at=row["created_at"],
    )

