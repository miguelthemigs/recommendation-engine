"""Unit tests for core.graph — synthetic items only, no Supabase/load."""

from config import MAX_GRAPH_NEIGHBORS
from core.graph import SimilarityGraph


def _item(id_, genres):
    return {"id": id_, "genres": genres, "keywords": [], "cast": []}


def test_build_links_similar_items_symmetrically():
    items = [
        _item(1, ["Drama", "Crime"]),
        _item(2, ["Drama", "Crime"]),  # identical to 1 → strong edge
        _item(3, ["Comedy"]),          # shares nothing
    ]
    g = SimilarityGraph()
    g.build(items)

    n1 = dict(g.neighbors("1"))
    n2 = dict(g.neighbors("2"))
    assert "2" in n1 and "1" in n2          # edge exists both ways
    assert n1["2"] == n2["1"]               # mirrored score (sim is symmetric)
    assert "3" not in n1                     # zero-similarity edges are dropped


def test_neighbors_top_k_limits_results():
    items = [_item(i, ["Drama"]) for i in range(5)]  # all mutually similar
    g = SimilarityGraph()
    g.build(items)
    assert len(g.neighbors("0", top_k=2)) == 2


def test_neighbors_pruned_to_max_graph_neighbors():
    # More mutual neighbors than the cap → each node keeps at most MAX_GRAPH_NEIGHBORS.
    items = [_item(i, ["Drama"]) for i in range(MAX_GRAPH_NEIGHBORS + 5)]
    g = SimilarityGraph()
    g.build(items)
    assert len(g.adjacency_list["0"]) == MAX_GRAPH_NEIGHBORS


def test_stats_reports_ready_after_build():
    g = SimilarityGraph()
    assert g.stats()["status"].startswith("not built")
    g.build([_item(1, ["Drama"]), _item(2, ["Drama"])])
    stats = g.stats()
    assert stats["status"] == "ready"
    assert stats["nodes"] == 2
    assert stats["edges"] == 1
