"""DI root: wires Database -> repositories -> services. No global singletons;
main.py and scripts construct exactly one Container each."""

from backend.config import Settings, load_settings
from backend.db.database import Database
from backend.db.repositories.concentrations import ConcentrationRepository
from backend.db.repositories.digests import DigestRepository
from backend.db.repositories.graph_edges import GraphEdgeRepository
from backend.db.repositories.persons import PersonRepository
from backend.db.repositories.signals import SignalRepository
from backend.digest.generator import DigestGenerator
from backend.digest.sender import NoopSender
from backend.discovery.concentrations import ConcentrationDetector
from backend.discovery.entity_resolution import EntityResolver
from backend.enrichment.contacts import ContactEnricher
from backend.enrichment.locations import LocationResolver
from backend.scoring.backtest import BacktestRunner
from backend.scoring.engine import ScoringEngine
from backend.services.candidate_service import CandidateService


class Container:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self.db = Database(self.settings.db_path)

        self.persons = PersonRepository(self.db)
        self.signals = SignalRepository(self.db)
        self.edges = GraphEdgeRepository(self.db)
        self.concentrations = ConcentrationRepository(self.db)
        self.digests = DigestRepository(self.db)

        self.engine = ScoringEngine(self.settings.recency_window_days)
        self.resolver = EntityResolver(self.persons, self.signals, self.edges)
        self.contact_enricher = ContactEnricher()
        self.location_resolver = LocationResolver(self.settings.school_locations_file)
        self.candidate_service = CandidateService(
            self.persons, self.signals, self.edges, self.engine, self.settings.flag_threshold
        )
        self.backtest = BacktestRunner(
            self.persons, self.signals, self.edges, self.engine, self.settings.flag_threshold
        )
        self.concentration_detector = ConcentrationDetector(self.concentrations)
        self.digest_generator = DigestGenerator(
            self.candidate_service, self.digests, self.settings.out_dir, self.settings.digest_size
        )
        self.email_sender = NoopSender()
