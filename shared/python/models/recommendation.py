"""
Recommendation models - Recommendation requests and responses
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from .attraction import AttractionResponse

class RecommendationRequest(BaseModel):
    """Schema for requesting a recommendation"""
    user_id: int
    trip_id: int
    location_id: int
    current_location: Optional[dict] = None  # {"lat": float, "lng": float}
    current_time: Optional[datetime] = None  # Local time at the destination ideally
    travel_style: Optional[str] = 'balanced' # budget, balanced, premium
    max_walk_km: Optional[float] = 2.0
    context: Optional[dict] = None  # weather, time_of_day, etc.
    
class RecommendationFeedback(BaseModel):
    """Schema for posting feedback on a recommendation"""
    user_id: int
    trip_id: int
    place_id: str
    action: str  # 'liked', 'skipped', 'visited'

class RecommendationResponse(BaseModel):
    """Schema for recommendation response"""
    attraction: AttractionResponse
    score: float  # Similarity/relevance score
    reasoning: Optional[str] = None  # Why this was recommended
    distance_km: Optional[float] = None
    estimated_duration_minutes: Optional[int] = None
    generated_at: datetime

