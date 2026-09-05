  # Architecture

  This documents the system **as it actually exists in the codebase today**,
  including everything added/changed during the investigation-evidence,
  graph-overflow, ingestion-error, and golden-scenario passes. It is a
  description, not a design proposal — where something is a known gap or a
  half-working path, that's stated explicitly rather than smoothed over.

  ## 1. Overall system flow

  ```
  merchant CSVs ──┐
                  ├──▶ ingestion ──▶ deterministic reconciliation ──▶ findings
  Razorpay API ───┘                                                     │
  (real orders/                                                         ▼
  payments/                                                        evidence
  settlements,                                                         │
  seeded once)                                                         ▼
                                                                    graph (only
                                                                    on exception)
                                                                        │
                                                          selected findings
                                                                        ▼
                                                                EvidenceBuilder
                                                            (finding → evidence
                                                            → records → subgraph)
                                                                        │
                                                                        ▼
                                                                AI investigator
                                                              (LLM + evidence pkg)
                                                                        │
                                                                        ▼
                                                              InvestigationPolicy
                                                            (citation/confidence
                                                                gate)
                                                                        │
                                                                ┌────────┴────────┐
                                                                ▼                 ▼
                                                          grounded root      abstention
                                                          cause + evidence   + reason
  ```

  Reconciliation is **always deterministic** — no LLM involvement, no
  probabilistic matching anywhere in `ReconcileSettlementService`. The LLM only
  ever sees a settlement *after* the deterministic engine has already decided
  it's an exception and already built the specific findings/evidence being
  investigated. The LLM can never override a deterministic finding — this is
  enforced by the system prompt ("Never override deterministic reconciliation
  facts") and structurally, since `InvestigationPolicy` only ever *validates or
  rejects* the LLM's output, never feeds anything back into `reconcile()`.

  ## 2. Razorpay vs merchant vs bank: three data "worlds"

  Every table in `schema.sql` belongs to exactly one of three worlds, and the
  reconciliation engine's whole job is comparing them:

  | World | Tables | Source of truth for | Ingested via |
  |---|---|---|---|
  | **Razorpay** | `razorpay_orders`, `payments`, `refunds`, `settlements`, `settlement_entries`, `transfers`, `adjustments` | The transaction itself: does it exist, what was captured, what settled | `CreateRazorpayOrderUseCase` (real orders) + direct repository writes for payments/refunds/settlements/settlement_entries (there's no "create a payment" use case — payments are a fact about what Razorpay's systems did, not something this app originates) |
  | **Merchant** | `merchant_orders`, `invoices`, `ledger_entries`, `bank_transactions`, `pos_transactions`, `gateway_transactions` | What the merchant's own systems believe happened — **contextual, not authoritative** | `POST /ingestion/merchant/batch` (CSV upload) |
  | **Bank** | (`bank_transactions`, actually merchant-sourced — see below) | What actually hit the merchant's bank account — **authoritative for settlement amount, together with Razorpay's own net** | Same batch ingestion endpoint, `bank_statement.csv` |

  Note the asymmetry that trips people up: `bank_transactions` is physically a
  *merchant*-ingested table (the merchant uploads their own bank statement,
  scoped by `source_id`/`import_pk` like every other merchant CSV), but
  **semantically** it's treated as authoritative alongside Razorpay's own net,
  never as "merchant-side" evidence. This is the Financial Authority rule
  (`CLAUDE.md`): **Razorpay settlement net vs. bank observed amount is
  authoritative; merchant ledger/order totals are contextual evidence only.**
  `ReconcileSettlementService.reconcile()` currently computes three figures —
  `merchant_expected`, `razorpay_net`, `bank_observed` — and (this is a known,
  reported, *not yet resolved* tension) its "reconciled" test requires **all
  three** to agree, which doesn't fully match the stated two-source authority
  model when a merchant's ledger legitimately books gross-of-fee amounts. See
  §13.

  Every merchant-world row is scoped by `source_id` (which of the 5 fixed file
  types it came from) and, except for `bank_transactions`/`pos_transactions`/
  `gateway_transactions`, by `import_pk` (which specific upload). As of this
  pass, `pos_transactions`, `gateway_transactions`, and `bank_transactions` all
  also carry a real `import_pk` FK — see §13's bug writeup for why that matters.

  ## 3. Settlement / payment / settlement-entry / bank UTR relationships

  ```
  razorpay_orders ──1:N──▶ payments ──1:N──▶ refunds
                                        │
                                        ▼
                                settlement_entries ◀──N:1── settlements
                                        │                       │
                                settlement_utr             settlements.utr
                                        │                       │
                                        └───────────┬───────────┘
                                                      ▼
                                            bank_transactions.utr
                                        (merchant-uploaded, matched by UTR)
  ```

  - A `settlement` has one `utr` (or none, if `status != "processed"`).
  - Every `settlement_entry` that belongs to it carries the *same* UTR in its
    own `settlement_utr` column — this is intentionally denormalized so a
    single entry can be traced back to its settlement's bank credit without a
    join, and so `RELATION_RULES`' `settlement --MATCHES_BANK_UTR--> bank_transaction`
    edge and the deterministic `BANK_TRANSACTION_MISSING` /
    `BANK_SETTLEMENT_AMOUNT_DIFFERENCE` checks can both key off `utr` directly.
  - `settlement_entries.entry_type` is `"payment"` (credits the net-of-fee
    amount) or `"refund"` (debits the refund amount) — `_calculate_razorpay_net`
    is simply `sum(credit - debit)` across all of a settlement's entries.
  - A `payment`/`refund` row can be referenced by at most one settlement_entry
    in this synthetic data model (1 entry per financial event).
  - `bank_transactions.utr` is merchant-supplied text with **no FK** to
    `settlements.utr` — matching is done at reconciliation time by exact string
    equality, never fuzzy. If the merchant's bank statement doesn't have a row
    with the settlement's UTR at all, that's `BANK_TRANSACTION_MISSING`; if it
    has one but the amount disagrees, that's `BANK_SETTLEMENT_AMOUNT_DIFFERENCE`
    (new this pass — previously this fell through to the unexplained top-level
    `FINANCIAL_DIFFERENCE`).

  ## 4. Backend layers and major use cases

  Hexagonal, one bounded context per subfolder under `src/recon/`:

  ```
  domain/            framework-free dataclasses (Money, MerchantOrder, RazorpayOrder,
                      LedgerEntry, GraphNode/Edge, EvidenceRef, ReconciliationFinding, ...)
                      — no I/O, no behavior beyond simple invariants
  application/        one folder per context: ingestion/ reconciliation/ investigation/ razorpay/
    <context>/dto/         request/response/internal shapes
    <context>/ports/       abstract interfaces (repository, gateway, storage, llm)
    <context>/services/    orchestration/pure logic, no I/O of their own
    <context>/use_cases/   one class per use case, execute() entrypoint
  infrastructure/      concrete adapters
    persistence/postgres/   repositories + schema.sql + migrations + entity_records.py
    storage/minio/          MinioObjectStorage (raw uploaded file bytes)
    razorpay/               RazorpayApiGateway (live Razorpay SDK/HTTP), client.py
    ai/                     HuggingFaceLLMClient (OpenAI-compatible), schemas.py
    investigation/          LLMInvestigator, mcp/document_tools.py
    ingestion/csv/          MerchantCsvAdapter
  api/
    app.py               FastAPI app + lifespan(): wires every port → adapter → use case by hand onto app.state (no DI framework)
    dependencies.py      Depends() functions pulling use cases off app.state
    routes/              ingestion.py, reconciliation.py, investigation.py — one router per context
  ```

  **Major use cases**, by context:

  - **razorpay**: `CreateRazorpayOrderUseCase` (order → real API → repository),
    `SyncRazorpaySettlementUseCase` (pulls Razorpay's own settlement recon feed
    — used for live-account sync, not the seeding scripts).
  - **ingestion**: `IngestMerchantSourceUseCase` — the single use case behind
    both `/ingestion/merchant` and `/ingestion/merchant/batch` (batch just
    calls it once per file). Pipeline inside: `MerchantSourceAdapterRegistry`
    (picks a parser by filename/content-type) → `MerchantSourceNormalizer`
    (column-alias detection + entity-type detection) →
    `MerchantRecordValidator` (required-field checks) →
    `MerchantDomainConstructor` (dict → domain dataclass) → repository persist.
    On any failure the import row is marked `"failed"` and the exception
    re-raised — nothing half-committed.
  - **reconciliation**: `ReconcileSettlementUseCase` (loads
    `SettlementReconciliationData`, calls `ReconcileSettlementService.reconcile()`,
    persists results + builds the graph iff exception), plus read use cases
    (`GetReconciliationUseCase`, `ListReconciliationsUseCase`,
    `ListFindingsUseCase`, `GetFindingUseCase`, `ListEvidenceUseCase`,
    `GetReconciliationGraphUseCase`).
  - **investigation**: `InvestigateExceptionUseCase` (loads graph + selected
    findings, builds an `EvidencePackage` via `EvidenceBuilder`, calls
    `InvestigationService`, persists the result), `GetInvestigationUseCase`.

  ## 5. PostgreSQL + MinIO

  - **Postgres** (asyncpg, raw SQL, no ORM) holds every structured record —
    Razorpay-world, merchant-world, graph nodes/edges, reconciliation
    findings/evidence, and investigation results (`investigations` table,
    `response` stored as `jsonb`). `docker-compose.yaml` mounts
    `schema.sql` as the init script for a fresh container; `migrations/*.sql`
    are incremental history already folded into `schema.sql` — editing the
    live schema means editing both.
  - **MinIO** (S3-compatible) holds the **raw uploaded file bytes** only — one
    object per ingested file, keyed `imports/{source_id}/{import_id}/{filename}`.
    Nothing else lives there. `EvidenceRef.object_key` points here when an
    evidence item traces back to an uploaded file; `DocumentTools` (see §10)
    is the only thing that ever reads these objects back out.

  ## 6. Real Razorpay order creation flow

  ```
  CreateOrderRequest(amount, currency, receipt)
          │
          ▼
  CreateRazorpayOrderUseCase.execute()
          │
          ├──▶ RazorpayGateway.create_order()  (RazorpayApiGateway → live Razorpay
          │                                     test-mode HTTP API, via client.py)
          │
          └──▶ RazorpayRepository.save_order()  (RazorpayPostgresRepository,
                                                  upsert into razorpay_orders)
          │
          ▼
    returns real order_id (e.g. "order_TY14N8tyquXCDl")
  ```

  This is the **only** order-creation path in the codebase — no fake/mock order
  generator exists. Both `scripts/seed_dataset.py` (old 20-scenario dataset)
  and `scripts/seed_golden_scenarios.py` (16 golden scenarios) call this exact
  use case, idempotently (looked up first by `receipt` in `razorpay_orders`; a
  match is reused, not recreated). Payments, refunds, settlements, and
  settlement_entries have no equivalent "use case" — they're written directly
  via `RazorpayRepository` because Razorpay's live test-mode API has no way to
  fabricate settlement events on demand; the seeding scripts derive them from
  each dataset's own `razorpay.json` and persist them as facts.

  ## 7. Merchant ingestion flow

  ```
  POST /ingestion/merchant/batch
    (multipart, repeated "files" fields; dispatched to a source purely by
    exact filename — SOURCE_BY_FILENAME in api/routes/ingestion.py)
          │
          ▼  (one call per file, sequentially, same order files were sent)
  IngestMerchantSourceUseCase.execute()
          │
          ├─ 1. MerchantIngestionRepository.create_import()   (status="processing")
          ├─ 2. ObjectStorage.put()                             (raw bytes → MinIO)
          ├─ 3. MerchantSourceAdapterRegistry.get_adapter()      (CSV → list[dict])
          ├─ 4. MerchantSourceNormalizer.normalize()             (alias detection,
          │                                                       entity-type scoring)
          ├─ 5. MerchantRecordValidator.validate()               (required fields;
          │                                                       raises on any error)
          ├─ 6. MerchantDomainConstructor.build()                (dict → domain object)
          └─ 7. MerchantIngestionRepository.persist_records()    (bulk insert,
                                                                  scoped by import_pk)
          │
          ▼ (any exception at any step)
    complete_import() / fail_import(), exception re-raised as-is
  ```

  **Order matters within one batch call**: `_persist_ledger_entries` resolves
  each ledger row's `merchant_order_pk` via `... FROM merchant_orders WHERE
  merchant_order_id = $1 ORDER BY id DESC LIMIT 1` — i.e. "the most recently
  inserted row with this text ID," not a value carried in the request itself.
  If `ledger.csv` is submitted *before* `merchant_orders.csv` in the same
  batch, this resolves to whatever unrelated row last happened to have that ID
  (observed and root-caused during the golden-scenario pass — see §13). The
  canonical, correct order (also what the frontend always sends, since
  `SOURCE_SLOTS` is ordered this way) is: `merchant_orders.csv`, `ledger.csv`,
  `bank_statement.csv`, `pos.csv`, `other_gateway.csv`.

  A CSV with **zero data rows** is rejected outright
  (`MerchantSourceNormalizer.normalize([])` returns `entity_type="unknown"`,
  which `MerchantRecordValidator` has no rule for → `"Unsupported entity type:
  unknown"`). Real callers (the frontend, and both seeding scripts) simply
  don't submit a file they have no rows for.

  A duplicate `merchant_order_id` within one `merchant_orders.csv` violates
  `uq_merchant_order_source UNIQUE(import_pk, merchant_order_id)` and is
  translated from a raw `asyncpg.UniqueViolationError` into a clean `400`
  (never a `500`) by `MerchantIngestionPostgresRepository.persist_records`.
  This is a deliberate, intentional validation boundary, not a bug — it is
  never weakened, per explicit instruction across multiple passes of this
  project.

  ## 8. Reconciliation engine and finding types

  `ReconcileSettlementService.reconcile()`:

  ```
  if settlement.status != "processed":
      return pending / "AWAITING_SETTLEMENT"   (no findings, no graph)

  findings = validate_razorpay_state(data)
          + validate_orders(data)                    # + DUPLICATE_ORDER (new)
          + validate_payments(data)
          + validate_merchant_sources(data)           # incl. BANK_TRANSACTION_MISSING
          + validate_ledger_amounts(data)              # MERCHANT_LEDGER_AMOUNT_MISMATCH (new)
          + validate_ledger_payment_references(data)   # DUPLICATE_PAYMENT / WRONG_PAYMENT_REFERENCE (new)
          + validate_multi_source_amounts(data)         # MULTI_SOURCE_DISAGREEMENT (new)
          + validate_source_amounts_against_payment(data) # POS_/GATEWAY_AMOUNT_MISMATCH (new)
          + validate_temporal(data)
          + validate_settlement_timing(data)             # SETTLEMENT_TIMING_ANOMALY (new)
          + validate_completeness(data)
          + validate_settlement(data)                     # incl. BANK_SETTLEMENT_AMOUNT_DIFFERENCE (new)

  razorpay_net = sum(entry.credit - entry.debit for settlement_entries)
  merchant_expected = sum(credit - debit for ledger_entries)
  bank_observed = sum(credit - debit for bank_transactions)

  if findings:                                    status = "exception", reason = priority(findings)
  elif merchant_expected == razorpay_net == bank_observed:   status = "reconciled"
  else:                                            status = "exception", reason = "FINANCIAL_DIFFERENCE"
  ```

  Only on `"exception"` is a `ReconciliationGraph` built and persisted
  alongside the findings/evidence — a reconciled settlement has no graph.

  **All finding codes** (pre-existing + new, new ones marked ✨):

  | Code | Checked in | Meaning |
  |---|---|---|
  | `ORDER_NOT_FOUND`, `PAYMENT_NOT_FOUND`, `REFUND_NOT_FOUND`, `TRANSFER_NOT_FOUND`, `ADJUSTMENT_NOT_FOUND` | `_validate_razorpay_state` | Settlement entry references a Razorpay-world id that doesn't exist |
  | `RAZORPAY_ORDER_NOT_FOUND`, `ORDER_AMOUNT_MISMATCH`, `ORDER_CURRENCY_MISMATCH`, `DUPLICATE_MERCHANT_ORDER` | `_validate_orders` | Merchant order vs. its claimed Razorpay order |
  | ✨ `DUPLICATE_ORDER` | `_validate_orders` | 2+ *different* merchant_order_ids reference the *same* razorpay_order_id |
  | `PAYMENT_ORDER_MISSING`, `PAYMENT_ORDER_NOT_FOUND`, `PAYMENT_AMOUNT_MISMATCH`, `PAYMENT_CURRENCY_MISMATCH` | `_validate_payments` | Razorpay's own payment vs. its own order (Razorpay-internal consistency — **not** merchant-vs-payment; see §13's G05 note) |
  | `LEDGER_ORDER_NOT_FOUND`, `POS_ORDER_NOT_FOUND`, `GATEWAY_ORDER_NOT_FOUND`, `BANK_TRANSACTION_MISSING` | `_validate_merchant_sources` | Merchant-side cross-references, and bank-data-entirely-absent |
  | ✨ `MERCHANT_LEDGER_AMOUNT_MISMATCH` | `_validate_ledger_amounts` | Ledger revenue (sum of that order's `entry_type == "credit"` rows only — a balancing debit row in a double-entry ledger is not a second, independent claim) vs. the *actual* Razorpay payment amount for that order |
  | ✨ `DUPLICATE_PAYMENT`, ✨ `WRONG_PAYMENT_REFERENCE` | `_validate_ledger_payment_references` | Same `razorpay_payment_id` cited by 2+ ledger entries under different merchant orders — genuinely ambiguous double-posting vs. one order citing someone else's real payment |
  | ✨ `MULTI_SOURCE_DISAGREEMENT` | `_validate_multi_source_amounts` | Ledger (same credit-only aggregation as above)/POS/gateway disagree on the amount for the same merchant order, with no authoritative side to check against |
  | ✨ `POS_AMOUNT_MISMATCH`, ✨ `GATEWAY_AMOUNT_MISMATCH` | `_validate_source_amounts_against_payment` | A POS or other-gateway record disagrees with the *actual* Razorpay payment for that order specifically (distinct from `MULTI_SOURCE_DISAGREEMENT`: here there is a single authoritative side to check against, so the wrong source is named directly) |
  | `PAYMENT_NOT_CAPTURED`, `REFUND_NOT_PROCESSED`, `PAYMENT_BEFORE_ORDER`, `CAPTURE_BEFORE_PAYMENT`, `SETTLEMENT_BEFORE_CAPTURE`, `SETTLEMENT_ENTRY_BEFORE_PAYMENT`, `ENTRY_AFTER_SETTLEMENT`, `SETTLED_BEFORE_ENTRY` | `_validate_temporal` | Chronological invariant violations |
  | ✨ `SETTLEMENT_TIMING_ANOMALY` | `_validate_settlement_timing` | Bank credit lands >7 days after the earliest payment it settles |
  | `UNSETTLED_PAYMENT`, `DUPLICATE_SETTLEMENT_ENTRY`, `SETTLEMENT_UTR_MISSING` | `_validate_completeness` / `_validate_settlement` | Coverage/duplication of settlement entries |
  | ✨ `BANK_SETTLEMENT_AMOUNT_DIFFERENCE` | `_validate_settlement` | Bank observed ≠ Razorpay computed net, itemized **per UTR** (one finding per mismatching settlement_entry/bank_transaction pair, not one blunt settlement-wide finding); mutually exclusive with `BANK_TRANSACTION_MISSING` |
  | `FINANCIAL_DIFFERENCE` | top-level fallback | The 3-way total mismatch with *no* itemized finding explaining it |
  | `ALL_SOURCES_AGREE` | top-level | Reconciled |
  | `AWAITING_SETTLEMENT` | top-level | Pending |

  New codes follow the pre-existing convention exactly: `code`
  (SCREAMING_SNAKE_CASE), `severity`, one or more `_evidence(...)` refs built
  via the same `_finding()`/`_evidence()`/`_entity()` helpers every other check
  uses — no special-casing anywhere downstream (evidence, graph, investigation
  all treat them identically to pre-existing codes).

  ## 9. EvidenceBuilder and evidence lifecycle

  ```
  ReconciliationFinding[] (selected by the caller)
          │
          ▼
  EvidenceBuilder.build(findings, depth=2)
          │
          ├─ _extract_evidence()      dedupe EvidenceRef across findings
          ├─ _resolve_nodes()          map evidence → graph node ids
          ├─ GraphTraversalService     BFS subgraph to `depth` hops
          └─ _fetch_records()          NEW: for each unique (source, entity_type,
                                        entity_id), an exact-key Postgres lookup
                                        via entity_records.fetch_entity_record()
          │
          ▼
  EvidencePackage(findings, evidence, records, nodes, edges)
  ```

  `EvidenceRecord` (the `records` field) was a DTO that already existed but
  was always populated with `[]` before this pass — nothing ever filled it in.
  `entity_records.py` (new) is a small shared helper: an `entity_type → (table,
  id_column, needs_latest_tiebreak)` map (mirroring
  `ReconciliationGraphBuilder._ENTITY_SPECS`), doing one exact-match SQL
  lookup per evidence item, stripping internal surrogate keys
  (`id`/`source_id`/`import_pk`). No fuzzy matching, no row scanning. The same
  helper backs `GET /reconciliation/settlements/{id}/evidence` too (via a new
  `EvidenceDetail` DTO that wraps `EvidenceRef` + `data`, kept separate from
  the domain `EvidenceRef` itself to avoid growing a widely-shared type) — so
  the Evidence Explorer shows the same record content an investigation would
  see.

  **Full evidence chain, end to end**: `finding.evidence[]` (an `EvidenceRef`,
  persisted in `reconciliation_evidence`) → `evidence_id` (deterministic,
  `f"ev:{source}:{entity_type}:{entity_id}:{reason}"`) → `source`/`entity_type`/
  `entity_id` → `data` (the live record, via `entity_records.py`) →
  `object_key` (the raw uploaded file in MinIO, when the entity came from an
  upload) → the corresponding `graph_node_id` (`f"{source}:{entity_type}:{entity_id}"`,
  same string shape used everywhere).

  ## 10. Graph construction and relationship rules

  Built only for exception settlements, by `ReconciliationGraphBuilder.build()`:

  ```
  _ENTITY_SPECS   (source, entity_type, collection, id_field) for every
                  entity type: merchant_order, ledger_entry, bank_transaction,
                  pos_transaction, gateway_transaction, razorpay_order,
                  payment, refund, transfer, adjustment, settlement,
                  settlement_entry

  RELATION_RULES  declarative (source_type, target_type, edge_type,
                  source_field, target_field) tuples — e.g. merchant_order
                  --REFERENCES_RAZORPAY_ORDER--> razorpay_order,
                  settlement --MATCHES_BANK_UTR--> bank_transaction

  build():
    nodes = one GraphNode per entity, node_id = f"{source}:{entity_type}:{entity_id}"
    edges = for each RELATION_RULES tuple, join source entities' source_field
            to target entities' target_field via a field_index — no manual
            per-relationship code
    affected_node_ids = nodes touched by the response's evidence
  ```

  Adding a new entity relationship means adding a row to `RELATION_RULES`, not
  editing the builder — this held true for every new finding type added this
  pass (none needed a new relation; all new codes reuse existing entity types
  and existing edges).

  At investigation time, `EvidenceBuilder` traverses this same graph via
  `GraphTraversalService` (breadth-first, `depth=2` from the finding's own
  evidence nodes) to decide which nodes/edges go into the `EvidencePackage` —
  the graph the frontend renders and the subgraph the LLM sees are the *same*
  graph, not two representations that could drift apart.

  ## 11. AI investigator: evidence/tool boundary, grounding, abstention

  ```
  InvestigationService.investigate(EvidencePackage)
          │
          ▼
  LLMInvestigator.investigate()
          │
          ├─ builds a JSON prompt: findings + evidence + records + nodes + edges
          ├─ calls HuggingFaceLLMClient.complete(tools=DocumentTools.definitions(),
          │                                       tool_handlers=<scoped>)
          │
          ▼
  InvestigationResponse (factual_observations, hypotheses[], root_cause,
                          missing_evidence[], should_abstain, abstain_reason)
          │
          ▼
  InvestigationPolicy.validate(response, package)
          │  rejects/forces-abstain on:
          │   - any cited evidence_id not in package.evidence         → abstain
          │   - any hypothesis confidence outside [0,1]                → abstain
          │   - zero hypotheses                                        → abstain
          │   - all hypotheses below MIN_CONFIDENCE = 0.60              → abstain
          │   - root_cause is null despite should_abstain=false         → abstain
          │   - root_cause references an unknown hypothesis_id           → abstain
          │   - root hypothesis below MIN_CONFIDENCE                      → abstain
          │   - root hypothesis has no supporting_evidence_ids             → abstain
          │   - any missing_evidence reported                               → abstain
          ▼
  grounded (root_cause + evidence) or abstained (should_abstain=true + reason)
  ```

  **Tool boundary** (the "narrow, application-owned evidence retrieval"
  requirement): `DocumentTools.get_document`/`search_document` wrap
  `ObjectStorage` and will fetch *any* object_key that exists in MinIO — they
  are themselves unscoped. The actual boundary lives in
  `LLMInvestigator._scoped_tool_handlers()`, which builds an allowlist from
  `{item.object_key for item in evidence.evidence if item.object_key}` for the
  *current* `EvidencePackage` and rejects (returns an error string to the
  model, doesn't throw) any call for a key outside it. The model can never
  address arbitrary files, only documents already named by evidence already
  in its own package.

  **Live constraint, not theoretical**: the currently-configured HF-hosted
  model rejects `tools` combined with strict `json_schema` output outright
  (`422`, confirmed via direct API probe). `HuggingFaceLLMClient.complete()`
  tries the tool-enabled path first and falls back transparently to schema-only
  on that specific first-round rejection (`_ToolCallingUnsupported`) — this is
  why grounded/abstained investigations still work even though document-tool
  retrieval doesn't currently execute against this model/provider. The
  mechanism is fully built and enabled; it's dormant only because of the
  provider.

  The LLM can **never** override a deterministic finding or change the
  authoritative status — it only ever produces a hypothesis *about why* a
  finding occurred, gated by the policy above before anything is persisted or
  shown as "grounded."

  ## 12. Frontend architecture

  ```
  frontend/
    app/[[...slug]]/page.tsx    single catch-all Next.js route; react-router-dom
                                owns actual client-side routing inside it
    components/views/            one component per page (Dashboard,
                                ReconciliationsList, NewReconciliation,
                                ReconciliationDetail, FindingDetail,
                                EvidenceExplorer, GraphPage, InvestigationPage)
    components/                  shared presentational pieces (Shell, Kpi,
                                SourceEvidence, async-state)
    lib/api/                     one file per resource (reconciliations,
                                findings, evidence, graph, investigations,
                                ingestion) — thin fetch wrappers, typed
    lib/hooks/                   TanStack Query hooks, one per resource,
                                query-keys.ts centralizes cache keys
    lib/types/domain.ts          hand-maintained types mirroring the actual
                                FastAPI DTOs (comment at the top says so
                                explicitly — never add a field the backend
                                doesn't return)
  ```

  Routes: `/` (dashboard) → `/reconciliations` (list) → `/reconciliations/new`
  (upload) → `/reconciliations/:id` (detail: status, KPIs, findings) →
  `/reconciliations/:id/findings/:findingId` (finding detail: evidence +
  "Investigate" action) → `/reconciliations/:id/evidence` (Evidence Explorer,
  independent of any one finding) → `/reconciliations/:id/graph` (React Flow
  canvas) → `/investigations/:id` (investigation result).

  **Data flow**: page component → `lib/hooks/use*` (TanStack Query) →
  `lib/api/*` (typed fetch) → FastAPI route — no component calls `fetch`
  directly; `ApiError` (with `.status`) is the one error type every caller
  handles.

  **New Reconciliation** (`new-reconciliation.tsx`): one multi-file `<input>`
  replaces five separate pickers; files are matched to a source slot purely by
  exact filename (`SLOT_BY_FILENAME`, the same contract the backend batch
  endpoint dispatches on), then sent as one `FormData` in one request via
  `useIngestMerchantSourcesBatch`. On a duplicate-constraint `400`, the raw
  Postgres error is parsed (`describeIngestionError`) into a plain-language
  "this order ID appears more than once, rejected by design" message with the
  raw detail kept behind a `<details>` disclosure — never hidden.

  **Graph page**: default `@xyflow/react` node type, `data.label` is a custom
  `.graph-node` div. Node width is set via an inline `style={{width:
  NODE_WIDTH}}` per node (the only thing that reliably overrides xyflow's own
  hardcoded `.react-flow__node-default { width: 150px }`, since inline style
  always wins the cascade); `.graph-node` itself is `width: 100%;
  box-sizing: border-box` so it can never assert an independent width that
  disagrees with its parent (the actual root cause of a real overflow bug
  found and fixed this pass — see §13). Selecting a node highlights it via a
  `selected` flag recomputed on the node array (not a DOM mutation) and
  deep-links from Evidence Explorer via `?focus=<node_id>`.

  **Evidence Explorer**: groups evidence by source (Razorpay/Merchant/Bank),
  shows "cited by" links back to whichever finding(s) reference each item, an
  expandable "View source record" (the `data` field from `EvidenceDetail`,
  distinguishing `undefined` = "not fetched by this endpoint" from `null` =
  "fetched, no record exists"), and a "View in graph" deep link.

  ## 13. Important bugs/fixes made during this project

  1. **`EvidencePackage.records` was always `[]`.** Fixed by adding
    `entity_records.py` + wiring it into `EvidenceBuilder._fetch_records()`
    and the reconciliation-context `list_evidence` path. Verified live: an
    investigation's `factual_observations` now directly quote real record
    field values, not just bare evidence stubs.
  2. **Document-tool retrieval was fully built but disabled**
    (`tools=None` in `LLMInvestigator`), and `HuggingFaceLLMClient
    ._complete_with_tools` had two real bugs (`response_schema` never
    forwarded; `tools`/`tool_choice` commented out of the actual API call) —
    re-enabling it as-is would have crashed immediately. Fixed both, added a
    6-round hard cap, added the `_scoped_tool_handlers` boundary (§11), and
    discovered/handled the live `422`-on-tools+schema provider limitation.
  3. **Graph node text overflow, twice.** First fix set the inner
    `.graph-node`'s width equal to the *outer* node's total width, ignoring
    the outer's own padding — guaranteed ~20px overflow on every node,
    independent of text length. Second (correct) fix: inner element is
    `width: 100%` of its actual parent, not an independently-asserted fixed
    value. Also fixed an unrelated but related overflow in the graph
    sidebar's Node ID/Connections display (`.kpi`'s 22px font sized for short
    numeric KPIs, not long identifiers).
  4. **Cross-settlement data leak in `_get_pos_transactions`/
    `_get_gateway_transactions`.** These joined POS/gateway rows to
    `merchant_orders` by bare text equality on `merchant_order_id` with no
    import scoping — since that id is only unique per import, two unrelated
    settlements sharing a name like "MORD-01" leaked each other's POS/gateway
    rows into one another's reconciliation. Root cause: `pos_transactions`/
    `gateway_transactions`/`bank_transactions` already had a live `import_pk`
    column + unique constraint in the running database that `schema.sql`
    didn't reflect at all (a fresh container would have failed to ingest).
    Fixed the queries to scope by `import_pk` (matching how `ledger_entries`
    already correctly worked), updated `schema.sql`, added
    `migrations/005_pos_gateway_import_scoping.sql`.
  5. **`_persist_ledger_entries` silently drops unresolvable rows.** A
    `ledger.csv` row whose `merchant_order_id` has no matching
    `merchant_orders` row is dropped by the `INSERT ... SELECT ... WHERE
    merchant_order_id = $1` (zero rows matched → zero rows inserted, no
    error). This makes the pre-existing `LEDGER_ORDER_NOT_FOUND` finding
    structurally unreachable for that shape of fault, and blocks the new
    `DUPLICATE_PAYMENT` check for scenarios that model a duplicate exactly
    this way (golden scenario G07). **Identified, not fixed** — needs
    `merchant_order_pk` to accept `NULL` on insert and the read-side query
    changed from an `INNER` to a `LEFT JOIN`.
  6. Two prior sessions' audits, corrected honestly rather than silently:
    an earlier claim of an "off-by-one ID collision" in the old dataset's
    scenario 07 was re-verified and found to be a misread (both rows
    correctly referenced the same razorpay order) — documented as a
    correction, not left standing.
  7. **`_validate_ledger_amounts`/`_validate_multi_source_amounts` broke
    against a genuine double-entry ledger** (rich_recon_60's `ledger.csv`:
    one credit revenue row + one debit receivable row per order, unlike the
    single-row-per-order ledgers both earlier datasets used). Both checks
    read `credit - debit` per *row* rather than aggregating per order, so
    every order's own balancing debit row (`-amount`, never equal to a
    positive payment) was flagged as a mismatch — live-tested: 60/60 and
    39/60 spurious findings respectively, on the very first run. Fixed by
    aggregating `entry_type == "credit"` rows per merchant_order_id before
    comparing (the debit row is not an independent revenue claim).
  8. **`bank_transactions` accumulates duplicate rows across repeated
    ingestions of the identical bank statement**, inflating `bank_observed`.
    Root cause: UTR-based matching is deliberately not import-scoped (a bank
    statement isn't tied 1:1 to one reconciliation run), so re-uploading the
    same file creates a new row per UTR each time with nothing collapsing
    identical re-uploads back to one. Found by doing exactly what was asked
    (running a scenario twice from a clean ingest) — first run after the fix
    above still showed `BANK_SETTLEMENT_AMOUNT_DIFFERENCE` on all 60 UTRs
    instead of the one genuinely short-settled one. Fixed with `SELECT
    DISTINCT ON (utr, transaction_date, debit, credit) ... ORDER BY ...,
    id DESC` in `_get_bank_transactions` — an exact-value collapse (rows
    identical in every financial respect become one), never fuzzy; two bank
    rows for the same UTR that actually differ in amount or date are still
    both surfaced. Also fixed while there: the itemized
    `BANK_SETTLEMENT_AMOUNT_DIFFERENCE` finding keyed every UTR's finding on
    the settlement itself, a latent finding-id collision for any settlement
    with 2+ anomalous UTRs (harmless with exactly one, as in every scenario
    tested so far) — now keyed on the specific settlement_entry id(s).

  ## 14. Golden scenario validation flow

  ```
  datasets/golden_scenarios/scenario_gNN_.../
    README.md, answers.json, razorpay.json, merchant_faulty/*.csv   (frozen source)
          │
          ▼  scripts/seed_golden_scenarios.py  (idempotent; real Razorpay API)
    order_mapping.json           scenario order id → real order_id
    merchant_seeded/*.csv         ingestible CSVs, enriched with the columns
                                  the real normalizer/validator require
                                  (currency, status, synthesized ids/entry_ids),
                                  amounts/dates/references copied verbatim
    Postgres: razorpay_orders, payments, refunds, settlements,
              settlement_entries — derived using a fee model
              (fee = round(amount * 0.0236, 2), no separate tax layer)
              reverse-engineered and verified exactly against 5 scenarios'
              own stated expected net before being trusted
          │
          ▼  scripts/run_golden_scenarios.py  (real HTTP calls, no mocks)
    POST /ingestion/merchant/batch → POST /reconciliation/settlements
          → POST /investigation/exceptions (when findings exist)
          │
          ▼
    datasets/golden_scenarios/golden_baseline_report.json  (per-scenario:
      expected vs actual status/findings/investigation mode, match/mismatch)
  ```

  Both scripts never modify the original scenario source files — everything
  they produce is a new, derived file/directory alongside the frozen
  originals, or a row in Postgres. See `docs/GOLDEN_SCENARIO_FINAL_REPORT.md`
  for the full current results table (5/16 fully verified end-to-end as of
  this writing, 5/16 with the correct deterministic status+finding pending
  investigation re-verification, the rest with specific identified root
  causes — not "unknown failures").

  ## 15. Tests and current verification state

  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest tests/`: **32 passed, 3
    failed**. The 3 failures (`EvidenceRef`/`role` kwarg, `MerchantOrder`
    missing arg) are pre-existing drift between `tests/` and the domain model,
    documented in `CLAUDE.md`, unrelated to and unchanged by this work.
  - `pnpm exec tsc --noEmit` / `pnpm build`: clean.
  - `tests/` only covers `src/recon/domain/*` (pure dataclasses) plus, as of
    this pass, `application/investigation/services/evidence_builder.py` and
    `investigation_policy.py` — there is still no automated coverage for
    `application/reconciliation` or any `infrastructure/` adapter; all
    verification of the new finding types and the pos/gateway fix was done via
    live calls against the real running system (`scripts/run_golden_scenarios.py`
    and manual `curl`/`psql`), not unit tests.
  - **Known, currently-blocking external constraint**: the HuggingFace account
    behind `HF_MODEL` has repeatedly returned `402 - monthly included credits
    depleted` during this project. This blocks live investigation
    verification for several scenarios and is not something fixable from
    inside this codebase.
