from fastapi import FastAPI
from src.db.connection import test_connection

app = FastAPI(title="Attraction Engine")

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


