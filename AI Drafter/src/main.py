"""
MLBB AI Drafter - Main Entry Point

Initializes all modules, starts the vision scan loop in a background thread,
and runs the PyQt5 overlay UI on the main thread.

Usage: python src/main.py
"""

from __future__ import annotations

import sys
import os
import time
import logging
import threading
import configparser
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

ROOT_DIR = SRC_DIR.parent
os.chdir(ROOT_DIR)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QTimer

from vision_scanner import VisionScanner
from draft_logic import DraftLogic
from ui_overlay import DraftOverlay


def setup_logging():
    log_format = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    date_format = "%H:%M:%S"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(ROOT_DIR / "drafter.log", encoding="utf-8"),
        ]
    )


logger = logging.getLogger("main")


class ScanLoop:
    """Background scan loop that periodically captures and analyzes the draft screen."""

    def __init__(self, scanner: VisionScanner, logic: DraftLogic, overlay: DraftOverlay):
        self.scanner = scanner
        self.logic = logic
        self.overlay = overlay
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Scan loop started")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        logger.info("Scan loop stopped")

    def _run(self):
        while self._running:
            try:
                if not self.scanner.paused:
                    result = self.scanner.scan_once()
                    with self._lock:
                        self.logic.update_state(result)
                        analysis = self.logic.analyze()
                    self.overlay.update_analysis(
                        analysis, self.logic.state, result.scan_time
                    )
                    logger.debug(
                        f"Scan: {result.scan_time:.2f}s | "
                        f"Team: {len(result.picks_team)} | "
                        f"Enemy: {len(result.picks_enemy)} | "
                        f"WR: {analysis.win_rate:.0f}%"
                    )
                time.sleep(self.scanner.scan_interval)
            except Exception as e:
                logger.error(f"Scan loop error: {e}", exc_info=True)
                time.sleep(2.0)


class HotkeyHandler:
    """Handles global hotkeys using pynput or keyboard library."""

    def __init__(self, scanner, logic, overlay, app):
        self.scanner = scanner
        self.logic = logic
        self.overlay = overlay
        self.app = app
        self._listener = None

    def start(self):
        try:
            from pynput import keyboard
            self._listener = keyboard.GlobalHotKeys({
                '<f9>': self._toggle_scan,
                '<f10>': self._reset_draft,
                '<f12>': self._quit_app,
            })
            self._listener.start()
            logger.info("Hotkey listener started (pynput)")
        except ImportError:
            try:
                import keyboard as kb
                kb.add_hotkey('f9', self._toggle_scan)
                kb.add_hotkey('f10', self._reset_draft)
                kb.add_hotkey('f12', self._quit_app)
                logger.info("Hotkey listener started (keyboard)")
            except ImportError:
                logger.warning(
                    "No hotkey library available. Install pynput or keyboard."
                )

    def stop(self):
        if self._listener:
            self._listener.stop()

    def _toggle_scan(self):
        paused = self.scanner.toggle_pause()
        QTimer.singleShot(0, lambda: self.overlay.set_paused(paused))

    def _reset_draft(self):
        self.scanner.reset()
        self.logic.reset()
        logger.info("Draft reset via hotkey")

    def _quit_app(self):
        logger.info("Quit requested via hotkey")
        QTimer.singleShot(0, self.app.quit)


def main():
    setup_logging()
    logger.info("=" * 50)
    logger.info("MLBB AI Drafter starting...")
    logger.info("=" * 50)

    config_path = str(ROOT_DIR / "config.ini")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    logger.info("Initializing Vision Scanner...")
    scanner = VisionScanner(config_path=config_path)

    logger.info("Initializing Draft Logic...")
    logic = DraftLogic(hero_data_path=str(ROOT_DIR / "hero_data.json"))

    logger.info("Initializing UI Overlay...")
    overlay = DraftOverlay(config_path=config_path)

    logger.info("Searching for Scrcpy window...")
    found = scanner.find_scrcpy_window()
    if found:
        overlay.position_near_scrcpy(
            scanner._window_x, scanner._window_y,
            scanner._window_w, scanner._window_h
        )
    else:
        screen = app.primaryScreen().geometry()
        overlay.move(screen.width() - overlay._overlay_width - 10, 10)

    overlay.set_click_through(True)
    overlay.show()
    logger.info("Overlay displayed")

    scan_loop = ScanLoop(scanner, logic, overlay)
    scan_loop.start()

    hotkey_handler = HotkeyHandler(scanner, logic, overlay, app)
    hotkey_handler.start()

    def reposition_overlay():
        if not scanner.paused:
            found_now = scanner.find_scrcpy_window()
            if found_now:
                overlay.position_near_scrcpy(
                    scanner._window_x, scanner._window_y,
                    scanner._window_w, scanner._window_h
                )

    reposition_timer = QTimer()
    reposition_timer.timeout.connect(reposition_overlay)
    reposition_timer.start(5000)

    def cleanup():
        logger.info("Cleaning up...")
        scan_loop.stop()
        hotkey_handler.stop()
        scanner.close()
        logger.info("MLBB AI Drafter stopped")

    app.aboutToQuit.connect(cleanup)

    exit_code = app.exec_()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()