# Razorpay Finance Reconciliation

A financial reconciliation system for Razorpay merchants. It ingests
merchant-side records (orders, ledger, POS, other-gateway, bank statement
CSVs), compares them against Razorpay's own records (orders, payments,
refunds, transfers, adjustments, settlements) and bank data, produces
deterministic findings when a settlement doesn't tie out, builds an entity
graph around the discrepancy, and hands that graph + findings to an
LLM-based investigator that proposes evidence-gated root-cause hypotheses.

**Project status: implementation frozen.** See
[`docs/FINAL_VERIFICATION_REPORT.md`](docs/FINAL_VERIFICATION_REPORT.md) for
the final verification pass, and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full factual
architecture writeup this README summarizes.

## Stack

- **Backend**: Python 3.14, FastAPI, PostgreSQL (asyncpg, raw SQL, no ORM),
  MinIO (raw uploaded file storage), managed with `uv`.
- **Frontend**: Next.js (`frontend/`), React, TypeScript, TanStack Query,
  Tailwind, shadcn/ui, React Flow.
- **External**: Razorpay API (live test-mode order/payment data),
  HuggingFace-hosted LLM (OpenAI-compatible client) for investigation.

## Architecture at a glance

```
merchant CSVs ──┐
                ├──▶ ingestion ──▶ deterministic reconciliation ──▶ findings
Razorpay API ───┘                                                     │
                                                                       ▼
                                                                   evidence
                                                                       │
                                                                       ▼
                                                          graph (exception only)
                                                                       │
                                                                       ▼
                                                              EvidenceBuilder
                                                                       │
                                                                       ▼
                                                              AI investigator
                                                                       │
                                                                       ▼
                                                            InvestigationPolicy
                                                              (citation/confidence
                                                                    gate)
                                                                       │
                                                             ┌─────────┴─────────┐
                                                             ▼                   ▼
                                                       grounded root        abstention
                                                       cause + evidence      + reason
```

Reconciliation is **always deterministic** — no LLM anywhere in
`ReconcileSettlementService`. The LLM only ever sees a settlement *after* the
deterministic engine has already decided it's an exception; it can propose a
root-cause hypothesis but can never override a finding or change the
authoritative status.

**Financial authority**: Razorpay settlement net vs. bank-observed amount is
authoritative for settlement correctness. Merchant order/ledger/POS/gateway
totals are contextual evidence only — never a gate on status.

Five presentation-ready diagrams (system architecture, three-world data
model, deterministic reconciliation flow, investigation/policy flow,
frontend→API→backend) are in
[`docs/ARCHITECTURE_DIAGRAM_GUIDE.md`](docs/ARCHITECTURE_DIAGRAM_GUIDE.md).

## Repository layout

```
src/recon/
  domain/            framework-free dataclasses, no I/O
  application/       one folder per bounded context: ingestion/ reconciliation/ investigation/ razorpay/
    <context>/dto/        request/response/internal shapes
    <context>/ports/      abstract interfaces (repository, gateway, storage, llm)
    <context>/services/   orchestration/pure logic
    <context>/use_cases/  one class per use case
  infrastructure/    concrete adapters (postgres, minio, razorpay, ai, investigation, csv)
api/
  app.py             FastAPI app + lifespan(): wires every port -> adapter -> use case
  routes/            one router per context: ingestion.py, reconciliation.py, investigation.py
frontend/            Next.js app (App Router catch-all + react-router-dom)
datasets/            frozen scenario fixtures + derived seeded CSVs (golden-16, rich-60)
scripts/             seeding/regression scripts against the real running system
migrations/          incremental schema history (schema.sql is the source of truth)
docs/                ARCHITECTURE.md, ARCHITECTURE_DIAGRAM_GUIDE.md, FINAL_VERIFICATION_REPORT.md
```

## Setup

Requires Docker, `uv`, and `pnpm`.

```bash
# 1. Backend deps
uv sync

# 2. Infra (Postgres :5432, MinIO :9000/9001)
docker compose up -d

# 3. .env — create with these required vars:
#    DATABASE_URL, MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY,
#    MINIO_BUCKET, MINIO_SECURE (optional), HF_TOKEN, HF_MODEL,
#    RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET

# 4. API
uv run uvicorn api.app:app --reload    # http://localhost:8000

# 5. Frontend
cd frontend
pnpm install
pnpm dev                               # http://localhost:3000
```

`docker-compose.yaml` mounts `src/recon/infrastructure/persistence/postgres/schema.sql`
as the Postgres init script, so a fresh container is schema-ready.
`migrations/*.sql` document the same DDL as incremental history but are not
auto-applied — edit `schema.sql` for the live schema and add a matching
migration file for the delta.

## Testing

```bash
# Backend — MUST scope to tests/, never run bare `uv run pytest`
# (a top-level module-name collision with scripts/test_razorpay.py aborts collection)
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest tests/

# Frontend
cd frontend
pnpm exec tsc --noEmit
pnpm build
```

`tests/` covers `src/recon/domain/*` and
`application/investigation/services/evidence_builder.py`; there is no
automated coverage for the rest of `application/` or any `infrastructure/`
adapter — that's verified via live runs against the real system
(`scripts/run_golden_scenarios.py`, `scripts/run_dataset_scenarios.py`,
manual `curl`/`psql`), documented in `docs/FINAL_VERIFICATION_REPORT.md`.

## Datasets

Three fixture sets, each with frozen source data plus a derived
`merchant_seeded/` directory (never edits the originals):

| Dataset | Scenarios | Purpose |
|---|---|---|
| `datasets/golden_scenarios` | G01–G16 | One canonical use case per scenario (clean, mismatch, duplicate, bank-short, pending, grounded/abstained investigation) |
| `/home/vivek/Downloads/reconciliation_dataset_ours` (external) | 01–23 | Original larger dataset, incl. intentional ingestion-boundary cases |
| `datasets/razorpay_recon_rich_dataset` | RICH-60 | 60-order dataset with 5 controlled faults and double-entry bookkeeping |

Seed with `scripts/seed_golden_scenarios.py` / `scripts/seed_dataset.py` /
`scripts/seed_rich_dataset.py` (all idempotent, real Razorpay orders — no
mocked order creation path exists). Run with `scripts/run_golden_scenarios.py`
/ `scripts/run_dataset_scenarios.py` against a running API server.

## Known limitations

Tracked in full in `docs/FINAL_VERIFICATION_REPORT.md` §5 — summary:

- G01–G03 / old-20 21–23: merchant ledgers book gross-of-fee amounts, so the
  3-way RECONCILED check can't currently agree even though the authoritative
  Razorpay-vs-bank check already does. Needs a product decision, not a fix.
- G07: a ledger row citing a nonexistent merchant order is silently dropped
  at ingestion, blocking `DUPLICATE_PAYMENT` detection for that shape of
  fault.
- HuggingFace investigation calls are frequently blocked by account quota
  exhaustion (external, not a code defect).
