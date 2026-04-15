from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
HERO_DATA_PATH = ROOT_DIR / "hero_data.json"
TEMPLATE_DIR = ROOT_DIR / "templates"

# Detection cadence (lower = more responsive, higher = lower CPU usage)
DETECTION_INTERVAL_MS = 700

# Template matching settings
TEMPLATE_SIZE = (56, 56)
MATCH_THRESHOLD = 0.62
HASH_DIFF_THRESHOLD = 3


@dataclass(frozen=True)
class NormalizedRect:
    """Rectangle represented in normalized coordinates (0.0 - 1.0)."""

    x: float
    y: float
    w: float
    h: float


# Static draft layout approximation for 16:9 scrcpy stream.
# Can be tuned manually if your HUD differs.
ALLY_BAN_RECTS = [
    NormalizedRect(0.090, 0.082, 0.048, 0.078),
    NormalizedRect(0.148, 0.082, 0.048, 0.078),
    NormalizedRect(0.206, 0.082, 0.048, 0.078),
    NormalizedRect(0.264, 0.082, 0.048, 0.078),
    NormalizedRect(0.322, 0.082, 0.048, 0.078),
]

ENEMY_BAN_RECTS = [
    NormalizedRect(0.862, 0.082, 0.048, 0.078),
    NormalizedRect(0.804, 0.082, 0.048, 0.078),
    NormalizedRect(0.746, 0.082, 0.048, 0.078),
    NormalizedRect(0.688, 0.082, 0.048, 0.078),
    NormalizedRect(0.630, 0.082, 0.048, 0.078),
]

ENEMY_PICK_RECTS = [
    NormalizedRect(0.116, 0.200, 0.058, 0.095),
    NormalizedRect(0.196, 0.200, 0.058, 0.095),
    NormalizedRect(0.276, 0.200, 0.058, 0.095),
    NormalizedRect(0.356, 0.200, 0.058, 0.095),
    NormalizedRect(0.436, 0.200, 0.058, 0.095),
]

ALLY_PICK_RECTS = [
    NormalizedRect(0.116, 0.705, 0.058, 0.095),
    NormalizedRect(0.196, 0.705, 0.058, 0.095),
    NormalizedRect(0.276, 0.705, 0.058, 0.095),
    NormalizedRect(0.356, 0.705, 0.058, 0.095),
    NormalizedRect(0.436, 0.705, 0.058, 0.095),
]


CORE_ROLES = ["EXP Lane", "Jungler", "Mid Lane", "Gold Lane", "Roamer"]

META_TIERS = {
    "S": {
        "Obsidia",
        "Julian",
        "Masha",
        "Diggie",
        "Kaja",
        "Lolita",
        "Zhuxin",
        "Gord",
        "Faramis",
    },
    "A": {
        "Barats",
        "Estes",
        "Natan",
        "Khufra",
        "Hylos",
        "Ruby",
        "Yve",
        "Kadita",
        "Freya",
        "Lunox",
        "Hanabi",
    },
}
