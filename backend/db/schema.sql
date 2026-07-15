-- Signal Scout SQLite schema. UUIDs, dates, and JSON stored as TEXT (spec §13).

CREATE TABLE IF NOT EXISTS persons (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    aliases TEXT NOT NULL DEFAULT '[]',
    cohort TEXT NOT NULL DEFAULT 'unknown',
    github_username TEXT,
    twitter_handle TEXT,
    linkedin_url TEXT,
    email TEXT,
    personal_site TEXT,
    contact_info TEXT NOT NULL DEFAULT '{}',
    school TEXT,
    graduation_year INTEGER,
    origin_location TEXT,
    current_location TEXT,
    region TEXT,
    fellowship TEXT,
    breakout_date TEXT,
    area TEXT,
    thesis TEXT,
    score REAL,
    needs_review INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_persons_github ON persons(github_username);
CREATE INDEX IF NOT EXISTS idx_persons_cohort ON persons(cohort);

CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY,
    person_id TEXT REFERENCES persons(id),
    person_name TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    signal_category TEXT NOT NULL,
    signal_date TEXT NOT NULL,
    signal_strength REAL NOT NULL,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    raw_data TEXT NOT NULL DEFAULT '{}',
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_signals_person ON signals(person_id);
CREATE INDEX IF NOT EXISTS idx_signals_date ON signals(signal_date);

CREATE TABLE IF NOT EXISTS graph_edges (
    id TEXT PRIMARY KEY,
    source_person_id TEXT REFERENCES persons(id),
    target_person_id TEXT REFERENCES persons(id),
    source_name TEXT NOT NULL,
    target_name TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    observed_date TEXT NOT NULL,
    source TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_edges_source ON graph_edges(source_person_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON graph_edges(target_person_id);

CREATE TABLE IF NOT EXISTS concentrations (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    key TEXT NOT NULL,
    count INTEGER NOT NULL,
    person_ids TEXT NOT NULL DEFAULT '[]',
    person_names TEXT NOT NULL DEFAULT '[]',
    computed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS digests (
    id TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    subject TEXT NOT NULL,
    entries TEXT NOT NULL DEFAULT '[]',
    html TEXT NOT NULL DEFAULT ''
);

-- Licensed-enrichment guardrails (Phase 1). Cache rows (including misses) are
-- authoritative for 30 days — never re-fetch a person inside the TTL.
CREATE TABLE IF NOT EXISTS enrichment_cache (
    cache_key TEXT PRIMARY KEY,  -- '<provider>:<person_id>'
    provider TEXT NOT NULL,
    person_id TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',  -- slim provider result; '{}' caches a miss
    fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_enrichment_cache_person ON enrichment_cache(person_id);

-- One row per UTC day; enforces DAILY_ENRICHMENT_BUDGET (skip, never error).
CREATE TABLE IF NOT EXISTS enrichment_usage (
    day TEXT PRIMARY KEY,  -- YYYY-MM-DD (UTC)
    count INTEGER NOT NULL DEFAULT 0
);
