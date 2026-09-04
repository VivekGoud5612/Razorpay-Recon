'use client'

import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowUpRight, Search } from 'lucide-react'
import { Shell, Title } from '@/components/shell'
import { LoadingState, ErrorState, EmptyState } from '@/components/async-state'
import { SourceEvidence } from '@/components/source-evidence'
import { useEvidence } from '@/lib/hooks/useEvidence'
import { useFindings } from '@/lib/hooks/useFindings'

export function EvidenceExplorer() {
  const { id = '' } = useParams()
  const evidenceQuery = useEvidence(id)
  const findingsQuery = useFindings(id)
  const [query, setQuery] = useState('')

  // Evidence on its own is just a flat dump of records — cross-reference
  // back to whichever finding(s) actually cite each evidence_id (findings
  // already carry their own evidence embedded) so the explorer can show
  // finding -> evidence -> source -> entity, not a disconnected list.
  const linkedFindings = useMemo(() => {
    const map: Record<string, { finding_id: string; code: string }[]> = {}
    for (const finding of findingsQuery.data ?? []) {
      for (const ev of finding.evidence) {
        ;(map[ev.evidence_id] ??= []).push({ finding_id: finding.finding_id, code: finding.code })
      }
    }
    return map
  }, [findingsQuery.data])

  const items = useMemo(() => {
    const all = evidenceQuery.data ?? []
    if (!query) return all
    const q = query.toLowerCase()
    return all.filter((e) => JSON.stringify(e).toLowerCase().includes(q))
  }, [evidenceQuery.data, query])

  return (
    <Shell>
      <main>
        <Title
          eyebrow={`RECONCILIATION / ${id}`}
          title="Evidence explorer"
          action={
            <Link className="button" to={`/reconciliations/${id}/graph`}>
              Open case graph <ArrowUpRight size={15} />
            </Link>
          }
        />
        <div className="toolbar">
          <div className="search">
            <Search size={16} />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search entity ID, source, reason" />
          </div>
        </div>

        {evidenceQuery.isLoading && <LoadingState label="Loading evidence…" />}
        {evidenceQuery.isError && <ErrorState error={evidenceQuery.error} retry={evidenceQuery.refetch} />}

        {!evidenceQuery.isLoading && !evidenceQuery.isError && (
          <>
            <div className="evidence-count">
              {items.length} backend-derived evidence record{items.length === 1 ? '' : 's'} · grouped by Razorpay, Merchant, Bank
              {findingsQuery.data && findingsQuery.data.length > 0 && (
                <> · click a finding code on any record to open the finding it belongs to</>
              )}
            </div>
            {items.length === 0 ? (
              <EmptyState
                title={query ? 'No matches' : 'No evidence yet'}
                message={query ? 'Try a different search term.' : 'Evidence is generated when a reconciliation produces findings.'}
              />
            ) : (
              <SourceEvidence items={items} linkedFindings={linkedFindings} settlementId={id} />
            )}
          </>
        )}
      </main>
    </Shell>
  )
}
