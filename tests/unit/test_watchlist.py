"""Unit tests for watchlist aggregation (direct + BFS) over a synthetic graph."""

from config import BFS_DECAY_FACTOR
from core.watchlist_direct import recommend_direct
from core.watchlist_bfs import recommend_bfs

# A small hand-built adjacency list so expected scores are computable by hand.
ADJ = {
    "A": [("B", 0.9), ("C", 0.5)],
    "B": [("A", 0.9), ("D", 0.4)],
    "C": [("A", 0.5)],
    "D": [("B", 0.4)],
}


def test_direct_aggregates_and_excludes_seeds():
    result = dict(recommend_direct(ADJ, ["A"]))
    assert result == {"B": 0.9, "C": 0.5}      # neighbors of A, normalized by 1


def test_direct_normalizes_by_watchlist_size():
    # Seeds A,B: C from A (0.5), D from B (0.4); A and B excluded; divide by 2.
    result = dict(recommend_direct(ADJ, ["A", "B"]))
    assert result == {"C": 0.25, "D": 0.2}


def test_bfs_applies_depth2_decay_and_excludes_seeds():
    result = dict(recommend_bfs(ADJ, ["A"]))
    assert "A" not in result                    # seed excluded
    assert result["B"] == 0.9                    # depth-1, full score
    assert result["C"] == 0.5                    # depth-1, full score
    # D is depth-2 (A→B→D): 0.4 * decay
    assert result["D"] == 0.4 * BFS_DECAY_FACTOR


def test_top_k_caps_both_algorithms():
    assert len(recommend_direct(ADJ, ["A"], top_k=1)) == 1
    assert len(recommend_bfs(ADJ, ["A"], top_k=1)) == 1
