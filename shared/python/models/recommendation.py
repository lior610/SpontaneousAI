"""
Recommendation models - Recommendation requests and responses
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from .attraction import AttractionResponse

class RecommendationRequest(BaseModel):
    """Schema for requesting a recommendation"""
    user_id: int
    trip_id: int
    current_location: Optional[dict] = None  # {"lat": float, "lng": float}
    current_time: Optional[datetime] = None  # Local time at the destination ideally
    context: Optional[dict] = None  # weather, time_of_day, etc.
    category_filter: Optional[str] = None  # e.g. "food" - restricts results to this category
    
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
    reachable_by: Optional[str] = None  # 'walking' | 'transit'
    transit_minutes: Optional[int] = None
    transit_summary: Optional[str] = None


class CompanionSuggestion(BaseModel):
    """
    A "because you liked X, you might also like Y" suggestion.

    Returned (optionally) by the feedback endpoint when a liked attraction
    belongs to a popular trip whose persona matches the user's preference vector.
    """
    place_id: str
    name: str
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    categories: Optional[List[str]] = None
    budget: Optional[str] = None
    hours: Optional[str] = None
    image_url: Optional[str] = None
    reason: str
    popular_trip_id: int
    persona_slug: Optional[str] = None
    similarity: float
    distance_km: Optional[float] = None

