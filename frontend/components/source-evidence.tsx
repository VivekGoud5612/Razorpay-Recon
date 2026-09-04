'use client'

import { FileText } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Evidence } from '@/lib/types/domain'

const GROUPS = ['RAZORPAY', 'MERCHANT', 'BANK']

/**
 * Groups backend-derived evidence records by source system, as in the
 * original design. When `linkedFindings` + `settlementId` are supplied
 * (the Evidence Explorer's cross-referenced view), each item also shows
 * which finding(s) actually cite it, linking back to that finding — the
 * evidence list otherwise reads as a flat, disconnected dump.
 */
export function SourceEvidence({
  items,
  linkedFindings,
  settlementId,
}: {
  items: Evidence[]
  linkedFindings?: Record<string, { finding_id: string; code: string }[]>
  settlementId?: string
}) {
  return (
    <div className="source-groups">
      {GROUPS.map((source) => {
        const groupItems = items.filter((e) => e.source.toUpperCase().includes(source))
        return (
          <div className="source-group" key={source}>
            <div className="source-heading">
              <span className={`source-marker ${source.toLowerCase()}`} />
              {source}
              <span>{groupItems.length}</span>
            </div>
            {groupItems.map((e) => {
              const findings = linkedFindings?.[e.evidence_id] ?? []
              return (
                <div className="source-item" key={e.evidence_id}>
                  <FileText size={14} />
                  <div>
                    <b>{e.entity_type}</b>
                    <span className="mono">{e.entity_id}</span>
                    {settlementId && findings.length > 0 && (
                      <span className="evidence-finding-links">
                        {findings.map((f) => (
                          <Link
                            key={f.finding_id}
                            className="text-link"
                            to={`/reconciliations/${settlementId}/findings/${encodeURIComponent(f.finding_id)}`}
                          >
                            {f.code}
                          </Link>
                        ))}
                      </span>
                    )}
                  </div>
                  <strong>{e.reason}</strong>
                </div>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}
