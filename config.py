import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

MOVIES_CACHE = DATA_DIR / "movies.json"
SHOWS_CACHE  = DATA_DIR / "shows.json"
GENRES_CACHE = DATA_DIR / "genres.json"

# ── TMDB ───────────────────────────────────────────────────────────────────────
TMDB_API_KEY  = os.getenv("TMDB_API_KEY", "")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_LANGUAGE = "en-US"          # explicit — avoids locale-based genre translations
TMDB_PAGES_TO_FETCH = 10         # 1 page = 20 items → 10 pages = ~200 per type

TOP_CAST_COUNT = 5               # how many cast members to store per title

# ── Similarity weights (must sum to 1.0) — tune these in your analysis ─────────
WEIGHT_GENRE   = 0.45
WEIGHT_KEYWORD = 0.35
WEIGHT_CAST    = 0.20

# ── Graph / Recommendations ────────────────────────────────────────────────────
DEFAULT_TOP_K       = 10
MAX_GRAPH_NEIGHBORS = 20

# ── Watchlist Algorithms ────────────────────────────────────────────────────
BFS_DECAY_FACTOR    = 0.5     # score multiplier for depth-2 neighbors in BFS
PAGERANK_DAMPING    = 0.85    # standard damping factor for random walk
PAGERANK_ITERATIONS = 20      # max iterations before forced stop
PAGERANK_EPSILON    = 1e-6    # convergence threshold (max delta per step)

# ── Cold Start ───────────────────────────────────────────────────────────────
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
COLDSTART_MODEL      = "gpt-4o-mini"
COLDSTART_MAX_TOKENS = 512
COLDSTART_SEED_COUNT = 5     # seed IDs fed into BFS
COLDSTART_SEARCH_LIMIT = 3   # store.search results taken per query

COLDSTART_QUESTIONS: list[str] = [
    "Do you prefer movies, TV shows, or both?",
    "Which genres interest you? (e.g. Action, Drama, Comedy, Thriller, Horror, Sci-Fi)",
    "Name a title you've enjoyed recently — doesn't have to be in our database.",
    "How do you feel about dark or intense content? (fine with it / prefer lighter / no preference)",
    "Are you looking for something familiar or something you've never seen before?",
]

COLDSTART_PROMPT_V1 = """You are a recommendation assistant. A user answered 5 onboarding questions.
Extract structured taste signals from their answers.

Q1 (movie/show/both): {q1}
Q2 (genres):          {q2}
Q3 (reference title): {q3}
Q4 (dark content):    {q4}
Q5 (familiar/new):    {q5}

Respond with ONLY valid JSON in this exact shape (no markdown, no explanation):
{{
  "genres":           ["<genre>", ...],
  "keywords":         ["<keyword>", ...],
  "reference_titles": ["<title>", ...],
  "mood":             "<light | dark | neutral>"
}}

Rules:
- genres: 2-5 genre names matching stated and implied preferences
- keywords: 3-6 thematic keywords implied by genres, title, and mood (e.g. "heist", "found family")
- reference_titles: the Q3 title plus 1-2 inferred similar titles; keep them recognizable
- mood: derive from Q4
- Return nothing outside the JSON object."""
