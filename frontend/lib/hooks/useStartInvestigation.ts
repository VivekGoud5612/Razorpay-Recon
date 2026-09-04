import { useMutation, useQueryClient } from '@tanstack/react-query'
import { startInvestigation } from '@/lib/api/investigations'
import { queryKeys } from '@/lib/api/query-keys'
import type { InvestigateExceptionRequest } from '@/lib/types/domain'

/**
 * Starts an AI investigation for the given findings. On success, seeds the
 * investigation-detail cache under its assigned investigation_id so
 * navigating straight to /investigations/:id renders instantly.
 */
export function useStartInvestigation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: InvestigateExceptionRequest) => startInvestigation(request),
    onSuccess: (investigation) => {
      queryClient.setQueryData(queryKeys.investigation(investigation.investigation_id), investigation)
    },
  })
}
