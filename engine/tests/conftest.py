"""
Pytest path setup for the engine.

Mirrors the runtime PYTHONPATH (engine root + shared/python) so that
`src.*`, `db.*`, and `models.*` imports resolve in unit tests.
"""
import sys
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
SHARED_PYTHON = ENGINE_ROOT.parent / "shared" / "python"

for _path in (str(ENGINE_ROOT), str(SHARED_PYTHON)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
