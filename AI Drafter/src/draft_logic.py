"""
Draft Logic Engine - Calculates meta points, win rate, and hero recommendations.

Consumes hero_data.json and ScanResult from vision_scanner to produce
real-time draft analysis including counter suggestions and win probability.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("draft_logic")

ROLE_SLOTS = ["EXP Lane", "Mid Lane", "Gold Lane", "Roamer", "Jungler"]


@dataclass
class HeroInfo:
    name: str
    roles: list
    base_win_rate: float
    counters: list
    countered_by: list
    synergies: list


@dataclass
class DraftState:
    bans_team: list = field(default_factory=lambda: [None] * 5)
    bans_enemy: list = field(default_factory=lambda: [None] * 5)
    picks_team: list = field(default_factory=lambda: [None] * 5)
    picks_enemy: list = field(default_factory=lambda: [None] * 5)

    def get_banned_heroes(self) -> list:
        return [h for h in self.bans_team + self.bans_enemy if h is not None]

    def get_team_heroes(self) -> list:
        return [h for h in self.picks_team if h is not None]

    def get_enemy_heroes(self) -> list:
        return [h for h in self.picks_enemy if h is not None]

    def get_all_picked(self) -> list:
        return self.get_team_heroes() + self.get_enemy_heroes()

    def get_unavailable(self) -> list:
        return self.get_banned_heroes() + self.get_all_picked()

    def get_empty_team_slots(self) -> int:
        return sum(1 for h in self.picks_team if h is None)


@dataclass
class Recommendation:
    hero: str
    score: float
    reason: str
    role: str


@dataclass
class DraftAnalysis:
    team_score: float = 0.0
    enemy_score: float = 0.0
    win_rate: float = 50.0
    team_counter_advantages: list = field(default_factory=list)
    team_counter_disadvantages: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)
    team_roles_filled: list = field(default_factory=list)
    team_roles_missing: list = field(default_factory=list)
    enemy_roles_detected: list = field(default_factory=list)


class DraftLogic:
    """Core analysis engine that evaluates draft state and produces recommendations."""

    def __init__(self, hero_data_path: str = "hero_data.json"):
        self.hero_data = {}
        self._load_hero_data(hero_data_path)
        self.state = DraftState()
        logger.info(f"DraftLogic initialized with {len(self.hero_data)} heroes")

    def _load_hero_data(self, path: str):
        data_path = Path(path)
        if not data_path.exists():
            data_path = Path(__file__).resolve().parent.parent / path
        if not data_path.exists():
            logger.error(f"hero_data.json not found at {path}")
            return

        with open(data_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        for name, info in raw.items():
            self.hero_data[name] = HeroInfo(
                name=name,
                roles=info.get("roles", []),
                base_win_rate=info.get("base_win_rate", 50.0),
                counters=info.get("counters", []),
                countered_by=info.get("countered_by", []),
                synergies=info.get("synergies", []),
            )

    def update_state(self, scan_result) -> DraftState:
        self.state.bans_team = list(scan_result.bans_team)
        self.state.bans_enemy = list(scan_result.bans_enemy)
        self.state.picks_team = list(scan_result.picks_team)
        self.state.picks_enemy = list(scan_result.picks_enemy)
        return self.state

    def reset(self):
        self.state = DraftState()

    def analyze(self) -> DraftAnalysis:
        analysis = DraftAnalysis()

        # Meta scores
        analysis.team_score = self._calc_team_score(self.state.get_team_heroes())
        analysis.enemy_score = self._calc_team_score(self.state.get_enemy_heroes())

        # Counter analysis
        analysis.team_counter_advantages = self._find_counter_advantages(
            self.state.get_team_heroes(), self.state.get_enemy_heroes()
        )
        analysis.team_counter_disadvantages = self._find_counter_advantages(
            self.state.get_enemy_heroes(), self.state.get_team_heroes()
        )

        # Adjust scores for counters
        counter_bonus = len(analysis.team_counter_advantages) * 3.0
        counter_penalty = len(analysis.team_counter_disadvantages) * 3.0
        analysis.team_score += counter_bonus
        analysis.enemy_score += counter_penalty

        # Win rate
        analysis.win_rate = self._calc_win_rate(analysis.team_score, analysis.enemy_score)

        # Role analysis
        analysis.team_roles_filled = self._get_filled_roles(self.state.get_team_heroes())
        analysis.team_roles_missing = self._get_missing_roles(analysis.team_roles_filled)
        analysis.enemy_roles_detected = self._get_filled_roles(self.state.get_enemy_heroes())

        # Recommendations
        analysis.recommendations = self._generate_recommendations(analysis)

        return analysis

    def _calc_team_score(self, heroes: list) -> float:
        if not heroes:
            return 0.0
        score = 0.0
        for hero_name in heroes:
            info = self.hero_data.get(hero_name)
            if info:
                score += (info.base_win_rate - 50.0) * 2
        return score

    def _find_counter_advantages(self, our_heroes: list, their_heroes: list) -> list:
        advantages = []
        for our_hero in our_heroes:
            our_info = self.hero_data.get(our_hero)
            if not our_info:
                continue
            for their_hero in their_heroes:
                if their_hero in our_info.counters:
                    advantages.append(f"{our_hero} -> {their_hero}")
        return advantages

    def _calc_win_rate(self, team_score: float, enemy_score: float) -> float:
        diff = team_score - enemy_score
        win_rate = 50.0 + (diff * 1.5)
        return max(15.0, min(85.0, win_rate))

    def _get_filled_roles(self, heroes: list) -> list:
        filled = []
        for hero_name in heroes:
            info = self.hero_data.get(hero_name)
            if info and info.roles:
                filled.append(info.roles[0])
        return filled

    def _get_missing_roles(self, filled_roles: list) -> list:
        missing = []
        for role in ROLE_SLOTS:
            if role not in filled_roles:
                missing.append(role)
        return missing

    def _generate_recommendations(self, analysis: DraftAnalysis) -> list:
        recommendations = []
        unavailable = self.state.get_unavailable()

        if self.state.get_empty_team_slots() == 0:
            return recommendations

        # Counter picks
        counter_recs = self._get_counter_recommendations(
            self.state.get_enemy_heroes(), unavailable, analysis
        )
        recommendations.extend(counter_recs)

        # Role-fill picks
        role_recs = self._get_role_recommendations(
            analysis.team_roles_missing, unavailable
        )
        recommendations.extend(role_recs)

        # Synergy picks
        synergy_recs = self._get_synergy_recommendations(
            self.state.get_team_heroes(), unavailable
        )
        recommendations.extend(synergy_recs)

        # Sort by score, deduplicate
        seen = set()
        unique_recs = []
        for rec in sorted(recommendations, key=lambda r: r.score, reverse=True):
            if rec.hero not in seen:
                seen.add(rec.hero)
                unique_recs.append(rec)

        return unique_recs[:5]

    def _get_counter_recommendations(self, enemy_heroes, unavailable, analysis):
        recs = []
        for enemy_name in enemy_heroes:
            enemy_info = self.hero_data.get(enemy_name)
            if not enemy_info:
                continue
            for counter_name in enemy_info.countered_by:
                if counter_name in unavailable:
                    continue
                if counter_name not in self.hero_data:
                    continue
                counter_info = self.hero_data[counter_name]
                score = 80.0 + counter_info.base_win_rate - 50.0
                recs.append(Recommendation(
                    hero=counter_name,
                    score=score,
                    reason=f"Counters {enemy_name}",
                    role=counter_info.roles[0] if counter_info.roles else "Unknown"
                ))
        return recs

    def _get_role_recommendations(self, missing_roles, unavailable):
        recs = []
        for role in missing_roles:
            candidates = []
            for name, info in self.hero_data.items():
                if name in unavailable:
                    continue
                if role in info.roles:
                    counter_value = 0
                    for enemy_name in self.state.get_enemy_heroes():
                        if enemy_name in info.counters:
                            counter_value += 5
                    score = 50.0 + (info.base_win_rate - 50.0) * 2 + counter_value
                    candidates.append((name, score, info))

            candidates.sort(key=lambda x: x[1], reverse=True)
            for name, score, info in candidates[:3]:
                recs.append(Recommendation(
                    hero=name,
                    score=score,
                    reason=f"Fills {role}",
                    role=role
                ))
        return recs

    def _get_synergy_recommendations(self, team_heroes, unavailable):
        recs = []
        for team_hero in team_heroes:
            info = self.hero_data.get(team_hero)
            if not info:
                continue
            for syn_name in info.synergies:
                if syn_name in unavailable:
                    continue
                if syn_name not in self.hero_data:
                    continue
                syn_info = self.hero_data[syn_name]
                score = 60.0 + syn_info.base_win_rate - 50.0
                recs.append(Recommendation(
                    hero=syn_name,
                    score=score,
                    reason=f"Synergy with {team_hero}",
                    role=syn_info.roles[0] if syn_info.roles else "Unknown"
                ))
        return recs