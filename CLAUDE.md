# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A financial reconciliation system for Razorpay merchants. It ingests merchant-side records (orders, ledger, POS, other-gateway, bank statement CSVs), compares them against Razorpay's own records (orders, payments, refunds, transfers, adjustments, settlements) and bank data, produces deterministic reconciliation findings when a settlement doesn't tie out, builds an entity graph around the discrepancy, and hands that graph + findings to an LLM-based investigator that proposes (evidence-gated) root-cause hypotheses.

Python 3.14, FastAPI, Postgres (asyncpg, raw SQL), MinIO (object storage for raw uploaded source files), managed with `uv`.

## Commands

```bash
# Install deps
uv sync

# Run the API (needs postgres + minio running, and a .env file)
docker compose up -d          # starts postgres:5432 and minio:9000/9001
uv run uvicorn api.app:app --reload

# Run tests — MUST scope to tests/, see "Test gotchas" below
uv run pytest tests/
uv run pytest tests/recon/domain/test_reconciliation.py::test_reconciliation_result  # single test
```

### Test gotchas (this machine)

- **Never run bare `uv run pytest`** (no path). It collects `scripts/test_razorpay.py` and `tests/recon/domain/test_razorpay.py` together; both are importable as the top-level module `test_razorpay` (no `__init__.py`/package structure), so pytest aborts with `import file mismatch`. Always pass `tests/` (or a more specific path) explicitly.
- This machine has a global ROS 2 Python install (`/opt/ros/...`) that registers a broken `pytest11` entry point (`launch_testing`, missing `osrf_pycommon`). If pytest fails immediately during plugin loading with `ModuleNotFoundError: No module named 'osrf_pycommon'`, prefix the command with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.
- No lint/format/type-check tooling is configured in `pyproject.toml` — don't invent `ruff`/`mypy`/`black` invocations.
- `tests/` currently only covers `src/recon/domain/*` (pure dataclasses/value objects, no I/O). There is no test coverage for `application/` or `infrastructure/` layers. A few domain tests are presently failing (e.g. `EvidenceRef` no longer accepts a `role` kwarg) — this is pre-existing drift between the domain model and the tests, not something you introduced; check `git blame`/diff before assuming a change of yours caused it.
- `scripts/smoke_*.py` are manual smoke-test scripts that hit a real Postgres/MinIO/Razorpay/HF — they are not run by pytest and some have stale imports (e.g. `smoke_recon.py` imports a module path that no longer exists). Don't trust them as living documentation without checking they still import cleanly.

### Environment

Config is loaded via `.env` (see `api/app.py`'s `lifespan`, `load_dotenv()`). Required vars: `DATABASE_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `MINIO_SECURE` (optional), `HF_TOKEN`, `HF_MODEL`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`. `docker-compose.yaml` only provisions postgres + minio (dev creds hardcoded there); it also mounts `src/recon/infrastructure/persistence/postgres/schema.sql` as the Postgres init script, so a fresh container is schema-ready — the `migrations/*.sql` files describe the same DDL as incremental history but are not auto-applied by anything.

## Architecture

Hexagonal/clean architecture, one bounded context per subfolder under `src/recon/`:

```
src/recon/
  domain/            # framework-free entities & value objects (dataclasses), no I/O
  application/        # use cases, ports (interfaces), and domain services, per bounded context
    ingestion/
    reconciliation/
    investigation/
    razorpay/
  infrastructure/      # concrete adapters implementing application ports
    persistence/postgres/
    storage/minio/
    ai/                # HuggingFace (OpenAI-compatible) LLM client
    investigation/      # LLMInvestigator + MCP-style document tools
    razorpay/            # Razorpay SDK/HTTP gateway
    ingestion/csv/        # CSV source adapter
api/
  app.py              # FastAPI app + lifespan: wires all ports -> adapters -> use cases into app.state
  dependencies.py     # FastAPI Depends() that pull use cases off app.state
  routes/             # one router per bounded context, calls a single use case
```

Within each `application/<context>/` package: `dto/` (request/response/internal data shapes), `ports/` (abstract interfaces the use case depends on — repository, gateway, object storage, LLM client), `services/` (pure/orchestration logic, no I/O of their own), `use_cases/` (one class per use case, `execute()` entrypoint, composed entirely of injected ports/services). There is no DI framework — everything is constructed by hand in `api/app.py`'s `lifespan()` and stashed on `app.state`; routes pull the use case via `Depends(get_*_use_case)` in `api/dependencies.py`.

### The three flows

1. **Ingestion** (`application/ingestion`): `POST /ingestion/merchant` (or `/merchant/batch`, which dispatches by a fixed `SOURCE_BY_FILENAME` map in `api/routes/ingestion.py`) uploads a merchant CSV. `IngestMerchantSourceUseCase` creates a `MerchantImport` record, stores the raw file in MinIO under `imports/{source_id}/{import_id}/{filename}`, picks a `MerchantSourceAdapter` (currently only `MerchantCsvAdapter`) via `MerchantSourceAdapterRegistry`, normalizes + validates the parsed rows, converts them to domain records (`MerchantDomainConstructor`), and persists them scoped to that import (`import_pk`). On any failure the import row is marked failed and the exception re-raised — nothing is left half-committed as "processing" silently.
2. **Reconciliation** (`application/reconciliation`): `POST /reconciliation/settlements` loads all relevant records for a settlement (`SettlementReconciliationData`), and `ReconcileSettlementService.reconcile()` runs a fixed pipeline of deterministic checks (`_validate_razorpay_state`, `_validate_orders`, `_validate_payments`, `_validate_merchant_sources`, `_validate_temporal`, `_validate_completeness`, `_validate_settlement`), each emitting `ReconciliationFinding`s with attached `EvidenceRef`s. It also cross-checks three independently-computed totals (merchant ledger net, Razorpay settlement-entry net, bank statement net) — a status of `"exception"` results either from a rule violation or from these totals disagreeing (`reason_code="FINANCIAL_DIFFERENCE"`); `"reconciled"` requires zero findings *and* all three totals to agree; `"pending"` is returned early if the settlement itself isn't `"processed"` yet. Only on `"exception"` does the use case build a `ReconciliationGraph` (`ReconciliationGraphBuilder`, driven by the declarative `RELATION_RULES` table in `application/reconciliation/graph/relation_rules.py`) and persist it + the findings/evidence — a reconciled settlement produces no graph.
3. **Investigation** (`application/investigation`): `POST /investigation/exceptions` takes a settlement + a set of finding IDs, loads the previously-persisted graph and findings, expands an `EvidencePackage` around the selected findings via `EvidenceBuilder` (graph traversal to a fixed depth of 2), and passes that package to `InvestigationService` → `LLMInvestigator`, which calls a HuggingFace-hosted model (OpenAI-compatible `responses`/`chat.completions` API, see `infrastructure/ai/huggingface_client.py`) with a strict JSON schema (`infrastructure/ai/schemas.py`) and a system prompt whose entire point is evidence discipline — the model must cite only supplied `evidence_id`s and is instructed to abstain rather than guess at fault. `InvestigationPolicy.validate()` (called from `InvestigationService`, not the use case) is a second, code-level enforcement layer: it strips/abstains the response if the model cited unknown evidence IDs, produced no hypothesis, all hypotheses are below `MIN_CONFIDENCE = 0.60`, or a root cause fails any of several integrity checks (unknown hypothesis id, low confidence, no supporting evidence, unresolved missing evidence). Document-level tool calling (`DocumentTools.get_document`/`search_document` against MinIO) is currently wired up but disabled in `LLMInvestigator.investigate()` (`tools=None` — see the commented-out lines).

### Data model (`src/recon/infrastructure/persistence/postgres/schema.sql`)

Three "worlds" of raw source data, all scoped by a `sources` row (`source_id`) and, for merchant data, an owning `merchant_imports` row (`import_pk`) so re-ingesting a source never collides with a previous import:
- **Razorpay world**: `razorpay_orders`, `payments`, `refunds`, `settlements`, `settlement_entries`, `transfers`, `adjustments` — Razorpay's own ledger, either synced via `application/razorpay/use_cases/sync_settlements.py` or seeded (see `scripts/seed*.py`).
- **Merchant world**: `merchant_orders`, `invoices`, `ledger_entries`, plus `bank_transactions`, `pos_transactions`, `gateway_transactions` — all uploaded by the merchant and ingested per-import.
- **Graph + results**: `graph_nodes`/`graph_edges` (both keyed per-`settlement_id`, not global — the same entity can appear in multiple settlements' graphs as distinct rows) and `reconciliation_findings`/`reconciliation_evidence`/`reconciliation_finding_evidence` (join table), all written only when a settlement reconciles to `"exception"`.

`migrations/*.sql` mirror history that has already been folded into `schema.sql` — when changing the schema, edit `schema.sql` (what `docker-compose.yaml` actually applies to a fresh container) and add a new numbered migration file describing the delta; don't assume the migrations directory is auto-run anywhere.

### Conventions to follow when extending this code

- Domain objects are `@dataclass(slots=True)` (frozen where the object is a pure value type like `Money`, `EntityReference`, `EvidenceRef`); they hold no behavior beyond simple invariants (e.g. `Money.add`/`subtract` reject mismatched currencies).
- Money fields are `Decimal`, never `float`.
- Ports are ABC-free protocol-shaped classes in `application/<context>/ports/`; infrastructure adapters implement them by matching method signatures and live under `infrastructure/`. Follow that split for any new integration — don't call a DB/HTTP client directly from a `use_cases/` or `services/` file.
- New finding types in `ReconcileSettlementService` follow the existing shape exactly: a `code` (SCREAMING_SNAKE_CASE), `severity` (`"error"`/`"warning"`), a `_finding(...)` built from one or more `_evidence(...)` refs, and (if relevant) a priority slot in `_get_reason_code`'s `priority` tuple.
- New entity relationships for the graph are added declaratively to `RELATION_RULES` (`application/reconciliation/graph/relation_rules.py`) rather than by hand-editing `ReconciliationGraphBuilder` — the builder is generic over that table plus the `_ENTITY_SPECS` table mapping entity type → source collection → id field.



## Frontend Integration

The frontend is a separate React/TypeScript application generated with v0.

Frontend stack:
- React
- TypeScript
- Vite or the existing generated frontend runtime
- React Router
- TanStack Query
- Tailwind
- shadcn/ui
- React Flow

The frontend must consume the backend API through a typed API client and TanStack Query hooks.

Do not put backend calls directly into presentational components.

Prefer:

page
→ hook
→ API client
→ FastAPI endpoint

Mock data may be used temporarily, but its structure should mirror the real backend response shape so it can be replaced without redesigning components.

## Frontend Product Flow

The complete intended user flow is:

New reconciliation
→ upload merchant files
→ ingest
→ run reconciliation
→ reconciliation result
→ findings
→ finding detail
→ evidence
→ graph
→ investigation
→ investigation result

The important product experience is:

deterministic finding
→ evidence assembly
→ entity resolution
→ evidence graph
→ investigation
→ grounded conclusion

The UI must make this progression visible.

## Evidence Semantics

There is no separate evidence file for the frontend.

Evidence is generated by the backend from reconciliation findings and related entities.

Do not create an evidence-upload requirement.

Frontend evidence views should consume the evidence returned by the backend.

## Financial Authority

For settlement correctness:

Razorpay settlement net
vs
bank observed amount

is authoritative.

Merchant expected/accounting totals are contextual evidence.

Do not change this hierarchy in frontend calculations, labels, or explanations.

## AI Investigation Semantics

AI is an investigation/reasoning layer over deterministic reconciliation.

The frontend must visually distinguish:
- deterministic engine result
- evidence
- AI hypothesis
- verified conclusion
- insufficient evidence

Do not present an AI hypothesis as a financial reconciliation result.

## Current API Contract For Frontend

Use the actual route definitions discovered in the repository.

Do not invent endpoints when an existing endpoint provides the required data.

When an endpoint's implementation and documented route differ, inspect the actual FastAPI router and DTO before changing either side.

## Integration Rules

Before changing backend code for frontend integration:

1. Inspect the existing router.
2. Inspect its request DTO.
3. Inspect its response DTO.
4. Inspect the injected use case.
5. Inspect existing tests.
6. Make the smallest change required.

Do not rewrite existing domain/application logic merely to make frontend integration easier.

Prefer adding dedicated read/fetch endpoints or DTOs when genuinely required by the UI.

## Verification

For every integration step:

- run the relevant backend tests
- run the frontend type/build check
- start the API when endpoint testing is required
- exercise the actual endpoint
- verify response data against the frontend type
- fix concrete errors before moving on

Do not claim an integration is complete based only on compilation.

The final acceptance criterion is the real end-to-end flow:

upload
→ ingest
→ run
→ findings
→ evidence
→ graph
→ investigation