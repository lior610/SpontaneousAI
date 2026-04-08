"""
Services package — submodules load on demand so importing e.g. preference_service
does not pull in attraction_service (vector search, filters) or double-load ST.
"""
from __future__ import annotations

import importlib
from typing import Any

__all__ = ["attraction_service", "embedding_service", "preference_service"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        return importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
