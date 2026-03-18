"""
Recommendations Router - API endpoints for receiving recommendations and posting feedback.
"""
import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends

from models.recommendation import RecommendationRequest, RecommendationResponse, RecommendationFeedback
from src.services.preference_service import PreferenceComposer
from src.services.cluster_retrieval import ClusterRetrievalService
from src.services.ranking_service import RankingEngine
from src.services.feedback_service import FeedbackService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

# Depending on your DI setup, you can instantiate these or inject them
preference_composer = PreferenceComposer()
cluster_retrieval = ClusterRetrievalService(top_per_cluster=5, max_clusters=5)
ranking_engine = RankingEngine()
feedback_service = FeedbackService(preference_composer=preference_composer)

@router.post("/", response_model=List[RecommendationResponse])
async def get_recommendations(req: RecommendationRequest):
    """
    Get dynamic, diverse recommendations based on user preference and real-time feedback.
    """
    try:
        # 1. Build or retrieve the user's latest preference vector
        preference_vector = await preference_composer.build(
            user_id=req.user_id,
            trip_id=req.trip_id,
            force_rebuild=False
        )
        
        # 2. Retrieve Cluster-Diverse Candidates
        # Here we extract hard filters from context if any (e.g. is_open)
        filters = {}
        # if req.context and req.context.get('is_open'):
        #     filters['hours'] = ...
            
        user_lat = req.current_location.get('lat') if req.current_location else None
        user_lng = req.current_location.get('lng') if req.current_location else None
        current_hour = req.current_time.hour if req.current_time else None
            
        candidates = cluster_retrieval.get_candidate_pool(
            location_id=req.location_id,
            trip_id=req.trip_id,
            preference_vector=preference_vector,
            context_filters=filters,
            user_lat=user_lat,
            user_lng=user_lng,
            max_walk_km=req.max_walk_km,
            current_hour=current_hour
        )
        
        # 3. Retrieve Explicitly Seen Categories for Diversity Ranking
        try:
            from db.usersConnection import get_db_connection as get_users_conn
            from db.attractionsConnection import get_db_connection as get_attr_conn
            from src.db.feedback_queries import get_excluded_place_ids, get_attraction_categories
            
            with get_users_conn() as users_conn:
                excluded_ids = list(get_excluded_place_ids(users_conn, req.trip_id))
            
            real_seen_categories = set()
            if excluded_ids:
                with get_attr_conn() as attr_conn:
                    real_seen_categories = get_attraction_categories(attr_conn, excluded_ids)
                    
        except Exception as e:
            logger.warning(f"Could not load explicitly seen categories: {e}")
            real_seen_categories = set()

        # 4. Rank the Candidates
        ranked_candidates = ranking_engine.rank_candidates(
            candidates=candidates,
            user_lat=user_lat,
            user_lng=user_lng,
            max_walk_km=req.max_walk_km,
            travel_style=req.travel_style,
            current_hour=current_hour,
            real_seen_categories=real_seen_categories
        )
        
        # 5. Format Output
        responses = []
        for c in ranked_candidates:
            responses.append(RecommendationResponse(
                attraction=c, # Note: Pydantic will coerce the dict to AttractionResponse
                score=c.get('final_score', 0.0),
                reasoning=str(c.get('scoring_breakdown', {})),
                distance_km=c.get('distance_km'),
                estimated_duration_minutes=None, # TBD by future logic
                generated_at=req.current_time or "2023-01-01T00:00:00Z" # Dummy fallback
            ))
            
        return responses
        
    except Exception as e:
        logger.exception("Failed to get recommendations")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback", status_code=201)
async def post_feedback(feedback: RecommendationFeedback):
    """
    Post interaction feedback on an attraction.
    Actions: 'liked', 'skipped', 'visited'.
    'liked' actions will trigger an EMA update on the user's preference vector.
    """
    try:
        result = await feedback_service.record_interaction(
            user_id=feedback.user_id,
            trip_id=feedback.trip_id,
            place_id=feedback.place_id,
            action=feedback.action
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Failed to record feedback")
        raise HTTPException(status_code=500, detail=str(e))
