# Ranking Engine: Majority Voting with Three Algorithms

## What This Document Covers

The attraction recommendation engine ranks a pool of ~15–25 candidate attractions and returns the best one to the user. This document explains:

1. The original ranking algorithm we had
2. Why we added two more algorithms
3. How each algorithm works, with concrete examples
4. How the majority voting (Borda count) combines all three
5. What code files were created or changed
6. A live test with mock data showing the results

---

## 1. The Original Algorithm — Linear Weighted Scoring

### How it worked

Every candidate attraction was scored using a single formula — a **weighted sum** of five independent scores:

```
final_score = (0.35 × semantic_score)
            + (0.20 × distance_score)
            + (0.10 × hours_score)
            + (0.10 × budget_score)
            + (0.20 × popularity_score)
            + (0.05 × diversity_bonus)
```

Each score is a number between 0 and 1:

| Score | How it's computed |
|---|---|
| `semantic_score` | Cosine similarity between the user's preference embedding and the attraction's embedding (from pgvector) |
| `distance_score` | `1 - (distance_km / max_walk_km)`, floored at 0. Closer = higher score |
| `hours_score` | 1.0 if open now, 0.5 if unknown, 0.0 if provably closed |
| `budget_score` | 1.0 if attraction price matches user's travel_style (budget/balanced/premium), lower otherwise |
| `popularity_score` | Normalized 0–1 value stored in the attractions DB (from OpenTripMap) |
| `diversity_bonus` | +1.0 if this attraction's category hasn't appeared in the results yet; cluster penalty if over-represented |

A hard filter applies at the end: if `hours_score == 0.0`, the entire score becomes 0.0 regardless of other factors.

### Why it was a good starting point

Simple, explainable, and fast. Each weight is tunable via environment variable. Works well when the weights are calibrated correctly.

### The core problem

**Semantic dominance.** The semantic score carries the most weight (0.35). An attraction that is a perfect preference match (semantic=0.99) but is far away, niche, and expensive can still beat a nearby, popular, well-rounded attraction — because one dimension dominates the others.

Example:
- Niche Museum: semantic=0.99, distance=0.10, popularity=0.20 → score ≈ 0.43
- Neighbourhood Park: semantic=0.70, distance=0.90, popularity=0.80 → score ≈ 0.58

Linear correctly picks the Park here — but if the Museum's semantic score were just a little higher, or the weights slightly different, it could flip. The algorithm is brittle to weight choices.

---

## 2. Why We Added Two More Algorithms

The goal was **robustness through disagreement**. No single ranking formula is optimal in all situations. But if three fundamentally different algorithms all agree that attraction X is good, that's a much stronger signal than one algorithm saying so alone.

This is called **majority voting** — the final ranking is decided by aggregating the votes of all three rankers, not by trusting any one of them.

The two new algorithms needed to cover **different failure modes** from the linear ranker:

| Algorithm | What failure mode it catches |
|---|---|
| Linear (existing) | Good when weights are calibrated, but one dimension can dominate |
| RRF (new) | Catches cases where linear's semantic weight unfairly buries well-rounded attractions |
| Max-Min (new) | Catches cases where one dimension is catastrophically bad (e.g. very far away) |

---

## 3. How Each Algorithm Works

### Algorithm 1 — Linear Weighted Sum (existing)

Already explained above. Multiplies each score by a weight, sums them up, sorts by the result.

---

### Algorithm 2 — Reciprocal Rank Fusion (RRF)

**Core idea:** Instead of combining raw scores, combine *ranks*. For each scoring dimension, rank all candidates from best to worst. Then compute a fusion score that rewards consistent high ranking across ALL dimensions.

**Formula:**

```
rrf_score = Σ  1 / (k + rank_i)
```

Where:
- `rank_i` is this attraction's rank on dimension `i` (rank 1 = best)
- `k = 60` (a conventional constant that softens the impact of very early ranks)
- The sum is across all 5 dimensions: semantic, distance, hours, budget, popularity

**Why this is different from linear:**

In linear, a score of 0.99 on semantic is *multiplied* by 0.35 — so even if this attraction is last on distance, the high semantic score carries it. In RRF, semantic rank #1 gives `1/(60+1) = 0.0164` points. Distance rank #10 (last place) gives `1/(60+10) = 0.0143` points. The gap is much smaller — being bad on distance genuinely hurts you, even if you're great on semantic.

**Example:**

| Attraction | Semantic rank | Distance rank | Popularity rank | RRF score |
|---|---|---|---|---|
| Niche Museum | **#1** (0.95) | #4 (very far) | #4 (niche) | 1/61 + 1/64 + 1/64 = **0.0473** |
| Central Park | #2 (0.70) | **#1** (closest) | **#1** (popular) | 1/62 + 1/61 + 1/61 = **0.0487** |

Central Park wins in RRF because it ranks high on *multiple* dimensions. The Museum's dominance on semantic alone isn't enough to overcome its poor distance and popularity ranks.

---

### Algorithm 3 — Max-Min ("No Weak Spots")

**Core idea:** An attraction's score equals the score of its *worst* dimension. It's only as good as its weakest link.

**Formula:**

```
score = min(semantic, distance, hours, budget, popularity)
```

**Why this is different:**

Linear rewards high averages. Max-Min rewards having no catastrophic weakness. An attraction that scores 0.9, 0.9, 0.9, 0.9, 0.0 on five dimensions gets a Max-Min score of 0.0 — because one dimension is terrible. Linear would give it a score of ~0.72, which is pretty good.

**Example:**

| Attraction | Semantic | Distance | Hours | Budget | Popularity | Max-Min score |
|---|---|---|---|---|---|---|
| Niche Museum | 0.95 | **0.0** (too far) | 1.0 | 1.0 | 0.30 | **0.0** — distance kills it |
| Central Park | 0.70 | 0.99 | 1.0 | **0.5** | 0.80 | **0.5** — budget is worst |
| Bistro 51 | **0.60** | 0.97 | 1.0 | 1.0 | 0.70 | **0.60** — semantic is worst, but nothing is catastrophic |

Bistro 51 wins here even though it has the worst semantic score — because it has *no catastrophically bad dimension*. Max-Min is the only algorithm that would promote it to #1.

---

## 4. How the Majority Vote Works — Borda Count

### The problem with 2 algorithms

With 2 algorithms, ties are common and there's no "majority" — it's just an average. You need at least 3 for true voting.

### Borda Count

Each ranker assigns **points** to each attraction based on its position in the ranked list:

```
Borda points = (N - 1) - rank_index
```

Where N is the total number of candidates and rank_index starts at 0 (so rank #1 gets the most points).

All three rankers contribute points independently. The attraction with the **most total Borda points** wins.

**Example with 4 candidates (N=4, so max points per ranker = 3):**

| Attraction | Linear rank | Linear pts | RRF rank | RRF pts | MaxMin rank | MaxMin pts | **Total Borda** |
|---|---|---|---|---|---|---|---|
| Central Park | #1 | 3 | #1 | 3 | #2 | 2 | **8** |
| Bistro 51 | #2 | 2 | #3 | 1 | #1 | 3 | **6** |
| Niche Museum | #3 | 1 | #2 | 2 | #3 | 1 | **4** |
| Night Cafe (closed) | #4 | 0 | #4 | 0 | #4 | 0 | **0** |

**Central Park wins** because it consistently ranks near the top across all three algorithms. No single algorithm strongly disagrees.

**Hard filter preserved:** Any attraction that is provably closed (hours_score = 0.0 in all rankers) is forced to the bottom of the final list, regardless of Borda points.

---

## 5. Code Changes

### Files Created

| File | Purpose |
|---|---|
| `engine/src/services/ranking_utils.py` | Shared raw scoring functions used by all three rankers. Extracts `compute_raw_scores()` which returns the five dimension scores (0–1) for a candidate given user/trip context. No weights applied here. |
| `engine/src/services/rrf_ranker.py` | RRF ranker class. Exposes same `rank_candidates()` interface as the existing `RankingEngine`. |
| `engine/src/services/maxmin_ranker.py` | Max-Min ranker class. Same interface. |
| `engine/src/services/majority_voter.py` | `MajorityVoter.vote(ranked_lists)` — takes N ranked lists, applies Borda count, returns single merged list. Closed attractions are pushed to the end. |

### Files Modified

**`engine/src/services/ranking_service.py`**

The existing `RankingEngine` previously had private methods `_score_distance`, `_score_hours`, `_score_budget`, `_score_popularity` defined inline. These were extracted into `ranking_utils.py` so all three rankers share the same scoring logic. The `rank_candidates()` method now calls `compute_raw_scores()` from the shared module.

**`engine/src/internal-routes/recommendations.py`**

Step 4 of the recommendation pipeline was updated. Previously:

```python
# OLD — single ranker
ranked_candidates = ranking_engine.rank_candidates(candidates=candidates, ...)
```

Now:

```python
# NEW — three rankers + majority vote
ranked_linear = ranking_engine.rank_candidates(candidates=list(candidates), **base_rank_kwargs)
ranked_rrf    = rrf_ranker.rank_candidates(candidates=list(candidates),    **base_rank_kwargs)
ranked_maxmin = maxmin_ranker.rank_candidates(candidates=list(candidates), **base_rank_kwargs)
ranked_candidates = majority_voter.vote([ranked_linear, ranked_rrf, ranked_maxmin])
```

Each ranker receives its own shallow copy of the candidate list (`list(candidates)`) so in-place mutations in one ranker don't affect the others.

Three new module-level instances were added alongside the existing `ranking_engine`:

```python
rrf_ranker    = RRFRanker()
maxmin_ranker = MaxMinRanker()
majority_voter = MajorityVoter()
```

---

## 6. Mock Data Test — Live Results

We ran all three rankers plus the Borda vote against four hand-crafted mock attractions. The user is standing at coordinates `(51.524, -0.158)`, it is 14:00, and their travel style is `balanced`.

### Input

| Attraction | Semantic | Popularity | Hours | Notes |
|---|---|---|---|---|
| Niche Museum | 0.95 | 0.30 | 09:00–17:00 | Very high semantic match, but far from user (lat 51.60) |
| Central Park | 0.70 | 0.80 | 08:00–20:00 | Decent on everything, right next to user |
| Night Cafe | 0.65 | 0.60 | 23:00–01:00 | **Closed at 14:00** |
| Bistro 51 | 0.60 | 0.70 | 11:00–22:00 | Balanced, open, close by |

### Results

```
── RANKER 1 — Linear weighted sum ──────────────────────────
  #1 Central Park      score=0.755
  #2 Bistro 51         score=0.737
  #3 Niche Museum      score=0.543
  #4 Night Cafe        score=0.0    ← closed

── RANKER 2 — RRF ──────────────────────────────────────────
  #1 Central Park      score=0.0807
  #2 Niche Museum      score=0.0799   ← promoted (semantic rank #1)
  #3 Bistro 51         score=0.0799
  #4 Night Cafe        score=0.0    ← closed

── RANKER 3 — Max-Min ──────────────────────────────────────
  #1 Bistro 51         score=0.60   worst_dim=semantic
  #2 Central Park      score=0.50   worst_dim=budget (free entry = below balanced range)
  #3 Niche Museum      score=0.0    worst_dim=distance  ← too far, floors to 0
  #4 Night Cafe        score=0.0    worst_dim=hours  ← closed

── BORDA COUNT (majority vote) ─────────────────────────────
  #1 Central Park      borda_points=8   final_score=0.889
  #2 Bistro 51         borda_points=6   final_score=0.667
  #3 Niche Museum      borda_points=4   final_score=0.444
  #4 Night Cafe        borda_points=0   final_score=0.0
```

### What the results show

**Central Park wins** — all three rankers independently place it at or near the top. Borda accumulates the most points for it (8 out of a max of 9).

**Niche Museum** is the interesting case. It has the highest semantic score (0.95) but is far from the user:
- Linear places it #3 — semantic carries it but distance and popularity drag it down
- RRF promotes it to #2 — being semantic rank #1 counts, but being distance rank #4 also hurts
- Max-Min scores it 0.0 — its worst dimension (distance) is catastrophic, so it gets the same score as the closed café

The Borda count correctly places it at #3, not #1 — the three algorithms together "debate" and settle on a middle-ground answer.

**Night Cafe** gets 0 Borda points (last place in every ranker) and its final score is forced to 0.0 by the hard-filter override. Regardless of how many Borda points it might theoretically accumulate, a closed attraction always ends up at the bottom.
