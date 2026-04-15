import cv2
import mss
import numpy as np
import pathlib
import pygetwindow as gw

class VisionEngine:
    def __init__(self, templates_dir: str):
        self.templates_dir = pathlib.Path(templates_dir)
        self.templates = {}
        self.target_title = "TECNO KM5n" 
        self.match_threshold = 0.60 # Lebih peka untuk laptop i3
        self.scales = (0.9, 1.0, 1.1) # Fokus di range skala standar

    def _load_templates(self):
        self.templates = {}
        count = 0
        for file_path in sorted(self.templates_dir.iterdir()):
            if file_path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                img = cv2.imread(str(file_path), cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    self.templates[file_path.stem] = img
                    count += 1
        print(f"[VISION] Templates Loaded: {count}")

    def get_target_rect(self):
        try:
            wins = gw.getWindowsWithTitle(self.target_title)
            if wins:
                win = wins[0]
                if win.visible and not win.isMinimized:
                    return {"left": win.left, "top": win.top, "width": win.width, "height": win.height}
        except: return None
        return None

    def detect_draft(self, rect):
        if not self.templates: self._load_templates()
        with mss.mss() as sct:
            img = np.array(sct.grab(rect))
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
        h, w = gray.shape
        results = {"ally": [], "enemy": [], "ally_bans": [], "enemy_bans": []}
        
        for name, temp in self.templates.items():
            best_val = 0
            best_loc = (0,0)
            best_scale = 1.0
            
            for scale in self.scales:
                tw, th = int(temp.shape[1] * scale), int(temp.shape[0] * scale)
                if tw > w or th > h: continue
                t_scaled = cv2.resize(temp, (tw, th))
                res = cv2.matchTemplate(gray, t_scaled, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val > best_val:
                    best_val, best_loc, best_scale = max_val, max_loc, scale
            
            if best_val >= self.match_threshold:
                tw, th = int(temp.shape[1] * best_scale), int(temp.shape[0] * best_scale)
                cx, cy = best_loc[0] + (tw // 2), best_loc[1] + (th // 2)
                det_obj = {"name": name, "score": best_val, "box": (best_loc[0], best_loc[1], tw, th)}
                
                # RE-ZONING (Berdasarkan screenshot TECNO lo)
                if cy < h * 0.18: # Barisan Ban
                    if cx < w * 0.45: results["ally_bans"].append(det_obj)
                    elif cx > w * 0.55: results["enemy_bans"].append(det_obj)
                elif cx < w * 0.45: # Sisi Kiri (Ally)
                    results["ally"].append(det_obj)
                elif cx > w * 0.55: # Sisi Kanan (Enemy)
                    results["enemy"].append(det_obj)
        
        # Bersihkan duplikat (Ambil score tertinggi)
        for k in results:
            unique = {}
            for d in results[k]:
                if d["name"] not in unique or d["score"] > unique[d["name"]]["score"]:
                    unique[d["name"]] = d
            results[k] = list(unique.values())[:5]
        return results