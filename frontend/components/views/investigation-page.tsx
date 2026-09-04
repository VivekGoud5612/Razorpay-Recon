'use client'

import { Link, useNavigate, useParams } from 'react-router-dom'
import { CircleDot } from 'lucide-react'
import { Shell, Title, Status } from '@/components/shell'
import { LoadingState, ErrorState, EmptyState } from '@/components/async-state'
import { useInvestigation } from '@/lib/hooks/useInvestigation'
import { formatDateTime } from '@/lib/format'

const TIMELINE_STEPS = ['Finding detected', 'Evidence collected', 'Relationships analyzed', 'Hypotheses generated', 'Policy validated', 'Conclusion']

// Purely a display tier over the backend's raw confidence float — no new
// data, just making the VERIFIED/LIKELY/UNCERTAIN distinction visible.
// 0.60 mirrors InvestigationPolicy.MIN_CONFIDENCE (below it a hypothesis can
// never become the root cause / triggers abstention).
function confidenceTier(confidence: number): { label: string; statusValue: string } {
  if (confidence >= 0.85) return { label: 'VERIFIED', statusValue: 'resolved' }
  if (confidence >= 0.6) return { label: 'LIKELY', statusValue: 'warning' }
  return { label: 'UNCERTAIN', statusValue: 'pending' }
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const tier = confidenceTier(confidence)
  return (
    <span className={`status ${tier.statusValue}`}>
      {tier.label} · {Math.round(confidence * 100)}%
    </span>
  )
}

export function InvestigationPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const investigationQuery = useInvestigation(id)

  if (investigationQuery.isLoading) {
    return (
      <Shell>
        <main>
          <LoadingState label="Loading investigation…" />
        </main>
      </Shell>
    )
  }

  if (investigationQuery.isError) {
    return (
      <Shell>
        <main>
          <ErrorState error={investigationQuery.error} retry={investigationQuery.refetch} />
        </main>
      </Shell>
    )
  }

  const investigation = investigationQuery.data

  if (!investigation) {
    return (
      <Shell>
        <main>
          <EmptyState title="Investigation not found" message={`No investigation ${id} exists.`} />
        </main>
      </Shell>
    )
  }

  const rootHypothesis = investigation.hypotheses.find((h) => h.hypothesis_id === investigation.root_cause?.hypothesis_id)

  return (
    <Shell>
      <main>
        <Title
          eyebrow={`INVESTIGATION / ${investigation.investigation_id}`}
          title="Case file"
          action={
            <button className="button" onClick={() => navigate(`/reconciliations/${investigation.settlement_id}`)}>
              Back to reconciliation
            </button>
          }
        />
        <div className="investigation-banner">
          <div>
            <span className="eyebrow">AI REASONING LAYER</span>
            <h2>Investigation {investigation.investigation_id}</h2>
            <p>AI hypotheses are proposals, separate from deterministic reconciliation results.</p>
          </div>
          <Status value={investigation.status} />
        </div>

        <div className="timeline">
          {TIMELINE_STEPS.map((step, i) => (
            <div className={i < 5 ? 'done' : ''} key={step}>
              <span>{i < 5 ? '✓' : '6'}</span>
              <b>{step}</b>
              <small>{formatDateTime(investigation.created_at)}</small>
            </div>
          ))}
        </div>

        {investigation.should_abstain && (
          <section className="investigation-teaser">
            <span className="eyebrow">
              <span className="status needs_review">ABSTAINED</span>
            </span>
            <h2>The model abstained from a root-cause conclusion</h2>
            <p>{investigation.abstain_reason ?? 'Evidence was insufficient to support a reliable conclusion.'}</p>
          </section>
        )}

        <div className="investigation-grid">
          <section className="panel">
            <div className="det-head">
              <div>
                <span className="eyebrow">ROOT CAUSE</span>
                <h2>{rootHypothesis ? rootHypothesis.statement : 'No root cause established'}</h2>
              </div>
              {investigation.root_cause ? (
                <ConfidenceBadge confidence={investigation.root_cause.confidence} />
              ) : (
                <span className="status needs_review">ABSTAINED</span>
              )}
            </div>

            {investigation.factual_observations.length > 0 && (
              <>
                <h3 className="subhead">Factual observations</h3>
                <ul>
                  {investigation.factual_observations.map((obs, i) => (
                    <li key={i} className="reasoning">
                      {obs}
                    </li>
                  ))}
                </ul>
              </>
            )}

            <h3 className="subhead">Hypotheses</h3>
            {investigation.hypotheses.length === 0 ? (
              <div className="empty">No hypotheses were generated.</div>
            ) : (
              investigation.hypotheses.map((h) => (
                <div className="callout" key={h.hypothesis_id}>
                  <div className="finding-top">
                    <b>{h.hypothesis_id}</b>
                    <ConfidenceBadge confidence={h.confidence} />
                  </div>
                  <p>{h.statement}</p>
                </div>
              ))
            )}
          </section>

          <section className="panel">
            <span className="eyebrow">SUPPORTING EVIDENCE</span>
            <h2>Evidence used</h2>
            {investigation.evidence.length === 0 ? (
              <div className="empty">No evidence recorded.</div>
            ) : (
              investigation.evidence.map((e) => (
                <div className="evidence-mini" key={e.evidence_id}>
                  <CircleDot size={15} />
                  <div>
                    <b>{e.reason}</b>
                    <span>
                      {e.source} · {e.entity_id}
                    </span>
                  </div>
                </div>
              ))
            )}

            <h3 className="subhead">Missing evidence</h3>
            {investigation.missing_evidence.length === 0 ? (
              <div className="empty">No missing evidence recorded.</div>
            ) : (
              <ul>
                {investigation.missing_evidence.map((item, i) => (
                  <li key={i} className="reasoning">
                    {item}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </main>
    </Shell>
  )
}
