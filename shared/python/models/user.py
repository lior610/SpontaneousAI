"""
User models - User profiles and authentication
"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    name: str

class UserCreate(UserBase):
    """Schema for creating a new user"""
    password: str  # Will be hashed before storage

class UserUpdate(BaseModel):
    """Schema for updating user"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None

class UserResponse(UserBase):
    """Schema for user response"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

