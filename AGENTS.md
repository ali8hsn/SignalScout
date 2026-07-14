# AGENTS.md

## Learned User Preferences

- Candidates and signals must be REAL people scraped from live public sources, never fake, mocked, or synthetic data.
- Prefer building genuinely functional features over faked demos or animations (e.g., a real "Run Discovery" pipeline trigger with live progress, not a staged animation).
- The backtest should run against known founders to prove the tool surfaces people before they became well-known, while keeping real customer discovery intact for the actual use case.
- Push code to the user's own GitHub account (`ali8hsn`).
- The end audience for the product/demo is an investor named Cory; framing and "warm signal" logic should optimize for what Cory would trust.

## Learned Workspace Facts

- "Signal Scout" (`signalScout`) finds exceptional people before they break out by collecting public signals (competitions, code, research, hackathons, network), scoring them, and backtesting against known founders.
- Stack: FastAPI + SQLite backend; Vite + React + Tailwind frontend with three tabs (Discover, Backtest, Digest). SQLite DB is `signal_scout.db`.
- Backend layering: domain dataclasses → repositories → scrapers → scoring/backtest → discovery/enrichment → digest → API, wired by `backend/container.py`.
- Data sources include GitHub, Twitter/X, USACO competitions, Semantic Scholar (co-authors), Devpost hackathons, and LinkedIn; typed relationships are stored in the `graph_edges` table.
- Scoring formula: `score = (Σ strength×weight + recency bonus) × diversity × age factor`, normalized 0–100 across the cohort; weights live in `backend/scoring/weights.py`.
- Key scripts: `scripts/build_db.py`, `run_backtest.py`, `run_scrapers.py`, `run_discovery.py`. Live scrapers require `GITHUB_TOKEN` and are optional (never required for the demo).
- Backend runs via `uvicorn backend.main:app --port 8000`; frontend dev server runs on port 5173.
- `plan.md` is a reference spec — do not edit it when implementing its to-dos.
