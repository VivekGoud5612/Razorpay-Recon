import { apiGet, apiPostJson } from './client'
import type { InvestigateExceptionRequest, Investigation } from '@/lib/types/domain'

/**
 * POST /investigation/exceptions — runs the AI investigation for the given
 * findings and persists the result (the backend assigns investigation_id).
 */
export function startInvestigation(request: InvestigateExceptionRequest): Promise<Investigation> {
  return apiPostJson<Investigation>('/investigation/exceptions', request)
}

/** GET /investigation/{investigation_id} */
export function getInvestigation(investigationId: string, options?: { signal?: AbortSignal }): Promise<Investigation> {
  return apiGet<Investigation>(`/investigation/${encodeURIComponent(investigationId)}`, options)
}
