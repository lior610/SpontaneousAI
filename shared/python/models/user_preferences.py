"""
User Preferences models - User interests, constraints, and preferences
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

class InterestCategory(str, Enum):
    """Interest categories"""
    HISTORY = "history"
    FOOD = "food"
    NIGHTLIFE = "nightlife"
    NATURE = "nature"
    ART = "art"
    SPORTS = "sports"
    SHOPPING = "shopping"
    ENTERTAINMENT = "entertainment"

class TransportationMode(str, Enum):
    """Transportation preferences"""
    WALKING = "walking"
    DRIVING = "driving"
    PUBLIC_TRANSPORT = "public_transport"
    MIXED = "mixed"

class UserPreferencesBase(BaseModel):
    """Base user preferences schema"""
    interests: List[InterestCategory] = []
    budget_level: Optional[str] = None  # "budget", "moderate", "luxury"
    max_walking_distance_km: Optional[float] = None
    transportation_mode: TransportationMode = TransportationMode.MIXED
    dietary_restrictions: List[str] = []

class UserPreferencesCreate(UserPreferencesBase):
    """Schema for creating user preferences"""
    user_id: int

class UserPreferencesUpdate(BaseModel):
    """Schema for updating user preferences"""
    interests: Optional[List[InterestCategory]] = None
    budget_level: Optional[str] = None
    max_walking_distance_km: Optional[float] = None
    transportation_mode: Optional[TransportationMode] = None
    dietary_restrictions: Optional[List[str]] = None

class UserPreferencesResponse(UserPreferencesBase):
    """Schema for user preferences response"""
    id: int
    user_id: int
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

