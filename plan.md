# Signal Scout — Build Plan

## Context

Greenfield repo (only `README.md`). Building Signal Scout for Cory Levy / Z Fellows interview (July 14). Product finds exceptional people before breakout by collecting public signals, resolving identities, scoring, and surfacing discoveries. The **backtest is the pitch**, the **digest is the demo**.

**Locked decisions:**
- **Design:** Match the pasted image, NOT spec §11.1. Light cream background (`#F5F3EC`-ish), olive/green accents (`#6B6B32`-ish), serif display headers, monospaced metadata/scores/dates/sources. Thin borders, restrained radius. Editorial-intelligence feel, not dark terminal.
- **Data:** Live GitHub scraper (real REST/GraphQL). Everything else seeded JSON + manual entry. `ground_truth.json` hand-built. Scraping must never block the demo.
- **Digest:** Preview + generate only. No real email send (Resend stubbed behind an interface, not wired).
- **Frontend:** React + Tailwind (Vite), trimmed to the 3 tabs in the image — **Discover, Backtest, Digest**. Concentrations = API only, no page yet.
- **Priorities (working backward from July 14):** the backtest headline number and the digest with real unknowns + contact info are non-negotiable. Everything else is supporting material. If forced to choose between a polished dashboard and a compelling digest, choose the digest. Don't automate what can be done manually for 10 people — hand-verify contact info for digest picks.

**New per-candidate data points (added to spec):**
- **Location/origin** — `origin_location` + `current_location` on persons. Sources: GitHub bio location field, school name → city/state mapping (`school_locations.json`), competition metadata (USACO lists state), Twitter bio when available. Feeds `ConcentrationDetector` so it flags regions, not just schools ("4 flagged candidates from the Research Triangle in 2 years").
- **Connections** — typed edges in `graph_edges` beyond GitHub follows: `github_follows`, `mutual_star`, `co_author` (Semantic Scholar gives this free), `hackathon_teammate` (Devpost), `fellowship_cohort`, `twitter_follows` (seeded/manual only). Connection count to seed founders becomes a scored signal (weight 3). Each profile shows connection context ("followed by 4 known founders on GitHub, co-authored with a known AI researcher") — this is what makes Cory trust an unknown.
- **Contact info** — `email`, `linkedin_url`, `twitter_handle`, `personal_site` columns + `contact_info` JSON catch-all on persons. Sources: GitHub public email, bio parsing for X handle + personal site, Semantic Scholar author emails, generated LinkedIn search URL (`site:linkedin.com/in "name" school`) — never scrape LinkedIn directly. Digest entries get one-click LinkedIn/X/email links so Cory can reach out immediately. Hand-verify for everyone in the digest: minimum LinkedIn + one other method.

**Design principles:** high modularity (one clear purpose per file, split on natural seams), class-based everywhere for dependency injection, folder structure as a first-class concern.

---

## Architecture

```
scrapers (classes) -> raw Signal records -> SQLite (via Repositories)
      -> EntityResolver -> ScoringEngine -> API (FastAPI) -> React dashboard
                                         -> BacktestRunner
                                         -> DigestGenerator
```

**Layering (each layer a class, injected into the next — no global singletons):**
1. **Domain models** — plain dataclasses (`Signal`, `Person`, `Concentration`, `DigestEntry`). No behavior beyond validation.
2. **Repositories** — one class per table wrapping SQLite. `PersonRepository`, `SignalRepository`, `GraphEdgeRepository`, `ConcentrationRepository`, `DigestRepository`. Take a `Database` (connection provider) in their constructor.
3. **Scrapers** — `BaseScraper` (abstract) + one subclass per source. Each returns `list[Signal]`. Only `GithubScraper` hits the network; others read seeded JSON via a shared `SeededScraper` base.
4. **Services / engines** — `ScoringEngine`, `BacktestRunner`, `EntityResolver`, `GraphExpander`, `ConcentrationDetector`, `DigestGenerator`. Each takes its repo/config dependencies in `__init__`.
5. **API** — FastAPI routers, thin. Depend on services via a `Container`.
6. **Container** — one wiring class that constructs DB, repos, services and hands them to FastAPI dependency overrides. This is the DI root.

---

## Folder structure

Follows spec §14 with the locked-decision trims.

```
signalScout/
├── backend/
│   ├── main.py                 # FastAPI app factory, mounts routers, builds Container
│   ├── container.py            # DI root: wires Database -> repos -> services
│   ├── config.py               # settings (paths, GitHub token, seed files) via env
│   ├── db/
│   │   ├── database.py         # Database class: connection, schema init, migrations
│   │   ├── schema.sql          # SQLite DDL (UUID/date/JSON as TEXT per spec §13)
│   │   └── repositories/
│   │       ├── base.py         # BaseRepository (shared row->model helpers)
│   │       ├── persons.py
│   │       ├── signals.py
│   │       ├── graph_edges.py
│   │       ├── concentrations.py
│   │       └── digests.py
│   ├── domain/
│   │   ├── signal.py           # Signal dataclass (the standard record, spec §4)
│   │   ├── person.py           # Person / ResolvedPerson dataclass (spec §6)
│   │   ├── concentration.py
│   │   └── digest.py           # DigestEntry
│   ├── scrapers/
│   │   ├── base.py             # BaseScraper (abstract .scrape()->list[Signal])
│   │   ├── seeded.py           # SeededScraper: loads list[Signal] from JSON fixtures
│   │   ├── github_scraper.py   # LIVE: GithubClient wrapper + signal derivation
│   │   ├── usaco.py            # seeded
│   │   ├── math_competitions.py# seeded (AMC/AIME/USAMO)
│   │   ├── imo_ioi.py          # seeded
│   │   ├── regeneron.py        # seeded (STS/ISEF)
│   │   ├── devpost.py          # seeded
│   │   ├── scholar.py          # seeded (Semantic Scholar shape)
│   │   ├── fellowships.py      # seeded (ground-truth labels + graph seeds)
│   │   └── debate.py           # seeded (NSDA)
│   ├── scoring/
│   │   ├── weights.py          # WEIGHTS table + signal_type->weight (spec §7.1)
│   │   ├── engine.py           # ScoringEngine.compute_score() (spec §7.2) + normalize 0-100
│   │   └── backtest.py         # BacktestRunner: recall, lead time, precision, distributions
│   ├── discovery/
│   │   ├── entity_resolution.py# EntityResolver (normalize, join keys, merge/flag)
│   │   ├── graph_expansion.py  # GraphExpander (one-hop follower crossref, typed edges)
│   │   └── concentrations.py   # ConcentrationDetector (school/program/geo/region grouping)
│   ├── enrichment/
│   │   ├── contacts.py         # ContactEnricher: email/X/site from GitHub, LinkedIn search URL
│   │   └── locations.py        # LocationResolver: bio + school -> origin/current location
│   ├── digest/
│   │   ├── generator.py        # DigestGenerator: pick top N, build entries + thesis
│   │   ├── sender.py           # EmailSender interface + NoopSender (Resend stub, not wired)
│   │   └── template.html       # digest HTML for preview
│   └── api/
│       ├── routes.py           # routers for all spec §16 endpoints
│       └── schemas.py          # Pydantic response/request models
├── frontend/
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js      # theme tokens: cream bg, olive accent, serif+mono fonts
│   ├── package.json
│   └── src/
│       ├── main.jsx
│       ├── App.jsx             # top nav (Discover/Backtest/Digest) + router
│       ├── api/client.js       # fetch wrapper to backend
│       ├── theme/tokens.css    # colors, fonts matching the image
│       ├── pages/
│       │   ├── Discover.jsx    # the hero candidate card from image + Browse all
│       │   ├── Backtest.jsx    # recall/lead-time metrics + score distribution
│       │   └── Digest.jsx      # "N people you should know" preview + generate
│       └── components/
│           ├── CandidateCard.jsx   # #001, avatar initials, score, thesis, top signals
│           ├── CandidateTable.jsx  # Browse-all dense table (spec §11.4)
│           ├── SignalBadge.jsx     # bordered signal chip (star/trophy/paper icons)
│           ├── SignalTimeline.jsx  # horizontal timeline w/ breakout marker
│           ├── ScoreDistribution.jsx # founder vs control chart
│           └── EvidenceTable.jsx   # signal/date/strength/source/why
├── data/
│   ├── ground_truth.json       # hand-built founders/fellows (spec §15 shape) + control group
│   ├── seed_accounts.json      # GitHub/Twitter seed usernames for graph expansion
│   ├── school_locations.json   # school name -> city/state/region for LocationResolver
│   └── seed_signals/           # per-source seeded signal fixtures (usaco.json, etc.)
├── scripts/
│   ├── run_scrapers.py         # run all scrapers -> store signals
│   ├── run_backtest.py         # compute + print backtest report
│   ├── run_discovery.py        # graph expansion -> candidates
│   └── build_db.py             # init schema + load ground truth + seeded signals
├── requirements.txt
└── README.md
```

---

## Core functionality (how it works)

### Signal model (spec §4)
`Signal` dataclass: `person_name, signal_type, signal_category, signal_date, signal_strength (0-1), source_url, raw_data, metadata`. Every scraper emits these. Persisted in `signals` table keyed to a `person_id` after resolution.

### Person model (spec §6 + new fields)
`persons` gains: `email`, `linkedin_url`, `twitter_handle`, `personal_site`, `origin_location`, `current_location`, and `contact_info` (JSON TEXT catch-all). `graph_edges` gains an `edge_type` column (`github_follows | mutual_star | co_author | hackathon_teammate | fellowship_cohort | twitter_follows`) plus `source` and `observed_date` so connection signals can be backtested (only count edges observed before breakout).

### Scrapers
- `BaseScraper.scrape() -> list[Signal]` abstract.
- `SeededScraper(source_file)` loads a JSON fixture and maps rows to `Signal`s using per-source strength tables from the spec (USACO Gold 0.7 / Plat 0.85 / Camp 1.0, AMC/AIME/USAMO, IMO/IOI, Regeneron, NSDA, Devpost, Scholar).
- `GithubScraper` is the only live one: wraps a `GithubClient` (authenticated REST/GraphQL, ~5k/hr). Per username collects account age, repos, stars/forks/langs, contributions/yr, followers/following, orgs, bio/location/links, **public email, and social accounts** (GitHub's `social_accounts` endpoint surfaces linked Twitter/LinkedIn for many users — cheapest contact-info source we have). Derives signals per spec §5.2 (early builder 0.7, star project 0.6/0.9, prolific 0.5, connected variable) and emits `github_follows` edges. Token from `config.py` (env `GITHUB_TOKEN`). Graceful degradation + rate-limit handling; failures recorded as coverage gaps, never fatal.

### Enrichment (new)
- `ContactEnricher.enrich(person)`: GitHub public email → `email`; bio/website regex for X handle and personal site; Semantic Scholar author email when a co-author edge exists; always generates `linkedin_search_url` (`site:linkedin.com/in "name" school`) into `contact_info` — LinkedIn is never scraped, the top 10–20 digest candidates get hand-verified `linkedin_url`s. Idempotent: never overwrites a manually-entered value.
- `LocationResolver.resolve(person)`: `current_location` from GitHub/Twitter bio; `origin_location` from school (via `school_locations.json`) or competition metadata (USACO state). Also normalizes to a `region` bucket (e.g. Bay Area, Research Triangle, Toronto–Waterloo) used by `ConcentrationDetector`.

### Entity resolution (spec §6)
`EntityResolver`: normalize names (lowercase, strip middle initials, Unicode), compare school/city/time window, use GitHub bio/website/linked socials as join keys. Merge confident matches into a `Person`; keep ambiguous separate and flag `needs_review`. Manual-correction friendly (idempotent, re-runnable).

### Scoring (spec §7)
`ScoringEngine.compute_score(person, today)` implements the exact formula: raw = Σ strength·weight; diversity multiplier `1 + 0.15·(categories-1)`; recency bonus `0.1` per signal <730 days; age factor from graduation_year (1.4 <18, 1.2 <20). Then **normalize to 0–100** across the cohort. Weights live in `weights.py`, tunable against backtest. Every score is decomposable into its contributing signals (needed for the evidence UI).

**Connection signal (new, weight 3):** derived from `graph_edges` — count of distinct seed founders a person is connected to (any edge type) as of the scoring date. Strength scales with count and edge quality (a `co_author` edge with a known researcher > a follow). In the backtest, only edges with `observed_date < breakout_date` count.

### Backtest (spec §8) — the pitch
`BacktestRunner`: for each ground-truth person, drop signals dated after `breakout_date`, recompute score on pre-breakout evidence only, apply tunable threshold, record flagged? + lead time. Reports recall by cohort, avg lead time, precision/false-positive, founder-vs-control distributions, most-predictive signals. Control group = 50–100 seeded random CS undergrads from GitHub. Also reports **connection stats** (how many flagged founders were already connected to other seed founders pre-breakout) and **concentration stats** (which schools/cities/regions produced the most flagged candidates) — both are strong talking points for the pitch.

### Discovery (spec §10) — feeds the demo
`GraphExpander`: seed with the top ~30 ground-truth GitHub usernames, pull one-hop followers/following, for each unknown check for an independent competition/code/hackathon/research signal, create+score a profile only when evidence exists, keep above-threshold as discoveries. Writes typed `graph_edges` as it goes. Discoveries then pass through `ContactEnricher` + `LocationResolver`; the top 10–15 get manual enrichment (verified LinkedIn, X handle, email, location) before entering the digest.

### Concentrations (spec §9)
`ConcentrationDetector.find(candidates)`: group by school/program/geo **and region** (via `LocationResolver` buckets), flag any source with 3+ flagged candidates, sorted by count. Persisted to `concentrations`. API only for now (no page).

### Digest (spec §11.7 / §12) — the killer moment
`DigestGenerator`: pick top 5–10 likely-unknown candidates, build each entry: name, age/school if known, one-line thesis, where they're from, top-3 signal tags, **connection context** ("followed by 4 known founders on GitHub"), "why now", evidence links, and **one-click contact links** (GitHub, LinkedIn, X, mailto). Render via `template.html` for preview. `sender.py` defines `EmailSender` interface with a `NoopSender`; Resend stays a stub, not wired. Rule: no one enters the digest without a verified LinkedIn + one other contact method.

### API (spec §16)
FastAPI routers, thin, service-backed via `Container`:
`GET /api/overview`, `/api/candidates`, `/api/candidates/{id}`, `/api/backtest`, `/api/concentrations`, `/api/digests/latest`, `POST /api/digests/generate`, `POST /api/digests/send` (returns preview, no real send), optional `POST /api/scrapers/run`.

---

## Frontend (matches the image)

**Theme tokens (`tailwind.config.js` + `tokens.css`):** cream page bg, off-white card, olive/green primary for the "View Evidence" button and accents, near-black serif for display headers (candidate names, "Signal Scout"), monospaced for score number, dates, source labels, `#001` rank. Thin 1px borders, small radius, generous whitespace but data-forward.

**Discover page:** center hero `CandidateCard` exactly like the image — rank `#001`, circular initials avatar with the thin progress arc, serif name, `School • Area` subline (location shown when known), `SIGNAL SCORE` + big mono number, `THESIS`, three bordered `SignalBadge`s (star/trophy/paper), a one-line connection context row ("connected to 3 seed founders"), mono contact-link row (GitHub / LinkedIn / X / email when present), olive `View Evidence →` + outlined `Add to Digest`. `Previous / N of M / Next / Browse all`. "Browse all" swaps to `CandidateTable` — sortable/filterable, with **location and connections columns**. Area filter dropdown at top.

**Backtest page:** headline metric (% flagged + avg lead time), `ScoreDistribution` (founder vs control), top predictive signals, one example `SignalTimeline` with breakout marker.

**Digest page:** "N people you should know this week", stacked candidate blocks (name, thesis, where they're from, top-3 signals, connection context, why-now, evidence links, contact links), Generate button, disabled/preview Send.

**Deferred (only if time allows):** mini network visualization on profile pages (`ConnectionGraph` component — candidate node + seed-founder nodes with typed edges). The connection context *sentence* ships regardless; the visualization is polish.

---

## Build order

Follows spec §17 recommended order, trimmed to locked decisions. Each step independently runnable/verifiable.

1. **Foundation** — `requirements.txt`, `config.py`, domain dataclasses, `Database` + `schema.sql` (incl. new person contact/location columns + typed `graph_edges`), repositories, `build_db.py`. Verify: schema creates, repos round-trip a row.
2. **Ground truth + seed data** — hand-build `data/ground_truth.json`: 30–50 known founders with breakout dates, fellowship info, GitHub usernames, Twitter handles, schools, locations (Z Fellows alumni, Thiel Fellowship list, 10–15 obvious names: Vitalik, Alexandr Wang, Shayne Coplan, etc.) + 50–100 control-group CS students from GitHub. Also `seed_accounts.json`, `school_locations.json`, and `data/seed_signals/*.json` for competitions (USACO + IMO first — cleanest data; if HTML is messy/anti-bot, manually enter results for backtest subjects rather than fighting scrapers). This is the backbone — nothing works without it.
3. **GitHub scraper (live)** — `GithubClient` + `GithubScraper` (profile, repos, followers/following, email, social accounts), `run_scrapers.py`. Verify: real fetch for a known username produces derived signals + edges + contact fields.
4. **Scoring + backtest** — `weights.py` (incl. connection signal, weight 3), `ScoringEngine`, `BacktestRunner`, `run_backtest.py`. Verify: prints recall / lead time / control separation on ground truth — the headline "would have flagged X% of fellows Y months before selection."
5. **Seeded scrapers** — `SeededScraper` + USACO / math / IMO-IOI / Regeneron / Devpost / Scholar / fellowships / debate from fixtures. Verify: signals load and attach to persons.
6. **Entity resolution + enrichment** — `EntityResolver`, `ContactEnricher`, `LocationResolver`, integrate into `build_db`/scrape flow. Verify: aliases merge, ambiguous flagged, known founders get contact fields + locations populated.
7. **API layer** — `Container`, routers, schemas, `main.py`. Verify: all §16 endpoints return real data (candidates include contact/location/connection fields).
8. **Frontend** — Vite scaffold, theme tokens, `api/client.js`, App nav, Discover (card + table with location/connection columns), Backtest, Digest, shared components. Verify: matches image, live data from API.
9. **Discovery + concentrations** — `GraphExpander` (top ~30 seeds, one hop), `ConcentrationDetector` (school + region), `run_discovery.py`, wire into candidates + `/api/concentrations`. Then manually enrich the top 10–15 discoveries (LinkedIn, X, email, location). Verify: discoveries surface with evidence and contact info.
10. **Digest** — `DigestGenerator`, `template.html` (contact links, connection context, location), `NoopSender`, generate endpoint + Digest page. Verify: preview renders 5–10 evidence-backed people, each with LinkedIn + one other contact method.

**Cut / deferred:** live scraping for non-GitHub sources, real Resend send, live Twitter/X, LinkedIn scraping (search-URL generation only), two-hop expansion, Concentrations page, network visualization component, dark theme.

**Cut order if running out of time (from spec + user guidance):** charts/concentration page first, then Discover hero polish (fall back to table-only single page), then seeded long-tail scrapers (Regeneron/debate/Devpost). Never cut: backtest number, digest with real unknowns + contact info, candidate table with working sort/filter.

---

## Verification

- **Unit-ish per layer:** repo round-trip, `ScoringEngine` against the spec formula worked example, `EntityResolver` merge cases.
- **Backtest report (the pitch):** `python scripts/run_backtest.py` prints recall %, avg lead time, founder-vs-control distributions — the headline metric for the interview.
- **API smoke:** `uvicorn backend.main:app` + curl each §16 endpoint for non-empty, source-linked payloads.
- **Frontend end-to-end:** `npm run dev`, load Discover/Backtest/Digest in browser, confirm the hero card matches the pasted image (cream/olive/serif/mono), score explainable via View Evidence, digest preview shows evidence-backed unknowns. Confirm visually — do not claim UI success without loading it.
- **Demo dry-run against §19 success criteria:** defensible early-ID metric, founder/control separation, current candidates with sources, one pre-breakout timeline, polished digest, an explanation for every candidate.

---

## MVP ideation — extra ideas worth the marginal effort

Ranked by demo-impact per hour. Each is small because the data layer above already supports it.

1. **"Why now" urgency line per digest entry** — a rule-based sentence from recent signals: "starred repo doubled in 60 days", "just won USACO Plat as a junior", "3 new seed-founder follows this quarter". Turns a static list into a call to action. (~30 min once signals exist.)
2. **Warm-intro path** — for each digest candidate, name the specific seed founder(s) they're connected to: "Reach out via <seed founder>, who follows them on GitHub." Cory doesn't just get contact info, he gets an intro route. Direct read off `graph_edges`. (~20 min.)
3. **Velocity/trajectory framing** — where cheap, compare a signal's earliest vs latest observation (follower count, star count in `raw_data`) and tag candidates as "rising". Even two data points make the pitch "we catch people while they're inflecting", which is the whole thesis. (Keep to GitHub only.)
4. **"Known vs unknown" flag** — a simple heuristic (in ground truth? >N followers? has a funded company in seed data?) so Discover can filter to *unknowns only*. The demo moment is showing people Cory has never heard of; make that one click.
5. **Score explanation strings** — every score renders as an itemized receipt ("USACO Gold 0.7×8 + co-author edge 0.6×3 + diversity ×1.15"). Falls out of the decomposable scoring engine; makes "why should I trust this number" unanswerable to fail.
6. **Coverage/confidence tag per candidate** — LOW/MED/HIGH based on how many sources contributed. Preempts the "is this just GitHub stalking?" question and shows intellectual honesty in the interview.
7. **Digest as shareable HTML file** — since Resend is stubbed, write the rendered digest to `out/digest-YYYY-MM-DD.html` so it can be opened full-screen in a browser during the interview (and screenshotted for follow-up). Nearly free.
8. **One rehearsed founder story** — pick one ground-truth founder with a rich pre-breakout timeline and make their profile page perfect (timeline, signals, connections). Demos open strongest on a narrative: "here's what the system saw about X two years before Z Fellows did."

**Explicitly not doing for MVP:** ML-learned weights (hand-tuned + backtest-validated is more explainable), real-time alerting, auth/multi-user, Twitter API integration (seeded edges only), any LinkedIn automation.

---

## Open notes / assumptions

- GitHub token required for the live scraper; reads `GITHUB_TOKEN` from env and degrades gracefully if absent (falls back to seeded GitHub signals so the demo never breaks).
- SQLite per spec; UUIDs/dates/JSON stored as TEXT, generated in app code.
- Resend kept behind `EmailSender` so it can be wired later without touching `DigestGenerator`.

---

## Session-by-session plan (context-safe increments)

Do not try to build all 10 steps in one session. Each session = one build-order step, ending with its verify. Suggested chunking:

- **Session A:** Step 1 (Foundation) + Step 2 (ground truth + seed data). Maps to user Phase 1.
- **Session B:** Step 3 (GitHub scraper) + Step 4 (scoring + backtest). Produces the pitch metric. Maps to Phases 2–3.
- **Session C:** Step 5 (seeded scrapers) + Step 6 (entity resolution + enrichment).
- **Session D:** Step 7 (API layer). All endpoints live.
- **Session E:** Step 8 (frontend). The visible demo.
- **Session F:** Step 9 (discovery + manual enrichment of top picks) + Step 10 (digest). Completes the demo. Maps to Phases 4–5.

At the start of each session, re-read this `plan.md` and the relevant spec sections, then implement only that session's step(s).
