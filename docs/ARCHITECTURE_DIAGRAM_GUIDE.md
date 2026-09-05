# Architecture Diagram Guide

Five diagrams, each simple enough to draw by hand on a whiteboard in a few
minutes. Boxes and arrows only — no tool required. Each one lists exactly
what to box, what to label the arrows, and one or two things worth
annotating because they're easy to draw wrong.

---

## 1. System architecture

**Boxes** (left to right, roughly matching request flow):

```
[ Frontend ]  →  [ FastAPI (api/) ]  →  [ Application use cases ]  →  [ Domain ]
                        │                        │
                        │                        ├──▶ [ Postgres ]
                        │                        ├──▶ [ MinIO ]
                        │                        └──▶ [ Razorpay API (live) ]
                        │
                        └──▶ [ HuggingFace LLM API (live) ]
```

- Draw **Application use cases** as one box, but write the four context
  names inside it: `ingestion`, `reconciliation`, `investigation`,
  `razorpay`. That's the whole hexagonal split — domain has no arrows going
  *out* of it (framework-free), only arrows coming *in* from application.
- Draw **Postgres**, **MinIO**, **Razorpay API**, **HuggingFace API** as four
  separate boxes at the bottom — they're peers, not layered. Nothing in this
  system talks to Postgres except through a repository in
  `infrastructure/persistence/postgres/`.
- Annotate the HuggingFace arrow with "⚠ tools+schema unsupported by
  current model, falls back automatically" — worth remembering on the
  diagram since it explains a lot of investigation behavior downstream.

---

## 2. Data/world separation

Three columns, one box per table, with a short list of what compares across
them:

```
   RAZORPAY WORLD          MERCHANT WORLD           BANK
  ┌────────────────┐     ┌──────────────────┐   ┌─────────────────┐
  │ razorpay_orders │     │ merchant_orders   │   │ bank_transactions│
  │ payments        │     │ ledger_entries    │   │ (merchant-       │
  │ refunds         │     │ pos_transactions  │   │  uploaded, but   │
  │ settlements     │     │ gateway_transactions│ │  AUTHORITATIVE)  │
  │ settlement_entries│   │                   │   └─────────────────┘
  │ transfers       │     └──────────────────┘
  │ adjustments     │
  └────────────────┘
        │                         │                        │
        └───────────AUTHORITATIVE─┴────────────────────────┘
                  (razorpay net vs bank observed)
                         merchant = CONTEXTUAL ONLY
```

- Draw a clear visual separator (a line or gap) between "Razorpay + Bank"
  and "Merchant" — the point of this diagram is that **two** of the three
  columns are authoritative and one is context-only, and Bank is drawn on
  its own because it's physically ingested through the merchant pipeline
  but semantically grouped with Razorpay for authority purposes. Say this
  out loud while drawing it, it's the one thing people get wrong.
- Under `merchant_orders`, draw a small arrow labeled `razorpay_order_id`
  pointing across to `razorpay_orders` — that's the one field that ties the
  two worlds together for every merchant-side check.

---

## 3. Reconciliation flow

A vertical pipeline, one box per validator, in the actual execution order:

```
SettlementReconciliationData
        │
        ▼
 status != "processed"? ──yes──▶ [ PENDING / AWAITING_SETTLEMENT ] (stop here)
        │ no
        ▼
 validate_razorpay_state
 validate_orders                 (+ DUPLICATE_ORDER)
 validate_payments
 validate_merchant_sources        (+ BANK_TRANSACTION_MISSING)
 validate_ledger_amounts          (MERCHANT_LEDGER_AMOUNT_MISMATCH)
 validate_ledger_payment_references (DUPLICATE_PAYMENT / WRONG_PAYMENT_REFERENCE)
 validate_multi_source_amounts     (MULTI_SOURCE_DISAGREEMENT)
 validate_temporal
 validate_settlement_timing         (SETTLEMENT_TIMING_ANOMALY)
 validate_completeness
 validate_settlement                 (+ BANK_SETTLEMENT_AMOUNT_DIFFERENCE)
        │
        ▼
   any findings? ──yes──▶ [ EXCEPTION ] ──▶ build graph ──▶ persist findings+evidence+graph
        │ no
        ▼
  merchant == razorpay == bank? ──yes──▶ [ RECONCILED ]
        │ no
        ▼
  [ EXCEPTION / FINANCIAL_DIFFERENCE ]  (no itemized finding)
```

- Draw the three-way box at the bottom (`merchant == razorpay == bank`) as a
  diamond/decision shape — it's the one place all three totals are compared
  at once, and it's worth marking with a note: "known tension: merchant
  ledger isn't supposed to be authoritative, but this check still requires
  it to agree."
- The row of `validate_*` boxes should be drawn as one continuous chain
  (each just appends to one findings list) — don't draw them as
  alternatives/branches, they all always run.

---

## 4. Investigation/tool flow

```
[ selected findings ]
        │
        ▼
 EvidenceBuilder ──┬─▶ extract evidence (dedupe)
                   ├─▶ resolve graph nodes → BFS subgraph (depth=2)
                   └─▶ fetch_entity_record() per evidence item (exact lookup)
        │
        ▼
 EvidencePackage (findings, evidence, records, nodes, edges)
        │
        ▼
 LLMInvestigator ──▶ builds JSON prompt ──▶ HuggingFaceLLMClient.complete()
        │                                        │
        │                              ┌─────────┴─────────┐
        │                              ▼                   ▼
        │                        tools+schema         (fallback)
        │                        [try first]      plain schema-only
        │                              │                   │
        │                        422? ─┴─────────▶ used instead
        │
        ▼
 InvestigationResponse
        │
        ▼
 InvestigationPolicy.validate() ──▶ [ GROUNDED ]  or  [ ABSTAINED + reason ]
```

- Draw a small padlock icon next to `HuggingFaceLLMClient.complete()`'s
  tool-calling branch, labeled "scoped to this package's object_keys only —
  model can't reach arbitrary files." That's the one security-relevant
  detail worth calling out visually.
- Draw `InvestigationPolicy.validate()` as a gate/funnel shape with multiple
  small arrows feeding into "ABSTAINED" (invalid citation, low confidence,
  no root cause, etc.) and exactly one path through to "GROUNDED" — visually
  reinforces that abstention is the default/easy path and grounding is the
  narrow one.

---

## 5. Frontend → API → backend flow

```
[ Page component ]                         e.g. GraphPage, FindingDetail
        │
        ▼
[ lib/hooks/use*.ts ]                       TanStack Query
        │
        ▼
[ lib/api/*.ts ]                            typed fetch wrapper
        │
        ▼  HTTP
[ api/routes/*.py ]                          one router per context
        │
        ▼
[ api/dependencies.py Depends() ]            pulls use case off app.state
        │
        ▼
[ Application use case ]                     (see diagram 1/3/4)
```

- Draw one lane per page → hook → api-client file, so it's visually obvious
  each page has its *own* thin vertical slice rather than sharing a big
  shared data layer — e.g. `GraphPage → useGraph → graph.ts → GET
  .../graph`, side by side with `EvidenceExplorer → useEvidence →
  evidence.ts → GET .../evidence`.
- Mark the New Reconciliation page's arrow specially: it's the one place
  that sends a *multipart* request (`FormData`, one POST with 5 files)
  instead of JSON — draw its box slightly differently (dashed border) to
  flag that.
- No arrow should ever go directly from a page component to `fetch` —
  if you're drawing this from the real code, every page's arrow passes
  through exactly one hook and exactly one api-client file. That's the
  rule this diagram is meant to enforce.
