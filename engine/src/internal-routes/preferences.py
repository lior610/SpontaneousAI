"""
Preference embedding build — called by the Node API after trip/user preference changes.
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.services.preference_service import PreferenceComposer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preferences", tags=["preferences"])

preference_composer = PreferenceComposer()


class PreferenceBuildRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    trip_id: int = Field(..., gt=0)
    force_rebuild: bool = True


@router.post("/build")
async def build_preference_embedding(req: PreferenceBuildRequest):
    """
    Build the user–trip preference vector and upsert into user_preference_embeddings.
    """
    try:
        vec = await preference_composer.build(
            user_id=req.user_id,
            trip_id=req.trip_id,
            force_rebuild=req.force_rebuild,
        )
        return {"status": "ok", "dimension": int(len(vec))}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception("preference build failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
