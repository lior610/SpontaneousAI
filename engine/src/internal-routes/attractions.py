"""
Attractions Router - API endpoints for attractions
"""
from fastapi import APIRouter, HTTPException
from models.attraction import AttractionCreate, AttractionResponse
from src.services.attraction_service import (
    get_attraction_by_id,
    create_attraction,
    search_attractions
)

router = APIRouter(prefix="/attractions", tags=["attractions"])

@router.get("/{attraction_id}", response_model=AttractionResponse)
async def get_attraction_endpoint(attraction_id: int):
    """Get attraction by ID"""
    attraction = await get_attraction_by_id(attraction_id)
    if not attraction:
        raise HTTPException(status_code=404, detail="Attraction not found")
    return attraction

@router.post("/", response_model=AttractionResponse, status_code=201)
async def create_attraction_endpoint(attraction: AttractionCreate):
    """Create a new attraction"""
    attraction_data = attraction.model_dump()
    created = await create_attraction(attraction_data)
    return created
