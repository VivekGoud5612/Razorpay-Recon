import type { Finding } from '@/lib/types/domain'
export const findings: Finding[] = [
 { id:'FND-0047', reconciliationId:'REC-2024-0842', code:'BANK_AMOUNT_MISMATCH', severity:'critical', status:'open', entityType:'Bank Transaction', entityId:'BNK-88291', impact:6510, explanation:'Bank received amount is lower than the Razorpay settlement net by ₹6,510.', razorpayNet:2486320, bankReceived:2479810, merchantExpected:2486320, variance:6510 },
 { id:'FND-0046', reconciliationId:'REC-2024-0842', code:'MISSING_SETTLEMENT_ENTRY', severity:'high', status:'investigating', entityType:'Settlement Entry', entityId:'SE-10933', impact:4200, explanation:'A settlement entry has no corresponding bank transaction.', razorpayNet:4200, bankReceived:0, merchantExpected:4200, variance:4200 },
 { id:'FND-0045', reconciliationId:'REC-2024-0842', code:'REFUND_TIMING_VARIANCE', severity:'medium', status:'open', entityType:'Refund', entityId:'RF-33109', impact:1800, explanation:'Refund was posted after the settlement cut-off window.', razorpayNet:1800, bankReceived:0, merchantExpected:1800, variance:1800 },
]
export const listFindings = async (id: string) => findings.filter((finding) => finding.reconciliationId === id)
export const getFinding = (id: string) => findings.find((finding) => finding.id === id) ?? findings[0]
