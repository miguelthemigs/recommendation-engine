# Rec-Engine Architecture

```
                            ┌─────────────────────────────────────────────────────────────────────┐
                            │                        FRONTEND  (React + Vite)                      │
                            │                         localhost:5173                                │
                            │                                                                      │
                            │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌───────────────────┐  │
                            │  │ BrowsePage │ │ SearchPage │ │ Watchlist  │ │  ColdStartPage    │  │
                            │  │ /movies    │ │ /search    │ │   Page     │ │  /discover        │  │
                            │  │ /shows     │ │            │ │ /watchlist │ │  5-Q survey       │  │
                            │  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └────────┬──────────┘  │
                            │        │              │              │                 │             │
                            │  ┌─────┴──────┐       │        ┌─────┴──────┐          │             │
                            │  │ ItemDetail │       │        │ Compare    │          │             │
                            │  │   Page     │       │        │ Panel      │          │             │
                            │  │ Jaccard vs │       │        │ 3 algos    │          │             │
                            │  │ TF-IDF     │       │        │ + overlap  │          │             │
                            │  └─────┬──────┘       │        └─────┬──────┘          │             │
                            │        │              │              │                 │             │
                            │  ┌─────┴──────────────┴──────────────┴─────────────────┴──────────┐  │
                            │  │                    Context Providers                            │  │
                            │  │  WatchlistContext (localStorage)  │  BenchmarkContext (session) │  │
                            │  │  ColdStartContext (session)                                    │  │
                            │  └─────────────────────────┬──────────────────────────────────────┘  │
                            │                            │                                         │
                            │  ┌─────────────────────────┴──────────────────────────────────────┐  │
                            │  │              API Layer  (api/client.ts + endpoints.ts)          │  │
                            │  │              fetch() → http://localhost:8000/*                  │  │
                            │  └─────────────────────────┬──────────────────────────────────────┘  │
                            └────────────────────────────┼─────────────────────────────────────────┘
                                                         │
                                                    HTTP (JSON)
                                                         │
┌────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────┐
│                                   BACKEND  (FastAPI + Uvicorn)                                               │
│                                    localhost:8000                                                             │
│                                                        │                                                     │
│   ┌────────────────────────────────────────────────────┴──────────────────────────────────────────────────┐   │
│   │                              api/routes.py  (thin HTTP layer)                                         │   │
│   │                                                                                                       │   │
│   │   GET /movies, /shows          GET /search         POST /recommend/watchlist/*    POST /coldstart     │   │
│   │   GET /movies/:id, /shows/:id  GET /recommend/*    POST /recommend/watchlist/compare                  │   │
│   │   GET /stats, /graph/stats     GET /recommend/compare/:id                                             │   │
│   └───────┬──────────────────────────┬──────────────────────┬────────────────────────────┬────────────────┘   │
│           │                          │                      │                            │                    │
│           ▼                          ▼                      ▼                            ▼                    │
│   ┌───────────────┐   ┌──────────────────────────────────────────────────┐   ┌─────────────────────────┐     │
│   │  core/store   │   │           RECOMMENDATION ENGINES                 │   │   core/coldstart.py     │     │
│   │   (RAM)       │   │                                                  │   │                         │     │
│   │               │   │  ┌─────────────────┐  ┌───────────────────────┐  │   │  UserAnswers (5 Q's)    │     │
│   │ _movies{}     │   │  │ Jaccard Graph   │  │   TF-IDF Index       │  │   │        │                │     │
│   │ _shows{}      │   │  │ core/graph.py   │  │   core/tfidf.py      │  │   │        ▼                │     │
│   │ _genres{}     │   │  │                 │  │                      │  │   │  ┌───────────┐          │     │
│   │               │   │  │ similarity.py   │  │ TfidfVectorizer      │  │   │  │  OpenAI   │          │     │
│   │ get_item()    │   │  │ Jaccard on:     │  │ cosine_similarity    │  │   │  │ GPT-4o-   │          │     │
│   │ all_items()   │   │  │ • genres 0.45   │  │ on overviews         │  │   │  │   mini    │ ◄──────────── External
│   │ search()      │   │  │ • keywords 0.35 │  │                      │  │   │  └─────┬─────┘          │     │
│   │ stats()       │   │  │ • cast 0.20     │  │ adjacency_list{}     │  │   │        │                │     │
│   │               │   │  │                 │  │ top-20 neighbors     │  │   │        ▼                │     │
│   └───────────────┘   │  │ adjacency_list{}│  └───────────────────────┘  │   │  TasteSignals          │     │
│           ▲           │  │ top-20 neighbors│                             │   │  (genres, keywords,    │     │
│           │           │  └────────┬────────┘                             │   │   mood, ref titles)    │     │
│           │           │           │                                      │   │        │                │     │
│           │           │  ┌────────┴──────────────────────────────────┐   │   │        ▼                │     │
│           │           │  │         WATCHLIST ALGORITHMS              │   │   │  _ground_signals()     │     │
│           │           │  │                                           │   │   │  search store for      │     │
│           │           │  │  ┌──────────┐ ┌─────────┐ ┌───────────┐  │   │   │  matching seed items   │     │
│           │           │  │  │  Direct  │ │  BFS    │ │ PageRank  │  │   │   │        │                │     │
│           │           │  │  │  Agg.    │ │ Depth-2 │ │ Personal. │  │   │   │        ▼                │     │
│           │           │  │  │ O(W×K)  │ │ O(W×K²) │ │ Iterative │  │   │   │  BFS expansion         │     │
│           │           │  │  │         │ │ decay   │ │ d=0.85    │  │   │   │  from seed set          │     │
│           │           │  │  │         │ │ =0.5    │ │ 20 iters  │  │   │   │        │                │     │
│           │           │  │  └──────────┘ └─────────┘ └───────────┘  │   │   │        ▼                │     │
│           │           │  └──────────────────────────────────────────┘   │   │  ColdStartResult       │     │
│           │           └──────────────────────────────────────────────────┘   └─────────────────────────┘     │
│           │                                                                                                  │
│   ┌───────┴───────────────────────────────────────────────────────────────┐                                   │
│   │                     main.py  (Startup / Lifespan)                      │                                   │
│   │                                                                        │                                   │
│   │   1. store.load()   →  JSON files → RAM                               │                                   │
│   │   2. graph.build()  →  O(N²) Jaccard pairwise → adjacency list        │                                   │
│   │   3. tfidf.build()  →  O(N²) cosine similarity → adjacency list       │                                   │
│   └───────┬────────────────────────────────────────────────────────────────┘                                   │
│           │                                                                                                   │
└───────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
   ┌─────────────────┐         ┌──────────────────────────────────────────────────────────┐
   │   data/*.json   │         │              TMDB API  (setup-time only)                 │
   │                 │ ◄────── │              api.themoviedb.org/3                        │
   │ movies.json     │         │                                                          │
   │ shows.json      │         │  scripts/fetch_tmdb.py  →  scripts/tmdb_client.py       │
   │ genres.json     │         │  Run once: fetches movies, shows, genres, keywords, cast │
   └─────────────────┘         └──────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════
                           DATA FLOW SUMMARY
═══════════════════════════════════════════════════════════════════════════════

  SETUP (one-time):    TMDB API ──► JSON cache files (data/*.json)

  STARTUP (per boot):  JSON files ──► RAM store ──► Jaccard graph + TF-IDF index

  RUNTIME (per req):   RAM lookups only ──► O(1) neighbor queries ──► JSON response

  COLD-START:          Survey ──► OpenAI LLM ──► Taste signals ──► Seed search ──► BFS

  PERSISTENCE:         Backend: all in-memory (rebuilt on restart)
                       Frontend: watchlist in localStorage, rest in React context
```
