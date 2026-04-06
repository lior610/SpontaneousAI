from typing import Optional, Literal
from pydantic import BaseModel

class UtilityRequest(BaseModel):
    """Request schema for retrieving closest utilities"""
    lat: float
    lng: float
    location_id: int
    parent_category: Literal["pharmacy", "medical", "grocery", "convenience", "police_emergency"]
    limit: Optional[int] = 5
    current_hour: Optional[int] = None
