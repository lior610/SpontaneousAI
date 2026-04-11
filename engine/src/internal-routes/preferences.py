"""
Build / refresh user preference embeddings (user_preference_embeddings).

Called by the Node API after trip create/update or when global user preferences change.
"""
import logging
from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException

from src.services.preference_service import PreferenceComposer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preferences", tags=["preferences"])

preference_composer = PreferenceComposer()


class PreferenceBuildRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    trip_id: int = Field(..., gt=0)
    force_rebuild: bool = True


@router.post("/build")
async def build_preference_embedding(body: PreferenceBuildRequest):
    """
    Compute and upsert the blended preference vector for (user_id, trip_id).

    Use force_rebuild=True after wizard saves so trip setup + user qualifiers
    are re-embedded instead of returning a stale cached vector.
    """
    try:
        await preference_composer.build(
            user_id=body.user_id,
            trip_id=body.trip_id,
            force_rebuild=body.force_rebuild,
        )
        return {"ok": True, "user_id": body.user_id, "trip_id": body.trip_id}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Failed to build preference embedding")
        raise HTTPException(status_code=500, detail=str(e))
