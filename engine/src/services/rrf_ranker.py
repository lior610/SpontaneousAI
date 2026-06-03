"""
RRF Ranker - Reciprocal Rank Fusion ranking algorithm.

Each dimension (semantic, distance, hours, budget, popularity) is ranked
independently across all candidates. The final score is the sum of
1 / (k + rank_i) across all dimensions.

Unlike linear weighting, RRF rewards consistent high ranking across ALL
dimensions rather than dominance on a single one. A semantically perfect
but very-far attraction will be penalised for its poor distance rank.
"""

import os
from typing import List, Dict, Any, Optional

from src.services.ranking_utils import compute_raw_scores

RRF_K = float(os.getenv("RRF_K", "60"))


class RRFRanker:

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

        # Step 1: compute raw scores for every candidate
        scored = []
        for c in candidates:
            raw = compute_raw_scores(c, user_lat, user_lng, max_walk_km, travel_style, current_hour)
            if c.get('distance_km') is None and raw['dist_km'] is not None:
                c['distance_km'] = round(raw['dist_km'], 2)
            scored.append((c, raw))

        # Step 2: for each dimension, sort descending and record rank (1-based)
        dimensions = ['semantic', 'distance', 'hours', 'budget', 'popularity']
        dim_ranks: Dict[str, Dict[int, int]] = {}  # dim -> {candidate_index -> rank}

        for dim in dimensions:
            order = sorted(range(len(scored)), key=lambda i: scored[i][1][dim], reverse=True)
            dim_ranks[dim] = {candidate_idx: rank + 1 for rank, candidate_idx in enumerate(order)}

        # Step 3: compute RRF score per candidate
        k = RRF_K
        result = []
        for idx, (c, raw) in enumerate(scored):
            rrf_score = sum(1.0 / (k + dim_ranks[dim][idx]) for dim in dimensions)

            # Hard filter: closed attractions go to 0
            if raw['is_closed']:
                rrf_score = 0.0

            c = dict(c)  # shallow copy to avoid mutating original
            c['final_score'] = round(rrf_score, 6)
            c['scoring_breakdown'] = {
                'semantic':   round(raw['semantic'],    3),
                'distance':   round(raw['distance'],    3),
                'hours':      round(raw['hours'],       3),
                'budget':     round(raw['budget'],      3),
                'popularity': round(raw['popularity'],  3),
                'rrf_ranks':  {dim: dim_ranks[dim][idx] for dim in dimensions},
            }
            result.append(c)

        result.sort(key=lambda x: x['final_score'], reverse=True)
        return result
