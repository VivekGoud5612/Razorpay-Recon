'use client'

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Search } from 'lucide-react'
import { Shell, Title, Status, Table } from '@/components/shell'
import { LoadingState, ErrorState, EmptyState } from '@/components/async-state'
import { useReconciliations } from '@/lib/hooks/useReconciliations'
import { money } from '@/lib/format'

export function ReconciliationsList() {
  const { data: reconciliations, isLoading, isError, error, refetch } = useReconciliations()
  const [query, setQuery] = useState('')

  const filtered = (reconciliations ?? []).filter((r) => r.settlement_id.toLowerCase().includes(query.toLowerCase()))

  return (
    <Shell>
      <main>
        <Title
          eyebrow="WORKSPACE / RECONCILIATIONS"
          title="Reconciliations"
          action={
            <Link className="button primary" to="/reconciliations/new">
              <Plus size={16} />
              New reconciliation
            </Link>
          }
        />
        <div className="toolbar">
          <div className="search">
            <Search size={16} />
            <input
              placeholder="Search settlement ID"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>

        {isLoading && <LoadingState label="Loading reconciliations…" />}
        {isError && <ErrorState error={error} retry={refetch} />}
        {!isLoading && !isError && filtered.length === 0 && (
          <EmptyState
            title={query ? 'No matches' : 'No reconciliations yet'}
            message={query ? 'Try a different settlement ID.' : 'Start a new reconciliation to see it here.'}
          />
        )}
        {!isLoading && !isError && filtered.length > 0 && (
          <Table
            headers={['Reconciliation', 'Razorpay Net', 'Bank Observed', 'Merchant Expected', 'Status']}
            rows={filtered.map((r) => [
              <Link className="id-link" to={`/reconciliations/${r.settlement_id}`} key={r.settlement_id}>
                {r.settlement_id}
              </Link>,
              money(r.razorpay_net),
              money(r.bank_observed),
              money(r.merchant_expected),
              <Status value={r.status} key={`${r.settlement_id}-status`} />,
            ])}
          />
        )}
      </main>
    </Shell>
  )
}
