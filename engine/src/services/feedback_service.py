"""
Feedback Service.

Handles real-time feedback loop. Persists actions (liked/skipped/visited)
and pushes EMA vector updates to the PreferenceService when an
attraction is liked.
"""
import sys
import logging
from typing import Dict, Any, Optional
from pathlib import Path

shared_path = str(Path(__file__).resolve().parents[3] / "shared" / "python")
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from db.usersConnection import get_db_connection
from src.db.feedback_queries import record_feedback
from src.services.preference_service import PreferenceComposer
from src.services.companion_service import CompanionSuggestionService

logger = logging.getLogger(__name__)

class FeedbackService:
    """Service handling runtime feedback (swipes/interactions)."""
    
    def __init__(
        self,
        preference_composer: PreferenceComposer,
        companion_service: Optional[CompanionSuggestionService] = None,
    ):
        self.preference_composer = preference_composer
        self.companion_service = companion_service

    async def record_interaction(
        self,
        user_id: int,
        trip_id: int,
        place_id: str,
        action: str
    ) -> Dict[str, Any]:
        """Record user interaction and update preference embeddings if applicable."""
        if action not in ("liked", "skipped", "visited"):
            raise ValueError("Invalid action. Allowed: 'liked', 'skipped', 'visited'.")
            
        try:
            with get_db_connection() as conn:
                record_feedback(conn, trip_id, place_id, action)
                # Explicit commit; usersConnection's context manager may or may not auto-commit.
                conn.commit()
                
            logger.info(f"Recorded feedback: User {user_id}, Trip {trip_id}, place {place_id} -> {action}")
            
            result: Dict[str, Any] = {"status": "success", "action": action}

            # If the action was 'liked', apply exponential moving average to dynamic trip vector
            if action == 'liked':
                await self.preference_composer.apply_feedback(user_id, trip_id, place_id)
                logger.info("Real-time EMA applied for liked attraction.")

                # After the EMA update, check the popular-trips pool for a
                # "because you liked X, you might also like Y" companion suggestion.
                if self.companion_service is not None:
                    suggestion = self.companion_service.suggest(user_id, trip_id, place_id)
                    if suggestion is not None:
                        result["companion_suggestion"] = suggestion
                        logger.info(
                            f"Companion suggestion for trip {trip_id}: "
                            f"{suggestion.get('place_id')} (sim={suggestion.get('similarity')})"
                        )

            return result
            
        except Exception as e:
            logger.error(f"Failed to record feedback: {str(e)}")
            raise RuntimeError(f"Error recording feedback: {str(e)}") from e
