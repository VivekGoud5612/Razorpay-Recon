from __future__ import annotations

from recon.domain.razorpay.adjustment import RazorpayAdjustment
from recon.domain.razorpay.order import RazorpayOrder
from recon.domain.razorpay.payment import RazorpayPayment
from recon.domain.razorpay.refund import RazorpayRefund
from recon.domain.razorpay.settlement import RazorpaySettlement
from recon.domain.razorpay.settlement_entry import RazorpaySettlementEntry
from recon.domain.razorpay.transfer import RazorpayTransfer

from recon.infrastructure.persistence.postgres.connection import PostgresConnection


class RazorpayPostgresRepository:

    def __init__(self, db: PostgresConnection) -> None:
        self._db = db

    async def save_order(
        self,
        order: RazorpayOrder,
    ) -> RazorpayOrder:

        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO razorpay_orders (
                    order_id,
                    amount,
                    currency,
                    status,
                    receipt,
                    created_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6
                )
                ON CONFLICT (order_id)
                DO UPDATE SET
                    amount = EXCLUDED.amount,
                    currency = EXCLUDED.currency,
                    status = EXCLUDED.status,
                    receipt = EXCLUDED.receipt,
                    created_at = EXCLUDED.created_at
                RETURNING
                    order_id,
                    amount,
                    currency,
                    status,
                    receipt,
                    created_at
                """,
                order.order_id,
                order.amount,
                order.currency,
                order.status,
                order.receipt,
                order.created_at,
            )

            if row is None:
                raise RuntimeError(
                    f"Failed to persist Razorpay order: "
                    f"{order.order_id}"
                )

            return RazorpayOrder(
                order_id=row["order_id"],
                amount=row["amount"],
                currency=row["currency"],
                status=row["status"],
                receipt=row["receipt"],
                created_at=row["created_at"],
            )

    async def save_payment(
        self,
        payment: RazorpayPayment,
    ) -> RazorpayPayment:

        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO payments (
                    payment_id,
                    order_id,
                    amount,
                    currency,
                    status,
                    method,
                    fee,
                    tax,
                    created_at,
                    captured_at
                )
                VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7, $8, $9, $10
                )
                ON CONFLICT (payment_id)
                DO UPDATE SET
                    order_id = EXCLUDED.order_id,
                    amount = EXCLUDED.amount,
                    currency = EXCLUDED.currency,
                    status = EXCLUDED.status,
                    method = EXCLUDED.method,
                    fee = EXCLUDED.fee,
                    tax = EXCLUDED.tax,
                    created_at = EXCLUDED.created_at,
                    captured_at = EXCLUDED.captured_at
                RETURNING
                    payment_id,
                    order_id,
                    amount,
                    currency,
                    status,
                    method,
                    fee,
                    tax,
                    created_at,
                    captured_at
                """,
                payment.payment_id,
                payment.order_id,
                payment.amount,
                payment.currency,
                payment.status,
                payment.method,
                payment.fee,
                payment.tax,
                payment.created_at,
                payment.captured_at,
            )

            if row is None:
                raise RuntimeError(
                    f"Failed to persist Razorpay payment: "
                    f"{payment.payment_id}"
                )

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

    async def save_settlement(self, settlement: RazorpaySettlement) -> RazorpaySettlement:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO settlements (
                    settlement_id,
                    amount,
                    fees,
                    tax,
                    utr,
                    status,
                    created_at,
                    processed_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (settlement_id)
                DO UPDATE SET
                    amount = EXCLUDED.amount,
                    fees = EXCLUDED.fees,
                    tax = EXCLUDED.tax,
                    utr = EXCLUDED.utr,
                    status = EXCLUDED.status,
                    created_at = EXCLUDED.created_at,
                    processed_at = EXCLUDED.processed_at
                RETURNING
                    settlement_id,
                    amount,
                    fees,
                    tax,
                    utr,
                    status,
                    created_at,
                    processed_at
                """,
                settlement.settlement_id,
                settlement.amount,
                settlement.fees,
                settlement.tax,
                settlement.utr,
                settlement.status,
                settlement.created_at,
                settlement.processed_at,
            )

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

    async def save_settlement_entry(
        self,
        entry: RazorpaySettlementEntry,
    ) -> RazorpaySettlementEntry:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO settlement_entries (
                    entry_id,
                    settlement_id,
                    entry_type,
                    amount,
                    debit,
                    credit,
                    fee,
                    tax,
                    payment_id,
                    refund_id,
                    transfer_id,
                    adjustment_id,
                    order_id,
                    settlement_utr,
                    description,
                    created_at,
                    settled_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9,
                    $10, $11, $12, $13, $14, $15, $16, $17
                )
                ON CONFLICT (entry_id)
                DO UPDATE SET
                    settlement_id = EXCLUDED.settlement_id,
                    entry_type = EXCLUDED.entry_type,
                    amount = EXCLUDED.amount,
                    debit = EXCLUDED.debit,
                    credit = EXCLUDED.credit,
                    fee = EXCLUDED.fee,
                    tax = EXCLUDED.tax,
                    payment_id = EXCLUDED.payment_id,
                    refund_id = EXCLUDED.refund_id,
                    transfer_id = EXCLUDED.transfer_id,
                    adjustment_id = EXCLUDED.adjustment_id,
                    order_id = EXCLUDED.order_id,
                    settlement_utr = EXCLUDED.settlement_utr,
                    description = EXCLUDED.description,
                    created_at = EXCLUDED.created_at,
                    settled_at = EXCLUDED.settled_at
                RETURNING
                    entry_id,
                    settlement_id,
                    entry_type,
                    amount,
                    debit,
                    credit,
                    fee,
                    tax,
                    payment_id,
                    refund_id,
                    transfer_id,
                    adjustment_id,
                    order_id,
                    settlement_utr,
                    description,
                    created_at,
                    settled_at
                """,
                entry.entry_id,
                entry.settlement_id,
                entry.entry_type,
                entry.amount,
                entry.debit,
                entry.credit,
                entry.fee,
                entry.tax,
                entry.payment_id,
                entry.refund_id,
                entry.transfer_id,
                entry.adjustment_id,
                entry.order_id,
                entry.settlement_utr,
                entry.description,
                entry.created_at,
                entry.settled_at,
            )

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

    async def save_refund(
        self,
        refund: RazorpayRefund,
    ) -> RazorpayRefund:

        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO refunds (
                    refund_id,
                    payment_id,
                    amount,
                    currency,
                    status,
                    created_at,
                    processed_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (refund_id)
                DO UPDATE SET
                    payment_id = EXCLUDED.payment_id,
                    amount = EXCLUDED.amount,
                    currency = EXCLUDED.currency,
                    status = EXCLUDED.status,
                    created_at = EXCLUDED.created_at,
                    processed_at = EXCLUDED.processed_at
                RETURNING
                    refund_id,
                    payment_id,
                    amount,
                    currency,
                    status,
                    created_at,
                    processed_at
                """,
                refund.refund_id,
                refund.payment_id,
                refund.amount,
                refund.currency,
                refund.status,
                refund.created_at,
                refund.processed_at,
            )

            if row is None:
                raise RuntimeError(f"Failed to persist Razorpay refund: {refund.refund_id}")

            return RazorpayRefund(
                refund_id=row["refund_id"],
                payment_id=row["payment_id"],
                amount=row["amount"],
                currency=row["currency"],
                status=row["status"],
                created_at=row["created_at"],
                processed_at=row["processed_at"],
            )

    async def save_transfer(
        self,
        transfer: RazorpayTransfer,
    ) -> RazorpayTransfer:

        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO transfers (
                    transfer_id,
                    payment_id,
                    amount,
                    fee,
                    tax,
                    status,
                    created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (transfer_id)
                DO UPDATE SET
                    payment_id = EXCLUDED.payment_id,
                    amount = EXCLUDED.amount,
                    fee = EXCLUDED.fee,
                    tax = EXCLUDED.tax,
                    status = EXCLUDED.status,
                    created_at = EXCLUDED.created_at
                RETURNING
                    transfer_id,
                    payment_id,
                    amount,
                    fee,
                    tax,
                    status,
                    created_at
                """,
                transfer.transfer_id,
                transfer.payment_id,
                transfer.amount,
                transfer.fee,
                transfer.tax,
                transfer.status,
                transfer.created_at,
            )

            if row is None:
                raise RuntimeError(f"Failed to persist Razorpay transfer: {transfer.transfer_id}")

            return RazorpayTransfer(
                transfer_id=row["transfer_id"],
                payment_id=row["payment_id"],
                amount=row["amount"],
                fee=row["fee"],
                tax=row["tax"],
                status=row["status"],
                created_at=row["created_at"],
            )

    async def save_adjustment(
        self,
        adjustment: RazorpayAdjustment,
    ) -> RazorpayAdjustment:

        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO adjustments (
                    adjustment_id,
                    settlement_id,
                    amount,
                    description,
                    created_at
                )
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (adjustment_id)
                DO UPDATE SET
                    settlement_id = EXCLUDED.settlement_id,
                    amount = EXCLUDED.amount,
                    description = EXCLUDED.description,
                    created_at = EXCLUDED.created_at
                RETURNING
                    adjustment_id,
                    settlement_id,
                    amount,
                    description,
                    created_at
                """,
                adjustment.adjustment_id,
                adjustment.settlement_id,
                adjustment.amount,
                adjustment.description,
                adjustment.created_at,
            )

            if row is None:
                raise RuntimeError(f"Failed to persist Razorpay adjustment: {adjustment.adjustment_id}")

            return RazorpayAdjustment(
                adjustment_id=row["adjustment_id"],
                settlement_id=row["settlement_id"],
                amount=row["amount"],
                description=row["description"],
                created_at=row["created_at"],
            )