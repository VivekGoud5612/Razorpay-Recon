import { useQuery } from '@tanstack/react-query'
import { getFinding, listFindings } from '@/lib/api/findings'
import { queryKeys } from '@/lib/api/query-keys'
import { shouldRetry } from './retry'

/** All findings for a reconciliation's settlement. */
export function useFindings(settlementId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.findings(settlementId ?? ''),
    queryFn: ({ signal }) => listFindings(settlementId as string, { signal }),
    enabled: Boolean(settlementId),
    retry: shouldRetry,
  })
}

/** A single finding, with its evidence references, by finding ID. */
export function useFinding(settlementId: string | undefined, findingId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.finding(settlementId ?? '', findingId ?? ''),
    queryFn: ({ signal }) => getFinding(settlementId as string, findingId as string, { signal }),
    enabled: Boolean(settlementId) && Boolean(findingId),
    retry: shouldRetry,
  })
}
