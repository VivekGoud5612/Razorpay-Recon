-- ============================================================
-- GRAPH → SETTLEMENT
-- ============================================================

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


-- ============================================================
-- RECONCILIATION FINDINGS
-- ============================================================

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


-- ============================================================
-- RECONCILIATION EVIDENCE
-- ============================================================

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


-- ============================================================
-- FINDING ↔ EVIDENCE
-- ============================================================

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


-- ============================================================
-- MERCHANT SOURCES
-- ============================================================

INSERT INTO sources (source_id, name, source_type, provider)
VALUES
    ('merchant_orders', 'Merchant Orders', 'merchant_order', 'merchant'),
    ('merchant_ledger', 'Merchant Ledger', 'ledger_entry', 'merchant'),
    ('merchant_invoices', 'Merchant Invoices', 'invoice', 'merchant'),
    ('merchant_pos', 'Merchant POS', 'pos_transaction', 'merchant'),
    ('merchant_gateway', 'Merchant Gateway', 'gateway_transaction', 'merchant'),
    ('merchant_bank', 'Merchant Bank', 'bank_transaction', 'merchant')
ON CONFLICT (source_id) DO NOTHING;

