"""
Persona catalog for the popular-trips pool.

Personas are the "types of people in society" used to (a) steer the LLM when it
composes popular routes and (b) match a live user to a popular trip at runtime.

Each persona `description` is embedded with the same model used for attractions
(all-MiniLM-L6-v2, 384d), so cosine similarity against a user's preference
vector is meaningful. Descriptions are intentionally rich and use the same
vocabulary as the attraction descriptions to keep the embedding space aligned.

This is plain data - extend or tune it freely, then re-run
generate_popular_trips.py to rebuild the pool.
"""
from typing import List, Dict

PERSONAS: List[Dict[str, str]] = [
    {
        "slug": "art-and-culture-lover",
        "name": "Art & Culture Lover",
        "description": (
            "Art and culture lover who seeks museums, galleries, exhibitions, "
            "theaters, and creative neighborhoods. Enjoys contemporary and classical "
            "art, design, architecture, and cultural landmarks over nightlife or shopping."
        ),
    },
    {
        "slug": "foodie",
        "name": "Foodie",
        "description": (
            "Food-focused traveler chasing restaurants, cafes, street food, markets, "
            "bakeries, and local culinary specialties. Prioritizes memorable dining "
            "experiences, tastings, and food culture."
        ),
    },
    {
        "slug": "history-buff",
        "name": "History Buff",
        "description": (
            "History enthusiast drawn to monuments, heritage sites, historic landmarks, "
            "castles, ruins, memorials, and old towns. Values sightseeing that tells the "
            "story of a place and its past."
        ),
    },
    {
        "slug": "nightlife-seeker",
        "name": "Nightlife Seeker",
        "description": (
            "Nightlife seeker who lives for bars, clubs, live music, cocktail lounges, "
            "and evening entertainment. Prefers a vibrant after-dark scene, drinks, and "
            "social energy."
        ),
    },
    {
        "slug": "family-with-kids",
        "name": "Family with Kids",
        "description": (
            "Family traveling with children looking for kid-friendly attractions such as "
            "parks, zoos, aquariums, science centers, playgrounds, and interactive museums. "
            "Values safe, easy, and fun activities for all ages."
        ),
    },
    {
        "slug": "budget-backpacker",
        "name": "Budget Backpacker",
        "description": (
            "Budget-conscious backpacker seeking free and cheap things to do: public parks, "
            "free museums, viewpoints, walking areas, and affordable local eats. Prioritizes "
            "value and authentic low-cost experiences."
        ),
    },
    {
        "slug": "nature-outdoors",
        "name": "Nature & Outdoors",
        "description": (
            "Outdoor and nature lover who prefers parks, gardens, greenery, waterfronts, "
            "hiking spots, and scenic viewpoints. Enjoys fresh air, walking, and open spaces "
            "over indoor venues."
        ),
    },
    {
        "slug": "luxury-traveler",
        "name": "Luxury Traveler",
        "description": (
            "Premium traveler who favors upscale dining, fine restaurants, luxury shopping, "
            "spas, iconic landmarks, and refined experiences. Prioritizes comfort, quality, "
            "and exclusivity over budget."
        ),
    },
]
