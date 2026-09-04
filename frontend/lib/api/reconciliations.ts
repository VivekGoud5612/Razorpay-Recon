import { apiGet, apiPostJson } from './client'
import type { ReconcileSettlementRequest, ReconcileSettlementResponse, Reconciliation } from '@/lib/types/domain'

/** GET /reconciliation/settlements */
export function listReconciliations(options?: { signal?: AbortSignal }): Promise<Reconciliation[]> {
  return apiGet<Reconciliation[]>('/reconciliation/settlements', options)
}

/** GET /reconciliation/settlements/{settlement_id} */
export function getReconciliation(settlementId: string, options?: { signal?: AbortSignal }): Promise<Reconciliation> {
  return apiGet<Reconciliation>(`/reconciliation/settlements/${encodeURIComponent(settlementId)}`, options)
}

/**
 * POST /reconciliation/settlements — runs deterministic reconciliation for
 * a settlement against the given merchant import IDs and persists the run.
 */
export function runReconciliation(request: ReconcileSettlementRequest): Promise<ReconcileSettlementResponse> {
  return apiPostJson<ReconcileSettlementResponse>('/reconciliation/settlements', request)
}
