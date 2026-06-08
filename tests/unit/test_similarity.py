"""Unit tests for core.similarity — pure Jaccard + weighted scoring, no I/O."""

from config import WEIGHT_GENRE, WEIGHT_KEYWORD, WEIGHT_CAST
from core.similarity import jaccard, similarity


def test_jaccard_identical_sets_is_one():
    assert jaccard({"Drama", "Action"}, {"Drama", "Action"}) == 1.0


def test_jaccard_disjoint_sets_is_zero():
    assert jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_partial_overlap():
    # {Drama} ∩ {Drama, Action} = 1 ; union = 2 → 0.5
    assert jaccard({"Drama"}, {"Drama", "Action"}) == 0.5


def test_jaccard_both_empty_is_zero_not_division_error():
    assert jaccard(set(), set()) == 0.0


def test_similarity_identical_items_equals_weight_sum():
    item = {"genres": ["Drama"], "keywords": ["heist"], "cast": ["X"]}
    # Every component is a perfect 1.0, so the score collapses to the weight sum.
    assert similarity(item, item) == WEIGHT_GENRE + WEIGHT_KEYWORD + WEIGHT_CAST


def test_similarity_is_bounded_zero_to_one():
    a = {"genres": ["Drama"], "keywords": ["heist"], "cast": ["X"]}
    b = {"genres": ["Comedy"], "keywords": ["wedding"], "cast": ["Y"]}
    assert similarity(a, b) == 0.0
    assert 0.0 <= similarity(a, a) <= 1.0


def test_similarity_tolerates_missing_fields():
    # Missing keys default to empty lists rather than raising KeyError.
    assert similarity({}, {}) == 0.0
