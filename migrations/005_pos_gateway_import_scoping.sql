-- pos_transactions/gateway_transactions had no import_pk column, so
-- reconciliation's lookup for "this settlement's POS/gateway rows" could
-- only join on merchant_order_id TEXT equality against merchant_orders.
-- merchant_order_id is only unique per import (see uq_merchant_order_source
-- / uq_merchant_order_import), not globally -- two different settlements
-- that both happen to name an order e.g. "MORD-01" would silently leak
-- each other's POS/gateway rows into one another's reconciliation runs.
-- ledger_entries never had this problem: it already carries a real
-- merchant_order_pk FK. This gives pos_transactions/gateway_transactions
-- the same kind of unambiguous scoping, via their own import_pk instead
-- (they are ingested one full file per import, so import_pk alone is
-- sufficient -- no merchant_order_pk needed).
--
-- NOTE: this column, and the corresponding uq_*_import constraints
-- (replacing the previous uq_*_source constraints), were already applied
-- directly to the running database before this migration file was written
-- (see ReconcileSettlementPostgresRepository / schema.sql for the current,
-- now-matching state). This file documents that delta for a fresh
-- container; it is idempotent so it is safe to also run once against an
-- already-patched database.

ALTER TABLE pos_transactions
    ADD COLUMN IF NOT EXISTS import_pk BIGINT REFERENCES merchant_imports(id);

ALTER TABLE gateway_transactions
    ADD COLUMN IF NOT EXISTS import_pk BIGINT REFERENCES merchant_imports(id);

ALTER TABLE pos_transactions
    DROP CONSTRAINT IF EXISTS uq_pos_transaction_source;

ALTER TABLE gateway_transactions
    DROP CONSTRAINT IF EXISTS uq_gateway_transaction_source;

ALTER TABLE pos_transactions
    ADD CONSTRAINT uq_pos_transaction_import UNIQUE (import_pk, transaction_id);

ALTER TABLE gateway_transactions
    ADD CONSTRAINT uq_gateway_transaction_import UNIQUE (import_pk, transaction_id);

CREATE INDEX IF NOT EXISTS idx_pos_transactions_import ON pos_transactions(import_pk);
CREATE INDEX IF NOT EXISTS idx_gateway_transactions_import ON gateway_transactions(import_pk);
