"""
Attraction models/schemas for request/response validation.
Aligned with places_enriched.json and pgvector attractions table.
"""
from typing import Optional, List
from pydantic import BaseModel


class AttractionBase(BaseModel):
    """Base schema matching places_enriched.json structure (excluding scraped_at)."""
    source: Optional[str] = None
    place_id: Optional[str] = None
    name: str
    categories: Optional[List[str]] = None
    category_id: Optional[List[str]] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    telephone: Optional[str] = None
    url: Optional[str] = None
    type: Optional[str] = None
    budget: Optional[str] = None
    hours: Optional[str] = None
    description: Optional[str] = None  # text description used to generate embedding
    embedding: Optional[List[float]] = None  # vector embedding for pgvector similarity search
    cluster_id: Optional[int] = None  # HDBSCAN/DBSCAN cluster assignment (-1 = noise)
    similarity: Optional[float] = None  # returned by vector search


class AttractionCreate(AttractionBase):
    """Schema for creating an attraction"""
    pass


class AttractionResponse(AttractionBase):
    """Schema for attraction response"""
    activity_id: str

    class Config:
        from_attributes = True

