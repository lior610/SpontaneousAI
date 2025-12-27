# Vector Search Tests

This directory contains tests for the Attraction Engine's vector search functionality.

## Overview

The vector search test validates that the system can give the X most similar attractions to a query currently processed for a user.
**THIS DOES NOT YET GOOD FOR HARDER CONSTRAINTS LIKE ENERGY LEVELS, THIS TESTS SEMANTIC SEARCH FOR NOW!**



## What This Tests

1. **System receives user context** (not a direct query!)
   - User's current state (energy level, hunger, tiredness)
   - Travel preferences (couple, solo, friends, kids)
   - Current situation (just finished lunch, morning start, rainy day)

2. **System converts context to vector embedding**
   - Uses SBERT (Sentence-BERT) model `all-MiniLM-L6-v2`
   - Converts natural language context into 384-dimensional vector

3. **System searches for similar attractions**
   - Uses pgvector's cosine similarity search
   - Compares query vector against 500-1000 attraction embeddings
   - Returns top 10 most semantically similar attractions

4. **Validates prediction quality**
   - Checks if returned attractions match expected criteria
   - Measures: category, tags, indoor/outdoor, effort level, good_for

## How to Run

### Prerequisites

1. **Running PostgreSQL database** with attractions data:
   ```bash
   # Generate mock data first
   cd scripts/generate-mock-data
   docker-compose up
   ```

2. **Python dependencies**:
   ```bash
   cd engine
   pip install -r requirements.txt
   ```

### Run the Test

#### Option 1: Direct execution (recommended for development)
```bash
cd engine
python3 tests/test_vector_search.py
```

#### Option 2: With pytest
```bash
cd engine
pytest tests/test_vector_search.py -v
```

### Environment Setup

The test automatically loads from `.env` and sets defaults:
- `POSTGRES_HOST=localhost`
- `POSTGRES_PORT=5432`
- `POSTGRES_USER=postgres`
- `POSTGRES_PASSWORD=postgres`
- `POSTGRES_ATTRACTIONS_DB=attractions`

## Understanding the Output

### Per-Scenario Output

```
================================================================================
Scenario 1: Morning start - couple on cultural trip
System Context: Couple traveling together, interested in museums...
Expected Match: {'categories': 'Museum', 'indoor_outdoor': 'indoor'...}
--------------------------------------------------------------------------------

Top 10 Predicted Activities:

  🎯 #1. Modern Museum (similarity: 0.8217)
      Category: Museum | Tags: educational
      Good for: couple, solo | indoor | Effort: high
      Match Quality: 100% - PERFECT MATCH
      Description: Discover world-class exhibitions showcasing...

  ✅ #2. Warefurt History Museum (similarity: 0.8306)
      Category: Museum | Tags: social, quiet
      Good for: couple | indoor | Effort: medium
      Match Quality: 75% - GOOD MATCH
      ...
```

### Icons Meaning
- 🎯 **PERFECT MATCH** (≥80%): Result matches all expected criteria
- ✅ **GOOD MATCH** (≥50%): Result matches most criteria
- ⚠️ **PARTIAL** (≥30%): Result partially matches
- ❌ **MISMATCH** (<30%): Result doesn't match well

### Final Performance Report

```
================================================================================
📊 ATTRACTION ENGINE PERFORMANCE
================================================================================
Average Prediction Accuracy:  57.2%  (Target: >70%)
Perfect Matches:              17/120 (14%)
Good Matches:                 79/120 (66%)
Avg Prediction Time:          42.0ms
P95 Prediction Time:          146.0ms
--------------------------------------------------------------------------------
✅ VERDICT: GOOD. Most predictions match user context well.
================================================================================
```

### Metrics Explained

| Metric | Description | Target |
|--------|-------------|--------|
| **Average Prediction Accuracy** | Mean relevance score across all results | >70% |
| **Perfect Matches** | Results scoring ≥80% relevance | Higher is better |
| **Good Matches** | Results scoring ≥50% relevance | >60% |
| **Avg Prediction Time** | Mean time for embedding + search | <100ms |
| **P95 Prediction Time** | 95th percentile latency | <200ms |

### Verdict Scale

- 🏆 **EXCELLENT** (≥70%): System accurately predicts user preferences
- ✅ **GOOD** (≥50%): Most predictions match user context well
- ⚠️ **OKAY** (≥30%): Predictions somewhat relevant, needs improvement
- ❌ **POOR** (<30%): System struggles to match user context

## Configuration

Edit the test configuration at the top of `test_vector_search.py`:

```python
NUM_QUERIES = 3      # Number of scenarios to test
TOP_K = 10           # Number of results to evaluate per scenario
MODEL_NAME = 'all-MiniLM-L6-v2'  # SBERT model
```

## How It Works Technically

### 1. Text Embedding (SBERT)
```python
query_vector = model.encode("Couple interested in museums...").tolist()
# Returns: [0.123, -0.456, 0.789, ... (384 dimensions)]
```

### 2. Vector Search (pgvector)
```sql
SELECT *, (1 - (embedding <=> query_vector) / 2) as similarity
FROM attractions
WHERE embedding IS NOT NULL
ORDER BY embedding <=> query_vector  -- cosine distance
LIMIT 10
```

### 3. Relevance Scoring
```python
# For each result, check:
- Does category match? (Museum vs Restaurant)
- Do tags match? (educational, romantic, kids...)
- Does indoor/outdoor match?
- Is it good for this group? (couple, solo, friends...)
- Does effort level match?

# Score = (matched criteria / total criteria)
```