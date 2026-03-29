"""
core/coldstart.py
─────────────────
Cold-start recommendation pipeline.

Flow:
  UserAnswers → LLM (OpenAI) → TasteSignals
              → _ground_signals → seed_ids (list[str])
              → recommend_bfs   → ColdStartResult
"""

import json
import logging
import time
from dataclasses import dataclass, field

from openai import OpenAI

from config import (
    OPENAI_API_KEY,
    COLDSTART_MAX_TOKENS,
    COLDSTART_MODEL,
    COLDSTART_PROMPT_V1,
    COLDSTART_SEARCH_LIMIT,
    COLDSTART_SEED_COUNT,
    DEFAULT_TOP_K,
)
from core.store import store
from core.watchlist_bfs import recommend_bfs

logger = logging.getLogger(__name__)

# Module-level singleton — instantiated once on first import
_client = OpenAI(api_key=OPENAI_API_KEY)


# ── Public data types ─────────────────────────────────────────────────────────

@dataclass
class UserAnswers:
    q1_media_type: str
    q2_genres:     str
    q3_title:      str
    q4_dark:       str
    q5_familiar:   str


@dataclass
class TasteSignals:
    genres:           list[str]
    keywords:         list[str]
    reference_titles: list[str]
    mood:             str          # "light" | "dark" | "neutral"


@dataclass
class ColdStartResult:
    recommendations: list[tuple[str, float]]
    seed_ids:        list[str]
    signals:         TasteSignals
    input_tokens:    int
    output_tokens:   int
    llm_time_ms:     float
    total_time_ms:   float


# ── Private helpers ───────────────────────────────────────────────────────────

def _call_llm(answers: UserAnswers) -> tuple[TasteSignals, int, int, float]:
    """
    Send the formatted prompt to Claude, parse the JSON response.

    Returns (signals, input_tokens, output_tokens, elapsed_ms).
    Raises ValueError if the LLM response is not valid JSON.
    """
    prompt = COLDSTART_PROMPT_V1.format(
        q1=answers.q1_media_type,
        q2=answers.q2_genres,
        q3=answers.q3_title,
        q4=answers.q4_dark,
        q5=answers.q5_familiar,
    )

    t0 = time.perf_counter()
    response = _client.chat.completions.create(
        model=COLDSTART_MODEL,
        max_tokens=COLDSTART_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

    raw_text = response.choices[0].message.content
    input_tokens  = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens

    logger.info(
        "[coldstart] model=%s input=%d output=%d elapsed=%.1fms",
        COLDSTART_MODEL, input_tokens, output_tokens, elapsed_ms,
    )
    print(
        f"[coldstart] model={COLDSTART_MODEL} input={input_tokens} "
        f"output={output_tokens} elapsed={elapsed_ms}ms"
    )

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM returned non-JSON response: {raw_text!r}"
        ) from exc

    signals = TasteSignals(
        genres=parsed.get("genres", []),
        keywords=parsed.get("keywords", []),
        reference_titles=parsed.get("reference_titles", []),
        mood=parsed.get("mood", "neutral"),
    )
    return signals, input_tokens, output_tokens, elapsed_ms


def _ground_signals(signals: TasteSignals, item_type_filter: str) -> list[str]:
    """
    Translate taste signals into real dataset IDs via store.search().

    Priority 1: reference_titles  → exact title search
    Priority 2: keywords          → keyword search, top-1 per kw
    Priority 3 (fallback):        genre intersection, sorted by popularity

    item_type_filter values: "movies" → "movie", "shows" → "show", anything else → "all"
    """
    type_map = {"movies": "movie", "shows": "show"}
    item_type = type_map.get(item_type_filter.lower(), "all")

    seen:  set[str]  = set()
    seeds: list[str] = []

    def _add(item_id: str) -> None:
        if item_id not in seen:
            seen.add(item_id)
            seeds.append(item_id)

    # Priority 1 — reference titles
    for title in signals.reference_titles:
        if len(seeds) >= COLDSTART_SEED_COUNT:
            break
        results = store.search(title, item_type, COLDSTART_SEARCH_LIMIT)
        if results:
            _add(str(results[0]["id"]))

    # Priority 2 — keywords
    for kw in signals.keywords:
        if len(seeds) >= COLDSTART_SEED_COUNT:
            break
        results = store.search(kw, item_type, COLDSTART_SEARCH_LIMIT)
        if results:
            _add(str(results[0]["id"]))

    # Priority 3 — genre fallback
    if len(seeds) < COLDSTART_SEED_COUNT:
        target_genres = {g.lower() for g in signals.genres}

        if item_type == "movie":
            pool = store.all_movies()
        elif item_type == "show":
            pool = store.all_shows()
        else:
            pool = store.all_items()

        def _genre_overlap(item: dict) -> int:
            item_genres = {g.lower() for g in item.get("genres", [])}
            return len(item_genres & target_genres)

        candidates = sorted(
            pool,
            key=lambda x: (_genre_overlap(x), x.get("popularity", 0)),
            reverse=True,
        )
        for item in candidates:
            if len(seeds) >= COLDSTART_SEED_COUNT:
                break
            _add(str(item["id"]))

    return seeds


# ── Public entry point ────────────────────────────────────────────────────────

def get_coldstart_recommendations(
    answers: UserAnswers,
    top_k: int = DEFAULT_TOP_K,
) -> ColdStartResult:
    """
    Full cold-start pipeline: LLM extraction → grounding → BFS recommendations.

    Returns a ColdStartResult with recommendations=[] if no seeds could be
    grounded (no exception raised — the route handler gets a clean 200).
    """
    from core.graph import graph  # local import avoids circular dependency at module load

    total_t0 = time.perf_counter()

    signals, input_tokens, output_tokens, llm_time_ms = _call_llm(answers)
    seed_ids = _ground_signals(signals, answers.q1_media_type)

    if not seed_ids:
        total_ms = round((time.perf_counter() - total_t0) * 1000, 2)
        return ColdStartResult(
            recommendations=[],
            seed_ids=[],
            signals=signals,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            llm_time_ms=llm_time_ms,
            total_time_ms=total_ms,
        )

    recommendations = recommend_bfs(graph.adjacency_list, seed_ids, top_k)
    total_ms = round((time.perf_counter() - total_t0) * 1000, 2)

    return ColdStartResult(
        recommendations=recommendations,
        seed_ids=seed_ids,
        signals=signals,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        llm_time_ms=llm_time_ms,
        total_time_ms=total_ms,
    )
