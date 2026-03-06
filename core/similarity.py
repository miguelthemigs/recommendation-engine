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
    TODO (Step 2): Implement Jaccard similarity.

    Expected behaviour:
        jaccard({"Drama"}, {"Drama", "Action"}) → 0.5
        jaccard(set(), set())                   → 0.0
        jaccard({"a"}, {"b"})                   → 0.0
    """
    # PLACEHOLDER
    raise NotImplementedError("Implement jaccard() in Step 2")


def similarity(item_a: dict, item_b: dict) -> float:
    """
    TODO (Step 2): Compute weighted similarity between two media items.

    Returns a score in [0.0, 1.0].
    Both items must have: genres (list), keywords (list), cast (list).
    """
    # PLACEHOLDER
    raise NotImplementedError("Implement similarity() in Step 2")
