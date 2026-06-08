"""Unit tests for core.tfidf — tiny in-memory corpus, real sklearn, no I/O."""

from core.tfidf import TFIDFIndex


def _item(id_, overview):
    return {"id": id_, "overview": overview}


def test_tfidf_links_textually_similar_overviews():
    items = [
        _item(1, "space alien invasion thriller in deep space"),
        _item(2, "space alien invasion adventure across deep space"),
        _item(3, "a quiet romantic comedy set in paris"),
    ]
    idx = TFIDFIndex()
    idx.build(items)

    n1 = dict(idx.neighbors("1"))
    assert "2" in n1            # shared space/alien/invasion vocabulary
    assert n1["2"] > 0.0
    # The romance shares no meaningful terms → no edge to item 1.
    assert "3" not in n1


def test_tfidf_edges_are_symmetric():
    items = [
        _item(1, "heist crew robs a casino vault"),
        _item(2, "heist crew plans a casino robbery"),
    ]
    idx = TFIDFIndex()
    idx.build(items)
    assert dict(idx.neighbors("1"))["2"] == dict(idx.neighbors("2"))["1"]


def test_tfidf_stats_ready_after_build():
    idx = TFIDFIndex()
    assert idx.stats()["status"] == "not built"
    idx.build([_item(1, "alpha beta"), _item(2, "alpha beta")])
    assert idx.stats()["status"] == "ready"
