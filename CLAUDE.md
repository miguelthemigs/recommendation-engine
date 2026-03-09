# CLAUDE.md — Rec Engine

## Stack
FastAPI · Python 3.11+ · TMDB API v3 · JSON cache · In-memory adjacency list

## Structure
```
rec-engine/
├── api/routes.py          ← thin HTTP layer only, zero logic
├── core/
│   ├── store.py           ← in-memory store ✅
│   ├── similarity.py      ← scoring         🔲
│   └── graph.py           ← adjacency list  🔲
├── scripts/
│   ├── tmdb_client.py     ← ALL http calls here, nowhere else ✅
│   └── fetch_tmdb.py      ← fetch + cache pipeline ✅
├── main.py                ✅
└── config.py              ← ALL constants here, nowhere else ✅
```

## Rules

**Code quality**
- Typed signatures on every function
- `NotImplementedError` for stubs — never silent/fake returns
- Unbuilt endpoints return `503` with a clear message

**Maintainability**
- New data source → only touch `tmdb_client.py`
- Tune weights → only touch `config.py`
- No constants duplicated across files

**Performance**
- Build (graph + similarity) happens once at startup, never per request
- Everything served from RAM after load
- Use `time.perf_counter()` for timing
- Log build time, node count, edge count on every build

## What's next
- `core/similarity.py` → Jaccard on genres/keywords/cast + TF-IDF on overview
- `core/graph.py` → O(N²) build, adjacency list, top-K query
- Watchlist algorithms → direct aggregation, BFS depth-2, PageRank
- Benchmark all of the above and compare
