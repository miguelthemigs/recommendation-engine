"""
core/graph.py
─────────────
PLACEHOLDER — Step 3

This module will build and store the weighted similarity graph
as an adjacency list.

Planned structure:
    _adjacency_list: dict[str, list[tuple[str, float]]]
    {
        "1396": [("1409", 0.84), ("1621", 0.71), ...],   ← Breaking Bad neighbors
        "1409": [("1396", 0.84), ("1406", 0.68), ...],   ← Sons of Anarchy neighbors
        ...
    }

Only top MAX_GRAPH_NEIGHBORS edges per node are kept (configured in config.py).
Build complexity : O(N²) pairwise comparisons
Query complexity : O(1) dict lookup after build
"""

import time
from collections import defaultdict

from config import MAX_GRAPH_NEIGHBORS, DEFAULT_TOP_K
from core.similarity import similarity


class SimilarityGraph:

    def __init__(self):
        self._adjacency_list: dict[str, list[tuple[str, float]]] = {}
        self._build_time_seconds: float = 0.0
        self._node_count: int = 0
        self._edge_count: int = 0

    def build(self, items: list[dict]) -> None:
        """
        Build the adjacency list from all items.

        Steps:
          1. Compute pairwise similarity for all item pairs (upper triangle only)
          2. Mirror scores (sim(A,B) == sim(B,A))
          3. Sort each node's neighbors by score descending
          4. Prune to top MAX_GRAPH_NEIGHBORS per node
          5. Record build time and stats
        """
        t0 = time.perf_counter()

        raw: dict[str, list[tuple[str, float]]] = defaultdict(list)

        for i in range(len(items)):
            id_a = str(items[i]["id"])
            for j in range(i + 1, len(items)):
                id_b  = str(items[j]["id"])
                score = similarity(items[i], items[j])
                if score > 0.0:
                    raw[id_a].append((id_b, score))
                    raw[id_b].append((id_a, score))

        self._adjacency_list = {
            node: sorted(neighbors, key=lambda x: x[1], reverse=True)[:MAX_GRAPH_NEIGHBORS]
            for node, neighbors in raw.items()
        }

        self._node_count       = len(self._adjacency_list)
        self._edge_count       = sum(len(v) for v in self._adjacency_list.values()) // 2
        self._build_time_seconds = time.perf_counter() - t0

        print(
            f"[graph] Built in {self._build_time_seconds:.3f}s — "
            f"{self._node_count} nodes, {self._edge_count} edges"
        )

    @property
    def adjacency_list(self) -> dict[str, list[tuple[str, float]]]:
        return self._adjacency_list

    def neighbors(self, item_id: str, top_k: int = DEFAULT_TOP_K) -> list[tuple[str, float]]:
        """
        Return top-K neighbors for a single item.
        Returns: [(neighbor_id, score), ...] sorted desc
        """
        return self._adjacency_list.get(item_id, [])[:top_k]

    def stats(self) -> dict:
        """Returns graph build stats — useful for your performance analysis."""
        if not self._adjacency_list:
            return {"status": "not built — Step 3 pending"}
        return {
            "status":             "ready",
            "nodes":              self._node_count,
            "edges":              self._edge_count,
            "build_time_seconds": round(self._build_time_seconds, 3),
        }


# Singleton
graph = SimilarityGraph()
