from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QColor, QPainter, QPen, QFont
from PyQt5.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget, QPushButton, QGridLayout

class OverlayWindow(QMainWindow):
    update_signal = pyqtSignal(object)
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.is_paused, self.is_minimized = True, False
        self.last_boxes = {"ally": [], "enemy": []}
        
        self._root = QWidget(self)
        self.setCentralWidget(self._root)
        main_layout = QVBoxLayout(self._root)
        
        self.panel = QFrame()
        self.panel.setObjectName("mainPanel")
        self.panel.setFixedWidth(600)
        p_lay = QVBoxLayout(self.panel)

        # Header
        h_row = QHBoxLayout()
        header_container = QVBoxLayout()
        header = QLabel("SYSTEM: NEURAL DRAFTER")
        header.setObjectName("headerText")
        v_tag = QLabel("OS VERSION: 4.2 // CALIBRATED")
        v_tag.setObjectName("versionTag")
        header_container.addWidget(header); header_container.addWidget(v_tag)
        
        self.min_btn = QPushButton("×")
        self.min_btn.setFixedSize(25, 25)
        self.min_btn.clicked.connect(self.toggle_min)
        
        h_row.addLayout(header_container); h_row.addStretch(); h_row.addWidget(self.min_btn)
        p_lay.addLayout(h_row)

        # Winrate & Bans
        status_bar = QHBoxLayout()
        self.win_rate_lbl = QLabel("WIN CHANCE: --%")
        self.win_rate_lbl.setObjectName("winRateText")
        status_bar.addWidget(self.win_rate_lbl); status_bar.addStretch()
        
        self.ban_container = QHBoxLayout()
        self.ally_bans = [QLabel("·") for _ in range(5)]
        self.enemy_bans = [QLabel("·") for _ in range(5)]
        for b in self.ally_bans: b.setObjectName("banAlly"); self.ban_container.addWidget(b)
        self.ban_container.addSpacing(10)
        for b in self.enemy_bans: b.setObjectName("banEnemy"); self.ban_container.addWidget(b)
        status_bar.addLayout(self.ban_container)
        p_lay.addLayout(status_bar)

        # Content Grid
        self.content = QWidget()
        grid = QGridLayout(self.content)
        
        box1 = QFrame(); box1.setObjectName("card")
        b1_lay = QVBoxLayout(box1)
        b1_lay.addWidget(QLabel("● CORE COUNTER TARGET"))
        self.f_hero = QLabel("WAITING..."); self.f_hero.setObjectName("focusHeroName")
        self.f_reason = QLabel("-"); self.f_reason.setWordWrap(True); self.f_reason.setObjectName("reasonText")
        b1_lay.addWidget(self.f_hero); b1_lay.addWidget(self.f_reason)
        grid.addWidget(box1, 0, 0)

        box2 = QFrame(); box2.setObjectName("card")
        b2_lay = QVBoxLayout(box2)
        b2_lay.addWidget(QLabel("● OPTIMAL LINEUP"))
        self.lane_labels = {}
        for l in ["EXP", "JNG", "MID", "GLD", "ROM"]:
            r = QHBoxLayout()
            lbl = QLabel(l); val = QLabel("----"); val.setObjectName("heroValue")
            r.addWidget(lbl); r.addStretch(); r.addWidget(val)
            b2_lay.addLayout(r); self.lane_labels[l] = val
        grid.addWidget(box2, 0, 1)

        box3 = QFrame(); box3.setObjectName("card")
        b3_lay = QVBoxLayout(box3)
        b3_lay.addWidget(QLabel("● ENEMY COUNTER ADVISOR"))
        adv_row = QHBoxLayout()
        self.enemy_adv = [QLabel("--") for _ in range(5)]
        for lbl in self.enemy_adv: lbl.setObjectName("enemyAdvLabel"); adv_row.addWidget(lbl)
        b3_lay.addLayout(adv_row)
        grid.addWidget(box3, 1, 0, 1, 2)

        p_lay.addWidget(self.content)
        self.status_lbl = QLabel("SYSTEM READY >> PRESS ALT+S")
        self.status_lbl.setObjectName("footerStatus")
        p_lay.addWidget(self.status_lbl)

        main_layout.addWidget(self.panel, alignment=Qt.AlignCenter)
        self._apply_styles()
        self.update_signal.connect(self.refresh_data)

    def toggle_min(self):
        self.is_minimized = not self.is_minimized
        self.content.setVisible(not self.is_minimized)
        self.panel.setFixedHeight(450 if not self.is_minimized else 100)

    def mousePressEvent(self, e): self.oldPos = e.globalPos()
    def mouseMoveEvent(self, e):
        delta = QPoint(e.globalPos() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y()); self.oldPos = e.globalPos()

    def refresh_data(self, data):
        self.is_paused = data.get("is_paused", True)
        self.last_boxes = data.get("boxes", {"ally": [], "enemy": []})
        
        if self.is_paused:
            self.status_lbl.setText("PAUSED // STANDBY MODE")
        else:
            ans = data.get("analysis", {})
            self.win_rate_lbl.setText(f"PROBABILITY: {ans.get('probability', 50):.1f}%")
            self.f_hero.setText(ans.get("focus", {}).get("name", "SCANNING..."))
            self.f_reason.setText(ans.get("focus", {}).get("reason", "-"))
            
            vec = ans.get("vectors", {})
            lane_map = {"EXP Lane": "EXP", "Jungler": "JNG", "Mid Lane": "MID", "Gold Lane": "GLD", "Roamer": "ROM"}
            for fk, sk in lane_map.items(): self.lane_labels[sk].setText(vec.get(fk, "----"))
            
            adv = ans.get("enemy_advice", [])
            for i in range(5): self.enemy_adv[i].setText(adv[i].split(":")[0] if i < len(adv) else "--")
            
            self.status_lbl.setText(f"DETECTION: A:{len(self.last_boxes['ally'])} E:{len(self.last_boxes['enemy'])}")
        self.update()

    def paintEvent(self, e):
        if self.is_paused: return
        p = QPainter(self)
        for t, c in [("ally", QColor(0, 255, 136, 200)), ("enemy", QColor(255, 68, 68, 200))]:
            p.setPen(QPen(c, 2))
            for det in self.last_boxes.get(t, []):
                x, y, w, h = det["box"]
                p.drawRect(x, y, w, h); p.drawText(x, y-5, det["name"].upper())

    def _apply_styles(self):
        self.setStyleSheet("""
            #mainPanel { background: rgba(10, 20, 10, 230); border: 2px solid #00FF88; border-radius: 15px; }
            #card { background: rgba(255, 255, 255, 15); border: 1px solid rgba(0, 255, 136, 60); border-radius: 8px; padding: 5px; }
            QLabel { font-family: 'Consolas'; color: #AAAAAA; font-size: 11px; }
            #headerText { color: #00FF88; font-size: 18px; font-weight: bold; }
            #versionTag { color: #008844; font-size: 9px; }
            #focusHeroName { color: #FFFFFF; font-size: 24px; font-weight: bold; }
            #enemyAdvLabel { background: rgba(255, 50, 50, 30); border: 1px solid #FF3232; color: #FF3232; border-radius: 4px; padding: 2px; }
            #footerStatus { color: #00FF88; border-top: 1px solid rgba(0,255,136,40); padding: 5px; }
            QPushButton { background: transparent; border: 1px solid #00FF88; color: #00FF88; border-radius: 12px; }
        """)

def create_app():
    return QApplication([]), OverlayWindow()