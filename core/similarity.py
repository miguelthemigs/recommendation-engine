"""
core/similarity.py
──────────────────
PLACEHOLDER — Step 2

This module will compute similarity scores between two media items.

Planned formula:
    sim(A, B) = WEIGHT_GENRE   * jaccard(genres)
              + WEIGHT_KEYWORD * jaccard(keywords)
              + WEIGHT_CAST    * jaccard(cast)

Jaccard similarity:
    jaccard(A, B) = |A ∩ B| / |A ∪ B|

Weights are defined in config.py so you can tune and benchmark them.
"""

from config import WEIGHT_GENRE, WEIGHT_KEYWORD, WEIGHT_CAST


def jaccard(set_a: set, set_b: set) -> float:
    """
    Jaccard similarity: |A ∩ B| / |A ∪ B|.

    Expected behaviour:
        jaccard({"Drama"}, {"Drama", "Action"}) → 0.5
        jaccard(set(), set())                   → 0.0
        jaccard({"a"}, {"b"})                   → 0.0
    """
    if not set_a and not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def similarity(item_a: dict, item_b: dict) -> float:
    """
    Weighted similarity between two media items.

    Returns a score in [0.0, 1.0].
    Both items must have: genres (list), keywords (list), cast (list).
    """
    genres   = jaccard(set(item_a.get("genres",   [])), set(item_b.get("genres",   [])))
    keywords = jaccard(set(item_a.get("keywords", [])), set(item_b.get("keywords", [])))
    cast     = jaccard(set(item_a.get("cast",     [])), set(item_b.get("cast",     [])))

    return WEIGHT_GENRE * genres + WEIGHT_KEYWORD * keywords + WEIGHT_CAST * cast
