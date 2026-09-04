from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, timezone
from decimal import Decimal

import asyncpg
from recon.infrastructure.persistence.postgres.config import DatabaseConfig


NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


async def seed() -> None:
    config = DatabaseConfig.from_env()
    conn = await asyncpg.connect(config.dsn)

    try:
        async with conn.transaction():

            # --------------------------------------------------
            # SOURCES
            # --------------------------------------------------

            await conn.execute(
                """
                INSERT INTO sources (
                    source_id,
                    name,
                    source_type,
                    provider
                )
                VALUES
                    ('SRC_ERP_01', 'Merchant ERP', 'erp', 'demo'),
                    ('SRC_BANK_01', 'Merchant Bank', 'bank', 'demo')
                ON CONFLICT (source_id) DO NOTHING
                """
            )

            erp_source_id = await conn.fetchval(
                """
                SELECT id
                FROM sources
                WHERE source_id = 'SRC_ERP_01'
                """
            )

            bank_source_id = await conn.fetchval(
                """
                SELECT id
                FROM sources
                WHERE source_id = 'SRC_BANK_01'
                """
            )

            # --------------------------------------------------
            # RAZORPAY ORDER
            # --------------------------------------------------

            await conn.execute(
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
                    'order_demo_001',
                    5000.00,
                    'INR',
                    'paid',
                    'receipt_demo_001',
                    $1
                )
                ON CONFLICT (order_id) DO NOTHING
                """,
                NOW,
            )

            # --------------------------------------------------
            # MERCHANT ORDER
            # --------------------------------------------------

            merchant_order_pk = await conn.fetchval(
                """
                INSERT INTO merchant_orders (
                    source_id,
                    merchant_order_id,
                    razorpay_order_id,
                    amount,
                    currency,
                    customer_ref,
                    invoice_id,
                    status,
                    created_at
                )
                VALUES (
                    $1,
                    'MORD_001',
                    'order_demo_001',
                    5000.00,
                    'INR',
                    'CUSTOMER_001',
                    'INV_001',
                    'paid',
                    $2
                )
                ON CONFLICT (source_id, merchant_order_id)
                DO UPDATE SET
                    razorpay_order_id = EXCLUDED.razorpay_order_id
                RETURNING id
                """,
                erp_source_id,
                NOW,
            )

            # --------------------------------------------------
            # INVOICE
            # --------------------------------------------------

            await conn.execute(
                """
                INSERT INTO invoices (
                    source_id,
                    invoice_id,
                    merchant_order_pk,
                    amount,
                    currency,
                    status,
                    issued_at,
                    due_at
                )
                VALUES (
                    $1,
                    'INV_001',
                    $2,
                    5000.00,
                    'INR',
                    'paid',
                    $3,
                    NULL
                )
                ON CONFLICT (source_id, invoice_id) DO NOTHING
                """,
                erp_source_id,
                merchant_order_pk,
                NOW,
            )

            # --------------------------------------------------
            # PAYMENT
            # --------------------------------------------------

            await conn.execute(
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
                    'pay_demo_001',
                    'order_demo_001',
                    5000.00,
                    'INR',
                    'captured',
                    'upi',
                    0.00,
                    0.00,
                    $1,
                    $1
                )
                ON CONFLICT (payment_id) DO NOTHING
                """,
                NOW,
            )

            # --------------------------------------------------
            # SETTLEMENT
            # --------------------------------------------------

            await conn.execute(
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
                VALUES (
                    'setl_demo_001',
                    5000.00,
                    0.00,
                    0.00,
                    'UTR_DEMO_001',
                    'processed',
                    $1,
                    $1
                )
                ON CONFLICT (settlement_id) DO NOTHING
                """,
                NOW,
            )

            # --------------------------------------------------
            # SETTLEMENT ENTRY
            # --------------------------------------------------

            await conn.execute(
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
                    'setentry_demo_001',
                    'setl_demo_001',
                    'payment',
                    5000.00,
                    0.00,
                    5000.00,
                    0.00,
                    0.00,
                    'pay_demo_001',
                    NULL,
                    NULL,
                    NULL,
                    'order_demo_001',
                    'UTR_DEMO_001',
                    'Captured payment settlement',
                    $1,
                    $1
                )
                ON CONFLICT (entry_id) DO NOTHING
                """,
                NOW,
            )

            # --------------------------------------------------
            # MERCHANT LEDGER
            # --------------------------------------------------
            #
            # V1 uses this as the merchant-side settlement
            # expectation. Full double-entry accounting can be
            # added after the vertical slice is working.
            #

            await conn.execute(
                """
                INSERT INTO ledger_entries (
                    source_id,
                    entry_id,
                    merchant_order_pk,
                    account_code,
                    entry_type,
                    debit,
                    credit,
                    currency,
                    posted_at,
                    reference,
                    description
                )
                VALUES (
                    $1,
                    'LEDGER_001',
                    $2,
                    'SETTLEMENT_RECEIVABLE',
                    'credit',
                    0.00,
                    5000.00,
                    'INR',
                    $3,
                    'INV_001',
                    'Expected Razorpay settlement'
                )
                ON CONFLICT (source_id, entry_id) DO NOTHING
                """,
                erp_source_id,
                merchant_order_pk,
                NOW,
            )

            # --------------------------------------------------
            # BANK TRANSACTION
            # --------------------------------------------------

            await conn.execute(
                """
                INSERT INTO bank_transactions (
                    source_id,
                    transaction_id,
                    utr,
                    transaction_date,
                    value_date,
                    description,
                    debit,
                    credit,
                    balance,
                    reference
                )
                VALUES (
                    $1,
                    'BANKTX_001',
                    'UTR_DEMO_001',
                    $2,
                    $2,
                    'Razorpay settlement credit',
                    0.00,
                    5000.00,
                    105000.00,
                    'setl_demo_001'
                )
                ON CONFLICT (source_id, transaction_id) DO NOTHING
                """,
                bank_source_id,
                date(2026, 8, 26),
            )

        print("✅ Happy-path scenario seeded.")
        print("   settlement_id      = setl_demo_001")
        print("   merchant_source_id = SRC_ERP_01")
        print("   UTR                 = UTR_DEMO_001")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())