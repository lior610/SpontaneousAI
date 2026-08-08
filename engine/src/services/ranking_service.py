"""
Ranking Service - Engine layer for scoring and re-ranking candidates.

Applies distance, opening hours, budget, and categorical diversity
filters dynamically on top of the vector similarity score.
"""

import os
from typing import List, Dict, Any, Optional

from src.services.ranking_utils import compute_raw_scores

# Scoring weights (must sum to 1.0 ideally)
WEIGHT_SEMANTIC = float(os.getenv("RANKING_WEIGHT_SEMANTIC", "0.35"))
WEIGHT_HOURS = float(os.getenv("RANKING_WEIGHT_HOURS", "0.10"))
WEIGHT_DISTANCE = float(os.getenv("RANKING_WEIGHT_DISTANCE", "0.20"))
WEIGHT_BUDGET = float(os.getenv("RANKING_WEIGHT_BUDGET", "0.10"))
WEIGHT_POPULARITY = float(os.getenv("RANKING_WEIGHT_POPULARITY", "0.20"))
WEIGHT_DIVERSITY = float(os.getenv("RANKING_WEIGHT_DIVERSITY", "0.05"))

# Penalties
CLUSTER_PENALTY_MULTIPLIER = float(os.getenv("RANKING_CLUSTER_PENALTY", "0.5"))

class RankingEngine:
    """
    Ranks a pool of candidate attractions based on weighted contextual scores.
    """

    def _apply_diversity_bonus(self, candidate: Dict[str, Any], seen_categories: set, cluster_counts: dict) -> float:
        diversity_bonus = 0.0
        
        cats = candidate.get('categories', [])
        if not cats:
            cats = [candidate.get('type')] if candidate.get('type') else []
            
        has_new_category = any(cat not in seen_categories for cat in cats)
        if has_new_category:
            diversity_bonus += 1.0
            
        cluster_id = candidate.get('location_cluster_id')
        if cluster_id is not None:
            count = cluster_counts.get(cluster_id, 0)
            if count > 0:
                diversity_bonus -= (CLUSTER_PENALTY_MULTIPLIER * count)
            cluster_counts[cluster_id] = count + 1
            
        for cat in cats:
            if cat:
                seen_categories.add(cat)
                
        return diversity_bonus

    def rank_candidates(
        self,
        candidates: List[Dict[str, Any]],
        user_lat: float,
        user_lng: float,
        max_walk_km: float,
        travel_style: str,
        current_hour: Optional[int] = None,
        real_seen_categories: Optional[set] = None
    ) -> List[Dict[str, Any]]:
        """Rank candidates by weighted contextual score, then apply the diversity bonus."""
        if not candidates:
            return []
            
        seen_categories = set(real_seen_categories) if real_seen_categories else set()
        cluster_counts = {}
        
        # Diversity bonus depends on processing order (seen_categories/cluster_counts
        # accumulate as we go), so it can't be scored independently in one pass —
        # base scores first, diversity bonus in a second pass below.

        for candidate in candidates:
            raw = compute_raw_scores(candidate, user_lat, user_lng, max_walk_km, travel_style, current_hour)

            if raw['dist_km'] is not None:
                candidate['distance_km'] = round(raw['dist_km'], 2)

            base_score = (
                WEIGHT_SEMANTIC * raw['semantic'] +
                WEIGHT_DISTANCE * raw['distance'] +
                WEIGHT_HOURS   * raw['hours'] +
                WEIGHT_BUDGET  * raw['budget'] +
                WEIGHT_POPULARITY * raw['popularity']
            )
            candidate['_base_score'] = 0.0 if raw['is_closed'] else base_score

            candidate['scoring_breakdown'] = {
                'semantic':   round(raw['semantic'],    3),
                'distance':   round(raw['distance'],    3),
                'hours':      round(raw['hours'],       3),
                'budget':     round(raw['budget'],      3),
                'popularity': round(raw['popularity'],  3),
            }
            
        # Sort initially by base score
        candidates.sort(key=lambda x: x['_base_score'], reverse=True)
        
        # 5. Apply Diversity Bonus (Greedy approach)
        final_list = []
        for candidate in candidates:
            diversity_bonus = self._apply_diversity_bonus(candidate, seen_categories, cluster_counts)
            
            final_score = candidate['_base_score'] + (WEIGHT_DIVERSITY * diversity_bonus)
            
            # Enforce hard filter: if unequivocally closed, the entire score is 0
            if candidate['scoring_breakdown']['hours'] == 0.0:
                final_score = 0.0
                
            candidate['final_score'] = round(final_score, 4)
            candidate['scoring_breakdown']['diversity'] = round(diversity_bonus, 3)
            
            final_list.append(candidate)
            
        # Re-sort using final_score (diversity bonus might have nudged some items)
        final_list.sort(key=lambda x: x['final_score'], reverse=True)
        
        # Clean up internal fields
        for item in final_list:
            item.pop('_base_score', None)
            
        return final_list
