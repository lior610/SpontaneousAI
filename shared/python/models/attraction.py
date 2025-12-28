"""
Attraction models/schemas for request/response validation.
Aligned with the attractions table and vector search output.
"""
from typing import Optional
from pydantic import BaseModel


class AttractionBase(BaseModel):
    name: str
    short_description: Optional[str] = None
    categories: Optional[str] = None
    tags: Optional[str] = None
    good_for: Optional[str] = None
    indoor_outdoor: Optional[str] = None
    typical_duration_min: Optional[int] = None
    effort_level: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    price_level: Optional[int] = None
    rating: Optional[float] = None
    requires_booking: Optional[bool] = None
    age_min: Optional[int] = None
    accessibility_features: Optional[bool] = None
    similarity: Optional[float] = None  # returned by vector search


class AttractionCreate(AttractionBase):
    """Schema for creating an attraction"""
    pass


class AttractionResponse(AttractionBase):
    """Schema for attraction response"""
    activity_id: str

    class Config:
        from_attributes = True

