'use client'

import { FileText } from 'lucide-react'
import type { Evidence } from '@/lib/types/domain'

const GROUPS = ['RAZORPAY', 'MERCHANT', 'BANK']

/** Groups backend-derived evidence records by source system, as in the original design. */
export function SourceEvidence({ items }: { items: Evidence[] }) {
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
            {groupItems.map((e) => (
              <div className="source-item" key={e.evidence_id}>
                <FileText size={14} />
                <div>
                  <b>{e.entity_type}</b>
                  <span className="mono">{e.entity_id}</span>
                </div>
                <strong>{e.reason}</strong>
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}
