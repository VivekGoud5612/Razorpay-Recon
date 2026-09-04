import { useQuery } from '@tanstack/react-query'
import { getGraph } from '@/lib/api/graph'
import { queryKeys } from '@/lib/api/query-keys'
import { shouldRetry } from './retry'

/** The evidence graph (nodes + edges) for a reconciliation's settlement. */
export function useGraph(settlementId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.graph(settlementId ?? ''),
    queryFn: ({ signal }) => getGraph(settlementId as string, { signal }),
    enabled: Boolean(settlementId),
    retry: shouldRetry,
  })
}
