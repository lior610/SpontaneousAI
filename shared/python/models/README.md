# Shared Models

## Why These Models Are Shared

These Pydantic models are shared between multiple services because they represent the **core domain entities** that multiple services need to understand and work with.

### Services That Use These Models

1. **Engine** (`/engine`) - FastAPI service
   - Uses: `AttractionResponse`, `RecommendationRequest`, `RecommendationResponse`
   - Needs to validate request/response data
   - Generates recommendations based on user preferences and trips

2. **Data Pipeline** (`/data-pipeline`) - ETL service
   - Uses: `AttractionCreate`, `DestinationResponse`
   - Creates attractions from scraped data
   - Manages pending destinations queue

3. **API** (`/api`) - Node.js orchestrator
   - Uses: All models (via OpenAPI spec generated from Engine)
   - Validates data before forwarding to Engine
   - Returns consistent response formats

4. **Web** (`/web`) - React frontend
   - Uses: All models (via TypeScript types generated from OpenAPI)
   - Type-safe API calls
   - Consistent data structures

## Benefits of Sharing

### 1. **Single Source of Truth**
- One definition of what an `Attraction` or `User` looks like
- Changes propagate to all services automatically
- No drift between service definitions

### 2. **Type Safety Across Services**
- Python services use Pydantic for validation
- TypeScript frontend gets generated types
- Catches mismatches at development time, not runtime

### 3. **Consistency**
- Same field names, types, and validation rules everywhere
- API responses match what frontend expects
- Database schemas align with models

### 4. **DRY Principle**
- Don't repeat model definitions in each service
- Update once, use everywhere
- Less code to maintain

## Model Breakdown

### `attraction.py`
**Used by:** Engine, Data Pipeline, API, Web
- Core entity: places/activities users can visit
- Engine returns these in recommendations
- Data Pipeline creates these from scraped data

### `user.py`
**Used by:** API, Engine (for user context)
- User accounts and authentication
- API handles user CRUD
- Engine uses user_id for personalized recommendations

### `trip.py`
**Used by:** API, Engine
- Active and planned trips
- API manages trip lifecycle
- Engine uses trip context for recommendations

### `user_preferences.py`
**Used by:** API, Engine
- User interests, constraints, budget
- API stores/updates preferences
- Engine uses these to match attractions

### `recommendation.py`
**Used by:** Engine, API, Web
- Request/response format for recommendations
- Engine generates these
- API forwards to frontend
- Web displays to user

### `destination.py`
**Used by:** Data Pipeline, API
- Pending destinations queue
- API adds destinations when users plan trips
- Data Pipeline processes queue and fetches data

## When NOT to Share

Models that are **service-specific** should stay in their service:

- **Engine-specific**: Internal recommendation algorithms, scoring models
- **Data Pipeline-specific**: Scraper configurations, ETL job status
- **API-specific**: Request middleware, authentication tokens
- **Web-specific**: UI state, form validation (client-side only)

## Migration Path

If you need to add a new shared model:

1. Create the model file in `shared/python/models/`
2. Export it in `__init__.py`
3. Use it in the services that need it
4. Run `shared/api/sync-types.sh` to regenerate TypeScript types
5. Update this README if it's a major addition

