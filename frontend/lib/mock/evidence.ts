import type { Evidence } from '@/lib/types/domain'
export const evidence: Evidence[] = [
 {id:'EV-8831',source:'Razorpay',entityType:'Settlement',entityId:'SET_9D81K2',amount:2486320,timestamp:'Aug 24, 14:31',findingId:'FND-0047',description:'Settlement net amount'},
 {id:'EV-8832',source:'Bank',entityType:'Bank Transaction',entityId:'BNK-88291',amount:2479810,timestamp:'Aug 24, 14:32',findingId:'FND-0047',description:'Credit received'},
 {id:'EV-8833',source:'Razorpay',entityType:'Settlement Entry',entityId:'SE-10933',amount:4200,timestamp:'Aug 24, 14:28',findingId:'FND-0046',description:'Unmatched settlement entry'},
 {id:'EV-8834',source:'Merchant',entityType:'Ledger Entry',entityId:'LED-7120',amount:6510,timestamp:'Aug 24, 14:33',findingId:'FND-0047',description:'Expected settlement ledger'},
]
export const listEvidence = async (id: string) => evidence
export const evidenceForFinding = async (id: string) => evidence.filter((item) => item.findingId === id)
