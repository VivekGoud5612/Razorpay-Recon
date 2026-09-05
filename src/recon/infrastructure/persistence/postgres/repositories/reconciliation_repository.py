from __future__ import annotations

import asyncpg 

from recon.infrastructure.persistence.postgres.connection import PostgresConnection
from recon.application.reconciliation.dto.data import SettlementReconciliationData

from recon.infrastructure.persistence.postgres.mappers import (
    map_bank_transaction,
    map_gateway_transaction,
    map_ledger_entry,
    map_merchant_order,
    map_pos_transaction,
    map_razorpay_adjustment,
    map_razorpay_order,
    map_razorpay_payment,
    map_razorpay_refund,
    map_razorpay_settlement,
    map_razorpay_transfer,
    map_settlement_entry,
)
from recon.infrastructure.persistence.postgres.helpers import partition_of_entry_ids


class ReconcileSettlementPostgresRepository:

    def __init__(
        self,
        pool: PostgresConnection,
    ) -> None:
        self._db = pool 


    async def get_settlement_context(
        self,
        settlement_id: str,
        import_ids: list[str],
    ) -> SettlementReconciliationData:
        async with self._db.acquire() as conn:
            settlement = await self._get_settlement(conn, settlement_id)
            settlement_entries = await self._get_settlement_entries(conn, settlement_id)

            settlement_order_ids, payment_ids, refund_ids, transfer_ids, adjustment_ids = partition_of_entry_ids(settlement_entries)

            settlement_order_ids = set(settlement_order_ids)

            import_db_ids = await self._get_import_db_ids(conn, import_ids)
            merchant_orders, merchant_order_pks = await self._get_merchant_orders_by_imports(conn, import_db_ids)

            merchant_order_razorpay_ids = {
                order.razorpay_order_id
                for order in merchant_orders
                if order.razorpay_order_id
            }

            order_ids = settlement_order_ids | merchant_order_razorpay_ids

            orders = await self._get_orders(conn, order_ids)
            payments = await self._get_payments(conn, payment_ids)
            refunds = await self._get_refunds(conn, refund_ids)
            transfers = await self._get_transfers(conn, transfer_ids)
            adjustments = await self._get_adjustments(conn, adjustment_ids)

            ledger_entries = await self._get_ledger_entries(conn, merchant_order_pks)
            bank_transactions = await self._get_bank_transactions(
                conn,
                {
                    entry.settlement_utr
                    for entry in settlement_entries
                    if entry.settlement_utr
                },
            )
            pos_transactions = await self._get_pos_transactions(conn, import_db_ids)
            gateway_transactions = await self._get_gateway_transactions(conn, import_db_ids)

            object_keys, entity_imports = await self._get_import_metadata(conn, import_ids)

        return SettlementReconciliationData(
            settlement=settlement,
            settlement_entries=settlement_entries,
            orders=orders,
            payments=payments,
            refunds=refunds,
            transfers=transfers,
            adjustments=adjustments,
            merchant_orders=merchant_orders,
            ledger_entries=ledger_entries,
            bank_transactions=bank_transactions,
            pos_transactions=pos_transactions,
            gateway_transactions=gateway_transactions,
            object_keys=object_keys,
            entity_imports=entity_imports,
        )
    

    async def _get_settlement(
        self,
        conn: asyncpg.Connection,
        settlement_id: str,
    ):
        query =  """
        SELECT
            settlement_id,
            amount,
            fees,
            tax,
            utr,
            status,
            created_at,
            processed_at
        FROM settlements
        WHERE settlement_id = $1
        """

        row = await conn.fetchrow(query, settlement_id)
        if row is None:
            raise ValueError(f"Settlement not found: {settlement_id}")

        return map_razorpay_settlement(row)


    async def _get_settlement_entries(
        self,
        conn: asyncpg.Connection,
        settlement_id: str,
    ):
        query =  """
        SELECT
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
        FROM settlement_entries
        WHERE settlement_id = $1
        ORDER BY settled_at NULLS LAST, entry_id
        """
        rows = await conn.fetch(query, settlement_id,)

        return [
            map_settlement_entry(row) for row in rows 
        ]


    async def _get_import_db_ids(
        self,
        conn: asyncpg.Connection,
        import_ids: list[str],
    ) -> list[int]:

        if not import_ids:
            return []

        rows = await conn.fetch(
            """
            SELECT id
            FROM merchant_imports
            WHERE import_id = ANY($1::text[])
            """,
            import_ids,
        )

        found = {row["id"] for row in rows}

        if len(found) != len(import_ids):
            raise ValueError(
                "One or more import IDs were not found."
            )

        return list(found)


    async def _get_merchant_orders_by_imports(
        self,
        conn: asyncpg.Connection,
        import_db_ids: list[int],
    ):
        if not import_db_ids:
            return []

        rows = await conn.fetch(
            """
            SELECT DISTINCT
                mo.merchant_order_id,
                mo.amount,
                mo.currency,
                mo.customer_ref,
                mo.invoice_id,
                mo.razorpay_order_id,
                mo.status,
                mo.created_at,
                mo.id
            FROM merchant_orders mo
            WHERE mo.import_pk = ANY($1::bigint[])
            """,
            import_db_ids,
        )

        return (
            [map_merchant_order(row) for row in rows],
            [row["id"] for row in rows],
        )

    async def _get_ledger_entries(
        self,
        conn: asyncpg.Connection,
        merchant_order_pks: list[int],
    ):
        query = """
        SELECT DISTINCT
            le.entry_id,
            mo.merchant_order_id,
            le.account_code,
            le.entry_type,
            le.debit,
            le.credit,
            le.currency,
            le.posted_at,
            le.reference,
            le.description
        FROM ledger_entries le
        JOIN merchant_orders mo
            ON mo.id = le.merchant_order_pk
        WHERE le.merchant_order_pk = ANY($1::bigint[])
        """
        rows = await conn.fetch(query, merchant_order_pks)
        return [
            map_ledger_entry(row) for row in rows 
        ]


    async def _get_bank_transactions(
        self,
        conn: asyncpg.Connection,
        utrs: set[str],
    ):
        # Matched by UTR only, deliberately not import-scoped: a merchant's
        # bank statement is not tied 1:1 to one ingestion batch the way
        # merchant_orders/ledger/POS/gateway are (RELATION_RULES' own
        # settlement<->bank_transaction edge is UTR-keyed for the same
        # reason). But re-ingesting the identical statement file (e.g. this
        # scenario re-run from a clean merchant state, or a merchant simply
        # re-uploading a rolling statement that repeats prior days) creates
        # a genuinely new row each time under a fresh import_pk -- with no
        # dedup, that silently inflates the observed total on every re-run.
        # DISTINCT ON collapses rows that are identical in every financial
        # respect (same utr/debit/credit/date) down to one -- an exact-value
        # match, not fuzzy: two bank rows for the same UTR that actually
        # differ in amount or date are NOT collapsed, and still surface as
        # two real rows for BANK_SETTLEMENT_AMOUNT_DIFFERENCE to reason
        # about.
        if not utrs:
            return []

        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (utr, transaction_date, debit, credit)
                transaction_id,
                utr,
                transaction_date,
                value_date,
                description,
                debit,
                credit,
                balance,
                reference
            FROM bank_transactions
            WHERE utr = ANY($1::text[])
            ORDER BY utr, transaction_date, debit, credit, id DESC
            """,
            list(utrs),
        )

        return [
            map_bank_transaction(row)
            for row in rows
        ]

    async def _get_payments(
        self,
        conn: asyncpg.Connection,
        payment_ids: list[str],
    ):

        if not payment_ids:
            return []

        rows = await conn.fetch(
            """
            SELECT
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
            FROM payments
            WHERE payment_id = ANY($1::text[])
            """,
            payment_ids,
        )

        return [map_razorpay_payment(row) for row in rows]


    async def _get_refunds(
        self,
        conn: asyncpg.Connection,
        refund_ids: list[str],
    ):

        if not refund_ids:
            return []

        rows = await conn.fetch(
            """
            SELECT
                refund_id,
                payment_id,
                amount,
                currency,
                status,
                created_at,
                processed_at
            FROM refunds
            WHERE refund_id = ANY($1::text[])
            """,
            refund_ids,
        )

        return [map_razorpay_refund(row) for row in rows]


    async def _get_transfers(
        self,
        conn: asyncpg.Connection,
        transfer_ids: list[str],
    ):

        if not transfer_ids:
            return []

        rows = await conn.fetch(
            """
            SELECT
                transfer_id,
                payment_id,
                amount,
                fee,
                tax,
                status,
                created_at
            FROM transfers
            WHERE transfer_id = ANY($1::text[])
            """,
            transfer_ids,
        )

        return [map_razorpay_transfer(row) for row in rows]


    async def _get_adjustments(
        self,
        conn: asyncpg.Connection,
        adjustment_ids: list[str],
    ):

        if not adjustment_ids:
            return []

        rows = await conn.fetch(
            """
            SELECT
                adjustment_id,
                settlement_id,
                amount,
                description,
                created_at
            FROM adjustments
            WHERE adjustment_id = ANY($1::text[])
            """,
            adjustment_ids,
        )

        return [map_razorpay_adjustment(row) for row in rows]

    
    async def _get_orders(
        self,
        conn: asyncpg.Connection,
        order_ids: list[str],
    ):
        if not order_ids:
            return []

        rows = await conn.fetch(
            """
            SELECT
                order_id,
                amount,
                currency,
                status,
                receipt,
                created_at
            FROM razorpay_orders
            WHERE order_id = ANY($1::text[])
            """,
            order_ids,
        )

        return [map_razorpay_order(row) for row in rows]


    async def _get_pos_transactions(
        self,
        conn: asyncpg.Connection,
        import_db_ids: list[int],
    ):
        # Scoped by the transaction's own import_pk (a real FK, populated
        # at ingestion time) rather than by joining on merchant_order_id
        # TEXT equality against merchant_orders -- that text value is not
        # globally unique (different settlements/imports can legitimately
        # both have an order named e.g. "MORD-01"), so a text join here
        # silently pulled in another settlement's POS rows whenever their
        # merchant_order_id happened to collide. import_pk is unambiguous.
        if not import_db_ids:
            return []

        rows = await conn.fetch(
            """
            SELECT
                pt.transaction_id,
                pt.merchant_order_id,
                pt.razorpay_order_id,
                pt.amount,
                pt.currency,
                pt.transaction_date,
                pt.status,
                pt.terminal_id
            FROM pos_transactions pt
            WHERE pt.import_pk = ANY($1::bigint[])
            """,
            import_db_ids,
        )

        return [
            map_pos_transaction(row)
            for row in rows
        ]


    async def _get_gateway_transactions(
        self,
        conn: asyncpg.Connection,
        import_db_ids: list[int],
    ):
        # See _get_pos_transactions -- same fix, same reason.
        if not import_db_ids:
            return []

        rows = await conn.fetch(
            """
            SELECT
                gt.transaction_id,
                gt.merchant_order_id,
                gt.gateway_order_id,
                gt.amount,
                gt.currency,
                gt.fee,
                gt.tax,
                gt.status,
                gt.created_at
            FROM gateway_transactions gt
            WHERE gt.import_pk = ANY($1::bigint[])
            """,
            import_db_ids,
        )

        return [
            map_gateway_transaction(row)
            for row in rows
        ]


    async def _get_import_metadata(
    self,
        conn: asyncpg.Connection,
        import_ids: list[str],
    ) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
        if not import_ids:
            return {}, {}

        rows = await conn.fetch(
            """
            SELECT id, import_id, object_key
            FROM merchant_imports
            WHERE import_id = ANY($1::text[])
            """,
            import_ids,
        )

        if len(rows) != len(set(import_ids)):
            raise ValueError("One or more import IDs were not found.")

        object_keys = {row["import_id"]: row["object_key"] for row in rows}
        db_id_to_import_id = {row["id"]: row["import_id"] for row in rows}
        import_db_ids = list(db_id_to_import_id)

        entity_imports: dict[tuple[str, str], str] = {}

        rows = await conn.fetch(
            """
            SELECT merchant_order_id, import_pk
            FROM merchant_orders
            WHERE import_pk = ANY($1::bigint[])
            """,
            import_db_ids,
        )

        entity_imports.update({
            ("merchant_order", row["merchant_order_id"]): db_id_to_import_id[row["import_pk"]]
            for row in rows
        })

        rows = await conn.fetch(
            """
            SELECT entry_id, import_pk
            FROM ledger_entries
            WHERE import_pk = ANY($1::bigint[])
            """,
            import_db_ids,
        )

        entity_imports.update({
            ("ledger_entry", row["entry_id"]): db_id_to_import_id[row["import_pk"]]
            for row in rows
        })

        rows = await conn.fetch(
            """
            SELECT transaction_id, import_pk
            FROM pos_transactions
            WHERE import_pk = ANY($1::bigint[])
            """,
            import_db_ids,
        )

        entity_imports.update({
            ("pos_transaction", row["transaction_id"]): db_id_to_import_id[row["import_pk"]]
            for row in rows
        })

        rows = await conn.fetch(
            """
            SELECT transaction_id, import_pk
            FROM gateway_transactions
            WHERE import_pk = ANY($1::bigint[])
            """,
            import_db_ids,
        )

        entity_imports.update({
            ("gateway_transaction", row["transaction_id"]): db_id_to_import_id[row["import_pk"]]
            for row in rows
        })

        return object_keys, entity_imports