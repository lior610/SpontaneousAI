"""
Feedback Service.

Handles real-time feedback loop. Persists actions (liked/skipped/visited)
and pushes EMA vector updates to the PreferenceService when an
attraction is liked.
"""
import sys
import logging
from typing import Dict, Any
from pathlib import Path

shared_path = str(Path(__file__).resolve().parents[3] / "shared" / "python")
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from db.usersConnection import get_db_connection
from src.db.feedback_queries import record_feedback
from src.services.preference_service import PreferenceComposer

logger = logging.getLogger(__name__)

class FeedbackService:
    """Service handling runtime feedback (swipes/interactions)."""
    
    def __init__(self, preference_composer: PreferenceComposer):
        self.preference_composer = preference_composer

    async def record_interaction(
        self,
        user_id: int,
        trip_id: int,
        place_id: str,
        action: str
    ) -> Dict[str, Any]:
        """
        Record user interaction and update preference embeddings if applicable.
        
        Args:
            user_id: ID of the user
            trip_id: Current trip context
            place_id: ID of the interacting attraction
            action: Action taken (e.g. 'liked', 'skipped', 'visited')
            
        Returns:
            Dictionary with operation status
        """
        if action not in ("liked", "skipped", "visited"):
            raise ValueError("Invalid action. Allowed: 'liked', 'skipped', 'visited'.")
            
        try:
            with get_db_connection() as conn:
                record_feedback(conn, trip_id, place_id, action)
                # Commit manually or ideally we rely on the context manager config depending
                # on usersConnection.py setup.
                conn.commit()
                
            logger.info(f"Recorded feedback: User {user_id}, Trip {trip_id}, place {place_id} -> {action}")
            
            # If the action was 'liked', apply exponential moving average to dynamic trip vector
            if action == 'liked':
                await self.preference_composer.apply_feedback(user_id, trip_id, place_id)
                logger.info("Real-time EMA applied for liked attraction.")
                
            return {"status": "success", "action": action}
            
        except Exception as e:
            logger.error(f"Failed to record feedback: {str(e)}")
            raise RuntimeError(f"Error recording feedback: {str(e)}") from e
