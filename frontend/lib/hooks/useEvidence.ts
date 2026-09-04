import { useQuery } from '@tanstack/react-query'
import { listEvidence } from '@/lib/api/evidence'
import { queryKeys } from '@/lib/api/query-keys'
import { shouldRetry } from './retry'

/** All evidence records collected for a reconciliation's settlement. */
export function useEvidence(settlementId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.evidence(settlementId ?? ''),
    queryFn: ({ signal }) => listEvidence(settlementId as string, { signal }),
    enabled: Boolean(settlementId),
    retry: shouldRetry,
  })
}
