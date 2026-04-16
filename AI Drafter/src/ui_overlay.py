"""
UI Overlay - Transparent always-on-top draft analysis display.
Futuristic hacker/terminal theme with neon green accents.
Borderless window with click-through capability, drag, and minimize.
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
    """Custom progress bar with neon glow for win rate display."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 50.0
        self.setFixedHeight(24)
        self.setMinimumWidth(200)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = max(0.0, min(100.0, v))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

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

        pen = QPen(QColor(0, 255, 65), 1)
        painter.setPen(pen)
        painter.drawRect(0, 0, w - 1, h - 1)

        painter.setPen(QColor(255, 255, 255))
        font = QFont(FONT_FAMILY, 9, QFont.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, f"WIN {self._value:.0f}%")
        painter.end()


class HeroSlotLabel(QLabel):
    """A single hero slot display."""

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
            self.setStyleSheet(
                "color: #00FF41; background-color: rgba(0, 20, 0, 180); "
                "border: 1px solid #008F11; border-radius: 2px; "
                "font-family: Consolas; font-size: 11px; padding: 1px 4px;"
            )
        else:
            self.setText(f"  {self._label}: ---")
            self.setStyleSheet(
                "color: #335533; background-color: rgba(0, 10, 0, 120); "
                "border: 1px solid #1a3a1a; border-radius: 2px; "
                "font-family: Consolas; font-size: 11px; padding: 1px 4px;"
            )


class RecommendationLabel(QLabel):
    """A recommendation entry with score and reason."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(20)
        self.setWordWrap(False)

    def set_recommendation(self, hero: str, score: float, reason: str, role: str):
        self.setText(f"  > {hero} [{role}] ({score:.0f}pts) - {reason}")
        if score >= 80:
            color = "#39FF14"
        elif score >= 60:
            color = "#00FF41"
        else:
            color = "#008F11"
        self.setStyleSheet(
            f"color: {color}; background-color: rgba(0, 15, 0, 150); "
            f"border: 1px solid #004400; border-radius: 2px; "
            f"font-family: Consolas; font-size: 10px; padding: 1px 4px;"
        )


class DraftOverlay(QWidget):
    """
    Transparent borderless overlay window for draft analysis.
    Always-on-top with click-through capability.
    Supports dragging by header and minimize to a small floating bar.
    """

    signal_update = pyqtSignal(object)

    def __init__(self, config_path: str = "config.ini", parent=None):
        super().__init__(parent)

        self.config = configparser.ConfigParser()
        self.config.read(config_path, encoding="utf-8")

        self._overlay_width = self.config.getint("ui", "overlay_width", fallback=320)
        self._opacity = self.config.getfloat("ui", "opacity", fallback=0.85)
        self._position = self.config.get("ui", "overlay_position", fallback="right")

        self._color_primary = hex_to_qcolor(
            self.config.get("ui", "color_primary", fallback="#00FF41")
        )
        self._color_bg = hex_to_qcolor(
            self.config.get("ui", "color_bg", fallback="#0D0D0D")
        )

        self._paused = False
        self._scan_time = 0.0

        # Drag state
        self._dragging = False
        self._drag_offset = QPoint()

        # Minimize state
        self._minimized = False
        self._normal_geometry = None

        self._setup_window()
        self._build_ui()
        self.signal_update.connect(self._on_update)

        logger.info("DraftOverlay initialized")

    def _setup_window(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedWidth(self._overlay_width)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(3)

        # === Title bar with drag handle + minimize button ===
        title_bar = QHBoxLayout()
        title_bar.setSpacing(4)

        self._header = QLabel("MLBB AI DRAFTER")
        self._header.setAlignment(Qt.AlignCenter)
        self._header.setStyleSheet(
            "color: #00FF41; background-color: rgba(0, 20, 0, 200); "
            "border: 1px solid #00FF41; border-radius: 3px; "
            "font-family: Consolas; font-size: 14px; font-weight: bold; "
            "padding: 4px; letter-spacing: 3px;"
        )
        self._header.setCursor(QCursor(Qt.OpenHandCursor))
        title_bar.addWidget(self._header, stretch=1)

        # Minimize button
        self._min_btn = QPushButton("\u2014")
        self._min_btn.setFixedSize(26, 26)
        self._min_btn.setToolTip("Minimize overlay")
        self._min_btn.setStyleSheet(
            "QPushButton {"
            "  color: #00FF41; background-color: rgba(0, 20, 0, 200);"
            "  border: 1px solid #008F11; border-radius: 3px;"
            "  font-family: Consolas; font-size: 14px; font-weight: bold;"
            "}"
            "QPushButton:hover {"
            "  color: #39FF14; background-color: rgba(0, 60, 0, 220);"
            "  border: 1px solid #00FF41;"
            "}"
            "QPushButton:pressed {"
            "  background-color: rgba(0, 80, 0, 255);"
            "}"
        )
        self._min_btn.clicked.connect(self._toggle_minimize)
        title_bar.addWidget(self._min_btn)

        main_layout.addLayout(title_bar)

        # === Content container (hides on minimize) ===
        self._content = QVBoxLayout()
        self._content.setSpacing(3)

        # Status
        self._status_label = QLabel("STATUS: SCANNING")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(
            "color: #39FF14; background-color: rgba(0, 15, 0, 150); "
            "border: 1px solid #008F11; border-radius: 2px; "
            "font-family: Consolas; font-size: 10px; padding: 2px;"
        )
        self._content.addWidget(self._status_label)

        # Win Rate
        wr_header = QLabel("WIN PROBABILITY")
        wr_header.setAlignment(Qt.AlignCenter)
        wr_header.setStyleSheet(
            "color: #008F11; font-family: Consolas; font-size: 9px; "
            "border-bottom: 1px solid #008F11; padding: 2px;"
        )
        self._content.addWidget(wr_header)
        self._win_rate_bar = NeonProgressBar()
        self._content.addWidget(self._win_rate_bar)

        # Team Picks
        team_header = QLabel("ALLY PICKS")
        team_header.setAlignment(Qt.AlignCenter)
        team_header.setStyleSheet(
            "color: #00FF41; font-family: Consolas; font-size: 10px; "
            "font-weight: bold; border-bottom: 1px solid #008F11; padding: 2px;"
        )
        self._content.addWidget(team_header)
        self._team_slots = []
        for i in range(5):
            slot = HeroSlotLabel(f"P{i+1}")
            self._content.addWidget(slot)
            self._team_slots.append(slot)

        # Enemy Picks
        enemy_header = QLabel("ENEMY PICKS")
        enemy_header.setAlignment(Qt.AlignCenter)
        enemy_header.setStyleSheet(
            "color: #FF0040; font-family: Consolas; font-size: 10px; "
            "font-weight: bold; border-bottom: 1px solid #660018; padding: 2px;"
        )
        self._content.addWidget(enemy_header)
        self._enemy_slots = []
        for i in range(5):
            slot = HeroSlotLabel(f"E{i+1}")
            self._content.addWidget(slot)
            self._enemy_slots.append(slot)

        # Bans
        bans_header = QLabel("BANS")
        bans_header.setAlignment(Qt.AlignCenter)
        bans_header.setStyleSheet(
            "color: #FFB800; font-family: Consolas; font-size: 9px; "
            "border-bottom: 1px solid #665500; padding: 2px;"
        )
        self._content.addWidget(bans_header)
        self._bans_label = QLabel("  None detected")
        self._bans_label.setStyleSheet(
            "color: #997700; font-family: Consolas; font-size: 9px; padding: 1px 4px;"
        )
        self._bans_label.setWordWrap(True)
        self._content.addWidget(self._bans_label)

        # Counter Analysis
        counter_header = QLabel("COUNTER ANALYSIS")
        counter_header.setAlignment(Qt.AlignCenter)
        counter_header.setStyleSheet(
            "color: #008F11; font-family: Consolas; font-size: 9px; "
            "border-bottom: 1px solid #004400; padding: 2px;"
        )
        self._content.addWidget(counter_header)
        self._counter_adv_label = QLabel("  Advantages: ---")
        self._counter_adv_label.setStyleSheet(
            "color: #00FF41; font-family: Consolas; font-size: 9px; padding: 1px 4px;"
        )
        self._counter_adv_label.setWordWrap(True)
        self._content.addWidget(self._counter_adv_label)
        self._counter_dis_label = QLabel("  Disadvantages: ---")
        self._counter_dis_label.setStyleSheet(
            "color: #FF0040; font-family: Consolas; font-size: 9px; padding: 1px 4px;"
        )
        self._counter_dis_label.setWordWrap(True)
        self._content.addWidget(self._counter_dis_label)

        # Recommendations
        rec_header = QLabel("RECOMMENDATIONS")
        rec_header.setAlignment(Qt.AlignCenter)
        rec_header.setStyleSheet(
            "color: #39FF14; font-family: Consolas; font-size: 10px; "
            "font-weight: bold; border-bottom: 1px solid #00FF41; padding: 2px;"
        )
        self._content.addWidget(rec_header)
        self._rec_labels = []
        for i in range(5):
            rec = RecommendationLabel()
            self._content.addWidget(rec)
            self._rec_labels.append(rec)

        # Missing Roles
        self._roles_label = QLabel("  Missing roles: ---")
        self._roles_label.setStyleSheet(
            "color: #FFB800; font-family: Consolas; font-size: 9px; padding: 1px 4px;"
        )
        self._roles_label.setWordWrap(True)
        self._content.addWidget(self._roles_label)

        # Footer
        self._footer = QLabel("F9:Pause  F10:Reset  F12:Quit")
        self._footer.setAlignment(Qt.AlignCenter)
        self._footer.setStyleSheet(
            "color: #335533; font-family: Consolas; font-size: 8px; "
            "border-top: 1px solid #1a3a1a; padding: 3px;"
        )
        self._content.addWidget(self._footer)

        main_layout.addLayout(self._content)

    # ------------------------------------------------------------------
    # Drag support - drag from the header/title bar area
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        """Start dragging when left-clicking on the header area."""
        if event.button() == Qt.LeftButton and event.y() < 40:
            self._dragging = True
            self._drag_offset = event.pos()
            self._header.setCursor(QCursor(Qt.ClosedHandCursor))

    def mouseMoveEvent(self, event):
        """Move the window while dragging."""
        if self._dragging and (event.buttons() & Qt.LeftButton):
            delta = event.pos() - self._drag_offset
            self.move(self.pos() + delta)

    def mouseReleaseEvent(self, event):
        """Stop dragging."""
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self._header.setCursor(QCursor(Qt.OpenHandCursor))

    def mouseDoubleClickEvent(self, event):
        """Double-click header to toggle minimize."""
        if event.y() < 40:
            self._toggle_minimize()

    # ------------------------------------------------------------------
    # Minimize / Restore
    # ------------------------------------------------------------------

    def _toggle_minimize(self):
        if self._minimized:
            self._restore()
        else:
            self._minimize()

    def _minimize(self):
        """Minimize to a small floating bar showing only the title."""
        self._minimized = True
        self._normal_geometry = self.geometry()

        # Hide all content widgets
        for i in range(self._content.count()):
            item = self._content.itemAt(i)
            if item.widget():
                item.widget().hide()
            elif item.layout():
                for j in range(item.count()):
                    sub = item.itemAt(j)
                    if sub and sub.widget():
                        sub.widget().hide()

        self.setFixedHeight(38)
        self._min_btn.setText("\u25A1")
        self._min_btn.setToolTip("Restore overlay")
        self.adjustSize()
        logger.info("Overlay minimized")

    def _restore(self):
        """Restore from minimized state."""
        self._minimized = False

        # Show all content widgets
        for i in range(self._content.count()):
            item = self._content.itemAt(i)
            if item.widget():
                item.widget().show()
            elif item.layout():
                for j in range(item.count()):
                    sub = item.itemAt(j)
                    if sub and sub.widget():
                        sub.widget().show()

        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        self._min_btn.setText("\u2014")
        self._min_btn.setToolTip("Minimize overlay")
        self.adjustSize()
        logger.info("Overlay restored")

    # ------------------------------------------------------------------
    # Analysis update
    # ------------------------------------------------------------------

    def update_analysis(self, analysis: DraftAnalysis, state: DraftState, scan_time: float = 0.0):
        self.signal_update.emit((analysis, state, scan_time))

    def _on_update(self, data):
        analysis, state, scan_time = data
        self._apply_update(analysis, state, scan_time)

    def _apply_update(self, analysis: DraftAnalysis, state: DraftState, scan_time: float):
        self._scan_time = scan_time

        # Win rate
        self._win_rate_bar.value = analysis.win_rate

        # Team picks
        for i, slot in enumerate(self._team_slots):
            if i < len(state.picks_team):
                slot.set_hero(state.picks_team[i])
            else:
                slot.set_hero(None)

        # Enemy picks
        for i, slot in enumerate(self._enemy_slots):
            if i < len(state.picks_enemy):
                slot.set_hero(state.picks_enemy[i])
            else:
                slot.set_hero(None)

        # Bans
        all_bans = state.get_banned_heroes()
        if all_bans:
            self._bans_label.setText(f"  {', '.join(all_bans)}")
            self._bans_label.setStyleSheet(
                "color: #FFB800; font-family: Consolas; font-size: 9px; padding: 1px 4px;"
            )
        else:
            self._bans_label.setText("  None detected")
            self._bans_label.setStyleSheet(
                "color: #665500; font-family: Consolas; font-size: 9px; padding: 1px 4px;"
            )

        # Counter advantages
        if analysis.team_counter_advantages:
            adv_text = " | ".join(analysis.team_counter_advantages)
            self._counter_adv_label.setText(f"  + {adv_text}")
        else:
            self._counter_adv_label.setText("  Advantages: ---")

        # Counter disadvantages
        if analysis.team_counter_disadvantages:
            dis_text = " | ".join(analysis.team_counter_disadvantages)
            self._counter_dis_label.setText(f"  - {dis_text}")
        else:
            self._counter_dis_label.setText("  Disadvantages: ---")

        # Recommendations
        for i, rec_label in enumerate(self._rec_labels):
            if i < len(analysis.recommendations):
                rec = analysis.recommendations[i]
                rec_label.set_recommendation(rec.hero, rec.score, rec.reason, rec.role)
            else:
                rec_label.setText("  ---")
                rec_label.setStyleSheet(
                    "color: #335533; font-family: Consolas; font-size: 10px; padding: 1px 4px;"
                )

        # Missing roles
        if analysis.team_roles_missing:
            self._roles_label.setText(f"  Need: {', '.join(analysis.team_roles_missing)}")
        else:
            self._roles_label.setText("  Roles: Complete!")

        if not self._minimized:
            self.adjustSize()

    def set_paused(self, paused: bool):
        self._paused = paused
        if paused:
            self._status_label.setText("STATUS: PAUSED")
            self._status_label.setStyleSheet(
                "color: #FFB800; background-color: rgba(30, 20, 0, 150); "
                "border: 1px solid #FFB800; border-radius: 2px; "
                "font-family: Consolas; font-size: 10px; padding: 2px;"
            )
        else:
            self._status_label.setText("STATUS: SCANNING")
            self._status_label.setStyleSheet(
                "color: #39FF14; background-color: rgba(0, 15, 0, 150); "
                "border: 1px solid #008F11; border-radius: 2px; "
                "font-family: Consolas; font-size: 10px; padding: 2px;"
            )

    def position_near_scrcpy(self, scrcpy_x: int, scrcpy_y: int, scrcpy_w: int, scrcpy_h: int):
        if self._position == "right":
            self.move(scrcpy_x + scrcpy_w + 5, scrcpy_y)
        else:
            self.move(scrcpy_x - self._overlay_width - 5, scrcpy_y)

    def set_click_through(self, enabled: bool):
        if enabled:
            self.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool |
                Qt.WindowTransparentForInput
            )
        else:
            self.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool
            )
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        bg_color = QColor(13, 13, 13, int(self._opacity * 255))
        painter.fillRect(self.rect(), bg_color)

        pen = QPen(QColor(0, 255, 65, 100), 1)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        pen = QPen(QColor(0, 143, 17, 30), 1, Qt.DotLine)
        painter.setPen(pen)
        for y in range(0, self.height(), 20):
            painter.drawLine(0, y, self.width(), y)

        painter.end()