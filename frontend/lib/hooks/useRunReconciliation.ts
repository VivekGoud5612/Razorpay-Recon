import { useMutation, useQueryClient } from '@tanstack/react-query'
import { runReconciliation } from '@/lib/api/reconciliations'
import { queryKeys } from '@/lib/api/query-keys'
import type { ReconcileSettlementRequest } from '@/lib/types/domain'

/**
 * Runs (or re-runs) deterministic reconciliation for a settlement. On
 * success, invalidates the reconciliation detail/list, findings, evidence
 * and graph for that settlement so dependent views refetch the persisted
 * result instead of showing a stale pre-run state.
 */
export function useRunReconciliation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: ReconcileSettlementRequest) => runReconciliation(request),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.reconciliation(response.settlement_id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.reconciliations() })
      queryClient.invalidateQueries({ queryKey: queryKeys.findings(response.settlement_id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.evidence(response.settlement_id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.graph(response.settlement_id) })
    },
  })
}
