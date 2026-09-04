-- ============================================================
-- ADD IMPORT OWNERSHIP
-- ============================================================

ALTER TABLE ledger_entries
ADD COLUMN import_pk BIGINT NOT NULL
REFERENCES merchant_imports(id);

ALTER TABLE bank_transactions
ADD COLUMN import_pk BIGINT NOT NULL
REFERENCES merchant_imports(id);

ALTER TABLE pos_transactions
ADD COLUMN import_pk BIGINT NOT NULL
REFERENCES merchant_imports(id);

ALTER TABLE gateway_transactions
ADD COLUMN import_pk BIGINT NOT NULL
REFERENCES merchant_imports(id);


-- ============================================================
-- IMPORT-SCOPED UNIQUENESS
-- ============================================================

ALTER TABLE ledger_entries
DROP CONSTRAINT uq_ledger_entry_source;

ALTER TABLE ledger_entries
ADD CONSTRAINT uq_ledger_entry_import
UNIQUE (import_pk, entry_id);

ALTER TABLE bank_transactions
DROP CONSTRAINT uq_bank_transaction_source;

ALTER TABLE bank_transactions
ADD CONSTRAINT uq_bank_transaction_import
UNIQUE (import_pk, transaction_id);

ALTER TABLE pos_transactions
DROP CONSTRAINT uq_pos_transaction_source;

ALTER TABLE pos_transactions
ADD CONSTRAINT uq_pos_transaction_import
UNIQUE (import_pk, transaction_id);

ALTER TABLE gateway_transactions
DROP CONSTRAINT uq_gateway_transaction_source;

ALTER TABLE gateway_transactions
ADD CONSTRAINT uq_gateway_transaction_import
UNIQUE (import_pk, transaction_id);


-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_ledger_entries_import
    ON ledger_entries(import_pk);

CREATE INDEX idx_bank_transactions_import
    ON bank_transactions(import_pk);

CREATE INDEX idx_pos_transactions_import
    ON pos_transactions(import_pk);

CREATE INDEX idx_gateway_transactions_import
    ON gateway_transactions(import_pk);