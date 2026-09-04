import { apiGet } from './client'
import type { Graph } from '@/lib/types/domain'

/** GET /reconciliation/settlements/{settlement_id}/graph */
export function getGraph(settlementId: string, options?: { signal?: AbortSignal }): Promise<Graph> {
  return apiGet<Graph>(`/reconciliation/settlements/${encodeURIComponent(settlementId)}/graph`, options)
}
