"""
core/watchlist_pagerank.py
──────────────────────────
Personalized PageRank (PPR) watchlist algorithm.

Strategy: teleportation distribution is uniform over watchlist items (seeds).
Iterative: PR(v) = (1-d)*seed(v) + d * Σ(PR(u)/out(u)) for u→v
Graph is sparse (top-20 neighbors per node) and symmetric,
so in-neighbors of v == stored neighbors of v.
Stops at convergence (max Δ < PAGERANK_EPSILON) or max iterations.
O(iterations × N × K)
"""

from config import DEFAULT_TOP_K, PAGERANK_DAMPING, PAGERANK_ITERATIONS, PAGERANK_EPSILON


def recommend_pagerank(
    adjacency_list: dict[str, list[tuple[str, float]]],
    watchlist_ids: list[str],
    top_k: int = DEFAULT_TOP_K,
) -> list[tuple[str, float]]:
    """
    Personalized PageRank from watchlist seeds.

    Returns top_k (id, score) tuples sorted descending,
    with watchlist items excluded.
    """
    seed_set = set(watchlist_ids)
    all_nodes = list(adjacency_list.keys())

    if not all_nodes:
        return []

    # Uniform teleportation distribution over seeds
    seed_weight = 1.0 / len(watchlist_ids) if watchlist_ids else 0.0
    teleport: dict[str, float] = {sid: seed_weight for sid in watchlist_ids}

    # Initialize PR scores uniformly
    pr: dict[str, float] = {node: 1.0 / len(all_nodes) for node in all_nodes}

    # Precompute out-degree (number of neighbors)
    out_degree: dict[str, int] = {node: len(neighbors) for node, neighbors in adjacency_list.items()}

    for _ in range(PAGERANK_ITERATIONS):
        new_pr: dict[str, float] = {}

        for node in all_nodes:
            # Collect contributions from in-neighbors (graph is symmetric)
            incoming = 0.0
            for neighbor_id, _ in adjacency_list.get(node, []):
                deg = out_degree.get(neighbor_id, 0)
                if deg > 0:
                    incoming += pr.get(neighbor_id, 0.0) / deg

            new_pr[node] = (1.0 - PAGERANK_DAMPING) * teleport.get(node, 0.0) + PAGERANK_DAMPING * incoming

        # Check convergence
        max_delta = max(abs(new_pr.get(n, 0.0) - pr.get(n, 0.0)) for n in all_nodes)
        pr = new_pr

        if max_delta < PAGERANK_EPSILON:
            break

    # Exclude watchlist items, sort by score descending
    ranked = [
        (node, score)
        for node, score in pr.items()
        if node not in seed_set
    ]
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked[:top_k]
