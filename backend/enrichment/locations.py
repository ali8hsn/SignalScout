"""LocationResolver: fill origin/current location + region bucket.

origin_location: school mapping (data/school_locations.json) or competition metadata.
current_location: GitHub/Twitter bio location.
region: normalized bucket used by ConcentrationDetector ("Research Triangle" etc).
"""

import json
from pathlib import Path

from backend.domain.person import Person
from backend.domain.signal import Signal

# City substring -> region bucket, for locations that don't come from a known school.
CITY_REGIONS = {
    "san francisco": "Bay Area", "palo alto": "Bay Area", "mountain view": "Bay Area",
    "cupertino": "Bay Area", "san jose": "Bay Area", "berkeley": "Bay Area",
    "oakland": "Bay Area", "stanford": "Bay Area", "fremont": "Bay Area",
    "new york": "NYC Metro", "brooklyn": "NYC Metro", "queens": "NYC Metro",
    "cambridge, ma": "Boston Metro", "boston": "Boston Metro",
    "raleigh": "Research Triangle", "durham": "Research Triangle",
    "chapel hill": "Research Triangle", "cary, nc": "Research Triangle",
    "toronto": "Toronto-Waterloo", "waterloo": "Toronto-Waterloo", "kitchener": "Toronto-Waterloo",
    "seattle": "Seattle", "austin": "Austin", "los angeles": "LA Metro",
    "long beach": "LA Metro", "miami": "Miami", "atlanta": "Southeast",
    "london": "UK", "limerick": "Ireland",
}


class LocationResolver:
    def __init__(self, school_locations_file: Path):
        data = json.loads(school_locations_file.read_text())
        self.schools = {k: v for k, v in data.items() if not k.startswith("_")}

    def resolve(self, person: Person, signals: list[Signal]) -> Person:
        school_info = self.schools.get(person.school or "")
        if not person.origin_location:
            state = next(
                (s.metadata.get("state") for s in signals
                 if isinstance(s.metadata, dict) and s.metadata.get("state")),
                None,
            )
            if school_info:
                person.origin_location = school_info["city"]
            elif state:
                person.origin_location = state

        if not person.current_location:
            bio_location = next(
                (s.raw_data.get("location") for s in signals
                 if s.source == "github" and isinstance(s.raw_data, dict) and s.raw_data.get("location")),
                None,
            )
            if bio_location:
                person.current_location = bio_location

        if not person.region:
            person.region = self._region_for(person.origin_location) or (
                school_info["region"] if school_info else None
            ) or self._region_for(person.current_location)
        return person

    @staticmethod
    def _region_for(location: str | None) -> str | None:
        if not location:
            return None
        loc = location.lower()
        for needle, region in CITY_REGIONS.items():
            if needle in loc:
                return region
        return None
