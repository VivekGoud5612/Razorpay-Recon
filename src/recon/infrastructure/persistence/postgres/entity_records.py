from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import asyncpg

# entity_type -> (table, id_column, needs_latest_tiebreak)
#
# Mirrors ReconciliationGraphBuilder._ENTITY_SPECS (same entity_type
# vocabulary, same tables) so evidence/investigation record lookups stay
# consistent with what the graph already considers "the" entity for a given
# (entity_type, entity_id). Merchant-world tables are only unique per
# import/source (see uq_merchant_order_source etc.), not globally, so a
# stale/repeated re-ingestion can leave more than one row behind for the same
# business id -- `needs_latest_tiebreak` picks the most recently written row
# in that case, the same convention already used for
# `_persist_ledger_entries` (ORDER BY id DESC LIMIT 1). Razorpay-world tables
# have a genuine DB-level UNIQUE constraint on their business key, so no
# tiebreak is possible or needed there.
_ENTITY_TABLES: dict[str, tuple[str, str, bool]] = {
    "merchant_order": ("merchant_orders", "merchant_order_id", True),
    "ledger_entry": ("ledger_entries", "entry_id", True),
    "pos_transaction": ("pos_transactions", "transaction_id", True),
    "gateway_transaction": ("gateway_transactions", "transaction_id", True),
    "bank_transaction": ("bank_transactions", "transaction_id", True),
    "razorpay_order": ("razorpay_orders", "order_id", False),
    "payment": ("payments", "payment_id", False),
    "refund": ("refunds", "refund_id", False),
    "transfer": ("transfers", "transfer_id", False),
    "adjustment": ("adjustments", "adjustment_id", False),
    "settlement": ("settlements", "settlement_id", False),
    "settlement_entry": ("settlement_entries", "entry_id", False),
}

# Internal surrogate/foreign keys -- not meaningful source-record content for
# an investigator or a human reading the Evidence Explorer.
_INTERNAL_COLUMNS = {"id", "source_id", "import_pk", "merchant_order_pk"}


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


async def resolve_import_pks(
    conn: asyncpg.Connection,
    settlement_id: str,
) -> list[int]:
    """The merchant_imports rows that fed a settlement's most recent
    reconciliation run (reconciliation_runs.import_ids, resolved to
    merchant_imports.id). Used to scope merchant-world entity lookups to
    this settlement -- see `fetch_entity_record`'s `import_pks` param.
    """
    rows = await conn.fetch(
        """
        SELECT mi.id
        FROM merchant_imports mi
        JOIN reconciliation_runs rr
            ON mi.import_id = ANY(rr.import_ids)
        WHERE rr.settlement_id = $1
        """,
        settlement_id,
    )
    return [row["id"] for row in rows]


async def fetch_entity_record(
    conn: asyncpg.Connection,
    entity_type: str,
    entity_id: str,
    import_pks: list[int] | None = None,
) -> dict[str, Any] | None:
    """Deterministic, exact-key lookup of the persisted record backing one
    evidence/graph entity. No fuzzy matching, no row scanning: entity_type
    selects exactly one table via `_ENTITY_TABLES`, entity_id is matched
    against that table's own unique business-key column.

    Merchant-world business ids (e.g. "MORD-01") are not globally unique --
    several unrelated scenarios/settlements can share the same friendly id
    across their own separate imports. For `needs_latest_tiebreak` entity
    types, `import_pks` (this settlement's own merchant_imports, from
    `resolve_import_pks`) restricts the match to rows that actually belong
    to the settlement being investigated, so a bare "most recently
    inserted" tiebreak can never resolve to a different settlement's row.
    When `import_pks` is omitted the lookup is unscoped (old behavior) --
    every current call site now supplies it.
    """
    spec = _ENTITY_TABLES.get(entity_type)

    if spec is None:
        return None

    table, id_column, needs_tiebreak = spec

    if needs_tiebreak and import_pks is not None:
        row = await conn.fetchrow(
            f"SELECT * FROM {table} WHERE {id_column} = $1 AND import_pk = ANY($2::bigint[]) ORDER BY id DESC LIMIT 1",  # noqa: S608
            entity_id,
            import_pks,
        )
    else:
        order_clause = "ORDER BY id DESC" if needs_tiebreak else ""
        row = await conn.fetchrow(
            f"SELECT * FROM {table} WHERE {id_column} = $1 {order_clause} LIMIT 1",  # noqa: S608
            entity_id,
        )

    if row is None:
        return None

    return {
        key: _jsonable(value)
        for key, value in dict(row).items()
        if key not in _INTERNAL_COLUMNS
    }
