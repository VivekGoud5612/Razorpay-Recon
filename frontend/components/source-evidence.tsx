'use client'

import { FileText, GitBranch } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Evidence } from '@/lib/types/domain'

const GROUPS = ['RAZORPAY', 'MERCHANT', 'BANK']

/**
 * Groups backend-derived evidence records by source system, as in the
 * original design. When `linkedFindings` + `settlementId` are supplied
 * (the Evidence Explorer's cross-referenced view), each item also shows
 * the full chain the product is meant to make visible:
 *
 *   finding -> evidence -> source -> entity -> underlying record -> graph
 *
 * Finding links come from `linkedFindings` (findings already carry their
 * own evidence embedded). The underlying record is `evidence.data`,
 * fetched by the backend via an exact entity_type/entity_id lookup -- shown
 * inline, not linked out, since it is not a separate page. The graph
 * connection is a deep link that pre-selects this evidence's node.
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
              const recordFields = e.data ? Object.entries(e.data) : []
              const recordNotFetchedHere = e.data === undefined
              const nodeId = `${e.source}:${e.entity_type}:${e.entity_id}`
              return (
                <div className="source-item evidence-chain" key={e.evidence_id}>
                  <FileText size={14} />
                  <div>
                    <div className="evidence-chain-head">
                      <b>{e.entity_type}</b>
                      <span className="mono">{e.entity_id}</span>
                    </div>
                    {settlementId && findings.length > 0 && (
                      <span className="evidence-finding-links">
                        cited by{' '}
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
                    <span className="evidence-reason">{e.reason}</span>

                    <div className="evidence-chain-actions">
                      {recordFields.length > 0 ? (
                        <details className="evidence-record">
                          <summary>View source record ({recordFields.length} fields)</summary>
                          <dl className="evidence-record-fields">
                            {recordFields.map(([key, value]) => (
                              <div key={key}>
                                <dt>{key}</dt>
                                <dd className="mono">{value === null ? '—' : String(value)}</dd>
                              </div>
                            ))}
                          </dl>
                        </details>
                      ) : recordNotFetchedHere ? (
                        settlementId ? (
                          <Link
                            className="text-link"
                            to={`/reconciliations/${settlementId}/evidence`}
                          >
                            View source record in Evidence Explorer
                          </Link>
                        ) : (
                          <span className="evidence-no-record">Source record not loaded here</span>
                        )
                      ) : (
                        <span className="evidence-no-record">
                          {e.object_key
                            ? 'No persisted record for this entity (source file only)'
                            : 'No underlying source record available'}
                        </span>
                      )}
                      {e.object_key && (
                        <span className="evidence-object-key mono" title={e.object_key}>
                          {e.object_key.split('/').pop()}
                        </span>
                      )}
                      {settlementId && (
                        <Link
                          className="text-link evidence-graph-link"
                          to={`/reconciliations/${settlementId}/graph?focus=${encodeURIComponent(nodeId)}`}
                        >
                          <GitBranch size={12} /> View in graph
                        </Link>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}
