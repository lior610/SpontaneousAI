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
    trip_id: Optional[int] = None
    current_location: Optional[dict] = None  # {"lat": float, "lng": float}
    current_time: Optional[datetime] = None
    context: Optional[dict] = None  # weather, time_of_day, etc.

class RecommendationResponse(BaseModel):
    """Schema for recommendation response"""
    attraction: AttractionResponse
    score: float  # Similarity/relevance score
    reasoning: Optional[str] = None  # Why this was recommended
    distance_km: Optional[float] = None
    estimated_duration_minutes: Optional[int] = None
    generated_at: datetime

