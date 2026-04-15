from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class HeroInfo:
    name: str
    roles: tuple[str, ...]
    base_win_rate: float
    counters: tuple[str, ...]
    countered_by: tuple[str, ...]
    synergies: tuple[str, ...]


class HeroDatabase:
    def __init__(self, heroes: dict[str, HeroInfo]) -> None:
        self._heroes = heroes

    @classmethod
    def from_json(cls, path: Path) -> "HeroDatabase":
        payload = json.loads(path.read_text(encoding="utf-8"))
        heroes: dict[str, HeroInfo] = {}
        for name, meta in payload.items():
            heroes[name] = HeroInfo(
                name=name,
                roles=tuple(meta.get("roles", [])),
                base_win_rate=float(meta.get("base_win_rate", 50.0)),
                counters=tuple(meta.get("counters", [])),
                countered_by=tuple(meta.get("countered_by", [])),
                synergies=tuple(meta.get("synergies", [])),
            )
        return cls(heroes)

    def __contains__(self, hero_name: str) -> bool:
        return hero_name in self._heroes

    def get(self, hero_name: str) -> HeroInfo | None:
        return self._heroes.get(hero_name)

    def all_heroes(self) -> Iterable[str]:
        return self._heroes.keys()

    def values(self) -> Iterable[HeroInfo]:
        return self._heroes.values()
