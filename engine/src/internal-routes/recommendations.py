"""
Recommendations Router - API endpoints for receiving recommendations and posting feedback.
"""
import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from models.recommendation import RecommendationRequest, RecommendationResponse, RecommendationFeedback
from src.services.preference_service import PreferenceComposer
from src.services.cluster_retrieval import ClusterRetrievalService
from src.services.ranking_service import RankingEngine
from src.services.feedback_service import FeedbackService
from db.attractionsConnection import get_db_connection as get_attr_conn

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
        
        # 2. Extract Hard Filters
        filters = {}
        if req.category_filter:
            filters['category_filter'] = req.category_filter
        
        user_lat = req.current_location.get('lat') if req.current_location else None
        user_lng = req.current_location.get('lng') if req.current_location else None
        
        # We start with UTC hour, but will adjust below based on destination timezone
        current_hour = req.current_time.hour if req.current_time else None
            
        try:
            from db.usersConnection import get_db_connection as get_users_conn
            from src.db.feedback_queries import get_excluded_place_ids
            from src.db.user_queries import get_trip, get_user
            from src.db.feedback_queries import get_attraction_categories

            with get_users_conn() as users_conn:
                excluded_ids = list(get_excluded_place_ids(users_conn, req.trip_id))
                trip_data = get_trip(users_conn, req.trip_id)
                user_data = get_user(users_conn, req.user_id)

            if not trip_data or not user_data:
                raise HTTPException(status_code=404, detail="Trip or User not found in database.")

            db_travel_style = user_data.get('travel_style')
            db_max_walk_km = trip_data.get('max_walking_distance')
            if not db_travel_style or db_max_walk_km is None:
                raise HTTPException(status_code=500, detail="Missing travel_style or max_walking_distance in database.")
            db_max_walk_km = float(db_max_walk_km)

            dest = trip_data.get("destination")
            if not dest:
                raise HTTPException(status_code=500, detail="Missing destination in database.")

            with get_attr_conn() as attr_conn:
                cursor = attr_conn.cursor()
                cursor.execute("SELECT id, timezone FROM locations WHERE LOWER(name) = LOWER(%s)", (dest,))
                row = cursor.fetchone()
                cursor.close()
                if not row:
                    raise HTTPException(status_code=500, detail=f"Destination '{dest}' not found in locations table.")
                db_location_id = row[0]
                db_timezone = row[1]
                
            # 2.5 Adjust current_hour to destination's local time
            if db_timezone and req.current_time:
                try:
                    local_time = req.current_time.astimezone(ZoneInfo(db_timezone))
                    current_hour = local_time.hour
                    logger.info(f"Timezone adjusted: UTC {req.current_time.hour}:00 -> {db_timezone} {current_hour}:00")
                except Exception as tz_err:
                    logger.warning(f"Failed to adjust timezone for {db_timezone}: {tz_err}")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Could not load explicitly DB limits: {e}")
            raise HTTPException(status_code=500, detail=f"Internal Server Error retrieving DB trip bounds: {e}")
            
        # 3. Retrieve Cluster-Diverse Candidates
        candidates = cluster_retrieval.get_candidate_pool(
            location_id=db_location_id,
            trip_id=req.trip_id,
            preference_vector=preference_vector,
            context_filters=filters,
            user_lat=user_lat,
            user_lng=user_lng,
            max_walk_km=db_max_walk_km,
            current_hour=current_hour
        )
        
        try:
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
            max_walk_km=db_max_walk_km,
            travel_style=db_travel_style,
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
