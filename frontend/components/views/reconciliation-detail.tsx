'use client'

import { Link, useParams } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'
import { Shell, Title, Status, Kpi, Table } from '@/components/shell'
import { LoadingState, ErrorState, EmptyState } from '@/components/async-state'
import { useReconciliation } from '@/lib/hooks/useReconciliation'
import { useFindings } from '@/lib/hooks/useFindings'
import { useRunReconciliation } from '@/lib/hooks/useRunReconciliation'
import { money, formatDateTime } from '@/lib/format'

export function ReconciliationDetail() {
  const { id = '' } = useParams()
  const reconciliationQuery = useReconciliation(id)
  const findingsQuery = useFindings(id)
  const rerun = useRunReconciliation()

  const reconciliation = reconciliationQuery.data

  const handleRerun = () => {
    if (!reconciliation) return
    rerun.mutate({ settlement_id: reconciliation.settlement_id, import_ids: reconciliation.import_ids })
  }

  if (reconciliationQuery.isLoading) {
    return (
      <Shell>
        <main>
          <LoadingState label="Loading reconciliation…" />
        </main>
      </Shell>
    )
  }

  if (reconciliationQuery.isError) {
    return (
      <Shell>
        <main>
          <div className="back">
            <Link to="/reconciliations">← All reconciliations</Link>
          </div>
          <ErrorState error={reconciliationQuery.error} retry={reconciliationQuery.refetch} />
        </main>
      </Shell>
    )
  }

  if (!reconciliation) {
    return (
      <Shell>
        <main>
          <div className="back">
            <Link to="/reconciliations">← All reconciliations</Link>
          </div>
          <EmptyState title="Reconciliation not found" message={`No reconciliation has been run yet for settlement ${id}.`} />
        </main>
      </Shell>
    )
  }

  const findings = findingsQuery.data ?? []
  const variance = Number(reconciliation.razorpay_net) - Number(reconciliation.bank_observed)

  return (
    <Shell>
      <main>
        <div className="back">
          <Link to="/reconciliations">← All reconciliations</Link>
        </div>
        <Title
          eyebrow="OPERATIONS WORKSPACE"
          title={reconciliation.settlement_id}
          action={
            <button className="button" onClick={handleRerun} disabled={rerun.isPending}>
              {rerun.isPending ? 'Running…' : 'Run / Re-run'}
            </button>
          }
        />
        {rerun.isError && <p className="form-error">{(rerun.error as Error).message}</p>}
        <div className="meta-line">
          <span>Reason: {reconciliation.reason_code}</span>
          <span>Last run {formatDateTime(reconciliation.updated_at)}</span>
          <Status value={reconciliation.status} />
        </div>
        <div className="kpis five">
          <Kpi label="Razorpay Net" value={money(reconciliation.razorpay_net)} sub="Authoritative settlement" />
          <Kpi label="Bank Observed" value={money(reconciliation.bank_observed)} sub="Statement credit" />
          <Kpi label="Merchant Expected" value={money(reconciliation.merchant_expected)} sub="Ledger derived" />
          <Kpi label="Razorpay vs Bank" value={money(variance)} sub="Requires review" tone={variance !== 0 ? 'red' : 'green'} />
          <Kpi label="Findings" value={String(findings.length)} sub="Findings queue" tone={findings.length ? 'red' : 'green'} />
        </div>

        <div className="section-head compact">
          <div>
            <span className="eyebrow">FINDINGS QUEUE / {findings.length}</span>
            <h2>Exceptions</h2>
          </div>
          <Link className="text-link" to={`/reconciliations/${reconciliation.settlement_id}/evidence`}>
            Explore evidence <ArrowUpRight size={14} />
          </Link>
        </div>

        {findingsQuery.isLoading && <LoadingState label="Loading findings…" />}
        {findingsQuery.isError && <ErrorState error={findingsQuery.error} retry={findingsQuery.refetch} />}
        {!findingsQuery.isLoading && !findingsQuery.isError && findings.length === 0 && (
          <EmptyState
            title="No findings"
            message={
              reconciliation.status === 'exception'
                ? 'This settlement has a financial difference but no rule-level findings.'
                : 'This settlement reconciled cleanly.'
            }
          />
        )}
        {!findingsQuery.isLoading && !findingsQuery.isError && findings.length > 0 && (
          <Table
            headers={['Finding', 'Code', 'Entity', 'Severity']}
            rows={findings.map((f) => [
              <Link className="id-link" to={`/reconciliations/${reconciliation.settlement_id}/findings/${f.finding_id}`} key={f.finding_id}>
                {f.finding_id}
              </Link>,
              <span className="mono" key={`${f.finding_id}-code`}>
                {f.code}
              </span>,
              f.affected_entity.entity_type,
              <Status value={f.severity} key={`${f.finding_id}-sev`} />,
            ])}
          />
        )}

        {reconciliation.status === 'exception' && (
          <div className="section-head compact">
            <div>
              <span className="eyebrow">EVIDENCE GRAPH</span>
              <h2>Relationship map</h2>
            </div>
            <Link className="text-link" to={`/reconciliations/${reconciliation.settlement_id}/graph`}>
              Open graph <ArrowUpRight size={14} />
            </Link>
          </div>
        )}
      </main>
    </Shell>
  )
}
