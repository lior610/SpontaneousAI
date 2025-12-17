"""
Attraction models/schemas for request/response validation
"""
from pydantic import BaseModel
from typing import Optional

class AttractionBase(BaseModel):
    """Base attraction schema"""
    # TODO: Add more fields as needed
    name: str
    description: Optional[str] = None
    location: Optional[str] = None

class AttractionCreate(AttractionBase):
    """Schema for creating an attraction"""
    pass

class AttractionResponse(AttractionBase):
    """Schema for attraction response"""
    id: int
    
    class Config:
        from_attributes = True

