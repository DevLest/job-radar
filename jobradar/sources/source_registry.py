"""Which sources exist, in the order they run. Adding a source = one import + one list entry."""

from .arbeitnow_source import ArbeitnowSource
from .ashby_source import AshbySource
from .greenhouse_source import GreenhouseSource
from .hackernews_source import HackerNewsSource
from .himalayas_source import HimalayasSource
from .jobicy_source import JobicySource
from .jobstreet_source import JobStreetSource
from .lever_source import LeverSource
from .linkedin_source import LinkedInSource
from .onlinejobs_source import OnlineJobsSource
from .remoteok_source import RemoteOkSource
from .remotive_source import RemotiveSource
from .weworkremotely_source import WeWorkRemotelySource

# Enabled per name in profile.yaml -> sources.<name>.
FEED_SOURCES = [JobStreetSource, OnlineJobsSource, LinkedInSource, RemotiveSource, RemoteOkSource, JobicySource,
                HimalayasSource, WeWorkRemotelySource, HackerNewsSource, ArbeitnowSource]
# One board per company slug in profile.yaml -> companies.<name>.
BOARD_SOURCES = [GreenhouseSource, LeverSource, AshbySource]
