"""
Majority Voter - Borda count ensemble across multiple ranked lists.

Each ranker contributes (N - rank_position) Borda points per attraction.
The attraction with the most total Borda points wins.

Hard filter preserved: attractions that are verifiably closed (final_score == 0
in ALL rankers) are placed after all open/unknown attractions regardless of
their Borda points.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class MajorityVoter:

    def vote(self, ranked_lists: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Combine N ranked lists via Borda count.

        Args:
            ranked_lists: Each element is a fully ranked list from one ranker,
                          sorted best-first. Items are identified by 'place_id'.

        Returns:
            Single merged list sorted by Borda points (descending).
            Closed attractions are sorted to the end.
        """
        if not ranked_lists:
            return []

        # Collect all unique place_ids; use first list as the canonical dict source
        all_ids: List[str] = []
        seen_ids = set()
        id_to_candidate: Dict[str, Dict[str, Any]] = {}

        for ranked in ranked_lists:
            for item in ranked:
                pid = item.get('place_id')
                if pid and pid not in seen_ids:
                    all_ids.append(pid)
                    seen_ids.add(pid)
                    id_to_candidate[pid] = item

        n = len(all_ids)
        borda_points: Dict[str, int] = {pid: 0 for pid in all_ids}
        ranker_scores: Dict[str, List[float]] = {pid: [] for pid in all_ids}

        # Accumulate Borda points: rank 1 (index 0) gets N-1 points
        for ranked in ranked_lists:
            rank_map = {item['place_id']: idx for idx, item in enumerate(ranked) if item.get('place_id')}
            for pid in all_ids:
                rank_idx = rank_map.get(pid, n - 1)  # missing = last place
                borda_points[pid] += (n - 1 - rank_idx)
                ranker_scores[pid].append(ranked[rank_idx]['final_score'] if rank_idx < len(ranked) else 0.0)

        # Determine which attractions are closed across all rankers
        def is_closed(pid: str) -> bool:
            scores = ranker_scores[pid]
            return bool(scores) and all(s == 0.0 for s in scores)

        self._log_disagreements(ranked_lists, borda_points, n)

        # Build result: attach borda metadata, separate closed from open
        open_list = []
        closed_list = []

        for pid in all_ids:
            candidate = dict(id_to_candidate[pid])
            candidate['borda_points'] = borda_points[pid]
            candidate['final_score'] = round(borda_points[pid] / max(1, (n - 1) * len(ranked_lists)), 4)

            existing_breakdown = candidate.get('scoring_breakdown', {})
            candidate['scoring_breakdown'] = {
                **existing_breakdown,
                'borda_points': borda_points[pid],
            }

            if is_closed(pid):
                candidate['final_score'] = 0.0
                closed_list.append(candidate)
            else:
                open_list.append(candidate)

        open_list.sort(key=lambda x: x['borda_points'], reverse=True)
        closed_list.sort(key=lambda x: x['borda_points'], reverse=True)

        return open_list + closed_list

    def _log_disagreements(
        self,
        ranked_lists: List[List[Dict[str, Any]]],
        borda_points: Dict[str, int],
        n: int,
    ) -> None:
        if not logger.isEnabledFor(logging.DEBUG):
            return
        top3_per_ranker = [
            [item.get('name', item.get('place_id')) for item in ranked[:3]]
            for ranked in ranked_lists
        ]
        top3_borda = sorted(borda_points, key=lambda p: borda_points[p], reverse=True)[:3]
        logger.debug("Ranker top-3: %s | Borda top-3: %s", top3_per_ranker, top3_borda)
