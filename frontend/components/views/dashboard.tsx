'use client'

import { Link } from 'react-router-dom'
import { ArrowUpRight, Plus } from 'lucide-react'
import { Shell, Title, Status, Kpi, Table } from '@/components/shell'
import { LoadingState, ErrorState, EmptyState } from '@/components/async-state'
import { useReconciliations } from '@/lib/hooks/useReconciliations'
import { money, formatDateTime } from '@/lib/format'

export function Dashboard() {
  const { data: reconciliations, isLoading, isError, error, refetch } = useReconciliations()

  const exceptions = reconciliations?.filter((r) => r.status === 'exception') ?? []
  const reconciled = reconciliations?.filter((r) => r.status === 'reconciled') ?? []

  return (
    <Shell>
      <main>
        <Title
          eyebrow="OVERVIEW"
          title="Reconciliation control room"
          action={
            <Link className="button primary" to="/reconciliations/new">
              <Plus size={16} />
              New reconciliation
            </Link>
          }
        />

        {!isLoading && !isError && reconciliations && (
          <div className="kpis">
            <Kpi label="Total reconciliations" value={String(reconciliations.length)} sub="All runs" />
            <Kpi label="Open exceptions" value={String(exceptions.length)} sub="Needs review" tone={exceptions.length ? 'red' : undefined} />
            <Kpi label="Reconciled" value={String(reconciled.length)} sub="All sources agree" tone="green" />
            <Kpi
              label="Match rate"
              value={reconciliations.length ? `${Math.round((reconciled.length / reconciliations.length) * 100)}%` : '—'}
              sub="Reconciled / total"
            />
          </div>
        )}

        <div className="section-head">
          <div>
            <span className="eyebrow">ACTIVE WORKSPACES</span>
            <h2>Recent reconciliations</h2>
          </div>
          <Link className="text-link" to="/reconciliations">
            View all <ArrowUpRight size={14} />
          </Link>
        </div>

        {isLoading && <LoadingState label="Loading reconciliations…" />}
        {isError && <ErrorState error={error} retry={refetch} />}
        {!isLoading && !isError && reconciliations && reconciliations.length === 0 && (
          <EmptyState title="No reconciliations yet" message="Start a new reconciliation to ingest sources and run the deterministic engine." />
        )}
        {!isLoading && !isError && reconciliations && reconciliations.length > 0 && (
          <Table
            headers={['Reconciliation', 'Updated', 'Razorpay Net', 'Status']}
            rows={reconciliations.slice(0, 8).map((r) => [
              <Link className="id-link" to={`/reconciliations/${r.settlement_id}`} key={r.settlement_id}>
                {r.settlement_id}
              </Link>,
              formatDateTime(r.updated_at),
              money(r.razorpay_net),
              <Status value={r.status} key={`${r.settlement_id}-status`} />,
            ])}
          />
        )}
      </main>
    </Shell>
  )
}
