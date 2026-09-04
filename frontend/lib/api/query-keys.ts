/** Centralized TanStack Query keys — keep cache invalidation consistent. */
export const queryKeys = {
  reconciliations: () => ['reconciliations'] as const,
  reconciliation: (settlementId: string) => ['reconciliations', settlementId] as const,
  findings: (settlementId: string) => ['reconciliations', settlementId, 'findings'] as const,
  finding: (settlementId: string, findingId: string) =>
    ['reconciliations', settlementId, 'findings', findingId] as const,
  evidence: (settlementId: string) => ['reconciliations', settlementId, 'evidence'] as const,
  graph: (settlementId: string) => ['reconciliations', settlementId, 'graph'] as const,
  investigation: (investigationId: string) => ['investigations', investigationId] as const,
}
