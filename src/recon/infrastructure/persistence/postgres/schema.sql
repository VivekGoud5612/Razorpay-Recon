-- ============================================================
-- RAZORPAY WORLD
-- ============================================================

CREATE TABLE razorpay_orders (
    id              BIGSERIAL PRIMARY KEY,
    order_id        TEXT NOT NULL UNIQUE,
    amount          NUMERIC(14, 2) NOT NULL,
    currency        TEXT NOT NULL,
    status          TEXT NOT NULL,
    receipt         TEXT,
    created_at      TIMESTAMPTZ NOT NULL
);

CREATE TABLE payments (
    id              BIGSERIAL PRIMARY KEY,
    payment_id      TEXT NOT NULL UNIQUE,
    order_id        TEXT NOT NULL REFERENCES razorpay_orders(order_id),
    amount          NUMERIC(14, 2) NOT NULL,
    currency        TEXT NOT NULL,
    status          TEXT NOT NULL,
    method          TEXT,
    fee             NUMERIC(14, 2) NOT NULL DEFAULT 0,
    tax             NUMERIC(14, 2) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL,
    captured_at     TIMESTAMPTZ
);

CREATE INDEX idx_payments_order_id
    ON payments(order_id);

CREATE TABLE refunds (
    id              BIGSERIAL PRIMARY KEY,
    refund_id       TEXT NOT NULL UNIQUE,
    payment_id      TEXT NOT NULL REFERENCES payments(payment_id),
    amount          NUMERIC(14, 2) NOT NULL,
    currency        TEXT NOT NULL,
    status          TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    processed_at    TIMESTAMPTZ
);

CREATE INDEX idx_refunds_payment_id
    ON refunds(payment_id);

CREATE TABLE settlements (
    id              BIGSERIAL PRIMARY KEY,
    settlement_id   TEXT NOT NULL UNIQUE,
    amount          NUMERIC(14, 2) NOT NULL,
    fees            NUMERIC(14, 2) NOT NULL DEFAULT 0,
    tax             NUMERIC(14, 2) NOT NULL DEFAULT 0,
    utr             TEXT,
    status          TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    processed_at    TIMESTAMPTZ
);

CREATE INDEX idx_settlements_utr
    ON settlements(utr);

CREATE TABLE settlement_entries (
    id                  BIGSERIAL PRIMARY KEY,
    entry_id            TEXT NOT NULL UNIQUE,
    settlement_id       TEXT NOT NULL REFERENCES settlements(settlement_id),
    entry_type          TEXT NOT NULL,

    amount              NUMERIC(14, 2) NOT NULL,
    debit               NUMERIC(14, 2) NOT NULL DEFAULT 0,
    credit              NUMERIC(14, 2) NOT NULL DEFAULT 0,
    fee                 NUMERIC(14, 2) NOT NULL DEFAULT 0,
    tax                 NUMERIC(14, 2) NOT NULL DEFAULT 0,

    payment_id          TEXT REFERENCES payments(payment_id),
    refund_id           TEXT REFERENCES refunds(refund_id),

    -- V1: optional references; dedicated tables follow.
    transfer_id         TEXT,
    adjustment_id       TEXT,

    order_id            TEXT REFERENCES razorpay_orders(order_id),
    settlement_utr      TEXT,

    description         TEXT,
    created_at          TIMESTAMPTZ NOT NULL,
    settled_at          TIMESTAMPTZ
);

CREATE INDEX idx_settlement_entries_settlement_id
    ON settlement_entries(settlement_id);

CREATE INDEX idx_settlement_entries_payment_id
    ON settlement_entries(payment_id);

CREATE TABLE transfers (
    id              BIGSERIAL PRIMARY KEY,
    transfer_id     TEXT NOT NULL UNIQUE,
    payment_id      TEXT NOT NULL REFERENCES payments(payment_id),
    amount          NUMERIC(14, 2) NOT NULL,
    fee             NUMERIC(14, 2) NOT NULL DEFAULT 0,
    tax             NUMERIC(14, 2) NOT NULL DEFAULT 0,
    status          TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_transfers_payment_id
    ON transfers(payment_id);

CREATE TABLE adjustments (
    id              BIGSERIAL PRIMARY KEY,
    adjustment_id   TEXT NOT NULL UNIQUE,
    settlement_id   TEXT NOT NULL REFERENCES settlements(settlement_id),
    amount          NUMERIC(14, 2) NOT NULL,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_adjustments_settlement_id
    ON adjustments(settlement_id);


-- ============================================================
-- MERCHANT WORLD
-- ============================================================
-- ============================================================
-- CREATING NEW SOURCES AND ALTER ORDERS TO REFER THIS
-- ============================================================

CREATE TABLE sources (
    id              BIGSERIAL PRIMARY KEY,
    source_id       TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    provider        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================
-- MERCHANT IMPORTS
-- One immutable ingestion/import attempt for a source.
-- ============================================================

CREATE TABLE merchant_imports (
    id                  BIGSERIAL PRIMARY KEY,

    source_id           BIGINT NOT NULL REFERENCES sources(id),

    import_id           TEXT NOT NULL UNIQUE,

    object_key          TEXT NOT NULL,
    filename            TEXT NOT NULL,
    content_type        TEXT NOT NULL,

    status              TEXT NOT NULL,
    records_ingested    INTEGER NOT NULL DEFAULT 0,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ

);

CREATE INDEX idx_merchant_imports_source
    ON merchant_imports(source_id);


CREATE TABLE merchant_orders (
    id                  BIGSERIAL PRIMARY KEY,
    source_id           BIGINT NOT NULL REFERENCES sources(id),
    import_pk           BIGINT NOT NULL REFERENCES merchant_imports(id),

    merchant_order_id   TEXT NOT NULL,
    -- No FK to razorpay_orders(order_id): a merchant-submitted order can
    -- legitimately reference a Razorpay order that doesn't exist (that's
    -- exactly what RAZORPAY_ORDER_NOT_FOUND in ReconcileSettlementService
    -- detects). The ingestion boundary must accept merchant data as-is;
    -- resolving/validating references against Razorpay is reconciliation's
    -- job, not a storage constraint. See migrations/004.
    razorpay_order_id   TEXT NOT NULL,

    amount              NUMERIC(14, 2) NOT NULL,
    currency            TEXT NOT NULL,
    customer_ref        TEXT,
    invoice_id          TEXT,
    status              TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL,

    CONSTRAINT uq_merchant_order_source
        UNIQUE (import_pk, merchant_order_id)
);

CREATE INDEX idx_merchant_orders_razorpay_order
    ON merchant_orders(razorpay_order_id);

CREATE INDEX idx_merchant_orders_source
    ON merchant_orders(source_id);

CREATE INDEX idx_merchant_orders_import
    ON merchant_orders(import_pk);


CREATE TABLE invoices (
    id                  BIGSERIAL PRIMARY KEY,

    source_id           BIGINT NOT NULL REFERENCES sources(id),

    invoice_id          TEXT NOT NULL,
    merchant_order_pk   BIGINT NOT NULL REFERENCES merchant_orders(id),

    amount              NUMERIC(14, 2) NOT NULL,
    currency            TEXT NOT NULL,
    status              TEXT NOT NULL,

    issued_at           TIMESTAMPTZ NOT NULL,
    due_at              TIMESTAMPTZ,

    CONSTRAINT uq_invoice_source
        UNIQUE (source_id, invoice_id)
);

CREATE INDEX idx_invoices_merchant_order
    ON invoices(merchant_order_pk);

CREATE INDEX idx_invoices_source
    ON invoices(source_id);


CREATE TABLE ledger_entries (
    id                  BIGSERIAL PRIMARY KEY,

    source_id           BIGINT NOT NULL REFERENCES sources(id),

    entry_id            TEXT NOT NULL,
    merchant_order_pk   BIGINT REFERENCES merchant_orders(id),

    account_code        TEXT NOT NULL,
    entry_type          TEXT NOT NULL,

    debit               NUMERIC(14, 2) NOT NULL DEFAULT 0,
    credit              NUMERIC(14, 2) NOT NULL DEFAULT 0,

    currency            TEXT NOT NULL,
    posted_at           TIMESTAMPTZ NOT NULL,
    reference           TEXT,
    description         TEXT,

    CONSTRAINT uq_ledger_entry_source
        UNIQUE (source_id, entry_id)
);

CREATE INDEX idx_ledger_entries_order
    ON ledger_entries(merchant_order_pk);

CREATE INDEX idx_ledger_entries_source
    ON ledger_entries(source_id);


-- ============================================================
-- BANK WORLD
-- ============================================================

CREATE TABLE bank_transactions (
    id                  BIGSERIAL PRIMARY KEY,

    source_id           BIGINT NOT NULL REFERENCES sources(id),

    transaction_id      TEXT NOT NULL,

    utr                 TEXT,
    transaction_date    DATE NOT NULL,
    value_date          DATE,

    description         TEXT NOT NULL,

    debit               NUMERIC(14, 2) NOT NULL DEFAULT 0,
    credit              NUMERIC(14, 2) NOT NULL DEFAULT 0,
    balance             NUMERIC(14, 2),

    reference            TEXT,

    CONSTRAINT uq_bank_transaction_source
        UNIQUE (source_id, transaction_id)
);

CREATE INDEX idx_bank_transactions_utr
    ON bank_transactions(utr);

CREATE INDEX idx_bank_transactions_source
    ON bank_transactions(source_id);


-- ============================================================
-- GRAPH / RELATIONSHIP MODEL
-- ============================================================

CREATE TABLE graph_nodes (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_graph_node
        UNIQUE (source, entity_type, entity_id)
);

CREATE TABLE graph_edges (
    id                  BIGSERIAL PRIMARY KEY,
    source_node_id      BIGINT NOT NULL REFERENCES graph_nodes(id),
    target_node_id      BIGINT NOT NULL REFERENCES graph_nodes(id),
    edge_type           TEXT NOT NULL,

    evidence_type       TEXT NOT NULL DEFAULT 'explicit_reference',
    confidence          NUMERIC(4, 3) NOT NULL DEFAULT 1.000,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_graph_edge
        UNIQUE (source_node_id, target_node_id, edge_type)
);

CREATE INDEX idx_graph_edges_source
    ON graph_edges(source_node_id);

CREATE INDEX idx_graph_edges_target
    ON graph_edges(target_node_id);



-- ============================================================
-- POS
-- ============================================================

CREATE TABLE pos_transactions (
    id                  BIGSERIAL PRIMARY KEY,

    source_id           BIGINT NOT NULL REFERENCES sources(id),
    import_pk           BIGINT NOT NULL REFERENCES merchant_imports(id),

    transaction_id      TEXT NOT NULL,
    merchant_order_id   TEXT NOT NULL,
    razorpay_order_id   TEXT,

    amount              NUMERIC(14, 2) NOT NULL,
    currency            TEXT NOT NULL,

    transaction_date    DATE NOT NULL,
    status              TEXT NOT NULL,
    terminal_id         TEXT NOT NULL,

    CONSTRAINT uq_pos_transaction_import
        UNIQUE (import_pk, transaction_id)
);

CREATE INDEX idx_pos_transactions_source
    ON pos_transactions(source_id);

CREATE INDEX idx_pos_transactions_import
    ON pos_transactions(import_pk);

CREATE INDEX idx_pos_transactions_merchant_order
    ON pos_transactions(merchant_order_id);


-- ============================================================
-- OTHER PAYMENT GATEWAY
-- ============================================================

CREATE TABLE gateway_transactions (
    id                      BIGSERIAL PRIMARY KEY,

    source_id               BIGINT NOT NULL REFERENCES sources(id),
    import_pk               BIGINT NOT NULL REFERENCES merchant_imports(id),

    transaction_id          TEXT NOT NULL,
    merchant_order_id       TEXT NOT NULL,
    gateway_order_id        TEXT NOT NULL,

    amount                  NUMERIC(14, 2) NOT NULL,
    currency                TEXT NOT NULL,

    fee                     NUMERIC(14, 2) NOT NULL DEFAULT 0,
    tax                     NUMERIC(14, 2) NOT NULL DEFAULT 0,

    status                  TEXT NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL,

    CONSTRAINT uq_gateway_transaction_import
        UNIQUE (import_pk, transaction_id)
);

CREATE INDEX idx_gateway_transactions_source
    ON gateway_transactions(source_id);

CREATE INDEX idx_gateway_transactions_import
    ON gateway_transactions(import_pk);

CREATE INDEX idx_gateway_transactions_merchant_order
    ON gateway_transactions(merchant_order_id);

CREATE INDEX idx_gateway_transactions_gateway_order
    ON gateway_transactions(gateway_order_id);


ALTER TABLE graph_nodes
ADD COLUMN settlement_id TEXT NOT NULL
REFERENCES settlements(settlement_id);

ALTER TABLE graph_edges
ADD COLUMN settlement_id TEXT NOT NULL
REFERENCES settlements(settlement_id);

ALTER TABLE graph_nodes
DROP CONSTRAINT uq_graph_node;

ALTER TABLE graph_nodes
ADD CONSTRAINT uq_graph_node
UNIQUE (settlement_id, source, entity_type, entity_id);

ALTER TABLE graph_edges
DROP CONSTRAINT uq_graph_edge;

ALTER TABLE graph_edges
ADD CONSTRAINT uq_graph_edge
UNIQUE (
    settlement_id,
    source_node_id,
    target_node_id,
    edge_type
);

CREATE INDEX idx_graph_nodes_settlement
    ON graph_nodes(settlement_id);

CREATE INDEX idx_graph_edges_settlement
    ON graph_edges(settlement_id);



CREATE TABLE reconciliation_findings (
    id BIGSERIAL PRIMARY KEY,
    settlement_id TEXT NOT NULL REFERENCES settlements(settlement_id),
    finding_id TEXT NOT NULL,
    code TEXT NOT NULL,
    severity TEXT NOT NULL,
    source TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_reconciliation_finding
        UNIQUE (settlement_id, finding_id)
);

CREATE INDEX idx_reconciliation_findings_settlement
    ON reconciliation_findings(settlement_id);

CREATE TABLE reconciliation_evidence (
    id BIGSERIAL PRIMARY KEY,
    settlement_id TEXT NOT NULL REFERENCES settlements(settlement_id),
    evidence_id TEXT NOT NULL,
    source TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    object_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_reconciliation_evidence
        UNIQUE (settlement_id, evidence_id)
);

CREATE INDEX idx_reconciliation_evidence_settlement
    ON reconciliation_evidence(settlement_id);

CREATE INDEX idx_reconciliation_evidence_entity
    ON reconciliation_evidence(source, entity_type, entity_id);


CREATE TABLE reconciliation_finding_evidence (
    settlement_id TEXT NOT NULL,
    finding_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,

    PRIMARY KEY (settlement_id, finding_id, evidence_id),

    FOREIGN KEY (settlement_id, finding_id)
        REFERENCES reconciliation_findings(settlement_id, finding_id),

    FOREIGN KEY (settlement_id, evidence_id)
        REFERENCES reconciliation_evidence(settlement_id, evidence_id)
);

CREATE INDEX idx_finding_evidence_finding
    ON reconciliation_finding_evidence(settlement_id, finding_id);


INSERT INTO sources (source_id, name, source_type, provider)
VALUES
    ('merchant_orders', 'Merchant Orders', 'merchant_order', 'merchant'),
    ('merchant_ledger', 'Merchant Ledger', 'ledger_entry', 'merchant'),
    ('merchant_invoices', 'Merchant Invoices', 'invoice', 'merchant'),
    ('merchant_pos', 'Merchant POS', 'pos_transaction', 'merchant'),
    ('merchant_gateway', 'Merchant Gateway', 'gateway_transaction', 'merchant'),
    ('merchant_bank', 'Merchant Bank', 'bank_transaction', 'merchant')
ON CONFLICT (source_id) DO NOTHING;


-- ============================================================
-- RECONCILIATION RUNS
-- Latest computed summary per settlement, so the frontend can
-- re-fetch a reconciliation's status/KPIs without re-running it.
-- ============================================================

CREATE TABLE reconciliation_runs (
    id                              BIGSERIAL PRIMARY KEY,
    settlement_id                   TEXT NOT NULL REFERENCES settlements(settlement_id),

    status                          TEXT NOT NULL,
    reason_code                     TEXT NOT NULL,

    merchant_expected               NUMERIC(14, 2) NOT NULL,
    razorpay_net                    NUMERIC(14, 2) NOT NULL,
    bank_observed                   NUMERIC(14, 2) NOT NULL,
    merchant_vs_razorpay_difference NUMERIC(14, 2) NOT NULL,
    razorpay_vs_bank_difference     NUMERIC(14, 2) NOT NULL,

    import_ids                      TEXT[] NOT NULL DEFAULT '{}',

    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_reconciliation_run_settlement UNIQUE (settlement_id)
);

CREATE INDEX idx_reconciliation_runs_updated_at
    ON reconciliation_runs(updated_at DESC);


-- ============================================================
-- INVESTIGATIONS
-- Persisted AI investigation results, addressable by ID so the
-- frontend can navigate to /investigations/:id and re-fetch them.
-- ============================================================

CREATE TABLE investigations (
    id                  BIGSERIAL PRIMARY KEY,
    investigation_id    TEXT NOT NULL UNIQUE,
    settlement_id       TEXT NOT NULL REFERENCES settlements(settlement_id),
    finding_ids         TEXT[] NOT NULL,

    status              TEXT NOT NULL,
    response            JSONB NOT NULL,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_investigations_settlement
    ON investigations(settlement_id);