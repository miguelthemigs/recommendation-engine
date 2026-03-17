"""
core/watchlist_bfs.py
─────────────────────
BFS depth-2 watchlist algorithm.

Strategy: BFS to depth 2 from each seed.
Depth-1 neighbors: full edge score.
Depth-2 neighbors: edge score × BFS_DECAY_FACTOR.
Uses max() per candidate to prevent depth-2 flooding.
O(W × K²) where K = MAX_GRAPH_NEIGHBORS
"""

from config import DEFAULT_TOP_K, BFS_DECAY_FACTOR


def recommend_bfs(
    adjacency_list: dict[str, list[tuple[str, float]]],
    watchlist_ids: list[str],
    top_k: int = DEFAULT_TOP_K,
) -> list[tuple[str, float]]:
    """
    BFS to depth 2 from each watchlist seed.

    Returns top_k (id, score) tuples sorted descending,
    with watchlist items excluded.
    """
    seed_set = set(watchlist_ids)
    scores: dict[str, float] = {}

    for seed_id in watchlist_ids:
        depth1 = adjacency_list.get(seed_id, [])
        for d1_id, d1_score in depth1:
            if d1_id not in seed_set:
                scores[d1_id] = max(scores.get(d1_id, 0.0), d1_score)

            # Depth-2 expansion
            for d2_id, d2_score in adjacency_list.get(d1_id, []):
                if d2_id not in seed_set and d2_id != seed_id:
                    decayed = d2_score * BFS_DECAY_FACTOR
                    scores[d2_id] = max(scores.get(d2_id, 0.0), decayed)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]
