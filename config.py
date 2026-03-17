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
