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

# --- CONFIGURATION ---
NUM_QUERIES = 3      # Number of test scenarios to run
TOP_K = 10             # Show top K results for each scenario
MODEL_NAME = 'all-MiniLM-L6-v2'

# --- TEST SCENARIOS ---
# Simulates the system's internal reasoning based on user state + context
# Format: What the system "knows" about the user right now
TEST_QUERIES = [
    {
        "scenario": "Morning start - couple on cultural trip",
        "query": "Couple travelers, 9am morning local time, high energy level, low tiredness, prefer museums and history categories, looking for educational indoor activity, typical duration 60-90 minutes, low effort level, crowd tolerance is low prefer quiet, budget style is balanced",
        "expected": {"categories": "Museum", "indoor_outdoor": "indoor", "tags": "educational", "good_for": "couple"}
    },
    {
        "scenario": "After lunch - solo traveler seeking relaxation",
        "query": "Solo traveler, 2pm afternoon, medium-low energy level after eating, high tiredness from morning activities, wants outdoor activity with chill vibe, very low effort level, typical duration 30-45 minutes, crowd tolerance medium, weather is sunny",
        "expected": {"indoor_outdoor": "outdoor", "effort_level": "low", "tags": "chill", "good_for": "solo"}
    },
    {
        "scenario": "Evening - romantic date",
        "query": "Couple on romantic trip, 7pm evening local time, medium energy, low hunger level need food soon, want restaurant category with romantic vibe, indoor preferred, typical duration 2-3 hours, premium budget style, effort level low prefer sitting",
        "expected": {"categories": "Restaurant", "tags": "romantic", "good_for": "couple"}
    },
    {
        "scenario": "Family with kids - afternoon",
        "query": "Traveling with kids, 3pm afternoon, kids have very high energy level, parents medium-low energy, need outdoor park category, kids-friendly tags, typical duration 1-2 hours, high activity intensity for kids to burn energy, crowd tolerance high kids can be loud, budget style is balanced prefer free or low cost",
        "expected": {"categories": "Park", "tags": "kids", "good_for": "kids", "indoor_outdoor": "outdoor"}
    },
    {
        "scenario": "Morning - adventurous solo hiker",
        "query": "Solo adventurer, 8am morning start, very high energy level, low tiredness well-rested, prefer adventure and nature categories, want hiking trail outdoor, high effort level and high activity intensity, typical duration 3-4 hours, crowd tolerance low prefer solitude, weather conditions excellent",
        "expected": {"categories": "Hiking", "tags": "adventure", "effort_level": "high", "good_for": "solo"}
    },
    {
        "scenario": "Night - friends seeking social experience",
        "query": "Friends group of 4, age group 20s-30s, 10pm night time Friday, high energy level, want bar category with lively social vibe, indoor preferred, typical duration 2-3 hours, crowd tolerance medium not too packed, nightlife and social preferences high, budget style balanced",
        "expected": {"categories": "Bar", "tags": "lively", "good_for": "friends"}
    },
    {
        "scenario": "Rainy day - entertainment needed",
        "query": "Solo traveler, 3pm afternoon, weather is heavy rain, medium energy level, want indoor entertainment cinema category, relaxation preference high, typical duration around 90-120 minutes, low effort level prefer sitting, crowd tolerance medium, budget style balanced",
        "expected": {"categories": "Cinema", "typical_duration_min": 90, "indoor_outdoor": "indoor"}
    },
    {
        "scenario": "Afternoon - casual browsing",
        "query": "Solo traveler, 2pm afternoon, medium energy but high tiredness from morning museums, want shopping category with chill vibe, indoor preferred for air conditioning, typical duration 1-2 hours, very low effort level just browsing, shopping preference medium, budget style budget-conscious not buying much",
        "expected": {"categories": "Shopping", "tags": "chill", "good_for": "solo"}
    },
    {
        "scenario": "After museum - more culture",
        "query": "Couple travelers, 4pm afternoon, medium-low energy level, medium-high tiredness from 2 hours standing indoors, want historical category outdoor for fresh air, educational tags, typical duration 60-90 minutes, low to medium effort level, pace preference slow can walk at own pace, museums and history preferences high",
        "expected": {"categories": "Historical", "tags": "educational", "indoor_outdoor": "outdoor"}
    },
    {
        "scenario": "Post-activity rest - needs caffeine",
        "query": "Solo traveler, 4pm afternoon, very low energy level exhausted, very high tiredness level, want cafe category with quiet vibe, indoor with AC, typical duration 60+ minutes need rest, very low effort level must sit, low crowd tolerance want peace, food and relaxation preferences high",
        "expected": {"categories": "Cafe", "tags": "quiet", "good_for": "solo"}
    },
    {
        "scenario": "Hungry after hiking - need food fast",
        "query": "Couple travelers, 12pm lunch time, low energy level from exertion, high tiredness and very high hunger level, want restaurant category casual, indoor preferred for AC, typical duration 60 minutes, low effort level need to sit and recover, food preference very high, budget style balanced",
        "expected": {"categories": "Restaurant", "good_for": "couple", "effort_level": "low"}
    },
    {
        "scenario": "Late afternoon - cultural exploration",
        "query": "Friends group of 3, age group 20s, 5pm early evening, medium energy level, low tiredness, want historical category outdoor, educational tags, social vibe prefer discussing together, typical duration 1-2 hours, low to medium effort level, museums and history preferences high, budget style budget-conscious students",
        "expected": {"categories": "Historical", "tags": "educational", "good_for": "friends"}
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

def run_evaluation():
    print(f"\n🚀 ATTRACTION ENGINE - CONTEXT-BASED RECOMMENDATION TEST")
    print(f"Simulating: System predicts next activity based on user state + context")
    print(f"Testing {NUM_QUERIES} randomly selected scenarios (from {len(TEST_QUERIES)} total), showing top {TOP_K} results each")
    print("-" * 80)

    # Load Model
    print("📦 Loading Embedding Model...")
    model = SentenceTransformer(MODEL_NAME)

    total_relevance_scores = []
    total_latencies = []
    
    # Randomly select NUM_QUERIES scenarios
    selected_scenarios = random.sample(TEST_QUERIES, min(NUM_QUERIES, len(TEST_QUERIES)))

    # Run each test scenario (randomly selected)
    for i, test_case in enumerate(selected_scenarios, 1):
        scenario_name = test_case["scenario"]
        query_text = test_case["query"]
        expected = test_case["expected"]
        
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
            limit=TOP_K
        )
        
        end_time = time.time()
        latency = (end_time - start_time) * 1000
        total_latencies.append(latency)
        
        # Analyze results
        print(f"\nTop {TOP_K} Predicted Activities:")
        query_relevance_scores = []
        
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
            print(f"      Good for: {attraction['good_for']} | {attraction['indoor_outdoor']} | Effort: {attraction['effort_level']}")
            print(f"      Match Quality: {relevance:.0%} - {status}")
            print(f"      Description: {attraction['short_description'][:80]}...")
        
        # Calculate metrics for this query
        avg_relevance = statistics.mean(query_relevance_scores)
        top1_relevance = query_relevance_scores[0] if query_relevance_scores else 0
        
        total_relevance_scores.extend(query_relevance_scores)
        
        print(f"\n  📊 Scenario Metrics:")
        print(f"      Best Prediction Accuracy: {top1_relevance:.0%}")
        print(f"      Avg Top-{TOP_K} Accuracy: {avg_relevance:.0%}")
        print(f"      Prediction Time: {latency:.1f}ms")

    # --- FINAL REPORT ---
    avg_relevance = statistics.mean(total_relevance_scores)
    avg_latency = statistics.mean(total_latencies)
    p95_latency = statistics.quantiles(total_latencies, n=20)[18] if len(total_latencies) >= 20 else max(total_latencies)
    
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
    run_evaluation()