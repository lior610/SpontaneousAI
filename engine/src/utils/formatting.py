"""
Formatting utilities for data transformation.
"""
from typing import List, Dict, Any


def format_embedding_for_pgvector(embedding: Any) -> str:
    """
    Convert embedding vector to pgvector format string.
    
    Args:
        embedding: List of floats or string in pgvector format
        
    Returns:
        String in pgvector format: "[0.1,0.2,...]"
        
    Raises:
        ValueError: If embedding format is invalid
    """
    if isinstance(embedding, str):
        return embedding
    if hasattr(embedding, "__iter__"):
        return "[" + ",".join(map(str, embedding)) + "]"
    raise ValueError("embedding must be a list of floats or a string")


def normalize_attraction_row(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize data types in attraction row for API response.
    
    Converts:
    - activity_id to string
    - embedding to list
    - similarity to float
    
    Args:
        row_dict: Dictionary with attraction data from database
        
    Returns:
        Dictionary with normalized data types
    """
    if row_dict.get("activity_id"):
        row_dict["activity_id"] = str(row_dict["activity_id"])
    if row_dict.get("embedding"):
        row_dict["embedding"] = list(row_dict["embedding"])
    if "similarity" in row_dict:
        row_dict["similarity"] = float(row_dict["similarity"])
    return row_dict

