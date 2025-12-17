# Shared API

## What This Does

Keeps your **frontend TypeScript types** in sync with your **backend Python API**. When you change the API in Python, the frontend automatically knows about it.

## The Problem It Solves

**Without this:**
- You write code calling the API
- You guess what data you'll get back
- Typos cause runtime errors
- No autocomplete in your IDE

**With this:**
- TypeScript knows exactly what the API returns
- IDE autocomplete works
- Errors caught before running code
- Always in sync with backend

## How It Works (Simple Version)

### Step 1: Engine Defines API (Python)
```python
# Engine says: "This returns AttractionResponse with id, name, description"
@router.get("/attractions/{id}")
async def get_attraction(id: int):
    return AttractionResponse(id=1, name="Museum", ...)
```

### Step 2: FastAPI Generates OpenAPI Spec
- FastAPI automatically creates a JSON file describing your API
- Available at: `http://localhost:8000/openapi.json`
- Contains: all endpoints, request/response shapes, data types

### Step 3: Sync Script Generates TypeScript Types
```bash
./shared/api/sync-types.sh
```

**What it does:**
1. Downloads `openapi.json` from Engine
2. Converts it to TypeScript types → `web/src/types/api.d.ts`
3. Now TypeScript knows what your API returns!

### Step 4: Use Types in Your Code
```typescript
import type { components } from '../types/api';

// TypeScript knows: "This returns AttractionResponse[]"
export const getRecommendation = async (query: string): 
  Promise<components['schemas']['AttractionResponse'][]> => {
  const response = await axios.get(`${ENGINE_URL}/attractions/search/${query}`);
  return response.data.results;
};
```

## Real Example

**In your React component:**
```typescript
import { getRecommendation } from './services/api';

const attractions = await getRecommendation("museums");

// ✅ IDE autocomplete works!
attractions[0].name        // IDE suggests: name, id, description, location
attractions[0].id         // ✅ Works
attractions[0].nam        // ❌ IDE error: "Property 'nam' does not exist"
attractions[0].price      // ❌ IDE error: "Property 'price' does not exist"
```

## When to Run the Script

Run `./shared/api/sync-types.sh` when:
- ✅ You add a new endpoint to Engine
- ✅ You change what an endpoint returns
- ✅ You add/remove fields from models
- ✅ Before starting frontend work on a new feature

**The script:**
- Downloads latest API definition from running Engine
- Generates fresh TypeScript types
- Takes ~5 seconds

## What Gets Generated

**File:** `web/src/types/api.d.ts`

Contains TypeScript definitions for:
- All API endpoints (paths)
- Request/response types (components)
- Data models (AttractionResponse, etc.)

**You don't edit this file** - it's auto-generated. If you need changes, update the Python API and re-run the script.

## Benefits

1. **Autocomplete** - IDE knows what fields exist
2. **Error Prevention** - Catches typos before runtime
3. **Documentation** - Hover to see what API returns
4. **Refactoring Safety** - If Engine changes, TypeScript shows what broke
5. **Always In Sync** - One source of truth (Engine) → Frontend types

## Quick Start

```bash
# 1. Make sure Engine is running
docker-compose up engine

# 2. Run sync script
./shared/api/sync-types.sh

# 3. Use types in your code
import type { components } from '../types/api';
```

That's it! Your frontend now has type-safe access to your backend API.
