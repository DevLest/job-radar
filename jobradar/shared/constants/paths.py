"""Filesystem locations. Everything user-specific lives next to the code and is gitignored."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
CV_DIR = DATA_DIR / "cv"
REPORTS_DIR = ROOT / "reports"
PROFILE_PATH = ROOT / "profile.yaml"
PROFILE_EXAMPLE_PATH = ROOT / "profile.example.yaml"
ENV_PATH = ROOT / ".env"
DB_PATH = ROOT / "jobs.db"
STATIC_DIR = ROOT / "jobradar" / "static"
