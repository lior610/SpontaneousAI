"""
Models module - Shared data models
"""
from .attraction import (
    AttractionBase,
    AttractionCreate,
    AttractionResponse
)
from .user import (
    UserBase,
    UserCreate,
    UserUpdate,
    UserResponse
)
from .trip import (
    TripBase,
    TripCreate,
    TripUpdate,
    TripResponse,
    TripStatus
)
from .user_preferences import (
    UserPreferencesBase,
    UserPreferencesCreate,
    UserPreferencesUpdate,
    UserPreferencesResponse,
    InterestCategory,
    TransportationMode
)
from .recommendation import (
    RecommendationRequest,
    RecommendationResponse
)
from .destination import (
    DestinationBase,
    DestinationCreate,
    DestinationUpdate,
    DestinationResponse,
    DestinationStatus
)
from .utility import (
    UtilityRequest
)

__all__ = [
    # Attraction
    'AttractionBase',
    'AttractionCreate',
    'AttractionResponse',
    # User
    'UserBase',
    'UserCreate',
    'UserUpdate',
    'UserResponse',
    # Trip
    'TripBase',
    'TripCreate',
    'TripUpdate',
    'TripResponse',
    'TripStatus',
    # User Preferences
    'UserPreferencesBase',
    'UserPreferencesCreate',
    'UserPreferencesUpdate',
    'UserPreferencesResponse',
    'InterestCategory',
    'TransportationMode',
    # Recommendation
    'RecommendationRequest',
    'RecommendationResponse',
    # Destination
    'DestinationBase',
    'DestinationCreate',
    'DestinationUpdate',
    'DestinationResponse',
    'DestinationStatus',
    # Utility
    'UtilityRequest',
]

