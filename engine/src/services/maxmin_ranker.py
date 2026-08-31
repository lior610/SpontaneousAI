"""
Max-Min Ranker - "No Weak Spots" ranking algorithm.

An attraction's score equals its WORST dimension score across
semantic, distance, hours, budget, and popularity.

This surfaces attractions that are reliably decent on everything rather than
excellent on one axis (semantic) while being poor on others (distance, budget).
"""

from typing import List, Dict, Any, Optional

from src.services.ranking_utils import compute_raw_scores


class MaxMinRanker:

    def rank_candidates(
        self,
        candidates: List[Dict[str, Any]],
        user_lat: Optional[float],
        user_lng: Optional[float],
        max_walk_km: float,
        travel_style: str,
        current_hour: Optional[int] = None,
        real_seen_categories: Optional[set] = None,
    ) -> List[Dict[str, Any]]:
        if not candidates:
            return []

        result = []
        for c in candidates:
            raw = compute_raw_scores(c, user_lat, user_lng, max_walk_km, travel_style, current_hour)

            if c.get('distance_km') is None and raw['dist_km'] is not None:
                c['distance_km'] = round(raw['dist_km'], 2)

            if raw['is_closed']:
                score = 0.0
            else:
                score = min(
                    raw['semantic'],
                    raw['distance'],
                    raw['hours'],
                    raw['budget'],
                    raw['popularity'],
                )

            c = dict(c)  # shallow copy to avoid mutating original
            c['final_score'] = round(score, 4)
            c['scoring_breakdown'] = {
                'semantic':   round(raw['semantic'],    3),
                'distance':   round(raw['distance'],    3),
                'hours':      round(raw['hours'],       3),
                'budget':     round(raw['budget'],      3),
                'popularity': round(raw['popularity'],  3),
                'worst_dim':  min(
                    (k for k in raw if k not in ('dist_km', 'is_closed', 'reachable_by')),
                    key=lambda k: raw[k],
                ),
            }
            result.append(c)

        result.sort(key=lambda x: x['final_score'], reverse=True)
        return result
