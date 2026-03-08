"""
Database Query Layer for Users and Trips.

Pure SQL query functions against the users DB.
No business logic — only fetches and returns raw dicts.

Flow: PreferenceService → user_queries → users DB
"""
from typing import Optional, Dict, Any


def get_user(conn, user_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch a user row by ID.

    Returns all columns as a dict, or None if not found.
    Relevant fields for preference building:
        age_group, travel_style, pace_preference,
        preferred_start_hour, dietary_style, energy_level, hunger_level
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            id, username, email,
            home_country, age_group, travel_style,
            pace_preference, preferred_start_hour,
            dietary_style, hunger_level, energy_level,
            created_at, updated_at
        FROM users
        WHERE id = %s
        """,
        (user_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    if row is None:
        return None
    columns = [
        "id", "username", "email",
        "home_country", "age_group", "travel_style",
        "pace_preference", "preferred_start_hour",
        "dietary_style", "hunger_level", "energy_level",
        "created_at", "updated_at",
    ]
    return dict(zip(columns, row))


def get_trip(conn, trip_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch a trip row by ID.

    Returns all columns as a dict, or None if not found.
    Relevant fields for preference building:
        preference_breakdown (JSONB), budget, max_walking_distance,
        preferred_transportation, max_travel_time_min, with_kids,
        current_lat, current_lng, timezone,
        local_hour_last_seen, day_of_week_last_seen
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            trip_id, user_id, destination,
            start_date, end_date, budget,
            preference_breakdown,
            max_walking_distance, preferred_transportation, max_travel_time_min,
            with_kids,
            current_lat, current_lng, timezone,
            local_hour_last_seen, day_of_week_last_seen,
            created_at, updated_at
        FROM trips
        WHERE trip_id = %s
        """,
        (trip_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    if row is None:
        return None
    columns = [
        "trip_id", "user_id", "destination",
        "start_date", "end_date", "budget",
        "preference_breakdown",
        "max_walking_distance", "preferred_transportation", "max_travel_time_min",
        "with_kids",
        "current_lat", "current_lng", "timezone",
        "local_hour_last_seen", "day_of_week_last_seen",
        "created_at", "updated_at",
    ]
    return dict(zip(columns, row))
