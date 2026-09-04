from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import asyncpg

from recon.domain.bank.transaction import BankTransaction
from recon.domain.gateway.transaction import GatewayTransaction
from recon.domain.merchant.import_ import MerchantImport
from recon.domain.merchant.ledger_entry import LedgerEntry
from recon.domain.merchant.order import MerchantOrder
from recon.domain.pos.transaction import PosTransaction
from recon.infrastructure.persistence.postgres.connection import (
    PostgresConnection,
)


class MerchantIngestionPostgresRepository:

    def __init__(
        self,
        db: PostgresConnection,
    ) -> None:
        self._db = db

    async def create_import(
        self,
        merchant_import: MerchantImport,
    ) -> MerchantImport:

        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO merchant_imports (
                    source_id,
                    import_id,
                    object_key,
                    filename,
                    content_type,
                    status,
                    records_ingested,
                    created_at,
                    completed_at
                )
                SELECT
                    s.id,
                    $1, $2, $3, $4, $5, $6, $7, $8
                FROM sources s
                WHERE s.source_id = $9
                RETURNING
                    import_id,
                    source_id,
                    object_key,
                    filename,
                    content_type,
                    status,
                    records_ingested,
                    created_at,
                    completed_at
                """,
                merchant_import.import_id,
                merchant_import.object_key,
                merchant_import.filename,
                merchant_import.content_type,
                merchant_import.status,
                merchant_import.records_ingested,
                merchant_import.created_at,
                merchant_import.completed_at,
                merchant_import.source_id,
            )

            if row is None:
                raise ValueError(
                    f"Merchant source not found: "
                    f"{merchant_import.source_id}"
                )

            source_row = await conn.fetchrow(
                "SELECT source_id FROM sources WHERE id = $1",
                row["source_id"],
            )

            return MerchantImport(
                import_id=row["import_id"],
                source_id=source_row["source_id"],
                object_key=row["object_key"],
                filename=row["filename"],
                content_type=row["content_type"],
                status=row["status"],
                records_ingested=row["records_ingested"],
                created_at=row["created_at"],
                completed_at=row["completed_at"],
            )

    async def persist_records(
        self,
        merchant_import: MerchantImport,
        entity_type: str,
        records: list[Any],
    ) -> None:

        if not records:
            return

        async with self._db.acquire() as conn:
            async with conn.transaction():

                import_row = await conn.fetchrow(
                    """
                    SELECT
                        mi.id,
                        mi.source_id
                    FROM merchant_imports mi
                    WHERE mi.import_id = $1
                    FOR UPDATE
                    """,
                    merchant_import.import_id,
                )

                if import_row is None:
                    raise ValueError(
                        f"Import not found: "
                        f"{merchant_import.import_id}"
                    )

                import_pk = import_row["id"]
                source_pk = import_row["source_id"]

                if entity_type == "merchant_order":
                    await self._persist_orders(
                        conn,
                        import_pk,
                        source_pk,
                        records,
                    )

                elif entity_type == "ledger_entry":
                    await self._persist_ledger_entries(
                        conn,
                        import_pk,
                        source_pk,
                        records,
                    )

                elif entity_type == "bank_transaction":
                    await self._persist_bank_transactions(
                        conn,
                        import_pk,
                        source_pk,
                        records,
                    )

                elif entity_type == "pos_transaction":
                    await self._persist_pos_transactions(
                        conn,
                        import_pk,
                        source_pk,
                        records,
                    )

                elif entity_type == "gateway_transaction":
                    await self._persist_gateway_transactions(
                        conn,
                        import_pk,
                        source_pk,
                        records,
                    )

                else:
                    raise ValueError(
                        f"Unsupported entity type: {entity_type}"
                    )

    async def _persist_orders(
        self,
        conn: asyncpg.Connection,
        import_pk: int,
        source_pk: int,
        records: list[MerchantOrder],
    ) -> None:

        await conn.executemany(
            """
            INSERT INTO merchant_orders (
                source_id,
                import_pk,
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
                $1, $2, $3, $4, $5,
                $6, $7, $8, $9, $10
            )
            """,
            [
                (
                    source_pk,
                    import_pk,
                    order.order_id,
                    order.razorpay_order_id,
                    order.amount,
                    order.currency,
                    order.customer_ref,
                    order.invoice_id,
                    order.status,
                    order.created_at,
                )
                for order in records
            ],
        )

    async def _persist_ledger_entries(
        self,
        conn: asyncpg.Connection,
        import_pk: int,
        source_pk: int,
        records: list[LedgerEntry],
    ) -> None:
        await conn.executemany(
            """
            INSERT INTO ledger_entries (
                source_id,
                import_pk,
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
            SELECT
                $1,
                $2,
                $3,
                mo.id,
                $4,
                $5,
                $6,
                $7,
                $8,
                $9,
                $10,
                $11
            FROM merchant_orders mo
            WHERE mo.merchant_order_id = $12
            """,
            [
                (
                    source_pk,
                    import_pk,
                    entry.entry_id,
                    entry.account_code,
                    entry.entry_type,
                    entry.debit,
                    entry.credit,
                    entry.currency,
                    entry.posted_at,
                    entry.reference,
                    entry.description,
                    entry.merchant_order_id,
                )
                for entry in records
            ],
        )

    async def _persist_bank_transactions(
        self,
        conn: asyncpg.Connection,
        import_pk: int,
        source_pk: int,
        records: list[BankTransaction],
    ) -> None:
        await conn.executemany(
            """
            INSERT INTO bank_transactions (
                source_id,
                import_pk,
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
                $2,
                $3,
                $4,
                $5,
                $6,
                $7,
                $8,
                $9,
                $10,
                $11
            )
            """,
            [
                (
                    source_pk,
                    import_pk,
                    transaction.transaction_id,
                    transaction.utr,
                    transaction.transaction_date,
                    transaction.value_date,
                    transaction.description,
                    transaction.debit,
                    transaction.credit,
                    transaction.balance,
                    transaction.reference,
                )
                for transaction in records
            ],
        )

    async def _persist_pos_transactions(
        self,
        conn: asyncpg.Connection,
        import_pk: int,
        source_pk: int,
        records: list[PosTransaction],
    ) -> None:
        await conn.executemany(
            """
            INSERT INTO pos_transactions (
                source_id,
                import_pk,
                transaction_id,
                merchant_order_id,
                razorpay_order_id,
                amount,
                currency,
                transaction_date,
                status,
                terminal_id
            )
            VALUES (
                $1,
                $2,
                $3,
                $4,
                $5,
                $6,
                $7,
                $8,
                $9,
                $10
            )
            """,
            [
                (
                    source_pk,
                    import_pk,
                    transaction.transaction_id,
                    transaction.merchant_order_id,
                    transaction.razorpay_order_id,
                    transaction.amount,
                    transaction.currency,
                    transaction.transaction_date,
                    transaction.status,
                    transaction.terminal_id,
                )
                for transaction in records
            ],
        )

    async def _persist_gateway_transactions(
        self,
        conn: asyncpg.Connection,
        import_pk: int,
        source_pk: int,
        records: list[GatewayTransaction],
    ) -> None:
        await conn.executemany(
            """
            INSERT INTO gateway_transactions (
                source_id,
                import_pk,
                transaction_id,
                merchant_order_id,
                gateway_order_id,
                amount,
                currency,
                fee,
                tax,
                status,
                created_at
            )
            VALUES (
                $1,
                $2,
                $3,
                $4,
                $5,
                $6,
                $7,
                $8,
                $9,
                $10,
                $11
            )
            """,
            [
                (
                    source_pk,
                    import_pk,
                    transaction.transaction_id,
                    transaction.merchant_order_id,
                    transaction.gateway_order_id,
                    transaction.amount,
                    transaction.currency,
                    transaction.fee,
                    transaction.tax,
                    transaction.status,
                    transaction.created_at,
                )
                for transaction in records
            ],
        )

    async def complete_import(
        self,
        import_id: str,
        records_ingested: int,
    ) -> MerchantImport:
        completed_at = datetime.now(timezone.utc)

        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE merchant_imports
                SET
                    status = 'completed',
                    records_ingested = $2,
                    completed_at = $3
                WHERE import_id = $1
                RETURNING
                    import_id,
                    source_id,
                    object_key,
                    filename,
                    content_type,
                    status,
                    records_ingested,
                    created_at,
                    completed_at
                """,
                import_id,
                records_ingested,
                completed_at,
            )

            if row is None:
                raise ValueError(f"Import not found: {import_id}")

            source_id = await conn.fetchval(
                "SELECT source_id FROM sources WHERE id = $1",
                row["source_id"],
            )

            return MerchantImport(
                import_id=row["import_id"],
                source_id=source_id,
                object_key=row["object_key"],
                filename=row["filename"],
                content_type=row["content_type"],
                status=row["status"],
                records_ingested=row["records_ingested"],
                created_at=row["created_at"],
                completed_at=row["completed_at"],
            )

    async def fail_import(
        self,
        import_id: str,
    ) -> MerchantImport:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE merchant_imports
                SET status = 'failed'
                WHERE import_id = $1
                RETURNING
                    import_id,
                    source_id,
                    object_key,
                    filename,
                    content_type,
                    status,
                    records_ingested,
                    created_at,
                    completed_at
                """,
                import_id,
            )

            if row is None:
                raise ValueError(f"Import not found: {import_id}")

            source_id = await conn.fetchval(
                "SELECT source_id FROM sources WHERE id = $1",
                row["source_id"],
            )

            return MerchantImport(
                import_id=row["import_id"],
                source_id=source_id,
                object_key=row["object_key"],
                filename=row["filename"],
                content_type=row["content_type"],
                status=row["status"],
                records_ingested=row["records_ingested"],
                created_at=row["created_at"],
                completed_at=row["completed_at"],
            )