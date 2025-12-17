"""
Trip models - Active and future trips
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

class TripStatus(str, Enum):
    """Trip status enumeration"""
    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TripBase(BaseModel):
    """Base trip schema"""
    destination: str
    start_date: datetime
    end_date: datetime
    status: TripStatus = TripStatus.PLANNING

class TripCreate(TripBase):
    """Schema for creating a new trip"""
    user_id: int

class TripUpdate(BaseModel):
    """Schema for updating trip"""
    destination: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[TripStatus] = None

class TripResponse(TripBase):
    """Schema for trip response"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

