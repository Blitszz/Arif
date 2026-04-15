import sys, json, keyboard, time
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal
from draft_logic import calculate_draft
from ui_overlay import create_app
from vision_engine import VisionEngine

class DrafterBot(QThread):
    data_signal = pyqtSignal(dict)
    def __init__(self, hero_data, temp_dir):
        super().__init__()
        self.hero_data, self.engine = hero_data, VisionEngine(temp_dir)
        self.paused, self.running = True, True
        print("[SYS] AI Drafter v4.0 Active. Window: TECNO KM5n")

    def toggle(self):
        self.paused = not self.paused
        print(f"[CTRL] Bot: {'RUNNING' if not self.paused else 'PAUSED'}")

    def run(self):
        while self.running:
            if self.paused:
                self.data_signal.emit({"is_paused": True}); time.sleep(0.5); continue
            rect = self.engine.get_target_rect()
            if not rect:
                self.data_signal.emit({"is_paused": False, "error": "NOT FOUND"}); time.sleep(1); continue
            try:
                det = self.engine.detect_draft(rect)
                print(f"[SCAN] A:{len(det['ally'])} E:{len(det['enemy'])} AB:{len(det['ally_bans'])} EB:{len(det['enemy_bans'])}", end='\r')
                ans = calculate_draft(self.hero_data, [d["name"] for d in det["ally"]], [d["name"] for d in det["enemy"]], [d["name"] for d in det["ally_bans"]], [d["name"] for d in det["enemy_bans"]])
                self.data_signal.emit({"is_paused": False, "boxes": det, "analysis": ans, "ally_bans": [d["name"] for d in det["ally_bans"]], "enemy_bans": [d["name"] for d in det["enemy_bans"]]})
            except Exception as e: print(f"\n[ERR] {e}")
            time.sleep(0.35)

    def stop(self): self.running = False

def main():
    root = Path(__file__).resolve().parent
    try:
        with open(root / "hero_data.json", "r", encoding="utf-8") as f: hero_data = json.load(f)
    except: return
    app, win = create_app(); win.show()
    bot = DrafterBot(hero_data, str(root / "templates"))
    bot.data_signal.connect(win.refresh_data)
    keyboard.add_hotkey('alt+s', bot.toggle)
    bot.start(); app.aboutToQuit.connect(bot.stop)
    sys.exit(app.exec_())

if __name__ == "__main__": main()