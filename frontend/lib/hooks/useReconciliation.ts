import { useQuery } from '@tanstack/react-query'
import { getReconciliation } from '@/lib/api/reconciliations'
import { queryKeys } from '@/lib/api/query-keys'
import { shouldRetry } from './retry'

/** A single reconciliation run's status/KPIs, by settlement ID. */
export function useReconciliation(settlementId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.reconciliation(settlementId ?? ''),
    queryFn: ({ signal }) => getReconciliation(settlementId as string, { signal }),
    enabled: Boolean(settlementId),
    retry: shouldRetry,
  })
}
