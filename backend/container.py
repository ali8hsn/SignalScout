"""DI root: wires Database -> repositories -> services. No global singletons;
main.py and scripts construct exactly one Container each."""

from backend.config import Settings, load_settings
from backend.db.database import Database
from backend.db.repositories.concentrations import ConcentrationRepository
from backend.db.repositories.digests import DigestRepository
from backend.db.repositories.enrichment import EnrichmentCacheRepository, EnrichmentUsageRepository
from backend.db.repositories.graph_edges import GraphEdgeRepository
from backend.db.repositories.persons import PersonRepository
from backend.db.repositories.signals import SignalRepository
from backend.db.repositories.subscriptions import (
    DigestSendRepository,
    FeedbackRepository,
    SubscriberRepository,
)
from backend.digest.generator import DigestGenerator
from backend.digest.sender import ResendSender
from backend.discovery.concentrations import ConcentrationDetector
from backend.discovery.entity_resolution import EntityResolver
from backend.enrichment.contacts import ContactEnricher
from backend.enrichment.locations import LocationResolver
from backend.enrichment.provider_enricher import ProviderEnricher, build_provider
from backend.scoring.backtest import BacktestRunner
from backend.scoring.engine import ScoringEngine
from backend.services.candidate_service import CandidateService
from backend.services.discovery_job import DiscoveryJobManager
from backend.services.subscriber_digest import SubscriberDigestService


class Container:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self.db = Database(self.settings.db_path, database_url=self.settings.database_url)

        self.persons = PersonRepository(self.db)
        self.signals = SignalRepository(self.db)
        self.edges = GraphEdgeRepository(self.db)
        self.concentrations = ConcentrationRepository(self.db)
        self.digests = DigestRepository(self.db)
        self.subscribers = SubscriberRepository(self.db)
        self.digest_sends = DigestSendRepository(self.db)
        self.feedback = FeedbackRepository(self.db)

        self.engine = ScoringEngine(self.settings.recency_window_days)
        self.resolver = EntityResolver(self.persons, self.signals, self.edges)
        self.contact_enricher = ContactEnricher()
        self.location_resolver = LocationResolver(self.settings.school_locations_file)
        self.enrichment_cache = EnrichmentCacheRepository(self.db)
        self.enrichment_usage = EnrichmentUsageRepository(self.db)
        self.provider_enricher = ProviderEnricher(
            build_provider(self.settings), self.signals, self.enrichment_cache,
            self.enrichment_usage, self.settings.daily_enrichment_budget,
        )
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
        self.email_sender = ResendSender(
            self.settings.resend_api_key,
            self.settings.digest_from_email,
        )
        self.subscriber_digest = SubscriberDigestService(
            self.subscribers,
            self.digest_sends,
            self.candidate_service,
            self.email_sender,
            self.settings.public_base_url,
            size=10,
        )
        self.discovery_job = DiscoveryJobManager(
            self.settings, container_factory=lambda: Container(self.settings)
        )
