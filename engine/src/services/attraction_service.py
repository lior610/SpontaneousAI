"""
Attraction Service - Business logic for attractions
"""
from src.db.attractionsConnection import get_connection
from src.services.embedding_service import generate_embedding

async def get_attractions():
    """Get all attractions"""
    # TODO: Implement database query
    return []

async def get_attraction_by_id(attraction_id: int):
    """Get attraction by ID"""
    # TODO: Implement database query
    return None

async def create_attraction(attraction_data: dict):
    """
    Create a new attraction (from scraping)
    Generates embedding and stores in database
    """
    # Generate embedding from attraction text
    attraction_text = f"{attraction_data.get('name', '')} {attraction_data.get('description', '')}"
    embedding = await generate_embedding(attraction_text)
    
    # TODO: Store attraction + embedding in database
    # INSERT INTO attractions (name, description, location, embedding) VALUES (...)
    
    return attraction_data

async def search_attractions(query: str):
    """
    Search attractions using vector similarity
    Generates query embedding and finds similar attractions
    """
    # Generate embedding for search query
    query_embedding = await generate_embedding(query)
    
    # TODO: Vector similarity search in database
    # SELECT * FROM attractions 
    # ORDER BY embedding <=> %s::vector 
    # LIMIT 10
    
    return []

