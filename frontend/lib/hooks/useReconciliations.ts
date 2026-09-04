import { useQuery } from '@tanstack/react-query'
import { listReconciliations } from '@/lib/api/reconciliations'
import { queryKeys } from '@/lib/api/query-keys'
import { shouldRetry } from './retry'

/** All reconciliation runs, newest first — backs the dashboard/list views. */
export function useReconciliations() {
  return useQuery({
    queryKey: queryKeys.reconciliations(),
    queryFn: ({ signal }) => listReconciliations({ signal }),
    retry: shouldRetry,
  })
}
