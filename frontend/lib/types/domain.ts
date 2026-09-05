// Types mirror the actual FastAPI response/request DTOs in
// src/recon/application/**/dto/*.py — see frontend/README.md for how these
// map to backend routes. Do not add fields the backend doesn't return.

// ---------------------------------------------------------------------------
// Reconciliation
// ---------------------------------------------------------------------------

export type ReconciliationStatus = 'pending' | 'reconciled' | 'exception'

/** GET /reconciliation/settlements, GET /reconciliation/settlements/{id} */
export interface Reconciliation {
  settlement_id: string
  status: ReconciliationStatus
  reason_code: string
  merchant_expected: string
  razorpay_net: string
  bank_observed: string
  merchant_vs_razorpay_difference: string
  razorpay_vs_bank_difference: string
  import_ids: string[]
  created_at: string
  updated_at: string
}

/** POST /reconciliation/settlements request body */
export interface ReconcileSettlementRequest {
  settlement_id: string
  import_ids: string[]
}

/** POST /reconciliation/settlements response (includes findings/evidence inline) */
export interface ReconcileSettlementResponse {
  settlement_id: string
  merchant_expected: string
  razorpay_net: string
  bank_observed: string
  merchant_vs_razorpay_difference: string
  razorpay_vs_bank_difference: string
  status: ReconciliationStatus
  reason_code: string
  findings: Finding[]
  evidence: Evidence[]
}

// ---------------------------------------------------------------------------
// Findings / Evidence
// ---------------------------------------------------------------------------

export type Severity = 'error' | 'warning'

export interface EntityReference {
  source: string
  entity_type: string
  entity_id: string
}

/** GET /reconciliation/settlements/{id}/findings, .../findings/{finding_id} */
export interface Finding {
  finding_id: string
  code: string
  severity: Severity
  affected_entity: EntityReference
  message: string
  evidence: Evidence[]
}

/** GET /reconciliation/settlements/{id}/evidence */
export interface Evidence {
  evidence_id: string
  source: string
  entity_type: string
  entity_id: string
  reason: string
  object_key: string | null
  /** The persisted source record this evidence item points to (exact
   * entity_type/entity_id lookup). Only GET .../evidence populates this;
   * evidence embedded in a Finding does not carry it, hence optional --
   * `undefined` means "not fetched here" (see Evidence Explorer instead),
   * `null` means "fetched, and no backing record exists". */
  data?: Record<string, unknown> | null
}

// ---------------------------------------------------------------------------
// Graph
// ---------------------------------------------------------------------------

export interface GraphNode {
  node_id: string
  source: string
  entity_type: string
  entity_id: string
}

export interface GraphEdge {
  edge_id: string
  source_node_id: string
  target_node_id: string
  edge_type: string
  source: string
  confidence: number
}

/** GET /reconciliation/settlements/{id}/graph */
export interface Graph {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

// ---------------------------------------------------------------------------
// Investigation
// ---------------------------------------------------------------------------

export interface Hypothesis {
  hypothesis_id: string
  statement: string
  supporting_evidence_ids: string[]
  confidence: number
}

export interface RootCause {
  hypothesis_id: string
  confidence: number
}

export interface InvestigationEvidence {
  evidence_id: string
  source: string
  entity_type: string
  entity_id: string
  reason: string
  data: Record<string, unknown>
  object_key: string | null
}

/** POST /investigation/exceptions request body */
export interface InvestigateExceptionRequest {
  settlement_id: string
  finding_ids: string[]
}

/** POST /investigation/exceptions response, GET /investigation/{id} */
export interface Investigation {
  investigation_id: string
  settlement_id: string
  finding_ids: string[]
  status: string
  factual_observations: string[]
  hypotheses: Hypothesis[]
  root_cause: RootCause | null
  evidence: InvestigationEvidence[]
  missing_evidence: string[]
  should_abstain: boolean
  abstain_reason: string | null
  created_at: string | null
}

// ---------------------------------------------------------------------------
// Ingestion
// ---------------------------------------------------------------------------

/**
 * Fixed source_id values seeded in the `sources` table
 * (src/recon/infrastructure/persistence/postgres/schema.sql) — the only
 * merchant_source_id values the ingestion endpoint accepts.
 */
export type MerchantSourceId =
  | 'merchant_orders'
  | 'merchant_ledger'
  | 'merchant_bank'
  | 'merchant_pos'
  | 'merchant_gateway'

/** POST /ingestion/merchant response */
export interface IngestMerchantSourceResponse {
  import_id: string
  merchant_source_id: string
  status: string
  records_ingested: number
}
