import type { Reconciliation } from '@/lib/types/domain'

export const reconciliations: Reconciliation[] = [
  { id: 'REC-2024-0842', settlementId: 'SET_9D81K2', createdAt: '2024-08-24T14:32:00Z', status: 'needs_review', razorpayNet: 2486320, bankReceived: 2479810, merchantExpected: 2486320, matched: 1248, exceptions: 7, pending: 23 },
  { id: 'REC-2024-0841', settlementId: 'SET_9D80J9', createdAt: '2024-08-23T11:08:00Z', status: 'completed', razorpayNet: 1854200, bankReceived: 1854200, merchantExpected: 1854200, matched: 982, exceptions: 0, pending: 0 },
  { id: 'REC-2024-0840', settlementId: 'SET_9D7FQ4', createdAt: '2024-08-22T16:45:00Z', status: 'processing', razorpayNet: 3128400, bankReceived: 0, merchantExpected: 3128400, matched: 0, exceptions: 0, pending: 1456 },
]
export const getReconciliation = (id: string) => reconciliations.find((item) => item.id === id) ?? reconciliations[0]
export const listReconciliations = async () => reconciliations
export const fetchReconciliation = async (id: string) => getReconciliation(id)
export const runReconciliation = async (id: string) => getReconciliation(id)
export const createReconciliation = async () => reconciliations[0]
export const uploadReconciliationFiles = async (id: string, files: File[]) => ({ id, files: files.map((file) => file.name) })
export const ingestReconciliation = async (id: string) => getReconciliation(id)
