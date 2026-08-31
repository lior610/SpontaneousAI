import json
import os
from typing import Dict, List, Tuple

def _find_coords_file() -> str:
    env_path = os.environ.get("FALLBACK_COORDS_PATH")
    if env_path and os.path.exists(env_path):
        return env_path
    
    candidates = [
        "/shared/fallback_coords.json",
        os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../shared/fallback_coords.json")),
        os.path.normpath(os.path.join(os.path.dirname(__file__), "../../shared/fallback_coords.json")),
        os.path.normpath(os.path.join(os.getcwd(), "shared/fallback_coords.json")),
        os.path.normpath(os.path.join(os.getcwd(), "../shared/fallback_coords.json")),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    # Fallback to default candidate if none found yet
    return "/shared/fallback_coords.json"

_json_path = _find_coords_file()

if os.path.exists(_json_path):
    with open(_json_path) as _f:
        _raw = json.load(_f)
else:
    _raw = {}

FALLBACK_COORDS: Dict[str, List[Tuple[float, float]]] = {
    k: [tuple(pair) for pair in v] for k, v in _raw.items()
}

