'use client'

import { useMemo, useState } from 'react'
import dynamic from 'next/dynamic'
import { Link, useParams } from 'react-router-dom'
import { GitBranch } from 'lucide-react'
import '@xyflow/react/dist/style.css'
import { Shell, Title, Kpi } from '@/components/shell'
import { LoadingState, ErrorState, EmptyState } from '@/components/async-state'
import { useGraph } from '@/lib/hooks/useGraph'
import type { GraphNode } from '@/lib/types/domain'

const ReactFlow = dynamic(() => import('@xyflow/react').then((m) => m.ReactFlow), { ssr: false })
const Background = dynamic(() => import('@xyflow/react').then((m) => m.Background), { ssr: false })
const Controls = dynamic(() => import('@xyflow/react').then((m) => m.Controls), { ssr: false })
const MiniMap = dynamic(() => import('@xyflow/react').then((m) => m.MiniMap), { ssr: false })

export function GraphPage() {
  const { id = '' } = useParams()
  const graphQuery = useGraph(id)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)

  const graph = graphQuery.data

  const flowNodes = useMemo(() => {
    if (!graph) return []
    return graph.nodes.map((n, i) => ({
      id: n.node_id,
      position: { x: (i % 4) * 240 + 30, y: Math.floor(i / 4) * 140 + 30 },
      data: {
        label: (
          <div className="graph-node">
            <span>{n.source} · {n.entity_type}</span>
            <b className="mono">{n.entity_id}</b>
          </div>
        ),
      },
    }))
  }, [graph])

  const flowEdges = useMemo(() => {
    if (!graph) return []
    return graph.edges.map((e) => ({
      id: e.edge_id,
      source: e.source_node_id,
      target: e.target_node_id,
      label: e.edge_type,
      // Every edge the backend returns is deterministic/rule-derived
      // (RELATION_RULES, confidence 1.0) — preserved on the edge's data so
      // consumers of the flow model see it, even though there is currently
      // no lower-confidence/candidate tier to visually contrast it with.
      data: { edgeType: e.edge_type, confidence: e.confidence },
      style: { stroke: '#395a78', strokeWidth: 1.5 },
    }))
  }, [graph])

  const connections = useMemo(() => {
    if (!graph || !selectedNode) return []
    return graph.edges
      .filter((e) => e.source_node_id === selectedNode.node_id || e.target_node_id === selectedNode.node_id)
      .map((e) => {
        const otherId = e.source_node_id === selectedNode.node_id ? e.target_node_id : e.source_node_id
        const other = graph.nodes.find((n) => n.node_id === otherId)
        return { edge: e, other }
      })
  }, [graph, selectedNode])

  const handleNodeClick = (_event: unknown, node: { id: string }) => {
    const match = graph?.nodes.find((n) => n.node_id === node.id) ?? null
    setSelectedNode(match)
  }

  return (
    <Shell>
      <main>
        <Title
          eyebrow={`RECONCILIATION / ${id}`}
          title="Evidence investigation canvas"
          action={
            <Link className="button" to={`/reconciliations/${id}`}>
              Back to reconciliation
            </Link>
          }
        />

        {graphQuery.isLoading && <LoadingState label="Loading evidence graph…" />}
        {graphQuery.isError && <ErrorState error={graphQuery.error} retry={graphQuery.refetch} />}

        {!graphQuery.isLoading && !graphQuery.isError && graph && graph.nodes.length === 0 && (
          <EmptyState
            title="No graph yet"
            message="An evidence graph is only built when a reconciliation produces an exception. Reconciled settlements have no graph."
          />
        )}

        {!graphQuery.isLoading && !graphQuery.isError && graph && graph.nodes.length > 0 && (
          <>
            <div className="graph-legend">
              <span className="eyebrow">RELATIONSHIP CONFIDENCE</span>
              <span>
                <i className="solid-line" /> Deterministic · engine-verified (all edges, confidence 1.00)
              </span>
            </div>
            <div className="graph-layout">
              <div className="graph-canvas">
                <ReactFlow nodes={flowNodes} edges={flowEdges} onNodeClick={handleNodeClick} fitView>
                  <Background color="#d8d5cd" gap={24} />
                  <Controls />
                  <MiniMap pannable zoomable />
                </ReactFlow>
              </div>
              <aside className="node-details">
                <span className="eyebrow">SELECTED EVIDENCE NODE</span>
                <GitBranch size={20} />
                {selectedNode ? (
                  <>
                    <h3>{selectedNode.entity_type}</h3>
                    <b className="mono">{selectedNode.entity_id}</b>
                    <p>Source: {selectedNode.source}</p>
                    <Kpi label="Node ID" value={selectedNode.node_id} sub="Graph identifier" />
                    {connections.length > 0 && (
                      <>
                        <span className="eyebrow" style={{ marginTop: 14 }}>
                          CONNECTIONS
                        </span>
                        <div className="rel-rows">
                          {connections.map(({ edge, other }) => (
                            <div className="relationship-list" key={edge.edge_id}>
                              <b>{edge.edge_type}</b>
                              <span>{other ? `${other.entity_type} ${other.entity_id}` : '—'}</span>
                            </div>
                          ))}
                        </div>
                      </>
                    )}
                  </>
                ) : (
                  <p>Click a node in the graph to see its details.</p>
                )}
              </aside>
            </div>
          </>
        )}
      </main>
    </Shell>
  )
}
