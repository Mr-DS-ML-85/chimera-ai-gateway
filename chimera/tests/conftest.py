"""
pytest conftest — adds project root to sys.path so `from chimera.X`
resolves to the root-level modules (api/, security/, transparency/, etc.)
which is how the codebase is structured (no chimera/ subdirectory).
"""
import sys
from pathlib import Path

# Project root = tests/ + 1 level up
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))