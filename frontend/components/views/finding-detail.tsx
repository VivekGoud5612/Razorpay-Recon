'use client'

import { useMemo, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { ArrowUpRight, FileText, ShieldCheck } from 'lucide-react'
import { Shell, Title, Status, Kpi } from '@/components/shell'
import { LoadingState, ErrorState, EmptyState } from '@/components/async-state'
import { SourceEvidence } from '@/components/source-evidence'
import { CaseMap } from '@/components/case-map'
import { useFinding } from '@/lib/hooks/useFindings'
import { useReconciliation } from '@/lib/hooks/useReconciliation'
import { useGraph } from '@/lib/hooks/useGraph'
import { useStartInvestigation } from '@/lib/hooks/useStartInvestigation'
import { money } from '@/lib/format'
import { ApiError } from '@/lib/api/client'

type Tab = 'evidence' | 'relationships' | 'investigation'

export function FindingDetail() {
  const { id = '', findingId = '' } = useParams()
  const navigate = useNavigate()
  const findingQuery = useFinding(id, findingId)
  const reconciliationQuery = useReconciliation(id)
  const graphQuery = useGraph(id)
  const startInvestigation = useStartInvestigation()

  const [tab, setTab] = useState<Tab>('evidence')

  const finding = findingQuery.data

  // Graph node ids are `${source}:${entity_type}:${entity_id}` (see
  // ReconciliationGraphBuilder) — the same convention the affected entity
  // and evidence refs use, so this is the actual node for the exception.
  const affectedNodeId = finding
    ? `${finding.affected_entity.source}:${finding.affected_entity.entity_type}:${finding.affected_entity.entity_id}`
    : null

  const caseMapNodes = useMemo(() => {
    if (!finding || !graphQuery.data) return []
    const ids = new Set(finding.evidence.map((e) => `${e.source}:${e.entity_type}:${e.entity_id}`))
    if (affectedNodeId) ids.add(affectedNodeId)
    return graphQuery.data.nodes.filter((n) => ids.has(n.node_id))
  }, [finding, graphQuery.data, affectedNodeId])

  const handleInvestigate = () => {
    if (!finding) return
    startInvestigation.mutate(
      { settlement_id: id, finding_ids: [finding.finding_id] },
      {
        onSuccess: (investigation) => {
          navigate(`/investigations/${investigation.investigation_id}`)
        },
      },
    )
  }

  if (findingQuery.isLoading) {
    return (
      <Shell>
        <main>
          <LoadingState label="Loading finding…" />
        </main>
      </Shell>
    )
  }

  if (findingQuery.isError) {
    return (
      <Shell>
        <main>
          <div className="back">
            <Link to={`/reconciliations/${id}`}>← {id}</Link>
          </div>
          <ErrorState error={findingQuery.error} retry={findingQuery.refetch} />
        </main>
      </Shell>
    )
  }

  if (!finding) {
    return (
      <Shell>
        <main>
          <div className="back">
            <Link to={`/reconciliations/${id}`}>← {id}</Link>
          </div>
          <EmptyState title="Finding not found" message={`No finding ${findingId} exists for this settlement.`} />
        </main>
      </Shell>
    )
  }

  const reconciliation = reconciliationQuery.data

  return (
    <Shell>
      <main>
        <div className="back">
          <Link to={`/reconciliations/${id}`}>← {id}</Link>
        </div>
        <div className="finding-hero">
          <div>
            <div className="finding-top">
              <Status value={finding.severity} />
              <span className="mono">{finding.finding_id}</span>
            </div>
            <h1>{finding.code}</h1>
            <p>{finding.message}</p>
            <div className="entity-pill">
              <FileText size={15} />
              {finding.affected_entity.entity_type} <b className="mono">{finding.affected_entity.entity_id}</b>
            </div>
          </div>
          <div className="impact">
            <span>AI INVESTIGATION</span>
            <button className="button primary" onClick={handleInvestigate} disabled={startInvestigation.isPending}>
              {startInvestigation.isPending ? 'Starting…' : 'Investigate'}
              <ArrowUpRight size={15} />
            </button>
            {startInvestigation.isError && (
              <p className="form-error">
                {startInvestigation.error instanceof ApiError ? startInvestigation.error.message : 'Investigation failed to start.'}
              </p>
            )}
          </div>
        </div>

        <section className="deterministic">
          <div className="det-head">
            <div>
              <span className="eyebrow">WHY THIS WAS FLAGGED</span>
              <h3>Deterministic result</h3>
            </div>
            <span className="verified-label">
              <ShieldCheck size={14} />
              ENGINE VERIFIED
            </span>
          </div>
          <p>{finding.message}</p>
        </section>

        {reconciliation && (
          <div className="kpis four">
            <Kpi label="Razorpay Net" value={money(reconciliation.razorpay_net)} sub="Settlement authority" />
            <Kpi label="Bank Observed" value={money(reconciliation.bank_observed)} sub="Statement credit" />
            <Kpi label="Merchant Expected" value={money(reconciliation.merchant_expected)} sub="Context only" />
            <Kpi
              label="Razorpay vs Bank"
              value={money(reconciliation.razorpay_vs_bank_difference)}
              sub="Reconciliation-level variance"
              tone={Number(reconciliation.razorpay_vs_bank_difference) !== 0 ? 'red' : 'green'}
            />
          </div>
        )}

        <div className="tabs">
          <button className={tab === 'evidence' ? 'selected' : ''} onClick={() => setTab('evidence')}>
            Evidence
          </button>
          <button className={tab === 'relationships' ? 'selected' : ''} onClick={() => setTab('relationships')}>
            Case map
          </button>
          <button className={tab === 'investigation' ? 'selected' : ''} onClick={() => setTab('investigation')}>
            Investigation
          </button>
        </div>

        {tab === 'evidence' && (
          <section className="panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">SOURCE-AWARE EVIDENCE</span>
                <h2>Records collected for {finding.finding_id}</h2>
              </div>
              <span className="muted">{finding.evidence.length} backend-derived records</span>
            </div>
            {finding.evidence.length === 0 ? (
              <EmptyState title="No evidence" message="This finding has no attached evidence references." />
            ) : (
              <SourceEvidence items={finding.evidence} settlementId={id} />
            )}
            <Link className="button" to={`/reconciliations/${id}/evidence`}>
              Explore all evidence <ArrowUpRight size={15} />
            </Link>
          </section>
        )}

        {tab === 'relationships' && (
          <div className="case-map">
            <div className="case-map-head">
              <div>
                <span className="eyebrow">CASE MAP</span>
                <h3>Entities referenced by this finding&apos;s evidence</h3>
              </div>
              <Link className="text-link" to={`/reconciliations/${id}/graph`}>
                Open full graph <ArrowUpRight size={14} />
              </Link>
            </div>
            {graphQuery.isLoading && <LoadingState label="Loading graph…" />}
            {graphQuery.isError && <ErrorState error={graphQuery.error} retry={graphQuery.refetch} />}
            {!graphQuery.isLoading && !graphQuery.isError && caseMapNodes.length === 0 && (
              <EmptyState title="No graph nodes" message="No evidence graph nodes matched this finding's evidence." />
            )}
            {caseMapNodes.length > 0 && (
              <CaseMap
                nodes={caseMapNodes}
                edges={graphQuery.data?.edges ?? []}
                highlightNodeId={affectedNodeId ?? undefined}
              />
            )}
          </div>
        )}

        {tab === 'investigation' && (
          <section className="investigation-teaser">
            <span className="eyebrow">AI INVESTIGATION</span>
            <h2>Ready for investigation</h2>
            <p>
              Use the collected evidence to test hypotheses. AI proposals remain separate from the engine-verified
              financial result — use the Investigate action above to start.
            </p>
          </section>
        )}
      </main>
    </Shell>
  )
}
