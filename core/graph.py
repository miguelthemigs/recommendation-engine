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

from config import MAX_GRAPH_NEIGHBORS, DEFAULT_TOP_K


class SimilarityGraph:

    def __init__(self):
        self._adjacency_list: dict[str, list[tuple[str, float]]] = {}
        self._build_time_seconds: float = 0.0
        self._node_count: int = 0
        self._edge_count: int = 0

    def build(self, items: list[dict]) -> None:
        """
        TODO (Step 3): Build the adjacency list from all items.

        Steps:
          1. Compute pairwise similarity for all item pairs (upper triangle only)
          2. Mirror scores (sim(A,B) == sim(B,A))
          3. Sort each node's neighbors by score descending
          4. Prune to top MAX_GRAPH_NEIGHBORS per node
          5. Record build time and stats
        """
        # PLACEHOLDER
        raise NotImplementedError("Implement build() in Step 3")

    def neighbors(self, item_id: str, top_k: int = DEFAULT_TOP_K) -> list[tuple[str, float]]:
        """
        TODO (Step 3): Return top-K neighbors for a single item.
        Returns: [(neighbor_id, score), ...] sorted desc
        """
        # PLACEHOLDER
        raise NotImplementedError("Implement neighbors() in Step 3")

    def neighbors_for_watchlist(
        self,
        item_ids: list[str],
        top_k: int = DEFAULT_TOP_K,
        exclude_watchlist: bool = True,
    ) -> list[tuple[str, float]]:
        """
        TODO (Step 4): Aggregate neighbor scores across a watchlist.

        Strategy: sum scores across all watchlist items.
        Items appearing as neighbor of multiple watchlist entries get boosted.
        Returns top-K items not already in the watchlist.
        """
        # PLACEHOLDER
        raise NotImplementedError("Implement neighbors_for_watchlist() in Step 4")

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
