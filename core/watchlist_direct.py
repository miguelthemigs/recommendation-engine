"""
core/watchlist_direct.py
────────────────────────
Direct aggregation watchlist algorithm.

Strategy: for each watchlist item look up its graph neighbors,
accumulate similarity scores, normalize by watchlist size.
Items that are neighbors of multiple watchlist items get boosted.
O(W × MAX_GRAPH_NEIGHBORS)
"""

from config import DEFAULT_TOP_K


def recommend_direct(
    adjacency_list: dict[str, list[tuple[str, float]]],
    watchlist_ids: list[str],
    top_k: int = DEFAULT_TOP_K,
) -> list[tuple[str, float]]:
    """
    Aggregate neighbor scores across all watchlist items.

    Returns top_k (id, score) tuples sorted descending,
    with watchlist items excluded.
    """
    seed_set = set(watchlist_ids)
    scores: dict[str, float] = {}

    for seed_id in watchlist_ids:
        for neighbor_id, score in adjacency_list.get(seed_id, []):
            if neighbor_id not in seed_set:
                scores[neighbor_id] = scores.get(neighbor_id, 0.0) + score

    # Normalize by watchlist size
    n = len(watchlist_ids)
    normalized = {nid: total / n for nid, total in scores.items()}

    ranked = sorted(normalized.items(), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]
