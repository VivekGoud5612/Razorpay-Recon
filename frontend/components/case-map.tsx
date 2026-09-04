'use client'

import type { GraphEdge, GraphNode } from '@/lib/types/domain'

/**
 * Compact, non-React-Flow rendering of a (sub)graph: a horizontal node flow
 * plus a relationship list for edges between the shown nodes. Used for the
 * "case map" preview on the reconciliation and finding workspaces — the full
 * interactive canvas lives at /reconciliations/:id/graph (GraphPage).
 *
 * All data here comes straight from the backend graph response; nothing is
 * fabricated. Every edge the backend returns is a deterministic,
 * rule-derived relationship (confidence 1.0 — see RELATION_RULES /
 * ReconciliationGraphBuilder), so the legend always reads "deterministic /
 * engine-verified" rather than distinguishing a candidate/AI tier the
 * backend doesn't produce.
 */
export function CaseMap({
  nodes,
  edges,
  highlightNodeId,
  maxNodes,
}: {
  nodes: GraphNode[]
  edges: GraphEdge[]
  highlightNodeId?: string
  maxNodes?: number
}) {
  const shown = maxNodes ? nodes.slice(0, maxNodes) : nodes
  const shownIds = new Set(shown.map((n) => n.node_id))
  const nodeById = new Map(nodes.map((n) => [n.node_id, n]))
  const relevantEdges = edges.filter((e) => shownIds.has(e.source_node_id) && shownIds.has(e.target_node_id))
  const hiddenCount = nodes.length - shown.length

  return (
    <div>
      <div className="case-flow">
        {shown.map((n) => (
          <div className={`case-node ${n.node_id === highlightNodeId ? 'highlighted' : ''}`} key={n.node_id}>
            <span>{n.source}</span>
            <b>{n.entity_type}</b>
            <small className="mono">{n.entity_id}</small>
          </div>
        ))}
        {hiddenCount > 0 && (
          <div className="case-node unresolved">
            <span>+{hiddenCount} more</span>
            <b>See full graph</b>
          </div>
        )}
      </div>

      {relevantEdges.length > 0 && (
        <div className="rel-rows">
          {relevantEdges.map((e) => {
            const s = nodeById.get(e.source_node_id)
            const t = nodeById.get(e.target_node_id)
            if (!s || !t) return null
            return (
              <div className="relationship-list" key={e.edge_id}>
                <span>
                  {s.entity_type} <span className="mono">{s.entity_id}</span>
                </span>
                <b>{e.edge_type}</b>
                <span>
                  {t.entity_type} <span className="mono">{t.entity_id}</span>
                </span>
              </div>
            )
          })}
        </div>
      )}

      <div className="graph-legend">
        <span className="eyebrow">RELATIONSHIP CONFIDENCE</span>
        <span>
          <i className="solid-line" /> Deterministic · engine-verified
        </span>
      </div>
    </div>
  )
}
