import { apiGet } from './client'
import type { Evidence } from '@/lib/types/domain'

/** GET /reconciliation/settlements/{settlement_id}/evidence */
export function listEvidence(settlementId: string, options?: { signal?: AbortSignal }): Promise<Evidence[]> {
  return apiGet<Evidence[]>(`/reconciliation/settlements/${encodeURIComponent(settlementId)}/evidence`, options)
}
