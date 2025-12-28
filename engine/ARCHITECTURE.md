# Engine Architecture

## Overview

The engine service follows a clear layered architecture for handling attraction search and management.

## Layer Flow

```
API Routes → Service Layer → Data Access Layer → Database
              ↓
         Embedding Service
```

## Layer Responsibilities

### 1. API Layer (`internal-routes/`)
- **Purpose**: HTTP request/response handling
- **Responsibilities**:
  - Parse HTTP requests
  - Validate input
  - Call service layer
  - Format HTTP responses
- **Files**: `attractions.py`

### 2. Service Layer (`services/`)
- **Purpose**: Business logic and orchestration
- **Responsibilities**:
  - Transform API requests into business operations
  - Build filters from user context
  - Orchestrate embedding generation and search
  - Handle business-level validation
- **Files**:
  - `attraction_service.py` - Main business logic for attractions
  - `embedding_service.py` - Text to vector conversion

### 3. Data Access Layer (`search/` and `db/`)
- **Purpose**: Database interaction and result formatting
- **Responsibilities**:
  - Format data for database queries
  - Execute database queries
  - Format results for service layer
  - Handle connection management
- **Files**:
  - `search/vector_search.py` - Vector search data access
  - `db/attractions_queries.py` - Pure SQL query construction

### 4. Utilities (`utils/`)
- **Purpose**: Shared helper functions
- **Responsibilities**:
  - Data formatting and transformation
  - Type normalization
- **Files**:
  - `utils/formatting.py` - Formatting utilities

## Function Flow Example: Search Attractions

1. **API Route** (`internal-routes/attractions.py`)
   - Receives HTTP GET request with query text and context
   - Calls `search_attractions()` from service layer

2. **Service Layer** (`services/attraction_service.py`)
   - `search_attractions()`:
     - Calls `generate_embedding()` to convert query text to vector
     - Calls `build_search_filters()` to create filter dictionary
     - Calls `search_similar_attractions()` from data access layer

3. **Data Access Layer** (`search/vector_search.py`)
   - `search_similar_attractions()`:
     - Formats embedding using `format_embedding_for_pgvector()`
     - Calls `fetch_similar_attractions()` from database layer
     - Normalizes results using `normalize_attraction_row()`
     - Returns formatted results

4. **Database Layer** (`db/attractions_queries.py`)
   - `fetch_similar_attractions()`:
     - Builds SQL query with filters
     - Executes query against PostgreSQL
     - Returns raw database results

## Key Design Principles

1. **Separation of Concerns**: Each layer has a single, clear responsibility
2. **No Business Logic in DB Layer**: Database queries only apply what's passed in
3. **Clear Data Flow**: Each function's inputs and outputs are well-defined
4. **Reusable Utilities**: Common formatting logic is centralized
5. **Type Safety**: Functions have clear type hints and docstrings

## Function Naming Conventions

- **Service functions**: Business operations (e.g., `search_attractions`, `create_attraction`)
- **Data access functions**: Data operations (e.g., `search_similar_attractions`, `fetch_similar_attractions`)
- **Utility functions**: Formatting/transformation (e.g., `format_embedding_for_pgvector`)
- **Private helpers**: Prefixed with `_` (e.g., `_apply_hard_filters`)

