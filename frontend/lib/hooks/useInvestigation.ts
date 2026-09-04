import { useQuery } from '@tanstack/react-query'
import { getInvestigation } from '@/lib/api/investigations'
import { queryKeys } from '@/lib/api/query-keys'
import { shouldRetry } from './retry'

/** A persisted AI investigation result, by investigation ID. */
export function useInvestigation(investigationId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.investigation(investigationId ?? ''),
    queryFn: ({ signal }) => getInvestigation(investigationId as string, { signal }),
    enabled: Boolean(investigationId),
    retry: shouldRetry,
  })
}
