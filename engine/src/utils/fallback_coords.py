from typing import Dict, List, Tuple

FALLBACK_COORDS: Dict[str, List[Tuple[float, float]]] = {
    "new york": [
        (40.7580, -73.9855),  # Times Square
        (40.7812, -73.9665),  # Central Park
    ],
    "tel aviv": [
        (32.0780, 34.7742),  # Dizengoff Square
        (32.0686, 34.7700),  # Nahalat Binyamin
    ],
    "london": [
        (51.5136, -0.1365),  # Soho
        (51.5117, -0.1240),  # Covent Garden
    ],
}
