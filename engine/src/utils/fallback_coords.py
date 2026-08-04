import json
import os
from typing import Dict, List, Tuple

_json_path = os.environ.get(
    "FALLBACK_COORDS_PATH",
    os.path.join(os.path.dirname(__file__), "../../../shared/fallback_coords.json"),
)

with open(_json_path) as _f:
    _raw = json.load(_f)

FALLBACK_COORDS: Dict[str, List[Tuple[float, float]]] = {
    k: [tuple(pair) for pair in v] for k, v in _raw.items()
}
