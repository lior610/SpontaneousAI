"""
Cluster Retrieval Service.

Orchestrates the retrieval of a diverse pool of candidate attractions
from the vector space by executing cluster-aware database queries.
"""
import sys
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np

shared_path = str(Path(__file__).resolve().parents[3] / "shared" / "python")
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from db.attractionsConnection import get_db_connection
from src.db.cluster_queries import execute_cluster_similarity_query
from src.db.feedback_queries import get_excluded_place_ids
from src.utils.formatting import format_embedding_for_pgvector, normalize_attraction_row

logger = logging.getLogger(__name__)

class ClusterRetrievalService:
    """
    Handles retrieving candidate attractions using cluster-diverse vector search.
    """
    
    def __init__(self, top_per_cluster: int = 3, max_clusters: int = 5):
        self.top_per_cluster = top_per_cluster
        self.max_clusters = max_clusters

    def get_candidate_pool(
        self,
        location_id: int,
        trip_id: int,
        preference_vector: np.ndarray,
        context_filters: Optional[Dict[str, Any]] = None,
        user_lat: Optional[float] = None,
        user_lng: Optional[float] = None,
        max_walk_km: Optional[float] = None,
        current_hour: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch a diverse candidate pool of attractions.
        
        Args:
            location_id: The ID of the current location/city
            trip_id: Current trip context (used to fetch excluded items)
            preference_vector: User's 384d preference embedding
            context_filters: Hard filters to apply in SQL
            
        Returns:
            List of normalized attraction dictionaries
        """
        if preference_vector is None or len(preference_vector) == 0:
            logger.error("preference_vector is empty or none")
            return []
            
        embedding_str = format_embedding_for_pgvector(preference_vector.tolist())
        
        try:
            from db.usersConnection import get_db_connection as get_users_conn
            with get_users_conn() as users_conn:
                excluded_ids = list(get_excluded_place_ids(users_conn, trip_id))
        except Exception as e:
            logger.warning(f"Could not load excluded attraction IDs: {e}")
            excluded_ids = []
            
        results = []
        try:
            with get_db_connection() as conn:
                rows, column_names = execute_cluster_similarity_query(
                    conn=conn,
                    location_id=location_id,
                    embedding_str=embedding_str,
                    excluded_place_ids=excluded_ids,
                    top_per_cluster=self.top_per_cluster,
                    max_clusters=self.max_clusters,
                    filters=context_filters,
                    user_lat=user_lat,
                    user_lng=user_lng,
                    max_walk_km=max_walk_km,
                    current_hour=current_hour
                )
                
                for row in rows:
                    attraction = dict(zip(column_names, row))
                    # Prevent Pydantic parsing errors and keep payload small
                    attraction.pop('embedding', None)
                    results.append(normalize_attraction_row(attraction))
                    
        except Exception as e:
            logger.error(f"Error performing cluster vector search: {str(e)}")
            raise RuntimeError(f"Error performing cluster vector search: {str(e)}") from e
            
        logger.info(f"Candidate pool retrieved: {len(results)} attractions across up to {self.max_clusters} clusters")
        return results

