"""ContactEnricher: surface email / X handle / personal site / LinkedIn search URL.

Sources (plan): GitHub public email + social accounts, bio parsing,
Semantic Scholar author emails, generated LinkedIn search query (never scraped).
Idempotent — never overwrites a manually-entered value.
"""

import re
from urllib.parse import quote_plus

from backend.domain.person import Person
from backend.domain.signal import Signal

TWITTER_RE = re.compile(r"(?:twitter\.com/|x\.com/|@)([A-Za-z0-9_]{2,15})")
URL_RE = re.compile(r"https?://[^\s)\"']+")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


class ContactEnricher:
    def enrich(self, person: Person, signals: list[Signal]) -> Person:
        github_profiles = [
            s.raw_data for s in signals
            if s.source == "github" and isinstance(s.raw_data, dict) and s.raw_data.get("login")
        ]
        for profile in github_profiles:
            self._apply_github_profile(person, profile)
        for signal in signals:
            email = signal.metadata.get("author_email") if isinstance(signal.metadata, dict) else None
            if email and not person.email:
                person.email = email
                person.contact_info.setdefault("email_source", signal.source)

        if not person.linkedin_url:
            query = f'site:linkedin.com/in "{person.name}"'
            if person.school:
                query += f' {person.school.split("(")[0].strip()}'
            person.contact_info.setdefault(
                "linkedin_search_url", f"https://www.google.com/search?q={quote_plus(query)}"
            )
        return person

    def _apply_github_profile(self, person: Person, profile: dict) -> None:
        if not person.email and profile.get("email"):
            person.email = profile["email"]
            person.contact_info.setdefault("email_source", "github")
        if not person.twitter_handle and profile.get("twitter_username"):
            person.twitter_handle = profile["twitter_username"]
        bio = profile.get("bio") or ""
        if not person.twitter_handle:
            match = TWITTER_RE.search(bio)
            if match:
                person.twitter_handle = match.group(1)
        blog = (profile.get("blog") or "").strip()
        if not person.personal_site and blog:
            person.personal_site = blog if blog.startswith("http") else f"https://{blog}"
        if not person.email:
            match = EMAIL_RE.search(bio)
            if match:
                person.email = match.group(0)
                person.contact_info.setdefault("email_source", "github_bio")
        for account in profile.get("social_accounts", []):
            url = account.get("url", "")
            if "linkedin.com" in url and not person.linkedin_url:
                person.linkedin_url = url
            if ("twitter.com" in url or "x.com" in url) and not person.twitter_handle:
                match = TWITTER_RE.search(url)
                if match:
                    person.twitter_handle = match.group(1)
