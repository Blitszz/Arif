"""
Vision Scanner Engine - Detects hero icons in MLBB draft screen via OpenCV.

Uses mss for fast screen capture and cv2 template matching in grayscale.
Optimized for low-end CPUs: 1-2 FPS scan loop, static area cropping.
"""

from __future__ import annotations

import configparser
import time
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np
import mss

logger = logging.getLogger("vision_scanner")


@dataclass
class ScanRegion:
    """A rectangular region on screen defined by (x, y, w, h)."""
    x: int
    y: int
    w: int
    h: int

    def as_mss_dict(self, offset_x: int = 0, offset_y: int = 0) -> dict:
        return {
            "left": offset_x + self.x,
            "top": offset_y + self.y,
            "width": self.w,
            "height": self.h,
        }


@dataclass
class DraftSlot:
    """Represents one ban/pick slot with its region and current detection."""
    name: str
    region: ScanRegion
    hero: Optional[str] = None


@dataclass
class ScanResult:
    """Result of one full scan pass."""
    bans_team: list = field(default_factory=lambda: [None] * 5)
    bans_enemy: list = field(default_factory=lambda: [None] * 5)
    picks_team: list = field(default_factory=lambda: [None] * 5)
    picks_enemy: list = field(default_factory=lambda: [None] * 5)
    scan_time: float = 0.0

    def all_detected(self) -> list:
        heroes = []
        for lst in (self.bans_team, self.bans_enemy, self.picks_team, self.picks_enemy):
            for h in lst:
                if h is not None:
                    heroes.append(h)
        return heroes


class VisionScanner:
    """
    Scans the Scrcpy window for hero icons using template matching.
    """

    def __init__(self, config_path: str = "config.ini"):
        self.config = configparser.ConfigParser()
        self.config.read(config_path, encoding="utf-8")

        self.confidence = self.config.getfloat("vision", "confidence", fallback=0.75)
        self.scan_interval = self.config.getfloat("vision", "scan_interval", fallback=1.0)
        self.use_grayscale = self.config.getboolean("vision", "grayscale", fallback=True)

        self._window_x = 0
        self._window_y = 0
        self._window_w = self.config.getint("resolution", "width", fallback=1280)
        self._window_h = self.config.getint("resolution", "height", fallback=720)

        self.ban_team_slots = []
        self.ban_enemy_slots = []
        self.pick_team_slots = []
        self.pick_enemy_slots = []
        self._build_slots()

        self.templates = {}
        self._load_templates()

        self._sct = mss.mss()
        self._paused = False
        self._running = False

        logger.info(
            f"VisionScanner init: {len(self.templates)} templates, "
            f"conf={self.confidence}, interval={self.scan_interval}s"
        )

    def _build_slots(self):
        sections = {
            "ban_team": "ban_team_slots",
            "ban_enemy": "ban_enemy_slots",
            "pick_team": "pick_team_slots",
            "pick_enemy": "pick_enemy_slots",
        }
        for prefix, attr_name in sections.items():
            slot_list = []
            for i in range(1, 6):
                key = f"{prefix}_{i}"
                val = self.config.get("scan_regions", key, fallback=None)
                if val:
                    parts = [int(v.strip()) for v in val.split(",")]
                    region = ScanRegion(x=parts[0], y=parts[1], w=parts[2], h=parts[3])
                    slot_list.append(DraftSlot(name=key, region=region))
            setattr(self, attr_name, slot_list)

    def _load_templates(self):
        templates_dir = Path(__file__).resolve().parent.parent / "templates"
        if not templates_dir.exists():
            logger.error(f"Templates dir not found: {templates_dir}")
            return

        for img_path in sorted(templates_dir.glob("*.png")):
            hero_name = img_path.stem
            img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                self.templates[hero_name] = img
            else:
                logger.warning(f"Failed to load template: {img_path.name}")

        logger.info(f"Loaded {len(self.templates)} hero templates")

    def find_scrcpy_window(self) -> bool:
        try:
            import ctypes
            import ctypes.wintypes

            user32 = ctypes.windll.user32
            window_title = self.config.get("scrcpy", "window_title", fallback="scrcpy")
            found_hwnd = None

            def enum_callback(hwnd, _):
                nonlocal found_hwnd
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        if window_title.lower() in buf.value.lower():
                            found_hwnd = hwnd
                            return False
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

            if found_hwnd:
                rect = ctypes.wintypes.RECT()
                user32.GetWindowRect(found_hwnd, ctypes.byref(rect))
                self._window_x = rect.left
                self._window_y = rect.top
                self._window_w = rect.right - rect.left
                self._window_h = rect.bottom - rect.top
                logger.info(
                    f"Scrcpy window at ({self._window_x}, {self._window_y}) "
                    f"size {self._window_w}x{self._window_h}"
                )
                return True
            else:
                logger.warning("Scrcpy window not found, using primary monitor")
                return False
        except Exception as e:
            logger.warning(f"Window detection failed: {e}")
            return False

    def _capture_region(self, region: ScanRegion):
        try:
            mss_region = region.as_mss_dict(self._window_x, self._window_y)
            shot = self._sct.grab(mss_region)
            img = np.array(shot)
            if self.use_grayscale:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
            else:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img
        except Exception as e:
            logger.debug(f"Capture failed: {e}")
            return None

    def _match_hero(self, crop):
        best_hero = None
        best_val = 0.0

        if len(crop.shape) == 3:
            crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        for hero_name, template in self.templates.items():
            if template.shape[0] > crop.shape[0] or template.shape[1] > crop.shape[1]:
                template_resized = cv2.resize(
                    template, (crop.shape[1], crop.shape[0]),
                    interpolation=cv2.INTER_AREA
                )
            else:
                template_resized = template

            try:
                result = cv2.matchTemplate(crop, template_resized, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                if max_val > best_val:
                    best_val = max_val
                    best_hero = hero_name
            except cv2.error:
                continue

        if best_val >= self.confidence and best_hero:
            return best_hero
        return None

    def scan_once(self) -> ScanResult:
        t0 = time.perf_counter()
        result = ScanResult()

        for i, slot in enumerate(self.ban_team_slots):
            crop = self._capture_region(slot.region)
            if crop is not None:
                hero = self._match_hero(crop)
                result.bans_team[i] = hero
                slot.hero = hero

        for i, slot in enumerate(self.ban_enemy_slots):
            crop = self._capture_region(slot.region)
            if crop is not None:
                hero = self._match_hero(crop)
                result.bans_enemy[i] = hero
                slot.hero = hero

        for i, slot in enumerate(self.pick_team_slots):
            crop = self._capture_region(slot.region)
            if crop is not None:
                hero = self._match_hero(crop)
                result.picks_team[i] = hero
                slot.hero = hero

        for i, slot in enumerate(self.pick_enemy_slots):
            crop = self._capture_region(slot.region)
            if crop is not None:
                hero = self._match_hero(crop)
                result.picks_enemy[i] = hero
                slot.hero = hero

        result.scan_time = time.perf_counter() - t0
        return result

    @property
    def paused(self):
        return self._paused

    def toggle_pause(self) -> bool:
        self._paused = not self._paused
        state = "PAUSED" if self._paused else "RESUMED"
        logger.info(f"Vision scanner {state}")
        return self._paused

    def reset(self):
        for slot_list in (
            self.ban_team_slots, self.ban_enemy_slots,
            self.pick_team_slots, self.pick_enemy_slots,
        ):
            for slot in slot_list:
                slot.hero = None
        logger.info("Vision scanner reset")

    def close(self):
        self._running = False
        try:
            self._sct.close()
        except Exception:
            pass
        logger.info("Vision scanner closed")