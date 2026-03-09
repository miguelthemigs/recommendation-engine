"""
core/tfidf.py
─────────────
TF-IDF cosine similarity index built on item overviews.

Each item's overview is vectorized with sklearn's TfidfVectorizer.
Pairwise cosine similarity is computed once at startup (O(N²)) and stored
as an adjacency list - same structure as graph.py so the two are directly comparable.

Build complexity : O(N²) cosine similarity computation
Query complexity : O(1) dict lookup after build
"""

import time
from collections import defaultdict

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import MAX_GRAPH_NEIGHBORS, DEFAULT_TOP_K


class TFIDFIndex:

    def __init__(self):
        self._adjacency_list: dict[str, list[tuple[str, float]]] = {}
        self._build_time_seconds: float = 0.0
        self._node_count: int = 0
        self._edge_count: int = 0

    def build(self, items: list[dict]) -> None:
        """
        Build the TF-IDF adjacency list from item overviews.

        Steps:
          1. Vectorize all overviews with TF-IDF (English stop words removed)
          2. Compute full NxN cosine similarity matrix
          3. Upper triangle → mirror into adjacency dict
          4. Sort each node's neighbors descending, prune to MAX_GRAPH_NEIGHBORS
          5. Record build time and stats
        """
        t0 = time.perf_counter()

        ids       = [str(item["id"]) for item in items]
        overviews = [item.get("overview", "") or "" for item in items]

        vectorizer   = TfidfVectorizer(stop_words="english", min_df=1)
        tfidf_matrix = vectorizer.fit_transform(overviews)
        sim_matrix   = cosine_similarity(tfidf_matrix)   # shape: (N, N)

        raw: dict[str, list[tuple[str, float]]] = defaultdict(list)
        n = len(ids)

        for i in range(n):
            for j in range(i + 1, n):
                score = float(sim_matrix[i, j])
                if score > 0.0:
                    raw[ids[i]].append((ids[j], score))
                    raw[ids[j]].append((ids[i], score))

        self._adjacency_list = {
            node: sorted(neighbors, key=lambda x: x[1], reverse=True)[:MAX_GRAPH_NEIGHBORS]
            for node, neighbors in raw.items()
        }

        self._node_count        = len(self._adjacency_list)
        self._edge_count        = sum(len(v) for v in self._adjacency_list.values()) // 2
        self._build_time_seconds = time.perf_counter() - t0

        print(
            f"[tfidf] Built in {self._build_time_seconds:.3f}s — "
            f"{self._node_count} nodes, {self._edge_count} edges"
        )

    def neighbors(self, item_id: str, top_k: int = DEFAULT_TOP_K) -> list[tuple[str, float]]:
        """Return top-K neighbors by TF-IDF cosine similarity. O(1) lookup."""
        return self._adjacency_list.get(item_id, [])[:top_k]

    def stats(self) -> dict:
        if not self._adjacency_list:
            return {"status": "not built"}
        return {
            "status":             "ready",
            "nodes":              self._node_count,
            "edges":              self._edge_count,
            "build_time_seconds": round(self._build_time_seconds, 3),
        }


# Singleton
tfidf_index = TFIDFIndex()
