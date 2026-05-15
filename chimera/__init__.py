# Chimera Gateway — namespace bridge
# Allows `from chimera.X` to resolve to root-level packages (api/, security/, etc.)
# Created automatically — do not delete
import sys
from pathlib import Path

_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))