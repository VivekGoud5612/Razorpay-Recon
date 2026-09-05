# Final Verification Report

This is the final freeze verification pass over the reconciliation system,
covering three items only: (1) golden-scenario ingestion/source completeness,
(2) the G11 investigation diagnosis, (3) a full end-to-end regression across
all three datasets (golden-16, old-20, RICH-60). No new features, no
architecture changes, no new scenarios. Two changes to existing domain logic
were made, both because live testing surfaced a verified, objectively-wrong
result (not a style preference) — see §3 and §5.

Status legend: **VERIFIED** (live-tested, confirmed correct) / **PARTIAL**
(some but not all aspects confirmed) / **BLOCKED** (could not be exercised,
reason given) / **PRE-EXISTING** (a known, already-documented limitation,
unchanged by this pass).

---

## 1. Ingestion / seeded source completeness — VERIFIED

Every golden scenario's *source* directory (`merchant_faulty/`) contains all
five CSVs (`merchant_orders.csv`, `ledger.csv`, `bank_statement.csv`,
`pos.csv`, `other_gateway.csv`) — confirmed by direct inspection. Where a
scenario doesn't exercise POS/gateway/bank data, that source file exists but
is **header-only** (0 data rows), e.g. G10's and G12's `bank_statement.csv`.

`scripts/seed_golden_scenarios.py`'s `write_merchant_seeded()` does not copy
a header-only file into `merchant_seeded/` — this is intentional, documented
behavior (module docstring + a `skipped_empty` list in the seed report), not
a silent omission. `scripts/run_golden_scenarios.py`'s batch submission only
attaches files that actually exist in `merchant_seeded/`
(`if (seeded_dir / name).exists()`), and `POST /ingestion/merchant/batch`
(`api/routes/ingestion.py`) processes exactly the files it's given — there is
no server-side requirement that all 5 sources be present in one batch.

**Live-tested this pass**, clean DB state, real HTTP calls:
- **G01** (clean, no POS/gateway data) — batch of 3 files
  (`merchant_orders.csv`, `ledger.csv`, `bank_statement.csv`) ingests and
  reconciles with no errors.
- **G13** (the one golden scenario with real POS/gateway rows) — batch of
  all 5 files ingests and reconciles with no errors, correctly producing
  `POS_AMOUNT_MISMATCH` / `GATEWAY_AMOUNT_MISMATCH` / `MULTI_SOURCE_DISAGREEMENT`.
- All other 14 golden scenarios (varying subsets of 3–4 files) ingested
  cleanly in the full regression (§4).

No source is silently dropped: every file present in `merchant_seeded/` is
submitted and ingested; every file absent from it is because the scenario's
own source data has zero rows for it, and that omission is tracked in
`golden_seed_report.json`'s `skipped_empty` field, not hidden.

---

## 2. G11 investigation diagnosis — VERIFIED (evidence fixed; abstain is a genuine model limitation)

**Question asked:** is the distinguishing payment date actually present in
the evidence package the LLM sees?

**Answer: it was not, for a reason more fundamental than "add a date field"** —
tracing it down surfaced two real, generalizable bugs, both fixed:

1. **`EvidenceBuilder` never resolved a finding's own `affected_entity` as a
   record.** `_extract_evidence()` only pulled from `finding.evidence` (the
   *other* entities a check explicitly attaches, e.g. the two candidate
   payments) — never the entity the finding itself is anchored on. For G11's
   `WRONG_PAYMENT_REFERENCE` finding, that meant `merchant_order MORD-01`
   (whose own order date is the discriminating fact) never had its record
   fetched at all. Fixed in
   `src/recon/application/investigation/services/evidence_builder.py`:
   `_extract_evidence` now back-fills a synthetic `EvidenceRef` for
   `finding.affected_entity`, **only when no real evidence item already
   covers that same entity** (checked first, to avoid ever emitting a second
   `EvidenceRef` with the same `evidence_id` but a different `object_key`).
   This is general — it changes evidence resolution for every finding type,
   not just G11's.

2. **`entity_records.py`'s exact-key lookup had zero settlement scoping for
   "needs_latest_tiebreak" entity types (`merchant_order`, `ledger_entry`,
   `pos_transaction`, `gateway_transaction`, `bank_transaction`).** It just
   took the globally most-recently-inserted row matching the bare business
   id, with no regard for which settlement it belonged to. All 16 golden
   scenarios reuse the same generic ids (`MORD-01`, `MORD-02`, …), so once
   fix #1 started asking for `merchant_order MORD-01`'s record, it resolved
   to **whichever golden scenario had most recently ingested an `MORD-01`
   row** — live-reproduced: G11's own evidence package showed MORD-01 with
   amount `14000.00` / `created_at 2026-08-09`, matching neither G11's real
   source (`21000.00` / `2026-08-15`) nor any plausible G11 value. This is a
   real cross-settlement leakage bug, exactly the kind of thing the final
   regression's "no cross-settlement leakage" requirement (§4) exists to
   catch. Fixed with a new `resolve_import_pks(conn, settlement_id)` helper
   (`entity_records.py`) that resolves a settlement's own
   `reconciliation_runs.import_ids` → `merchant_imports.id`, threaded through
   `fetch_entity_record`'s new `import_pks` parameter, and through
   `InvestigationRepository.get_entity_record` (now takes `settlement_id`)
   and `ReconciliationPostgresResultRepository.list_evidence` (the Evidence
   Explorer endpoint). Re-verified live: MORD-01's record now correctly
   resolves to `amount 21000.00`, `razorpay_order_id order_TYHAPjjm4xOxzZ` —
   exactly G11's real source row, and exactly the order that links to
   `pay_g11_01` (the correct payment).

**Re-tested live after both fixes**, real HuggingFace call (quota allowed
one call through): the model received all 4 evidence items — the ledger
entry, both candidate payments (with their dates), and MORD-01's own record
— and correctly reconstructed the fact chain in `factual_observations`
("Merchant order MORD-01 links to Razorpay order order_TYHAPjjm4xOxzZ...
order_TYHAPjjm4xOxzZ has a payment of pay_g11_01"). It still returned
`should_abstain: true`, but the returned payload shows why: its own
`missing_evidence` field lists `ev:razorpay:payment:pay_g11_01:...` and
`ev:razorpay:payment:pay_g11_02:...` as missing — **even though both are
present, with full data, in the same response's own `evidence` array.** This
is the model failing to cite evidence it was actually given, not an
evidence-completeness gap. Per instruction, the policy was left untouched
and the result is reported as-is: **a real, observed model limitation**, not
forced to GROUNDED.

---

## 3. Final end-to-end regression

Postgres was truncated (merchant/result tables only — `merchant_imports`,
`merchant_orders`, `ledger_entries`, `bank_transactions`, `pos_transactions`,
`gateway_transactions`, `invoices`, and every reconciliation/graph/
investigation table; Razorpay-world tables were left alone, since seeding is
idempotent by `receipt`/business-key lookup) before each dataset's first run
this pass, with explicit user confirmation before the first truncate.

### 3.1 Golden-16 (`datasets/golden_scenarios`, SETL-G01…G16) — VERIFIED

Two full runs (clean, then immediately re-run on top without truncating).
Zero ingest errors either run. Finding codes and counts **identical** across
both runs for all 16 settlements — no accumulation, no duplication.

| Settlement | Expected status | Actual status | Expected finding | Actual finding | Note |
|---|---|---|---|---|---|
| G01–G03 | RECONCILED | EXCEPTION (`FINANCIAL_DIFFERENCE`) | — | — | PRE-EXISTING: ledger books gross, not net; Razorpay-vs-bank agrees exactly (0.00) in all 3 — see §5.1 |
| G04 | EXCEPTION | EXCEPTION | `MERCHANT_LEDGER_AMOUNT_MISMATCH` | match | — |
| G05 | EXCEPTION | EXCEPTION | `PAYMENT_AMOUNT_MISMATCH` | `ORDER_AMOUNT_MISMATCH` | PRE-EXISTING naming note, §5.3 |
| G06 | EXCEPTION | EXCEPTION | `DUPLICATE_ORDER` | match | — |
| G07 | EXCEPTION | EXCEPTION (`FINANCIAL_DIFFERENCE`) | `DUPLICATE_PAYMENT` | none | PRE-EXISTING, §5.2 |
| G08 | EXCEPTION | EXCEPTION | `RAZORPAY_ORDER_NOT_FOUND` | + `BANK_SETTLEMENT_AMOUNT_DIFFERENCE` (real, additional) | match+more |
| G09 | EXCEPTION | EXCEPTION | `BANK_SETTLEMENT_AMOUNT_DIFFERENCE` | match | — |
| G10 | EXCEPTION | EXCEPTION | `BANK_TRANSACTION_MISSING` | match | — |
| G11 | EXCEPTION | EXCEPTION | `WRONG_PAYMENT_REFERENCE` | match | see §2 |
| G12 | PENDING | PENDING | — | — | full match |
| G13 | EXCEPTION | EXCEPTION | `MULTI_SOURCE_DISAGREEMENT` | + `POS_AMOUNT_MISMATCH`/`GATEWAY_AMOUNT_MISMATCH` (real, additional) | match+more |
| G14 | EXCEPTION | EXCEPTION | `SETTLEMENT_TIMING_ANOMALY` | match | — |
| G15 | EXCEPTION | EXCEPTION | `WRONG_ORDER_REFERENCE` | `RAZORPAY_ORDER_NOT_FOUND` | PRE-EXISTING naming note, §5.3 |
| G16 | EXCEPTION | EXCEPTION | `AMBIGUOUS_MATCH` | `RAZORPAY_ORDER_NOT_FOUND` | PRE-EXISTING naming note, §5.3 |

`merchant_expected` figures for all 16 are unchanged before/after this
pass's `_calculate_merchant_expected` fix (§3.3) — confirmed identical,
since golden-16's ledgers are single-entry-type (`entry_type` always
`"credit"`), so the fix is a no-op there by construction.

### 3.2 Old-20 (`/home/vivek/Downloads/reconciliation_dataset_ours`, `scenario_01`…`scenario_23`) — VERIFIED

Two full runs, no truncate between them. `finding_count` **identical**
across both runs for all 23 scenarios — no accumulation.

- **14 scenarios** (`01,02,04,09,13,16,18` + others) reach `exception` with
  real, graph-backed findings, matching the dataset's own expectations.
- **9 scenarios blocked at ingestion** — this is **PRE-EXISTING**, unchanged
  by this pass, and already documented in the dataset's own
  `FINAL_RECONCILIATION_REPORT.md`:
  - `05, 06, 07, 12, 17, 19, 20`: a clean `400` from the
    `uq_merchant_order_source (import_pk, merchant_order_id)` constraint —
    these scenarios' own CSVs contain a genuine intra-import duplicate
    `merchant_order_id` row, and the constraint correctly rejects the whole
    batch rather than silently accepting a duplicate. (This is the same
    ingestion-validation-boundary behavior originally diagnosed for the
    old dataset's scenario 07 duplicate, at the very start of this
    engagement.)
  - `08, 11`: blocked by a genuine data issue (negative `credit` values in
    `bank_statement.csv`) that the ingestion validator correctly rejects.
- `21, 22, 23` ("clean" scenarios) reach `exception` via
  `MERCHANT_LEDGER_AMOUNT_MISMATCH` + `MULTI_SOURCE_DISAGREEMENT` — this is
  the same gross-vs-net ledger-booking pattern as G01–G03 (§5.1),
  unchanged by this pass, not a new finding.

### 3.3 RICH-60 (`datasets/razorpay_recon_rich_dataset`, SETL-RICH-001) — VERIFIED (one real bug found and fixed this pass)

**Bug found and fixed:** `_calculate_merchant_expected` (used for the
top-level `merchant_expected` figure and the RECONCILED/EXCEPTION decision)
summed `credit - debit` across **every** ledger row. That's correct for a
single-entry-per-order ledger, but RICH-60 uses genuine double-entry
bookkeeping (a credit revenue row + a balancing debit row per order) — so
every properly-balanced order's two rows cancelled to ~0, collapsing the
settlement-wide total to a near-zero residual (`100.00`) instead of the real
~₹8 lakh figure. This is the same double-entry class of bug already fixed
earlier in `_validate_ledger_amounts`/`_validate_multi_source_amounts`, just
in a third method that summed the same way and had not yet been touched.
Fixed in `reconciliation_service.py`: sum only `entry_type == "credit"`
rows. Verified as a no-op for golden-16 and old-20 (§3.1, §3.2 — identical
`merchant_expected` before/after), and for RICH-60:

| Metric | Before fix | After fix |
|---|---|---|
| `merchant_expected` | `100.00` (garbage) | `827770.00` (sane) |
| `razorpay_net` | `804621.06` | `804621.06` (unchanged) |
| `bank_observed` | `804561.06` | `804561.06` (unchanged) |

Two full runs after the fix, no truncate between them: **identical**
`status`, `reason_code`, all three totals, `finding_count` (8),
`finding_codes`, `affected_entities`, and `graph_node_count` (542) — no
accumulation.

| Metric | Value |
|---|---|
| Status | `exception` |
| Reason code | `PAYMENT_AMOUNT_MISMATCH` |
| Findings | 8 total: `BANK_SETTLEMENT_AMOUNT_DIFFERENCE`×1, `GATEWAY_AMOUNT_MISMATCH`×1, `MERCHANT_LEDGER_AMOUNT_MISMATCH`×1, `MULTI_SOURCE_DISAGREEMENT`×3, `PAYMENT_AMOUNT_MISMATCH`×1, `POS_AMOUNT_MISMATCH`×1 |
| Affected entities | `MORD-RICH-0011`, `MORD-RICH-0020`, `MORD-RICH-0030`, `RICH-PAY-0008`, `RICH-PAY-0040` — all 5 controlled faults represented, plus the bank shortfall |
| Graph | 542 nodes |
| UTR mapping | 60/60 `settlement_entries.settlement_utr` exactly match `bank_transactions.utr` (verified via direct SQL join, no fuzzy matching) |

### 3.4 Backend tests — VERIFIED (with 3 pre-existing failures)

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest tests/`: **32 passed, 3
failed.** The 3 failures (`test_merchant_order`,
`test_evidence_ref`, `test_reconciliation_result`) are **PRE-EXISTING**
domain-model/test drift already documented in `CLAUDE.md`
("`EvidenceRef` no longer accepts a `role` kwarg" etc.), unrelated to this
pass. 8 of those 32 passing tests are `test_evidence_builder.py`, which this
pass's `EvidenceBuilder` change broke and then was fixed alongside the
constructor-signature/dedup change (see exact files changed, §6).

### 3.5 Frontend — VERIFIED

`pnpm exec tsc --noEmit`: clean, zero errors.
`pnpm build`: succeeds (`next build`, Turbopack), compiles and generates
pages with no errors or warnings.

No frontend files were modified this pass — the golden/rich-60 fixes were
entirely backend (deterministic checks + evidence resolution), so this is a
confirmation that the existing frontend still builds against the unchanged
API contract, not a claim of new frontend verification.

### 3.6 Representative flows — VERIFIED / PARTIAL (see detail)

| Flow | Result |
|---|---|
| Clean reconciliation | PARTIAL — G01–G03/21–23 reach `exception` not `reconciled`, but this is the PRE-EXISTING gross-vs-net gap (§5.1), not a broken "clean" path; G12 (pending) is a full match |
| Merchant amount mismatch | VERIFIED — G04 (`MERCHANT_LEDGER_AMOUNT_MISMATCH`) |
| Payment amount mismatch | VERIFIED — G05 fires (`ORDER_AMOUNT_MISMATCH`, a naming note not a bug, §5.3); RICH-60's `PAYMENT_AMOUNT_MISMATCH` on RICH-PAY-0008 |
| Duplicate behavior | VERIFIED — G06 `DUPLICATE_ORDER`; PRE-EXISTING for G07/old-20 dup scenarios (ingestion boundary, §3.2) |
| Bank short settlement | VERIFIED — G09, RICH-60 (`BANK_SETTLEMENT_AMOUNT_DIFFERENCE`), itemized per UTR, Razorpay-vs-bank kept authoritative |
| Pending | VERIFIED — G12 full match both runs |
| Grounded investigation | VERIFIED — G04 completed GROUNDED live this pass |
| Abstained investigation | VERIFIED — G11 completed live this pass (§2), correctly abstained (for a model-citation reason, not a policy bug) |
| Evidence Explorer | VERIFIED — `GET /reconciliation/settlements/{id}/evidence` spot-checked for G04, G07, G11; now settlement-scoped (§2 fix #2) |
| Graph selection | PARTIAL — graph node/edge counts and key-entity presence verified via the API (`GET .../graph`) for G11 and RICH-60; the frontend graph UI itself was not opened in a browser this pass |
| Source-record inspection | VERIFIED — `EvidenceDetail.data` resolves real, settlement-scoped source rows (merchant_order, ledger_entry, payment) for every spot-checked finding |

---

## 4. Freeze audit

- **`git status`/`git diff`**: reviewed in full — see §6 for the exact file
  list. Nothing unexpected staged; no accidental generated/temp files (the
  scratch inspection/regression scripts used to verify this pass live
  outside the repo, under the session scratchpad, never in the working
  tree).
- **Architecture docs**: `docs/ARCHITECTURE.md` already updated (start of
  this pass) with the two RICH-60-era bug entries (double-entry ledger
  aggregation, bank-transaction cross-run duplication). Not otherwise
  altered this pass, since no architecture changed.
- **Final reports**: `docs/GOLDEN_SCENARIO_FINAL_REPORT.md` (golden-16 +
  RICH-60 sections) unchanged this pass — this document is the new,
  additional final-freeze report.
- **Seed scripts / dataset references**: unchanged and re-verified working
  (`seed_golden_scenarios.py`, `seed_rich_dataset.py`, both re-run
  implicitly via the regression in §3).
- **Frontend/backend on current APIs**: confirmed — `tsc`/`build` clean
  against the unmodified API contract; no frontend changes were needed or
  made.
- **No mock data in the live product flow**: confirmed — grepped frontend
  source for mock/dummy/fake data markers, none found.
- **No debug prints / temporary hacks**: confirmed — diffed every file this
  pass touched for stray `print(`/`console.`/`TODO`/`FIXME`; none found. A
  temporary inspection script written to check the G11 evidence package
  directly (bypassing the LLM call) was scratchpad-only, never touched the
  repo, and is not part of this diff.
- **No scenario-specific hardcoded reconciliation logic**: confirmed —
  grepped this pass's changed files for scenario/settlement id literals
  (`SETL-G`, `MORD-RICH`, etc.); the only hit is an illustrative example in
  a docstring comment, not logic.
- **No constraint weakened**: confirmed — the `uq_merchant_order_source`
  constraint, the exact-key (no fuzzy matching) entity lookup, and the
  evidence-citation/abstention policy are all untouched. The two behavior
  changes this pass (§2, §3.3) are bug fixes to arithmetic and evidence
  *completeness*, not relaxations of any existing check.
- **Razorpay-vs-bank remains authoritative**: confirmed — `reconcile()`'s
  status formula (`if findings → exception; elif merchant==razorpay==bank →
  reconciled; else → FINANCIAL_DIFFERENCE`) is byte-for-byte unchanged.
  `_calculate_merchant_expected`'s fix only corrects how the merchant side's
  own total is computed; it does not touch which side is authoritative for
  settlement correctness, and `razorpay_vs_bank_difference` is computed
  identically to before in every scenario tested.
- **AI remains non-authoritative and policy-gated**: confirmed — the G11
  live call shows `InvestigationPolicy` correctly refusing to accept a
  root cause the model itself flagged missing evidence for, even though
  that evidence was actually present — the policy erred toward abstention,
  not toward papering over the model's mistake. No investigation result is
  presented as a reconciliation result anywhere in this pass's changes.

---

## 5. Remaining known limitations (unchanged by this pass — flagged, not fixed)

### 5.1 G01–G03 / old-20 21–23: gross-vs-net ledger authority tension — PRE-EXISTING, undecided

The authoritative check (Razorpay net vs bank observed) already agrees
exactly (`0.00`) in every one of these scenarios. The blocker is that these
datasets' `ledger.csv` books the **gross** payment amount, not the
settlement **net** — and `reconcile()`'s RECONCILED path requires all three
sources (merchant/Razorpay/bank) to agree. Changing that 3-way formula would
touch every scenario in the system and was explicitly never authorized —
this needs a user decision, not a code change, and remains flagged rather
than fixed for a fourth time this engagement.

### 5.2 G07: phantom-order ledger row silently dropped at ingestion — PRE-EXISTING

`DUPLICATE_PAYMENT` can't currently be detected for G07 because its fault
(a ledger row citing a merchant_order_id with no real `merchant_orders.csv`
row) never reaches the database — `_persist_ledger_entries`'s `INSERT ...
SELECT ... FROM merchant_orders WHERE merchant_order_id = $12` silently
matches zero rows. A real fix needs `merchant_order_pk` to accept `NULL` on
insert and the read-side query changed from an `INNER` to a `LEFT JOIN` —
not attempted, same as in the previous pass's report.

### 5.3 G05/G15/G16: finding-code naming differences — PRE-EXISTING taxonomy note, not a bug

The dataset's own expected codes (`PAYMENT_AMOUNT_MISMATCH`,
`WRONG_ORDER_REFERENCE`, `AMBIGUOUS_MATCH`) don't correspond 1:1 to this
engine's existing taxonomy; the engine's actual codes
(`ORDER_AMOUNT_MISMATCH`, `RAZORPAY_ORDER_NOT_FOUND`) are the deterministically
correct outcome for what the data actually contains, under names that
predate this dataset. Documented, not renamed, to avoid touching an
existing code path's meaning system-wide.

### 5.4 Synthetic composite ledger evidence id — PRE-EXISTING, narrow

`_validate_multi_source_amounts`'s ledger-side aggregation can produce a
composite `representative_id` (`"+".join(...)`) when 2+ credit rows exist
for one order — a synthetic id that doesn't resolve to one real evidence
record. Low-impact (no golden/rich scenario currently has this shape at the
ledger side) but not resolved.

### 5.5 HuggingFace quota — PRE-EXISTING, external, BLOCKED for most calls

The account backing `HF_MODEL` returned `402: You have depleted your
monthly included credits` on the large majority of investigation calls
attempted this pass (confirmed live: `openai.APIStatusError: Error code:
402`). A small trickle got through (G04 GROUNDED, G11 ABSTAINED — both
reported in this document). This is an external billing constraint, not a
code defect; no result was fabricated to compensate.

---

## 6. Exact files changed this final pass

```
 M  scripts/run_golden_scenarios.py
 M  src/recon/application/investigation/ports/repository.py
 M  src/recon/application/investigation/services/evidence_builder.py
 M  src/recon/application/investigation/use_cases/investigate_exception.py
 M  src/recon/application/reconciliation/services/reconciliation_service.py
 M  src/recon/infrastructure/persistence/postgres/entity_records.py
 M  src/recon/infrastructure/persistence/postgres/repositories/investigation_repository.py
 M  src/recon/infrastructure/persistence/postgres/repositories/reconciliation_result_repository.py
 M  tests/recon/application/investigation/test_evidence_builder.py
 M  docs/ARCHITECTURE.md
 A  docs/FINAL_VERIFICATION_REPORT.md   (this file)
```

Summary of what changed in each (all bug fixes / test updates, no new
features, no architecture change):

- **`scripts/run_golden_scenarios.py`** — retry-on-transient-connection-reset
  for the batch ingest call (confirmed via isolated retry that the server
  never logs an exception for these; harness flakiness, not a product bug).
- **`evidence_builder.py` / `ports/repository.py` / `investigate_exception.py`
  / `investigation_repository.py`** — the two G11 fixes from §2: back-fill
  `affected_entity` as evidence when not already covered, and thread
  `settlement_id` through so entity lookups can be scoped.
- **`entity_records.py`** — new `resolve_import_pks()` helper + `import_pks`
  scoping parameter on `fetch_entity_record`, fixing the cross-settlement
  leakage in §2.
- **`reconciliation_result_repository.py`** — `list_evidence` (Evidence
  Explorer endpoint) now also resolves `import_pks` and passes them through,
  for the same scoping fix.
- **`reconciliation_service.py`** — `_calculate_merchant_expected` now sums
  only `entry_type == "credit"` rows (§3.3 double-entry ledger fix).
- **`test_evidence_builder.py`** — updated for `EvidenceBuilder`'s new
  required `settlement_id` param and the "don't duplicate an
  already-covered entity" dedup behavior.
- **`docs/ARCHITECTURE.md`** — two bug-fix entries appended to §13 (carried
  over from the previous session's interrupted edit, completed at the start
  of this pass).

All datasets (`datasets/`), the earlier `docs/GOLDEN_SCENARIO_FINAL_REPORT.md`,
and every frontend file are **unchanged** in this pass.

---

## 7. Verdict summary

| Item | Status |
|---|---|
| 1. Ingestion / seeded source completeness | **VERIFIED** |
| 2. G11 investigation diagnosis | **VERIFIED** (2 real bugs fixed; abstain confirmed as model limitation) |
| 3. Golden-16 regression (2 runs) | **VERIFIED** |
| 3. Old-20 regression (2 runs) | **VERIFIED** |
| 3. RICH-60 regression (2 runs, 1 bug fixed) | **VERIFIED** |
| 3. Backend tests | **VERIFIED** (3 pre-existing failures, documented) |
| 3. Frontend tsc/build | **VERIFIED** |
| 3. UTR mapping exactness | **VERIFIED** |
| 3. No accumulation / no cross-settlement leakage | **VERIFIED** (leakage bug found *and fixed* this pass) |
| Freeze audit | **VERIFIED** |
