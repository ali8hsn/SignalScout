"""GraphExpander (spec §10): one-hop expansion from seed GitHub accounts.

Live mode (needs GITHUB_TOKEN): for each seed founder, look at BOTH who they
follow (strong warm signal — a founder chose to follow this person) and who
follows them (weaker). Keep only genuinely unknown candidates (not already
famous), and only those with independent evidence on their own profile.
Without a token the pipeline uses the seeded discovery fixtures loaded by
build_db.py — discovery never blocks the demo.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from backend.db.repositories.graph_edges import GraphEdgeRepository
from backend.db.repositories.persons import PersonRepository
from backend.domain.graph_edge import GraphEdge
from backend.domain.person import Person
from backend.scrapers.github_scraper import GithubScraper, parse_grad_year

logger = logging.getLogger(__name__)

# Account older than this (years) is assumed established, not pre-breakout.
MAX_ACCOUNT_AGE_YEARS = 13


class GraphExpander:
    def __init__(self, scraper: GithubScraper, persons: PersonRepository, edges: GraphEdgeRepository):
        self.scraper = scraper
        self.persons = persons
        self.edges = edges

    def expand(
        self,
        seed_usernames: list[str],
        max_per_seed: int = 60,
        follower_cap: int = 2000,
        on_progress: Callable[[str, int], None] | None = None,
        repos_per_seed: int = 3,
        contributors_per_repo: int = 30,
        org_members_per_seed: int = 30,
        stargazers_per_repo: int = 20,
        forkers_per_repo: int = 15,
        interactions_per_repo: int = 20,
        niche_repo_star_ceiling: int = 2000,
    ) -> list[Person]:
        """One hop out from each seed across capped GitHub relationship surfaces.

        `seed_follows`  = the seed founder follows this person (high-signal).
        `follows_seed`  = this person follows the seed founder (lower-signal).
        `co_contributor` = contributes to one of the seed's top repos (working
        relationship — trusted above a follow).
        `org_mate`      = shares a public GitHub org with the seed.
        `starred_repo`  = starred a seed-owned niche repo (one-way, not mutual).
        `forked_repo`   = forked a seed-owned niche repo.
        `issue_pr_interaction` = opened an issue or PR on a seed-owned niche repo.
        A candidate is kept only if unknown (see `_is_unknown`) and has at least
        one independent signal on their own GitHub profile.

        `on_progress(stage, count)` (optional) is called with live counts for the
        "scrape" (profiles inspected) and "resolve" (unknowns kept) stages so a UI
        can animate the pipeline as it runs.
        """
        def tick(stage: str, count: int) -> None:
            if on_progress:
                on_progress(stage, count)

        # login -> list[(seed_person, link_type, metadata)]
        candidate_links: dict[str, list[tuple[Person, str, dict]]] = {}
        seen_links: set[tuple[str, str, str, str]] = set()

        def add_link(login: str | None, seed_person: Person, link_type: str, metadata: dict) -> None:
            if not login or login.lower() == (seed_person.github_username or "").lower():
                return
            key = (login, seed_person.id, link_type, str(sorted(metadata.items())))
            if key in seen_links:
                return
            seen_links.add(key)
            candidate_links.setdefault(login, []).append((seed_person, link_type, metadata))

        for seed in seed_usernames:
            seed_person = self.persons.find_by_github(seed)
            if not seed_person:
                continue
            for direction, users in (
                ("seed_follows", self.scraper.client.following(seed, limit=max_per_seed)),
                ("follows_seed", self.scraper.client.followers(seed, limit=max_per_seed)),
            ):
                for user in users:
                    add_link(user.get("login"), seed_person, direction, {})

            # Mine only a few top non-fork repos. Attention surfaces are limited
            # to niche repos so popular projects do not swamp discovery.
            if repos_per_seed > 0 and any(
                cap > 0
                for cap in (
                    contributors_per_repo,
                    stargazers_per_repo,
                    forkers_per_repo,
                    interactions_per_repo,
                )
            ):
                repos = [r for r in self.scraper.client.repos(seed) if not r.get("fork")]
                repos.sort(key=lambda r: -(r.get("stargazers_count") or 0))
                for repo in repos[:repos_per_seed]:
                    repo_name = repo["name"]
                    full_name = repo.get("full_name") or repo_name
                    if contributors_per_repo > 0:
                        contributors = self.scraper.client.repo_contributors(
                            seed, repo_name, limit=contributors_per_repo
                        )[:contributors_per_repo]
                        for user in contributors:
                            add_link(
                                user.get("login"), seed_person, "co_contributor",
                                {"repo": full_name},
                            )

                    stars = repo.get("stargazers_count") or 0
                    if stars > niche_repo_star_ceiling:
                        continue
                    if stargazers_per_repo > 0:
                        for user in self.scraper.client.repo_stargazers(
                            seed, repo_name, limit=stargazers_per_repo
                        )[:stargazers_per_repo]:
                            add_link(
                                user.get("login"), seed_person, "starred_repo",
                                {"repo": full_name, "mutual": False},
                            )
                    if forkers_per_repo > 0:
                        for fork in self.scraper.client.repo_forkers(
                            seed, repo_name, limit=forkers_per_repo
                        )[:forkers_per_repo]:
                            owner = fork.get("owner") or {}
                            add_link(
                                owner.get("login"), seed_person, "forked_repo",
                                {"repo": full_name},
                            )
                    if interactions_per_repo > 0:
                        for issue in self.scraper.client.repo_issues(
                            seed, repo_name, limit=interactions_per_repo
                        )[:interactions_per_repo]:
                            user = issue.get("user") or {}
                            add_link(
                                user.get("login"), seed_person, "issue_pr_interaction",
                                {
                                    "repo": full_name,
                                    "number": issue.get("number"),
                                    "kind": "pull_request" if issue.get("pull_request") else "issue",
                                    "url": issue.get("html_url"),
                                },
                            )

            # Fellow members of the seed's public orgs.
            if org_members_per_seed > 0:
                collected = 0
                for org in self.scraper.client.user_orgs(seed):
                    if collected >= org_members_per_seed:
                        break
                    org_login = org.get("login")
                    if not org_login:
                        continue
                    for user in self.scraper.client.org_members(
                        org_login, limit=org_members_per_seed - collected
                    ):
                        add_link(user.get("login"), seed_person, "org_mate", {"org": org_login})
                        collected += 1

        discovered: list[Person] = []
        scraped = 0
        today = datetime.now(timezone.utc).date().isoformat()
        for login, links in candidate_links.items():
            if self.persons.find_by_github(login):
                continue  # already known (founder or prior discovery)
            profile = self.scraper.client.user(login)
            scraped += 1
            tick("scrape", scraped)
            if not self._is_unknown(profile, follower_cap):
                continue
            signals = self.scraper.scrape_user(login, user=profile)
            if not signals:
                continue  # no independent evidence -> not a candidate (spec §10)

            name = signals[0].person_name
            person = Person(
                name=name,
                github_username=login,
                cohort="discovery",
                discovery_origin="github",
                enrichment_status="pending_budget",
            )
            person.graduation_year = parse_grad_year(profile.get("bio"))
            person.contact_info["github_followers"] = profile.get("followers", 0)
            person.contact_info["github_created_at"] = profile.get("created_at")
            self.persons.save(person)

            edges = []
            for seed_person, link_type, meta in links:
                if link_type in ("seed_follows", "follows_seed"):
                    # edge points source -> target where source follows target
                    src, tgt = (seed_person, person) if link_type == "seed_follows" else (person, seed_person)
                    edge_type, metadata = "github_follows", {"direction": link_type}
                elif link_type in ("starred_repo", "forked_repo", "issue_pr_interaction"):
                    # Candidate acted on the seed's repository: candidate -> seed.
                    src, tgt = person, seed_person
                    edge_type, metadata = link_type, dict(meta)
                else:
                    # co_contributor / org_mate are symmetric; point seed -> candidate
                    src, tgt = seed_person, person
                    edge_type, metadata = link_type, dict(meta)
                edge = GraphEdge(
                    source_name=src.name, target_name=tgt.name, edge_type=edge_type,
                    observed_date=today, source="github", metadata=metadata,
                )
                edge.source_person_id = src.id
                edge.target_person_id = tgt.id
                edges.append(edge)
            self.edges.save_many(edges)
            discovered.append(person)
            tick("resolve", len(discovered))
            logger.info("discovered %s (%d seed links)", login, len(links))
        return discovered

    @staticmethod
    def _is_unknown(profile: dict | None, follower_cap: int) -> bool:
        """Filter out orgs/bots and already-famous accounts — we hunt pre-breakout people."""
        if not profile:
            return False
        if profile.get("type") != "User":
            return False
        if profile.get("followers", 0) > follower_cap:
            return False
        created = (profile.get("created_at") or "")[:4]
        if created.isdigit():
            age_years = datetime.now(timezone.utc).year - int(created)
            if age_years > MAX_ACCOUNT_AGE_YEARS:
                return False
        return True
