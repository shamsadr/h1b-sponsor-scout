"""Put app/ on sys.path so tests import app modules the way the running app does."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
