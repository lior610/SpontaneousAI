import asyncio
from fastapi import FastAPI
from typing import List, Optional
from pydantic import BaseModel, Field

# --- SCHEMAS ---
class Reviews(BaseModel):
    author: str
    rating: int = Field(..., ge=1, le=5)
    text: Optional[str] = None
    relative_time_description: Optional[str] = None


class GooglePlace(BaseModel):
    name: str
    address: str
    opening_hours: Optional[List[str]] = None
    rating: float = Field(..., ge=0.0, le=5.0)
    reviews: Optional[List[Reviews]] = None
    type: str


# --- APP DEFINITION ---
app = FastAPI(title="Google Maps Scraper API", version="1.0.0")

# --- ROUTES ---
@app.get("/healthz")
async def health_check():
    return {"status": "ok"}

@app.get("/get-places/<city_name>", response_model=GooglePlace)
async def get_places(city_name: str):
    await asyncio.sleep(1) 
    return None  # Placeholder for actual implementation