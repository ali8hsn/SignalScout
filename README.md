# Signal Scout

Finds exceptional people **before** they break out, by collecting public signals
(competitions, code, research, hackathons, network), scoring them, and backtesting
against known founders. The backtest is the pitch; the digest is the demo.

## Quick start

```bash
# backend
pip install -r requirements.txt
python scripts/build_db.py          # build DB: ground truth + seeds + scoring
python scripts/run_backtest.py      # print the pitch metric
uvicorn backend.main:app --port 8000

# frontend (separate terminal)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

Optional live data (never required for the demo):

```bash
GITHUB_TOKEN=... python scripts/run_scrapers.py    # live GitHub signals for known usernames
GITHUB_TOKEN=... python scripts/run_discovery.py   # one-hop graph expansion from seed accounts
```

## Layout

- `backend/` — FastAPI + SQLite. Layers: domain dataclasses → repositories → scrapers →
  scoring/backtest → discovery/enrichment → digest → API. Wired by `backend/container.py`.
- `data/` — hand-curated ground truth (30 founders + researcher anchors), seed signal
  fixtures per source, school→location map, seed accounts for graph expansion.
- `frontend/` — Vite + React + Tailwind. Three tabs: Discover, Backtest, Digest.
- `scripts/` — `build_db.py`, `run_backtest.py`, `run_scrapers.py`, `run_discovery.py`.
- `out/` — generated digest HTML (shareable artifact).

## How scoring works

`score = (Σ strength×weight + recency bonus) × diversity × age factor`, normalized 0–100
across the cohort. Weights live in `backend/scoring/weights.py`. Connections to seed
founders (typed graph edges: follows, co-authorship, hackathon teams, cohorts) are a
weight-3 signal. Every score decomposes into an itemized receipt in the UI.

The backtest recomputes each founder's score using **only** signals dated before their
breakout, with a 60-person control group for the false-positive rate.
