from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (parent of engine/)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI
from db.connection import test_connection
import importlib.util

# Import internal-routes
attractions_path = __file__.replace('main.py', 'internal-routes/attractions.py')
spec_attractions = importlib.util.spec_from_file_location("attractions", attractions_path)
attractions = importlib.util.module_from_spec(spec_attractions)
spec_attractions.loader.exec_module(attractions)

recommendations_path = __file__.replace('main.py', 'internal-routes/recommendations.py')
spec_recs = importlib.util.spec_from_file_location("recommendations", recommendations_path)
recommendations = importlib.util.module_from_spec(spec_recs)
spec_recs.loader.exec_module(recommendations)

app = FastAPI(title="Attraction Engine")

# Include routers
app.include_router(attractions.router)
app.include_router(recommendations.router)

@app.get("/status")
def status():
    """Status endpoint - returns engine service status"""
    return {"service": "engine", "status": "running"}

@app.get("/health")
def health():
    """Health check endpoint - tests connection to PostgreSQL host"""
    db_test = test_connection()
    if db_test["success"]:
        return {"status": "healthy", "db_host": "connected"}
    else:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503, 
            detail=f"Database host connection failed: {db_test.get('error', 'Unknown error')}"
        )


