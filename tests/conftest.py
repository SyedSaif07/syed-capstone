"""tests/conftest.py — make the project root importable for tests.

Adds the repo root (the directory containing this `tests/` folder's parent)
to `sys.path` so tests can do `from src.pipeline.pipeline import ...` and
`from api.main import app` from anywhere.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
