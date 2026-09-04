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
