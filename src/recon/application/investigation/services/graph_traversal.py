from __future__ import annotations

from collections import deque

from recon.domain.graph.edge import GraphEdge
from recon.domain.graph.graph import ReconciliationGraph
from recon.domain.graph.node import GraphNode


class GraphTraversalService:

    def __init__(self, graph: ReconciliationGraph) -> None:
        self._graph = graph

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._graph.nodes.get(node_id)

    def get_neighbors(self, node_id: str) -> list[GraphNode]:
        neighbors: list[GraphNode] = []

        for edge in self._graph.edges.values():
            if edge.source_node_id == node_id:
                node = self._graph.nodes.get(edge.target_node_id)

                if node is not None:
                    neighbors.append(node)

            elif edge.target_node_id == node_id:
                node = self._graph.nodes.get(edge.source_node_id)

                if node is not None:
                    neighbors.append(node)

        return neighbors

    def get_subgraph(
        self,
        start_node_ids: set[str],
        depth: int = 2,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque(
            (node_id, 0)
            for node_id in start_node_ids
            if node_id in self._graph.nodes
        )

        while queue:
            node_id, current_depth = queue.popleft()

            if node_id in visited:
                continue

            visited.add(node_id)

            if current_depth >= depth:
                continue

            for neighbor in self.get_neighbors(node_id):
                if neighbor.node_id not in visited:
                    queue.append(
                        (neighbor.node_id, current_depth + 1)
                    )

        nodes = [
            self._graph.nodes[node_id]
            for node_id in visited
        ]

        edges = [
            edge
            for edge in self._graph.edges.values()
            if (
                edge.source_node_id in visited
                and edge.target_node_id in visited
            )
        ]

        return nodes, edges