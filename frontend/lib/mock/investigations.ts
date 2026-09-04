import type { Investigation } from '@/lib/types/domain'
import { evidence } from './evidence'
export const investigations: Investigation[] = [{id:'INV-204',reconciliationId:'REC-2024-0842',findingId:'FND-0047',status:'complete',rootCause:'Settlement timing discrepancy',confidence:'Likely',reasoning:'The bank credit is lower than the Razorpay settlement net. Evidence suggests an adjustment was applied after the settlement file was generated.',recommendation:'Request bank transaction detail for BNK-88291 and verify the adjustment against the next settlement cycle.',supporting:evidence.slice(0,3),contradicting:[]}]
export const getInvestigation = async (id: string) => investigations.find((item) => item.id === id) ?? investigations[0]
export const createInvestigation = async (id: string, findingId: string) => investigations[0]
