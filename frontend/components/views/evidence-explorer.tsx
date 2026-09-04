'use client'

import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Search } from 'lucide-react'
import { Shell, Title } from '@/components/shell'
import { LoadingState, ErrorState, EmptyState } from '@/components/async-state'
import { SourceEvidence } from '@/components/source-evidence'
import { useEvidence } from '@/lib/hooks/useEvidence'

export function EvidenceExplorer() {
  const { id = '' } = useParams()
  const evidenceQuery = useEvidence(id)
  const [query, setQuery] = useState('')

  const items = useMemo(() => {
    const all = evidenceQuery.data ?? []
    if (!query) return all
    const q = query.toLowerCase()
    return all.filter((e) => JSON.stringify(e).toLowerCase().includes(q))
  }, [evidenceQuery.data, query])

  return (
    <Shell>
      <main>
        <Title eyebrow={`RECONCILIATION / ${id}`} title="Evidence explorer" />
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
            </div>
            {items.length === 0 ? (
              <EmptyState
                title={query ? 'No matches' : 'No evidence yet'}
                message={query ? 'Try a different search term.' : 'Evidence is generated when a reconciliation produces findings.'}
              />
            ) : (
              <SourceEvidence items={items} />
            )}
          </>
        )}
      </main>
    </Shell>
  )
}
