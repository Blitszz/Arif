"""
UI Overlay - Transparent always-on-top draft analysis display.
"""

from __future__ import annotations

import configparser
import logging
from typing import Optional

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QFrame, QSizePolicy, QPushButton
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QPoint
from PyQt5.QtGui import (
    QFont, QColor, QPalette, QPainter, QPen,
    QLinearGradient, QBrush, QCursor
)

from draft_logic import DraftAnalysis, DraftState

logger = logging.getLogger("ui_overlay")
FONT_FAMILY = "Consolas"

def hex_to_qcolor(hex_str: str) -> QColor:
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 6:
        return QColor(int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))
    return QColor(0, 255, 65)


class NeonProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 50.0
        self.setFixedHeight(24)
        self.setMinimumWidth(200)

    @property
    def value(self): return self._value

    @value.setter
    def value(self, v):
        self._value = max(0.0, min(100.0, v))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(13, 13, 13))

        team_w = int(w * (self._value / 100.0))
        if team_w > 0:
            grad = QLinearGradient(0, 0, team_w, 0)
            grad.setColorAt(0, QColor(0, 143, 17))
            grad.setColorAt(1, QColor(0, 255, 65))
            painter.fillRect(0, 0, team_w, h, QBrush(grad))

        enemy_w = w - team_w
        if enemy_w > 0:
            grad = QLinearGradient(team_w, 0, w, 0)
            grad.setColorAt(0, QColor(255, 0, 64))
            grad.setColorAt(1, QColor(139, 0, 35))
            painter.fillRect(team_w, 0, enemy_w, h, QBrush(grad))

        painter.setPen(QPen(QColor(0, 255, 65), 1))
        painter.drawRect(0, 0, w - 1, h - 1)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        painter.drawText(self.rect(), Qt.AlignCenter, f"WIN {self._value:.0f}%")
        painter.end()


class HeroSlotLabel(QLabel):
    def __init__(self, label: str = "", parent=None):
        super().__init__(parent)
        self._label = label
        self._hero_name = None
        self.setFixedHeight(22)
        self._update_text()

    def set_hero(self, hero_name: Optional[str]):
        self._hero_name = hero_name
        self._update_text()

    def _update_text(self):
        if self._hero_name:
            self.setText(f"  {self._label}: {self._hero_name}")
            self.setStyleSheet("color: #00FF41; background-color: rgba(0, 20, 0, 180); border: 1px solid #008F11; border-radius: 2px; font-family: Consolas; font-size: 11px; padding: 1px 4px;")
        else:
            self.setText(f"  {self._label}: ---")
            self.setStyleSheet("color: #335533; background-color: rgba(0, 10, 0, 120); border: 1px solid #1a3a1a; border-radius: 2px; font-family: Consolas; font-size: 11px; padding: 1px 4px;")


class RecommendationLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(20)

    def set_recommendation(self, hero: str, score: float, reason: str, role: str):
        self.setText(f"  > {hero} [{role}] ({score:.0f}pts) - {reason}")
        color = "#39FF14" if score >= 80 else ("#00FF41" if score >= 60 else "#008F11")
        self.setStyleSheet(f"color: {color}; background-color: rgba(0, 15, 0, 150); border: 1px solid #004400; border-radius: 2px; font-family: Consolas; font-size: 10px; padding: 1px 4px;")


class DraftOverlay(QWidget):
    signal_update = pyqtSignal(object)

    def __init__(self, config_path: str = "config.ini", parent=None):
        super().__init__(parent)
        self.config = configparser.ConfigParser()
        self.config.read(config_path, encoding="utf-8")
        self._overlay_width = self.config.getint("ui", "overlay_width", fallback=320)
        self._opacity = self.config.getfloat("ui", "opacity", fallback=0.85)
        self._position = self.config.get("ui", "overlay_position", fallback="right")
        self._paused = False
        self._dragging = False
        self._drag_offset = QPoint()
        self._minimized = False

        self._setup_window()
        self._build_ui()
        self.signal_update.connect(self._on_update)

    def _setup_window(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.NoFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedWidth(self._overlay_width)
        self.setMinimumHeight(100)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.setCursor(QCursor(Qt.OpenHandCursor)) # Kursor default tangan terbuka buat drag

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(3)

        title_bar = QHBoxLayout()
        self._header = QLabel("MLBB AI DRAFTER")
        self._header.setAlignment(Qt.AlignCenter)
        self._header.setStyleSheet("color: #00FF41; background-color: rgba(0, 20, 0, 200); border: 1px solid #00FF41; border-radius: 3px; font-family: Consolas; font-size: 14px; font-weight: bold; padding: 4px;")
        title_bar.addWidget(self._header, stretch=1)

        self._min_btn = QPushButton("\u2014")
        self._min_btn.setFixedSize(26, 26)
        self._min_btn.setStyleSheet("QPushButton {color: #00FF41; background-color: rgba(0, 20, 0, 200); border: 1px solid #008F11; border-radius: 3px; font-weight: bold;} QPushButton:hover {color: #39FF14; border: 1px solid #00FF41;}")
        self._min_btn.clicked.connect(self._toggle_minimize)
        title_bar.addWidget(self._min_btn)
        main_layout.addLayout(title_bar)

        self._content = QVBoxLayout()
        self._status_label = QLabel("STATUS: SCANNING")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet("color: #39FF14; background-color: rgba(0, 15, 0, 150); border: 1px solid #008F11; font-family: Consolas; font-size: 10px; padding: 2px;")
        self._content.addWidget(self._status_label)

        self._win_rate_bar = NeonProgressBar()
        self._content.addWidget(self._win_rate_bar)

        self._team_slots = [HeroSlotLabel(f"P{i+1}") for i in range(5)]
        for s in self._team_slots: self._content.addWidget(s)

        self._enemy_slots = [HeroSlotLabel(f"E{i+1}") for i in range(5)]
        for s in self._enemy_slots: self._content.addWidget(s)

        self._bans_label = QLabel("  None detected")
        self._bans_label.setStyleSheet("color: #997700; font-size: 9px;")
        self._content.addWidget(self._bans_label)

        self._rec_labels = [RecommendationLabel() for _ in range(5)]
        for r in self._rec_labels: self._content.addWidget(r)

        self._footer = QLabel("Alt+S:Pause  Alt+M:Min  F10:Reset")
        self._footer.setAlignment(Qt.AlignCenter)
        self._footer.setStyleSheet("color: #335533; font-size: 8px; border-top: 1px solid #1a3a1a;")
        self._content.addWidget(self._footer)
        main_layout.addLayout(self._content)

    # --- DRAG BEBAS DI MANA SAJA ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_offset = event.pos()
            self.setCursor(QCursor(Qt.ClosedHandCursor))

    def mouseMoveEvent(self, event):
        if self._dragging and (event.buttons() & Qt.LeftButton):
            self.move(self.pos() + event.pos() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self.setCursor(QCursor(Qt.OpenHandCursor))

    def mouseDoubleClickEvent(self, event):
        self._toggle_minimize()

    def _toggle_minimize(self):
        if self._minimized:
            self._minimized = False
            for i in range(self._content.count()):
                item = self._content.itemAt(i)
                if item.widget(): item.widget().show()
            self.setMinimumHeight(100)
            self._min_btn.setText("\u2014")
            self.adjustSize()
        else:
            self._minimized = True
            for i in range(self._content.count()):
                item = self._content.itemAt(i)
                if item.widget(): item.widget().hide()
            self.setFixedHeight(38)
            self._min_btn.setText("\u25A1")
            self.adjustSize()

    def update_analysis(self, analysis: DraftAnalysis, state: DraftState, scan_time: float):
        self.signal_update.emit((analysis, state, scan_time))

    def _on_update(self, data):
        analysis, state, scan_time = data
        self._win_rate_bar.value = analysis.win_rate
        for i, s in enumerate(self._team_slots): s.set_hero(state.picks_team[i] if i < len(state.picks_team) else None)
        for i, s in enumerate(self._enemy_slots): s.set_hero(state.picks_enemy[i] if i < len(state.picks_enemy) else None)
        bans = state.get_banned_heroes()
        self._bans_label.setText(f"  {', '.join(bans)}" if bans else "  None detected")
        for i, r in enumerate(self._rec_labels):
            if i < len(analysis.recommendations):
                rec = analysis.recommendations[i]
                r.set_recommendation(rec.hero, rec.score, rec.reason, rec.role)
            else:
                r.setText("  ---")
        if not self._minimized: self.adjustSize()

    def set_paused(self, paused: bool):
        self._paused = paused
        if paused:
            self._status_label.setText("STATUS: PAUSED")
            self._status_label.setStyleSheet("color: #FFB800; background-color: rgba(30, 20, 0, 150); border: 1px solid #FFB800; font-size: 10px; padding: 2px;")
        else:
            self._status_label.setText("STATUS: SCANNING")
            self._status_label.setStyleSheet("color: #39FF14; background-color: rgba(0, 15, 0, 150); border: 1px solid #008F11; font-size: 10px; padding: 2px;")

    def position_near_scrcpy(self, scrcpy_x: int, scrcpy_y: int, scrcpy_w: int, scrcpy_h: int, screen_geom):
        # Mencegah window keluar dari batas layar
        target_x = scrcpy_x + scrcpy_w + 5 if self._position == "right" else scrcpy_x - self._overlay_width - 5
        target_y = scrcpy_y

        max_x = screen_geom.width() - self.width()
        max_y = screen_geom.height() - self.height()

        # Clamp nilai X dan Y agar ga pernah off-screen
        target_x = max(0, min(target_x, max_x))
        target_y = max(0, min(target_y, max_y))

        self.move(target_x, target_y)

    def set_click_through(self, enabled: bool):
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.NoFocus
        if enabled: flags |= Qt.WindowTransparentForInput
        self.setWindowFlags(flags)
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(13, 13, 13, int(self._opacity * 255)))
        painter.setPen(QPen(QColor(0, 255, 65, 100), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.end()