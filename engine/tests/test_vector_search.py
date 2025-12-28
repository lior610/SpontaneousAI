#!/usr/bin/env python3
"""
Vector Search Relevance Test
-----------------------------
Tests if the search returns semantically relevant results for complex queries.
Measures: relevance, ranking quality, and semantic matching across multiple fields.
"""

import os
import sys
import random
import time
import statistics
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# --- SETUP ---
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Set defaults for local development
os.environ.setdefault('POSTGRES_HOST', 'localhost')
os.environ.setdefault('POSTGRES_PORT', '5432')
os.environ.setdefault('POSTGRES_USER', 'postgres')
os.environ.setdefault('POSTGRES_PASSWORD', 'postgres')

# Add parent directory to path so we can import src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.search.vector_search import search_similar_attractions
from src.search.hard_filters import build_hard_filters
from src.search.soft_filters import apply_soft_filters, calculate_combined_score

# --- CONFIGURATION ---
NUM_QUERIES = 3      # Number of test scenarios to run
TOP_K = 10             # Show top K results for each scenario
MODEL_NAME = 'all-MiniLM-L6-v2'

# Pool of cities/countries to randomly assign per scenario
LOCATION_POOL = [
    ("Paris", "France"),
    ("London", "UK"),
    ("Berlin", "Germany"),
    ("Athens", "Greece"),
    ("Tokyo", "Japan"),
    ("Arizona", "USA"),
    ("Tel Aviv", "Israel"),
    ("New York", "USA"),
]

# --- TEST SCENARIOS ---
# Simulates the system's internal reasoning based on user state + context
# Format: What the system "knows" about the user right now
TEST_QUERIES = [
    {
        "scenario": "Morning start - couple on cultural trip",
        "query": "Couple travelers, 9am morning local time, high energy level, low tiredness, prefer museums and history categories, looking for educational indoor activity, typical duration 60-90 minutes, low effort level, crowd tolerance is low prefer quiet, budget style is balanced",
        "expected": {"categories": "Museum", "indoor_outdoor": "indoor", "tags": "educational", "good_for": "couple", "city": "Paris", "country": "France"},
        "filters": {"city": "Paris", "country": "France"}
    },
    {
        "scenario": "After lunch - solo traveler seeking relaxation",
        "query": "Solo traveler, 2pm afternoon, medium-low energy level after eating, high tiredness from morning activities, wants outdoor activity with chill vibe, very low effort level, typical duration 30-45 minutes, crowd tolerance medium, weather is sunny",
        "expected": {"indoor_outdoor": "outdoor", "effort_level": "low", "tags": "chill", "good_for": "solo", "city": "Barcelona", "country": "Spain"},
        "filters": {"city": "Barcelona", "country": "Spain"}
    },
    {
        "scenario": "Evening - romantic date",
        "query": "Couple on romantic trip, 7pm evening local time, medium energy, low hunger level need food soon, want restaurant category with romantic vibe, indoor preferred, typical duration 2-3 hours, premium budget style, effort level low prefer sitting",
        "expected": {"categories": "Restaurant", "tags": "romantic", "good_for": "couple", "city": "Paris", "country": "France"},
        "filters": {"city": "Paris", "country": "France"}
    },
    {
        "scenario": "Family with kids - afternoon",
        "query": "Traveling with kids, 3pm afternoon, kids have very high energy level, parents medium-low energy, need outdoor park category, kids-friendly tags, typical duration 1-2 hours, high activity intensity for kids to burn energy, crowd tolerance high kids can be loud, budget style is balanced prefer free or low cost",
        "expected": {"categories": "Park", "tags": "kids", "good_for": "kids", "indoor_outdoor": "outdoor", "city": "London", "country": "UK"},
        "filters": {"city": "London", "country": "UK"}
    },
    {
        "scenario": "Morning - adventurous solo hiker",
        "query": "Solo adventurer, 8am morning start, very high energy level, low tiredness well-rested, prefer adventure and nature categories, want hiking trail outdoor, high effort level and high activity intensity, typical duration 3-4 hours, crowd tolerance low prefer solitude, weather conditions excellent",
        "expected": {"categories": "Hiking", "tags": "adventure", "effort_level": "high", "good_for": "solo", "city": "Denver", "country": "USA"},
        "filters": {"city": "Berlin", "country": "Germany"}
    },
    {
        "scenario": "Night - friends seeking social experience",
        "query": "Friends group of 4, age group 20s-30s, 10pm night time Friday, high energy level, want bar category with lively social vibe, indoor preferred, typical duration 2-3 hours, crowd tolerance medium not too packed, nightlife and social preferences high, budget style balanced",
        "expected": {"categories": "Bar", "tags": "lively", "good_for": "friends", "city": "London", "country": "UK"},
        "filters": {"city": "London", "country": "UK"}
    },
    {
        "scenario": "Rainy day - entertainment needed",
        "query": "Solo traveler, 3pm afternoon, weather is heavy rain, medium energy level, want indoor entertainment cinema category, relaxation preference high, typical duration around 90-120 minutes, low effort level prefer sitting, crowd tolerance medium, budget style balanced",
        "expected": {"categories": "Cinema", "typical_duration_min": 90, "indoor_outdoor": "indoor", "city": "London", "country": "UK"},
        "filters": {"city": "London", "country": "UK"}
    },
    {
        "scenario": "Afternoon - casual browsing",
        "query": "Solo traveler, 2pm afternoon, medium energy but high tiredness from morning museums, want shopping category with chill vibe, indoor preferred for air conditioning, typical duration 1-2 hours, very low effort level just browsing, shopping preference medium, budget style budget-conscious not buying much",
        "expected": {"categories": "Shopping", "tags": "chill", "good_for": "solo", "city": "Tokyo", "country": "Japan"},
        "filters": {"city": "Tokyo", "country": "Japan"}
    },
    {
        "scenario": "After museum - more culture",
        "query": "Couple travelers, 4pm afternoon, medium-low energy level, medium-high tiredness from 2 hours standing indoors, want historical category outdoor for fresh air, educational tags, typical duration 60-90 minutes, low to medium effort level, pace preference slow can walk at own pace, museums and history preferences high",
        "expected": {"categories": "Historical", "tags": "educational", "indoor_outdoor": "outdoor", "city": "Rome", "country": "Italy"},
        "filters": {"city": "Tel Aviv", "country": "Israel"}
    },
    {
        "scenario": "Post-activity rest - needs caffeine",
        "query": "Solo traveler, 4pm afternoon, very low energy level exhausted, very high tiredness level, want cafe category with quiet vibe, indoor with AC, typical duration 60+ minutes need rest, very low effort level must sit, low crowd tolerance want peace, food and relaxation preferences high",
        "expected": {"categories": "Cafe", "tags": "quiet", "good_for": "solo", "city": "Berlin", "country": "Germany"},
        "filters": {"city": "Berlin", "country": "Germany"}
    },
    {
        "scenario": "Hungry after hiking - need food fast",
        "query": "Couple travelers, 12pm lunch time, low energy level from exertion, high tiredness and very high hunger level, want restaurant category casual, indoor preferred for AC, typical duration 60 minutes, low effort level need to sit and recover, food preference very high, budget style balanced",
        "expected": {"categories": "Restaurant", "good_for": "couple", "effort_level": "low", "city": "Denver", "country": "USA"},
        "filters": {"city": "Tokyo", "country": "Japan"}
    },
    {
        "scenario": "Late afternoon - cultural exploration",
        "query": "Friends group of 3, age group 20s, 5pm early evening, medium energy level, low tiredness, want historical category outdoor, educational tags, social vibe prefer discussing together, typical duration 1-2 hours, low to medium effort level, museums and history preferences high, budget style budget-conscious students",
        "expected": {"categories": "Historical", "tags": "educational", "good_for": "friends", "city": "Athens", "country": "Greece"},
        "filters": {"city": "Tel Aviv", "country": "Israel"}
    },
]

def check_relevance(result, expected_criteria):
    """
    Check if a result matches the expected criteria.
    Returns score (0-1) indicating how well it matches.
    """
    score = 0
    checks = 0
    
    for field, expected_value in expected_criteria.items():
        checks += 1
        result_value = result.get(field)
        
        if field == "tags" or field == "tags_alt":
            # Tags are comma-separated, check if expected tag is in there
            if result_value and expected_value.lower() in result_value.lower():
                score += 1
        elif field == "good_for":
            # Good_for is comma-separated, check if expected is in there
            if result_value and expected_value.lower() in result_value.lower():
                score += 1
        elif field == "typical_duration_min":
            # Check if duration is within range
            if result_value and abs(result_value - expected_value) <= 30:
                score += 1
        else:
            # Exact match for other fields
            if result_value and str(result_value).lower() == str(expected_value).lower():
                score += 1
    
    return score / checks if checks > 0 else 0


def test_hard_filters():
    """Test hard filter building functionality."""
    print("\n" + "="*80)
    print("🧪 TESTING HARD FILTERS")
    print("="*80)
    
    # Test 1: Basic location filters
    context1 = {"city": "Paris", "country": "France"}
    filters1 = build_hard_filters(context1)
    assert filters1 == {"city": "Paris", "country": "France"}, f"Expected location filters, got {filters1}"
    print("✅ Test 1: Location filters work correctly")
    
    # Test 2: Availability filter
    context2 = {"is_open_now": True}
    filters2 = build_hard_filters(context2)
    assert filters2 == {"is_open_now": True}, f"Expected open_now filter, got {filters2}"
    print("✅ Test 2: Availability filter works correctly")
    
    # Test 3: Combined filters
    context3 = {"city": "London", "country": "UK", "is_open_now": True}
    filters3 = build_hard_filters(context3)
    assert filters3 == {"city": "London", "country": "UK", "is_open_now": True}, f"Expected combined filters, got {filters3}"
    print("✅ Test 3: Combined filters work correctly")
    
    # Test 4: Empty context
    filters4 = build_hard_filters({})
    assert filters4 == {}, f"Expected empty filters, got {filters4}"
    print("✅ Test 4: Empty context returns empty filters")
    
    # Test 5: Ignore non-filter keys
    context5 = {"city": "Berlin", "random_key": "should_be_ignored", "another_key": 123}
    filters5 = build_hard_filters(context5)
    assert "city" in filters5, "City filter should be included"
    assert "random_key" not in filters5, "Non-filter keys should be ignored"
    assert "another_key" not in filters5, "Non-filter keys should be ignored"
    print("✅ Test 5: Non-filter keys are ignored")
    
    # Test 6: False values are ignored
    context6 = {"city": "Tokyo", "is_open_now": False}
    filters6 = build_hard_filters(context6)
    assert "city" in filters6, "City filter should be included"
    assert "is_open_now" not in filters6, "False values should be ignored"
    print("✅ Test 6: False values are ignored")
    
    print("\n✅ All hard filter tests passed!\n")


def test_soft_filters():
    """Test soft filter functionality."""
    print("\n" + "="*80)
    print("🧪 TESTING SOFT FILTERS")
    print("="*80)
    
    # Create mock results
    mock_results = [
        {"name": "Museum A", "similarity": 0.85, "rating": 4.5, "price_level": 2},
        {"name": "Museum B", "similarity": 0.80, "rating": 4.8, "price_level": 1},
        {"name": "Museum C", "similarity": 0.75, "rating": 3.9, "price_level": 3},
    ]
    
    # Test 1: Empty context returns results unchanged
    result1 = apply_soft_filters(mock_results, None)
    assert result1 == mock_results, "Empty context should return results unchanged"
    assert len(result1) == 3, "Should return all results"
    print("✅ Test 1: Empty context returns results unchanged")
    
    # Test 2: Empty results list
    result2 = apply_soft_filters([], {"some_context": "value"})
    assert result2 == [], "Empty results should return empty list"
    print("✅ Test 2: Empty results handled correctly")
    
    # Test 3: Results with context (currently placeholder, but should work)
    result3 = apply_soft_filters(mock_results, {"preference": "budget"})
    assert len(result3) == 3, "Should return all results (soft filters don't exclude)"
    assert result3[0]["name"] == "Museum A", "Results should maintain order (placeholder)"
    print("✅ Test 3: Soft filters work with context (placeholder implementation)")
    
    # Test 4: None context
    result4 = apply_soft_filters(mock_results, None)
    assert result4 == mock_results, "None context should return results unchanged"
    print("✅ Test 4: None context handled correctly")
    
    print("\n✅ All soft filter tests passed!")
    print("   Note: Soft filters are currently placeholders - implement scoring logic to enhance results\n")


def test_combined_score():
    """Test combined score calculation."""
    print("\n" + "="*80)
    print("🧪 TESTING COMBINED SCORE CALCULATION")
    print("="*80)
    
    # Test 1: Basic similarity score (placeholder returns similarity unchanged)
    attraction1 = {"name": "Test Attraction", "rating": 4.5}
    score1 = calculate_combined_score(0.75, attraction1, None)
    assert score1 == 0.75, f"Expected 0.75, got {score1}"
    print("✅ Test 1: Basic similarity score works")
    
    # Test 2: Score with context (placeholder)
    context2 = {"prefer_high_rating": True}
    score2 = calculate_combined_score(0.80, attraction1, context2)
    assert score2 == 0.80, "Placeholder should return similarity unchanged"
    print("✅ Test 2: Score with context works (placeholder)")
    
    # Test 3: Edge cases
    score3 = calculate_combined_score(0.0, attraction1, None)
    assert score3 == 0.0, "Zero similarity should return 0.0"
    print("✅ Test 3: Zero similarity handled")
    
    score4 = calculate_combined_score(1.0, attraction1, None)
    assert score4 == 1.0, "Perfect similarity should return 1.0"
    print("✅ Test 4: Perfect similarity handled")
    
    print("\n✅ All combined score tests passed!")
    print("   Note: Combined scoring is currently a placeholder - implement logic to combine similarity + business factors\n")


def test_filter_integration():
    """Test integration of hard and soft filters with vector search."""
    print("\n" + "="*80)
    print("🧪 TESTING FILTER INTEGRATION WITH VECTOR SEARCH")
    print("="*80)
    
    # Load model for embedding
    print("📦 Loading Embedding Model...")
    model = SentenceTransformer(MODEL_NAME)
    
    # Test query
    query_text = "romantic dinner restaurant"
    query_vector = model.encode(query_text).tolist()
    
    # Test 1: Hard filters only
    context1 = {"city": "Paris", "country": "France"}
    hard_filters1 = build_hard_filters(context1)
    print(f"\n📍 Testing with hard filters: {hard_filters1}")
    
    results1 = search_similar_attractions(
        query_embedding=query_vector,
        limit=5,
        filters=hard_filters1,
    )
    
    if results1:
        print(f"✅ Found {len(results1)} results with hard filters")
        # Verify all results match filters
        for result in results1:
            assert result.get("city") == "Paris", f"Result should be in Paris, got {result.get('city')}"
            assert result.get("country") == "France", f"Result should be in France, got {result.get('country')}"
        print("✅ All results match hard filter constraints")
    else:
        print("⚠️  No results found (database may be empty or no matches)")
    
    # Test 2: Hard filters + soft filters
    context2 = {"city": "Paris", "country": "France", "prefer_budget": True}
    hard_filters2 = build_hard_filters(context2)
    print(f"\n📍 Testing with hard filters + soft filters: {hard_filters2}")
    
    results2 = search_similar_attractions(
        query_embedding=query_vector,
        limit=5,
        filters=hard_filters2,
    )
    
    if results2:
        print(f"✅ Found {len(results2)} results before soft filtering")
        results2_filtered = apply_soft_filters(results2, context2)
        assert len(results2_filtered) == len(results2), "Soft filters shouldn't exclude results"
        print(f"✅ Soft filters applied: {len(results2_filtered)} results (same count, rankings may differ)")
    else:
        print("⚠️  No results found (database may be empty or no matches)")
    
    print("\n✅ Filter integration tests passed!\n")


def run_evaluation(custom_query: str = None, custom_expected: dict = None):
    print(f"\n🚀 ATTRACTION ENGINE - CONTEXT-BASED RECOMMENDATION TEST")
    print(f"Simulating: System predicts next activity based on user state + context")
    if custom_query:
        print(f"Testing 1 custom scenario from CLI, showing top {TOP_K} results")
    else:
        print(f"Testing {NUM_QUERIES} randomly selected scenarios (from {len(TEST_QUERIES)} total), showing top {TOP_K} results each")
    print("-" * 80)

    # Load Model
    print("📦 Loading Embedding Model...")
    model = SentenceTransformer(MODEL_NAME)

    total_relevance_scores = []
    total_latencies = []
    
    # Choose scenarios
    if custom_query:
        selected_scenarios = [{
            "scenario": "Custom CLI Query",
            "query": custom_query,
            "expected": custom_expected or {},
        }]
    else:
        selected_scenarios = random.sample(TEST_QUERIES, min(NUM_QUERIES, len(TEST_QUERIES)))

    # Run each test scenario
    for i, test_case in enumerate(selected_scenarios, 1):
        scenario_name = test_case["scenario"]
        query_text = test_case["query"]
        expected = dict(test_case.get("expected", {}))

        # Randomize location per run to exercise different geos
        city, country = random.choice(LOCATION_POOL)
        expected["city"] = city
        expected["country"] = country

        # Build hard filters using the new filter function
        base_context = dict(test_case.get("filters", {}))
        base_context["city"] = city
        base_context["country"] = country
        filters = build_hard_filters(base_context)
        
        print(f"\n{'='*80}")
        print(f"Scenario {i}: {scenario_name}")
        print(f"System Context: {query_text}")
        print(f"Expected Match: {expected}")
        print("-" * 80)
        
        # Generate embedding
        start_time = time.time()
        query_vector = model.encode(query_text).tolist()
        
        # Use the actual search function from vector_search.py
        results = search_similar_attractions(
            query_embedding=query_vector,
            limit=TOP_K,
            filters=filters,
        )
        
        # Apply soft filters (post-query scoring)
        results = apply_soft_filters(results, base_context)
        
        end_time = time.time()
        latency = (end_time - start_time) * 1000
        total_latencies.append(latency)
        
        # Analyze results
        print(f"\nTop {TOP_K} Predicted Activities:")
        query_relevance_scores = []
        
        if not results:
            print("  ⚠️  No results returned for this scenario.")
            continue

        for rank, attraction in enumerate(results, 1):
            relevance = check_relevance(attraction, expected)
            query_relevance_scores.append(relevance)
            
            # Visual relevance indicator
            if relevance >= 0.8:
                icon = "🎯"
                status = "PERFECT MATCH"
            elif relevance >= 0.5:
                icon = "✅"
                status = "GOOD MATCH"
            elif relevance >= 0.3:
                icon = "⚠️"
                status = "PARTIAL"
            else:
                icon = "❌"
                status = "MISMATCH"
            
            print(f"\n  {icon} #{rank}. {attraction['name']} (similarity: {attraction['similarity']:.4f})")
            print(f"      Category: {attraction['categories']} | Tags: {attraction['tags']}")
            print(f"      Location: {attraction.get('city')}, {attraction.get('country')}")
            print(f"      Good for: {attraction['good_for']} | {attraction['indoor_outdoor']} | Effort: {attraction['effort_level']}")
            print(f"      Match Quality: {relevance:.0%} - {status}")
            print(f"      Description: {attraction['short_description'][:80]}...")
        
        # Calculate metrics for this query
        avg_relevance = statistics.mean(query_relevance_scores) if query_relevance_scores else 0
        top1_relevance = query_relevance_scores[0] if query_relevance_scores else 0
        
        total_relevance_scores.extend(query_relevance_scores)
        
        print(f"\n  📊 Scenario Metrics:")
        print(f"      Best Prediction Accuracy: {top1_relevance:.0%}")
        print(f"      Avg Top-{TOP_K} Accuracy: {avg_relevance:.0%}")
        print(f"      Prediction Time: {latency:.1f}ms")

    # --- FINAL REPORT ---
    avg_relevance = statistics.mean(total_relevance_scores) if total_relevance_scores else 0
    avg_latency = statistics.mean(total_latencies) if total_latencies else 0
    p95_latency = statistics.quantiles(total_latencies, n=20)[18] if len(total_latencies) >= 20 else (max(total_latencies) if total_latencies else 0)
    
    # Count how many predictions were accurate
    perfect_matches = sum(1 for s in total_relevance_scores if s >= 0.8)
    good_matches = sum(1 for s in total_relevance_scores if s >= 0.5)
    total_predictions = len(total_relevance_scores)
    
    print("\n" + "="*80)
    print("📊 ATTRACTION ENGINE PERFORMANCE")
    print("="*80)
    print(f"Average Prediction Accuracy:  {avg_relevance:.1%}  (Target: >70%)")
    print(f"Perfect Matches:              {perfect_matches}/{total_predictions} ({perfect_matches/total_predictions:.0%})")
    print(f"Good Matches:                 {good_matches}/{total_predictions} ({good_matches/total_predictions:.0%})")
    print(f"Avg Prediction Time:          {avg_latency:.1f}ms")
    print(f"P95 Prediction Time:          {p95_latency:.1f}ms")
    print("-" * 80)
    
    if avg_relevance >= 0.7:
        print("🏆 VERDICT: EXCELLENT. Engine accurately predicts user preferences.")
    elif avg_relevance >= 0.5:
        print("✅ VERDICT: GOOD. Most predictions match user context well.")
    elif avg_relevance >= 0.3:
        print("⚠️  VERDICT: OKAY. Predictions are somewhat relevant but need improvement.")
    else:
        print("❌ VERDICT: POOR. Engine struggles to match user context.")
    print("="*80 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run vector search relevance tests.")
    parser.add_argument("--query", type=str, help="Custom query text to test (bypasses predefined scenarios).")
    parser.add_argument("--expected", type=str, help="Optional expected criteria as JSON string, e.g. '{\"categories\":\"Museum\",\"tags\":\"educational\"}'.")
    parser.add_argument("--test-filters", action="store_true", help="Run filter function tests only.")
    parser.add_argument("--test-integration", action="store_true", help="Run filter integration tests with vector search.")
    args = parser.parse_args()

    # Run filter tests if requested
    if args.test_filters:
        test_hard_filters()
        test_soft_filters()
        test_combined_score()
        sys.exit(0)
    
    # Run integration tests if requested
    if args.test_integration:
        test_filter_integration()
        sys.exit(0)

    # Run full evaluation
    custom_expected = None
    if args.expected:
        try:
            custom_expected = json.loads(args.expected)
        except Exception as e:
            print(f"Failed to parse --expected JSON: {e}")
            sys.exit(1)

    run_evaluation(custom_query=args.query, custom_expected=custom_expected)