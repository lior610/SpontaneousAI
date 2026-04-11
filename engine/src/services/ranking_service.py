"""
Ranking Service - Engine layer for scoring and re-ranking candidates.

Applies distance, opening hours, budget, and categorical diversity
filters dynamically on top of the vector similarity score.
"""

import math
import os
from typing import List, Dict, Any, Optional

# Scoring weights (must sum to 1.0 ideally)
WEIGHT_SEMANTIC = float(os.getenv("RANKING_WEIGHT_SEMANTIC", "0.35"))
WEIGHT_HOURS = float(os.getenv("RANKING_WEIGHT_HOURS", "0.10"))
WEIGHT_DISTANCE = float(os.getenv("RANKING_WEIGHT_DISTANCE", "0.20"))
WEIGHT_BUDGET = float(os.getenv("RANKING_WEIGHT_BUDGET", "0.10"))
WEIGHT_POPULARITY = float(os.getenv("RANKING_WEIGHT_POPULARITY", "0.20"))
WEIGHT_DIVERSITY = float(os.getenv("RANKING_WEIGHT_DIVERSITY", "0.05"))

# Penalties
CLUSTER_PENALTY_MULTIPLIER = float(os.getenv("RANKING_CLUSTER_PENALTY", "0.5"))

def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in km."""
    R = 6371.0  # Earth radius in kilometers

    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

class RankingEngine:
    """
    Ranks a pool of candidate attractions based on weighted contextual scores.
    """
    
    def _score_distance(
        self, 
        attraction_lat: Optional[float], 
        attraction_lng: Optional[float], 
        user_lat: Optional[float], 
        user_lng: Optional[float], 
        max_walk_km: float
    ) -> tuple[float, Optional[float]]:
        dist_km = None
        distance_score = 0.0
        if attraction_lat and attraction_lng and user_lat and user_lng:
            dist_km = calculate_haversine_distance(user_lat, user_lng, attraction_lat, attraction_lng)
            # Max walk constraint - floor at 0 as requested by spec
            distance_score = max(0.0, 1.0 - (dist_km / max(0.1, max_walk_km)))
        return distance_score, dist_km

    def _score_hours(self, hours_str: Optional[str], current_hour: Optional[int]) -> float:
        hours_score = 0.5  # Default unknown
        if hours_str and current_hour is not None:
            try:
                parts = hours_str.split('-')
                if len(parts) == 2:
                    open_hr = int(parts[0].split(':')[0])
                    close_hr = int(parts[1].split(':')[0])
                    if open_hr <= close_hr:
                        if open_hr <= current_hour < close_hr:
                            hours_score = 1.0
                        else:
                            hours_score = 0.0
                    else:
                        # Overnight e.g. 22:00-02:00
                        if current_hour >= open_hr or current_hour < close_hr:
                            hours_score = 1.0
                        else:
                            hours_score = 0.0
            except Exception:
                pass
        return hours_score
        
    def _score_budget(self, attr_budget_str: str, travel_style: str) -> float:
        budget_score = 0.5
        budget_val = None
        if attr_budget_str:
            numeric_str = ''.join(c for c in attr_budget_str if c.isdigit() or c == '.')
            if numeric_str:
                try:
                    budget_val = float(numeric_str)
                except ValueError:
                    pass
        
        if budget_val is not None:
            if travel_style == 'budget':
                budget_score = 1.0 if budget_val <= 15.0 else 0.2
            elif travel_style == 'balanced':
                budget_score = 1.0 if 10.0 <= budget_val <= 50.0 else 0.5
            elif travel_style == 'premium':
                budget_score = 1.0 if budget_val >= 40.0 else 0.5
        return budget_score

    def _score_popularity(self, popularity_val: Any) -> float:
        try:
            pop = float(popularity_val)
            return max(0.0, min(1.0, pop))
        except (ValueError, TypeError):
            return 0.2

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
        """
        Rank the candidates based on contextual parameters.
        
        Args:
            candidates: List of attractions from the Cluster Retrieval
            user_lat: Current user latitude
            user_lng: Current user longitude
            max_walk_km: Maximum preferred walking distance
            travel_style: 'budget', 'balanced', or 'premium'
            current_hour: Current local hour (0-23)
            
        Returns:
            Sorted list of attractions containing final breakdown scores.
        """
        if not candidates:
            return []
            
        seen_categories = set(real_seen_categories) if real_seen_categories else set()
        cluster_counts = {}
        
        # We need to process diversity bonus dynamically, so we can't fully
        # independent score. However, we'll do an initial pass for base scores.
        
        for candidate in candidates:
            attraction_lat = candidate.get('latitude')
            attraction_lng = candidate.get('longitude')
            
            # 1. Semantic Score (0-1)
            semantic_score = candidate.get('similarity', 0.0)
            
            # 2. Distance Score (0-1)
            distance_score, dist_km = self._score_distance(
                attraction_lat, attraction_lng, user_lat, user_lng, max_walk_km
            )
            if dist_km is not None:
                candidate['distance_km'] = round(dist_km, 2)
                
            # 3. Hours Score (0, 0.5, 1)
            hours_score = self._score_hours(candidate.get('hours'), current_hour)
                
            # 4. Budget Score (0-1)
            attr_budget = str(candidate.get('budget', '')).strip()
            budget_score = self._score_budget(attr_budget, travel_style)
            
            # 5. Popularity Score (0-1)
            popularity_score = self._score_popularity(candidate.get('popularity'))
            
            # Save base scores before diversity bonus
            candidate['_base_score'] = (
                (WEIGHT_SEMANTIC * semantic_score) + 
                (WEIGHT_DISTANCE * distance_score) + 
                (WEIGHT_HOURS * hours_score) + 
                (WEIGHT_BUDGET * budget_score) +
                (WEIGHT_POPULARITY * popularity_score)
            )
            
            # If verifiably closed, tank the score to 0
            if hours_score == 0.0:
                candidate['_base_score'] = 0.0
            
            # Append component scores for debugging / explanations
            candidate['scoring_breakdown'] = {
                'semantic': round(semantic_score, 3),
                'distance': round(distance_score, 3),
                'hours': round(hours_score, 3),
                'budget': round(budget_score, 3),
                'popularity': round(popularity_score, 3)
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
