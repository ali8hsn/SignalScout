# Scrapers

The scrapers module collects raw evidence from external sources (GitHub, Devpost, Semantic Scholar, OpenAlex, fellowship/competition pages, Product Hunt) and curated fixture files, converting each into the shared `Signal` (and sometimes `GraphEdge`) domain records that the scoring module consumes, or — for the free-source discovery lane (`fellowship_scraper.py`, `competition_scraper.py`, `producthunt_scraper.py`, `resolve.py`) — into candidate leads resolved against existing `Person` records. Every scraper is designed to fail soft — partial or total source failures degrade gracefully to an empty result rather than raising.

## backend/scrapers/__init__.py
Empty package marker file; no code.

## backend/scrapers/base.py
Defines the shared abstract scraper contract that concrete signal-emitting scrapers implement.

- `BaseScraper` — abstract base class establishing the common scraper interface: a `name` attribute identifying the source, and a `scrape()` method contract requiring implementations to never raise on partial failure and instead return whatever was successfully collected.
  - `BaseScraper.scrape() -> list[Signal]` — abstract method; concrete scrapers collect and return signals from their source, degrading gracefully (returning partial/empty results) rather than raising on failure.

## backend/scrapers/competition_scraper.py
`CompetitionScraper` — a one-line subclass of `ConfigSourceScraper` (`name = "competition"`) pointed at `data/competition_sources.json` (loaded via `Settings.competition_sources_file`). Covers USACO, IMO, IOI, Putnam, Regeneron STS. Devpost is intentionally excluded — it already has a dedicated teammate-graph scraper (`devpost_scraper.py`); duplicating it here as a plain lead-extraction source would produce lower-quality leads than the existing bespoke parser.

## backend/scrapers/config_scraper.py
Shared scrape-from-JSON-source-list base class factored out of `fellowship_scraper.py`/`competition_scraper.py` (they were otherwise near-identical). Same config-file convention as `backend/discovery/openalex_labs.py`'s `targets_file`, so URLs can be corrected without a code change.

- `USER_AGENT` — module-level browser-like User-Agent string used for every request.
- `ConfigSourceScraper` — base class for a scraper whose targets are a JSON list of `{id, url}` sources; subclasses set only `name` and are constructed with their own sources file.
  - `ConfigSourceScraper.__init__(sources_file, session=None)` — stores the sources file path and creates/stores a `requests.Session` with `USER_AGENT`.
  - `ConfigSourceScraper.scrape(source_id=None, max_leads_per_source=50) -> list[RawLead]` — fetches every configured source (or just one matching `source_id`) and runs each page's HTML through `lead_extraction.extract_leads`, returning the combined `RawLead` list.
  - `ConfigSourceScraper._get(url) -> str | None` — fetches a URL, returning the HTML text or `None` on any non-200 response or request exception (logged, never raised).
  - `ConfigSourceScraper._sources() -> list[dict]` — reads and JSON-parses the sources file's `"sources"` array, returning `[]` and logging a warning if missing/invalid.

## backend/scrapers/devpost_scraper.py
Scrapes public Devpost hackathon portfolio and project pages via stdlib regex (no official API) to emit hackathon win/finalist signals and teammate connection edges; source is public HTML at devpost.com, no auth/env vars required.

- `DevpostScraper` — per-person collector of Devpost hackathon history and teammate relationships, parsing defensively since markup can change.
  - `DevpostScraper.__init__(max_projects=3, request_gap_seconds=0.5)` — sets up a `requests.Session` with a browser-like User-Agent, caps how many projects are fetched per person, and sets the delay between project page requests.
  - `DevpostScraper._get(path) -> str | None` — fetches a Devpost page by path, returning the HTML text or `None` on any non-200 response or request exception (logged, never raised).
  - `DevpostScraper.user_projects(username) -> list[str]` — extracts the ordered, de-duplicated list of project slugs linked from a user's public portfolio page.
  - `DevpostScraper.github_username(username) -> str | None` — extracts a GitHub username explicitly linked from a user's public Devpost profile page, if present.
  - `DevpostScraper.project(slug) -> dict | None` — fetches and parses a project page into a dict with title, URL, team members (username/display name pairs), and per-hackathon submission info (hackathon name, won/finalist flags, prize text).
  - `DevpostScraper.collect(person, devpost_username) -> tuple[list[Signal], list[GraphEdge]]` — for a person's Devpost username, fetches up to `max_projects` projects they're confirmed team members of, emitting a `hackathon_win` signal (strength 0.8) for won submissions or `hackathon_finalist` (strength 0.6) for finalist submissions, plus `hackathon_teammate` graph edges to every other team member on each project.
  - `DevpostScraper._submission_date(hackathon, fallback) -> str` (static) — best-effort submission date derived from a 4-digit year found in the hackathon name, falling back to a provided date string.
  - `DevpostScraper._project_date(project, fallback) -> str` (static) — best-effort project date taken from the year in the first submission's hackathon name that matches, falling back to a provided date string.

## backend/scrapers/fellowship_scraper.py
`FellowshipScraper` — a one-line subclass of `ConfigSourceScraper` (`name = "fellowship"`) pointed at `data/fellowship_sources.json` (loaded via `Settings.fellowship_sources_file`). Covers Z Fellows, Thiel Fellowship, Neo Scholars, 1517 Fund, Contrary Talent, Interact Fellowship. Not to be confused with `backend/discovery/fellowship_seeds.py` (a static, hand-curated alumni list, no live HTTP).

## backend/scrapers/github_scraper.py
The only live (non-seeded) scraper: pulls a GitHub user's public profile, repos, and social/follow data via the GitHub REST API to derive builder, star-project, prolific, and student signals plus follow edges. Requires the `GITHUB_TOKEN` env var (used by the caller to construct `GithubClient`); without a token the pipeline falls back to the seeded fixture `data/seed_signals/github_seeded.json` so the demo doesn't break.

- `parse_grad_year(bio) -> int | None` — best-effort graduation-year extraction from a GitHub bio string, matching patterns like "class of 2027", "'27", or "2027 grad".
- `looks_like_student(bio) -> bool` — returns whether a bio matches student-related keywords (e.g. "undergrad", "high school", "class of") or a university-name hint (e.g. "MIT", "Stanford", ".edu").
- `GithubClient` — thin authenticated wrapper around the GitHub REST API; every method fails soft (returns `None`/`[]`) rather than raising.
  - `GithubClient.__init__(token)` — builds a `requests.Session` with a Bearer token authorization header and the GitHub API version header.
  - `GithubClient._get(path, params=None)` — issues a GET request against the GitHub API, returning parsed JSON, or `None` on rate-limit (403 with zero remaining), any non-200 status, or a request exception.
  - `GithubClient.user(username) -> dict | None` — fetches a user's public profile.
  - `GithubClient.repos(username) -> list[dict]` — fetches up to 100 of a user's public repos sorted by last-pushed.
  - `GithubClient.social_accounts(username) -> list[dict]` — fetches a user's linked social accounts.
  - `GithubClient.following(username, limit=100) -> list[dict]` — fetches accounts the user follows, capped at `limit`.
  - `GithubClient.followers(username, limit=100) -> list[dict]` — fetches the user's followers, capped at `limit`.
  - `GithubClient.repo_contributors(owner, repo, limit=30) -> list[dict]` — fetches a repo's contributors, capped at `limit`.
  - `GithubClient.repo_stargazers(owner, repo, limit=20) -> list[dict]` — fetches users who starred a repo (a one-way signal, not mutual), capped at `limit`.
  - `GithubClient.repo_forkers(owner, repo, limit=15) -> list[dict]` — fetches a repo's forks, capped at `limit`.
  - `GithubClient.repo_issues(owner, repo, limit=20) -> list[dict]` — fetches a repo's issues (GitHub's endpoint includes PRs), sorted by most recently updated, capped at `limit`.
  - `GithubClient.org_members(org, limit=30) -> list[dict]` — fetches an organization's members, capped at `limit`.
  - `GithubClient.user_orgs(username) -> list[dict]` — fetches the organizations a user belongs to.
- `GithubScraper` — orchestrates per-user signal collection from `GithubClient` data, implementing `BaseScraper`.
  - `GithubScraper.__init__(client, usernames, display_names=None)` — stores the `GithubClient`, the list of usernames to scrape, and an optional login-to-display-name override map.
  - `GithubScraper.scrape() -> list[Signal]` — iterates all configured usernames, collecting each user's signals via `scrape_user` and logging (never raising) on per-user failure.
  - `GithubScraper.scrape_user(username, user=None) -> list[Signal]` — fetches (or reuses) a user's profile and repos, then emits: a `github_early_builder` signal (strength 0.7) if the account has 3+ repos; a `github_star_project` signal per repo with 100+ stars (strength 0.9 if 1000+, else 0.6); a `github_prolific` signal (strength 0.5) if the user has 30+ repos; and a `student_builder` signal (strength 0.7) if the bio matches `looks_like_student`.
  - `GithubScraper.follow_edges(username, name) -> list[GraphEdge]` — builds `github_follows` graph edges from each of the user's followers to the user.

## backend/scrapers/lead_extraction.py
Generic, best-effort HTML lead extraction shared by `fellowship_scraper.py` and `competition_scraper.py` (via `ConfigSourceScraper.scrape`). Real cohort/results pages vary in markup and many are JS-rendered (unparseable here) — this extracts whatever a name is near: a LinkedIn URL, a GitHub URL, or a personal site. Never raises; unparseable pages simply yield no leads.

- `NAME_RE`, `LINKEDIN_RE`, `GITHUB_RE`, `PERSONAL_SITE_RE` — module-level compiled regexes for name-like text, LinkedIn profile URLs, GitHub profile URLs, and a non-LinkedIn/GitHub/Twitter personal-site URL, respectively.
- `WINDOW = 300` — characters to look around a matched name for nearby links.
- `extract_leads(html, source, source_url="", school=None, year=None, max_leads=50) -> list[RawLead]` — finds name-like text directly in the raw HTML (URLs live in `href` attributes, so tags are never stripped before this search — an earlier tag-stripped-first version destroyed the hrefs before the link regexes could see them), then for each match looks in a `WINDOW`-character radius for a LinkedIn URL, a GitHub URL, or (only if neither is found) a personal-site URL; a name with no nearby link anywhere in its window is dropped as too ambiguous to be worth a paid lookup downstream; de-dupes by lower-cased name within one page and stops at `max_leads`.
- `_first(pattern, text) -> str | None` — returns the first regex match in `text`, or `None`.

## backend/scrapers/openalex.py
Scrapes the free, unauthenticated OpenAlex API (author search -> works -> co-authors) to emit co-authored-paper signals and `co_author` graph edges for discovery-cohort people with real names — same shape as `semantic_scholar.py`, used both for co-author expansion of known people and by `backend/discovery/openalex_labs.py`'s lab-affiliation lead-gen. No API key required; a `mailto` param is honored for OpenAlex's polite pool (priority routing/higher limits). The client backs off and retries on HTTP 429 and fails soft.

- `OpenAlexClient` — thin wrapper around the OpenAlex API with retry/backoff on rate limiting; all failures return `None`/`[]`.
  - `OpenAlexClient.__init__(mailto="", max_retries=3, backoff_seconds=2.0)` — sets up a `requests.Session`, stores the polite-pool `mailto` (attached to every request when set).
  - `OpenAlexClient._get(path, params=None)` — issues a GET request, retrying with linearly increasing backoff on HTTP 429 up to `max_retries` times, returning parsed JSON or `None` on any other failure or exhausted retries.
  - `OpenAlexClient.search_author(name) -> list[dict]` — searches for authors by name, returning candidate records with id/display_name/works_count/cited_by_count.
  - `OpenAlexClient.author(author_id) -> dict | None` — fetches one author's full record (works_count, cited_by_count, summary_stats, last_known_institutions).
  - `OpenAlexClient.author_works(author_id, limit=10) -> list[dict]` — fetches an author's works (id/title/publication_year/publication_date/authorships) up to `limit`.
  - `OpenAlexClient.works_by_affiliation(affiliation, from_date=None, limit=25, institution_id=None) -> list[dict]` — fetches recent works matching a lab: filters by the precise `institutions.id` when OpenAlex has resolved the lab as its own institution (e.g. MIT CSAIL), otherwise falls back to a free-text `raw_affiliation_strings.search` match (e.g. Stanford SAIL/Berkeley BAIR, which OpenAlex hasn't resolved separately from their university) — no HTML scraping of lab pages either way.
- `MAX_AUTHOR_WORKS = 30`, `MAX_AUTHOR_CITED_BY = 500` — the early-career gate thresholds: above either, an author reads as an established researcher, not a pre-breakout person.
- `OpenAlexScraper` — per-person collector that resolves a person to an OpenAlex author and emits co-authorship signals/edges; capped so one person costs at most 2 API calls.
  - `OpenAlexScraper.has_real_name` — the same static check as `SemanticScholarScraper.has_real_name` (imported, not duplicated).
  - `OpenAlexScraper.is_early_career(author) -> bool` (static) — `True` when `1 <= works_count <= MAX_AUTHOR_WORKS` and `cited_by_count <= MAX_AUTHOR_CITED_BY`.
  - `OpenAlexScraper.find_author(name) -> dict | None` — searches for an author by name and returns the single normalized-name-exact, early-career match; ambiguous or prolific results are treated as no match.
  - `OpenAlexScraper.collect(person, author=None) -> tuple[list[Signal], list[GraphEdge]]` — for a person with a real name, resolves (or reuses) their author record, then for up to `max_papers` co-authored works (skipping solo works with no co-authors) emits a `co_authored_paper` signal (strength 0.6, `source="openalex"`) per work and a `co_author` graph edge (`source="openalex"`) to up to `max_coauthors_per_paper` co-authors per work.

## backend/scrapers/producthunt_scraper.py
`ProductHuntScraper` — the one free source that needs a real browser, not a plain GET. PH's leaderboard and product pages are JS-rendered SPAs and actively bot-fingerprinted, so this renders each page with Playwright (headless Chromium) before falling back to the same plain-regex parsing convention as the rest of the module. Two-level crawl: the leaderboard page (`data/producthunt_sources.json`, loaded via `Settings.producthunt_sources_file`) lists product links but no maker names; each product page is then rendered separately to find its makers, exposed only as PH-internal profile links (`/@username`) with no external LinkedIn/GitHub/site link on the page. That profile link is still a stable per-person identifier, so it's carried on the `RawLead` as `personal_site` — no schema change needed for `lead_extraction`'s "needs a nearby link" rule or `LeadResolver`'s PDL-Identify fallback to work on a Product Hunt lead. The `playwright` import is lazy inside `scrape()`, so an environment without the browser installed degrades to zero leads rather than crashing at container-wiring time.

- `BASE = "https://www.producthunt.com"` — base URL used to resolve relative maker-profile links to absolute URLs.
- `PRODUCT_LINK_RE`, `MAKER_RE`, `NAME_RE` — module-level compiled regexes for product page links (`/posts/<slug>` or `/products/<slug>`), a maker's profile-link + anchor-text pair (`/@username` -> display text), and plausible full-name text, respectively.
- `ProductHuntScraper.__init__(sources_file, max_products_per_source=10)` — stores the sources file path and the default cap on how many product pages are rendered per leaderboard source.
- `ProductHuntScraper.scrape(source_id=None, max_products_per_source=None) -> list[RawLead]` — lazily imports `playwright.sync_api`, returning `[]` and logging a warning if it isn't installed; otherwise launches headless Chromium, renders every configured source (or just one matching `source_id`) via `_scrape_source`, and always closes the browser (`finally`) even if a source scrape raises.
- `ProductHuntScraper._scrape_source(context, source, limit) -> list[RawLead]` — renders the leaderboard page, extracts up to `limit` product URLs via `_product_urls`, renders each product page, and extracts makers via `_makers`.
- `ProductHuntScraper._render(context, url) -> str | None` — opens a new Playwright page, navigates with a 20s timeout waiting for network idle, returns the rendered HTML, and always closes the page; any exception (navigation timeout, bot-block, etc.) is logged and returns `None`.
- `ProductHuntScraper._product_urls(html, base_url) -> list[str]` (static) — de-duplicated, order-preserved list of absolute product URLs found in the rendered leaderboard HTML.
- `ProductHuntScraper._makers(html, source_id, product_url) -> list[RawLead]` (static) — for each `/@username` profile link on a rendered product page, keeps it only if the anchor text matches `NAME_RE` (filters out non-name anchor text like "Follow"), de-dupes by profile path, and returns a `RawLead` per maker with `personal_site` set to the absolute profile URL.
- `ProductHuntScraper._sources() -> list[dict]` — reads and JSON-parses the sources file's `"sources"` array, returning `[]` and logging a warning if missing/invalid (same convention as `ConfigSourceScraper._sources`, duplicated rather than shared since this scraper isn't a `ConfigSourceScraper` subclass — its fetch step is a full browser render, not a `requests.Session` GET).

## backend/scrapers/resolve.py
`LeadResolver`: dedupe-first matching of `RawLead`s (extracted by `fellowship_scraper.py`/`competition_scraper.py`) against existing candidates, then a bounded paid lookup for anyone unresolved. Source-specific HTML parsing lives in the scrapers; this module only ever sees the extracted `RawLead`, never raw HTML. Reuses `ProviderEnricher.run()` — the same PDL/Coresignal single-person enrichment path GitHub candidates go through — for the paid-lookup step, so budget/cache/signal-emission behave identically regardless of how a candidate was found.

- `RawLead` — dataclass holding the strongest identifiers a free-source scraper could extract for one person: `name`, `source` (e.g. `"z_fellows"`, `"usaco"`), `source_url`, `school`, `company`, `year`, `linkedin_url`, `personal_site`, `github_username` — everything but `name`/`source` is best-effort and may be empty.
- `ResolveResult` — dataclass holding `matched` (leads that resolved to an already-stored `Person`), `created` (leads newly identified via a paid lookup), `unresolved` (leads with no match and no confirmable paid-lookup result).
- `LeadResolver` — composes `PersonRepository`, `ProviderIdentityRepository`, `ProviderEnricher`.
  - `LeadResolver.__init__(persons, identities, enricher)` — stores the repositories/enricher used for dedupe and identification.
  - `LeadResolver.resolve(leads) -> ResolveResult` — for each lead, checks `_find_existing` first (skip — no paid lookup) and only calls `_identify` (paid lookup) for leads with no existing match; buckets every lead into `matched`/`created`/`unresolved`.
  - `LeadResolver._find_existing(lead) -> Person | None` — standard ladder minus provider ID (free sources don't have one): LinkedIn URL (via `identities.find_person_by_linkedin`) -> normalized name corroborated by a shared school (same rule as `ProviderExpander._resolve_existing`'s name tier — a name-only match with no shared school is not merged).
  - `LeadResolver._identify(lead) -> Person | None` — builds a bare `Person` (name, school, linkedin_url, github_username, personal_site, `discovery_origin`/`discovery_source` both set to `lead.source`), saves it *before* calling `enricher.run(person)` (required because `run()` derives `Signal` rows that FK-reference `persons`, so the row must exist first), and deletes the tentative row (`persons.delete`) if the outcome isn't `"matched"` — since `run()` only derives signals for a matched outcome, nothing is orphaned by the rollback.

## backend/scrapers/seeded.py
Loads curated signal fixtures from `data/seed_signals/*.json` for every non-GitHub source used in the demo; fixture shape mirrors exactly what a live scraper for that source would emit so a real scraper can later be swapped in without changing downstream code. No external network calls or env vars.

- `SeededScraper` — implements `BaseScraper` by reading signals from a JSON fixture file instead of a live source.
  - `SeededScraper.__init__(fixture_path)` — stores the fixture file path and derives the scraper's `name` from the file stem.
  - `SeededScraper.scrape() -> list[Signal]` — returns `[]` if the fixture file doesn't exist; otherwise parses the JSON file's `signals` array into `Signal` records, defaulting each record's `source`/`signal_category` to the fixture's top-level `source`/`category` (or the file stem) when not specified per-row.

## backend/scrapers/semantic_scholar.py
Scrapes the free, unauthenticated Semantic Scholar Graph API (author search -> papers -> co-authors, plus per-paper citations -> citing authors) to emit co-authored-paper signals, co-author graph edges, and attention-tier paper-citation graph edges for discovery-cohort people with real (full) names. No API key/env var required; the client backs off and retries on HTTP 429 rate-limiting and fails soft.

- `SemanticScholarClient` — thin wrapper around the Semantic Scholar Graph API with retry/backoff on rate limiting; all failures (including persistent 429s) return `None`/`[]`.
  - `SemanticScholarClient.__init__(max_retries=3, backoff_seconds=2.0)` — sets up a `requests.Session` with a descriptive User-Agent and configures retry count/backoff.
  - `SemanticScholarClient._get(path, params=None)` — issues a GET request, retrying with linearly increasing backoff on HTTP 429 up to `max_retries` times, returning parsed JSON or `None` on any other failure or exhausted retries.
  - `SemanticScholarClient.search_author(name) -> list[dict]` — searches for authors by name, returning candidate author records with name/paperCount/hIndex/url.
  - `SemanticScholarClient.author_papers(author_id, limit=10) -> list[dict]` — fetches an author's papers (paperId, title, year, url, authors) up to `limit`.
  - `SemanticScholarClient.paper_citations(paper_id, limit=10) -> list[dict]` — fetches papers that cite the given paper (each row wraps a `citingPaper` dict with title/year/authors), up to `limit`.
- `SemanticScholarScraper` — per-person collector that resolves a person to a Semantic Scholar author and emits co-authorship signals/edges plus citation edges; capped so one person costs at most 2 API calls for co-authorship (more for citation walking, each fail-soft).
  - `SemanticScholarScraper.__init__(client=None, max_papers=3, max_coauthors_per_paper=5)` — stores (or default-constructs) a `SemanticScholarClient` and caps on papers/co-authors processed per person.
  - `SemanticScholarScraper.has_real_name(person) -> bool` (static) — returns whether a person has a plausible full name (contains a space, and isn't identical to their GitHub login) suitable for author search, avoiding false matches from bare usernames.
  - `SemanticScholarScraper.find_author(name) -> dict | None` — searches for an author by name and returns the single normalized-name-exact match whose paper count is between 1 and `MAX_AUTHOR_PAPERS` (50), treating any ambiguous (multiple matches) or overly prolific (established academic) result as no match.
  - `SemanticScholarScraper.collect(person, author=None) -> tuple[list[Signal], list[GraphEdge]]` — for a person with a real name, resolves (or reuses) their author record, then for up to `max_papers` co-authored papers (skipping solo papers with no co-authors) emits a `co_authored_paper` signal (strength 0.6) per paper and a `co_author` graph edge to up to `max_coauthors_per_paper` co-authors per paper.
  - `SemanticScholarScraper.collect_citations(person, author=None, max_papers=3, max_citations_per_paper=5) -> tuple[list[Signal], list[GraphEdge]]` — for a person with a real name, resolves (or reuses) their author record, then for up to `max_papers` of their papers that have a `paperId`, fetches citing papers and emits a `paper_citation` graph edge (person -> citing author) per citing author, up to `max_citations_per_paper` per paper, plus a `cited_paper` signal (strength 0.6) per cited paper — but only when `person.cohort == "discovery"`, so a founder's pre-breakout score (and therefore the backtest reference scale) is never affected by this signal.
