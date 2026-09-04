import { apiGet } from './client'
import type { Finding } from '@/lib/types/domain'

/** GET /reconciliation/settlements/{settlement_id}/findings */
export function listFindings(settlementId: string, options?: { signal?: AbortSignal }): Promise<Finding[]> {
  return apiGet<Finding[]>(`/reconciliation/settlements/${encodeURIComponent(settlementId)}/findings`, options)
}

/** GET /reconciliation/settlements/{settlement_id}/findings/{finding_id} */
export function getFinding(settlementId: string, findingId: string, options?: { signal?: AbortSignal }): Promise<Finding> {
  return apiGet<Finding>(
    `/reconciliation/settlements/${encodeURIComponent(settlementId)}/findings/${encodeURIComponent(findingId)}`,
    options,
  )
}
