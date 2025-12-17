"""
Destination models - Pending destinations queue for data fetching
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class DestinationStatus(str, Enum):
    """Destination queue status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DestinationBase(BaseModel):
    """Base destination schema"""
    location: str  # City, region, or coordinates
    priority: int = 0  # Higher = more urgent

class DestinationCreate(DestinationBase):
    """Schema for adding destination to queue"""
    requested_by_user_id: Optional[int] = None

class DestinationUpdate(BaseModel):
    """Schema for updating destination status"""
    status: Optional[DestinationStatus] = None
    error_message: Optional[str] = None

class DestinationResponse(DestinationBase):
    """Schema for destination response"""
    id: int
    status: DestinationStatus
    requested_by_user_id: Optional[int] = None
    created_at: datetime
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True

