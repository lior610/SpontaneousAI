"""
Utilities Router - API endpoints for immediate need utilities
"""
from fastapi import APIRouter, HTTPException
from typing import List
from models.utility import UtilityRequest
from models.attraction import AttractionResponse
from src.services.utility_service import get_closest_utilities

router = APIRouter(prefix="/utilities", tags=["utilities"])

@router.post("/closest", response_model=List[AttractionResponse])
async def post_closest_utilities(req: UtilityRequest):
    """
    Get the closest utilities based on parent category and geographic proximity.
    Returns a list of matching attraction locations.
    """
    try:
        results = await get_closest_utilities(
            parent_category=req.parent_category,
            lat=req.lat,
            lng=req.lng,
            location_id=req.location_id,
            current_hour=req.current_hour,
            limit=req.limit or 5
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
