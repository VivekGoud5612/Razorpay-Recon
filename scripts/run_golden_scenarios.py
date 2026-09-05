"""
Baseline runner for the 16 golden scenarios, against whatever the engine
currently does -- no fixes applied here. For each scenario (after
scripts/seed_golden_scenarios.py has run): ingest merchant_seeded/ via the
real POST /ingestion/merchant/batch, run POST /reconciliation/settlements,
pull findings, and (if status == exception and findings exist) run
POST /investigation/exceptions on all of them. Writes
datasets/golden_scenarios/golden_baseline_report.json and prints a summary
table comparing against each scenario's own answers.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

DATASET_ROOT = Path(__file__).resolve().parent.parent / "datasets" / "golden_scenarios"
API_BASE = os.environ.get("API_BASE", "http://localhost:8000")


def run_scenario(client: httpx.Client, scenario_dir: Path) -> dict:
    ans = json.loads((scenario_dir / "answers.json").read_text())
    settlement_id = ans["scenario_id"]
    seeded_dir = scenario_dir / "merchant_seeded"

    # Must match the real application's canonical submission order (see
    # new-reconciliation.tsx's SOURCE_SLOTS / run_dataset_scenarios.py's
    # FILES), NOT alphabetical -- merchant_orders.csv has to land before
    # ledger.csv within the same batch, because _persist_ledger_entries
    # resolves each ledger row's merchant_order_pk via "the most recently
    # inserted merchant_order row with this id" (needed for idempotent
    # re-ingestion of the same order). If ledger.csv is persisted first,
    # that resolves to whatever stale row happened to exist from a
    # completely unrelated earlier import instead of the one just
    # submitted alongside it.
    CANONICAL_ORDER = ["merchant_orders.csv", "ledger.csv", "bank_statement.csv", "pos.csv", "other_gateway.csv"]
    files = [
        ("files", (name, (seeded_dir / name).read_bytes(), "text/csv"))
        for name in CANONICAL_ORDER
        if (seeded_dir / name).exists()
    ] if seeded_dir.exists() else []

    ingest_error = None
    import_ids: list[str] = []
    if files:
        # Rapid back-to-back multipart uploads against local uvicorn
        # occasionally hit a transient ECONNRESET on the client socket
        # (confirmed via isolated retry -- the server never logs an
        # exception for these; each request succeeds when re-sent alone).
        # Retry a couple of times before treating it as a real ingest
        # failure, so harness flakiness doesn't masquerade as a regression.
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = client.post(f"{API_BASE}/ingestion/merchant/batch", files=files, timeout=60)
                resp.raise_for_status()
                import_ids = [r["import_id"] for r in resp.json()]
                last_exc = None
                break
            except httpx.HTTPStatusError as exc:
                ingest_error = f"{exc.response.status_code}: {exc.response.text[:300]}"
                last_exc = None
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
        if last_exc is not None:
            ingest_error = str(last_exc)[:300]

    reconcile_error = None
    rec: dict = {}
    if not ingest_error:
        try:
            resp = client.post(
                f"{API_BASE}/reconciliation/settlements",
                json={"settlement_id": settlement_id, "import_ids": import_ids},
                timeout=60,
            )
            resp.raise_for_status()
            rec = resp.json()
        except httpx.HTTPStatusError as exc:
            reconcile_error = f"{exc.response.status_code}: {exc.response.text[:300]}"
        except Exception as exc:  # noqa: BLE001
            reconcile_error = str(exc)[:300]

    findings = rec.get("findings", [])
    finding_codes = sorted({f["code"] for f in findings})

    investigation = None
    investigation_error = None
    if not reconcile_error and rec.get("status") == "exception" and findings:
        finding_ids = [f["finding_id"] for f in findings]
        try:
            resp = client.post(
                f"{API_BASE}/investigation/exceptions",
                json={"settlement_id": settlement_id, "finding_ids": finding_ids},
                timeout=90,
            )
            resp.raise_for_status()
            inv = resp.json()
            investigation = {
                "should_abstain": inv["should_abstain"],
                "abstain_reason": inv["abstain_reason"],
                "root_cause": inv["root_cause"],
                "hypothesis_count": len(inv["hypotheses"]),
            }
        except httpx.HTTPStatusError as exc:
            investigation_error = f"{exc.response.status_code}: {exc.response.text[:300]}"
        except Exception as exc:  # noqa: BLE001
            investigation_error = str(exc)[:300]

    actual_investigation_mode = "NOT_RUN"
    if investigation is not None:
        actual_investigation_mode = "ABSTAINED" if investigation["should_abstain"] else "GROUNDED"
    elif rec.get("status") in ("reconciled", "pending"):
        actual_investigation_mode = "NOT_REQUIRED"

    expected_status = ans["expected_status"]
    actual_status = (rec.get("status") or "ERROR").upper()
    expected_findings = sorted({f["code"] for f in ans.get("expected_findings", [])})

    status_match = expected_status == actual_status
    finding_match = (not expected_findings and not finding_codes) or bool(set(expected_findings) & set(finding_codes))
    inv_match = ans["investigation_mode"] == actual_investigation_mode

    return {
        "scenario": scenario_dir.name,
        "settlement_id": settlement_id,
        "ingest_error": ingest_error,
        "reconcile_error": reconcile_error,
        "expected_status": expected_status,
        "actual_status": actual_status,
        "reason_code": rec.get("reason_code"),
        "merchant_expected": rec.get("merchant_expected"),
        "razorpay_net": rec.get("razorpay_net"),
        "bank_observed": rec.get("bank_observed"),
        "expected_finding_codes": expected_findings,
        "actual_finding_codes": finding_codes,
        "finding_count": len(findings),
        "expected_investigation_mode": ans["investigation_mode"],
        "actual_investigation_mode": actual_investigation_mode,
        "investigation": investigation,
        "investigation_error": investigation_error,
        "status_match": status_match,
        "finding_match": finding_match,
        "investigation_match": inv_match,
        "overall_match": status_match and finding_match and inv_match,
    }


def main() -> None:
    only = sys.argv[1:] or None
    scenario_dirs = sorted(p for p in DATASET_ROOT.glob("scenario_g*") if p.is_dir())
    if only:
        scenario_dirs = [p for p in scenario_dirs if any(o in p.name for o in only)]

    results = []
    with httpx.Client() as client:
        for d in scenario_dirs:
            print(f"--- running {d.name} ---", flush=True)
            r = run_scenario(client, d)
            print(json.dumps(r, default=str), flush=True)
            results.append(r)

    (DATASET_ROOT / "golden_baseline_report.json").write_text(json.dumps(results, indent=2, default=str))

    print("\n=== BASELINE SUMMARY ===")
    print(f"{'Scenario':10s} {'Exp.Status':12s} {'Act.Status':10s} {'Exp.Finding':32s} {'Act.Finding':32s} {'Exp.Inv':12s} {'Act.Inv':12s} Match")
    for r in results:
        exp_f = ",".join(r["expected_finding_codes"]) or "-"
        act_f = ",".join(r["actual_finding_codes"]) or "-"
        print(
            f"{r['settlement_id']:10s} {r['expected_status']:12s} {r['actual_status']:10s} "
            f"{exp_f:32s} {act_f:32s} {r['expected_investigation_mode']:12s} {r['actual_investigation_mode']:12s} "
            f"{'MATCH' if r['overall_match'] else 'MISMATCH'}"
        )


if __name__ == "__main__":
    main()
