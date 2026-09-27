"""Palette et feuille de style QSS — transposition directe du thème Tkinter."""

BG = "#171a21"
PANEL = "#1e2530"
CARD = "#242c38"
CARD_HOVER = "#2b3543"
BORDER = "#39424f"
ACCENT = "#66c0f4"
ACCENT_DARK = "#3d6e96"
SUCCESS = "#6cbd91"
WARNING = "#d8b356"
DANGER = "#d4655f"
TEXT = "#e8eaed"
MUTED = "#9aa5b1"

TOAST_KINDS = {"info": ACCENT, "success": SUCCESS, "error": DANGER}

ROW_TINTS = {
    "running": "#1f2d3a",
    "completed": "#1f3128",
    "failed": "#372225",
    "cancelled": "#2a2530",
    "paused": "#2e2a20",
}

STATE_LABELS = {
    "queued": "En attente",
    "running": "En cours",
    "paused": "En pause",
    "cancelled": "Annulé",
    "failed": "Échec",
    "completed": "Terminé",
}


def score_color(score):
    if score >= 85:
        return SUCCESS
    if score >= 70:
        return WARNING
    return DANGER


QSS = f"""
QMainWindow, QWidget {{ background: {BG}; color: {TEXT}; font-size: 13px; }}
QListWidget#sidebar {{ background: {PANEL}; border: none; outline: 0; font-size: 14px; }}
QListWidget#sidebar::item {{ padding: 13px 16px; color: {MUTED};
                             border-left: 3px solid transparent; }}
QListWidget#sidebar::item:selected {{ background: {CARD}; color: {ACCENT};
                                      border-left: 3px solid {ACCENT}; }}
QListWidget#sidebar::item:hover:!selected {{ color: {TEXT}; background: #212833; }}
QWidget#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}
QWidget#card[hover="true"] {{ border: 1px solid {ACCENT}; background: {CARD_HOVER}; }}
QLabel {{ background: transparent; border: none; }}
QLabel#cardTitle {{ font-weight: bold; font-size: 13px; }}
QLabel#cardMeta {{ color: {MUTED}; font-size: 11px; }}
QLabel#cardSize {{ color: {MUTED}; font-size: 10px; }}
QLabel#chip {{ border-radius: 8px; padding: 1px 7px; font-size: 10px; font-weight: bold; }}
QLabel#heading {{ font-size: 20px; font-weight: bold; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#empty {{ color: {MUTED}; font-size: 14px; }}
QPushButton#cardBtn {{ background: #31435a; border: none; border-radius: 7px;
                       padding: 7px; font-weight: bold; color: {TEXT}; }}
QPushButton#cardBtn:hover {{ background: {ACCENT}; color: #10212e; }}
QPushButton#cardBtn:pressed {{ background: {ACCENT_DARK}; }}
QPushButton {{ background: #2c3542; border: none; border-radius: 6px;
               padding: 7px 12px; color: {TEXT}; }}
QPushButton:hover {{ background: {ACCENT_DARK}; }}
QPushButton:disabled {{ background: {PANEL}; color: {MUTED}; }}
QPushButton#primary {{ background: {ACCENT}; color: #10212e; font-weight: bold; }}
QPushButton#primary:hover {{ background: #8bd0f7; }}
QLineEdit {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 6px;
             padding: 6px; color: {TEXT}; selection-background-color: {ACCENT_DARK}; }}
QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
QComboBox {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 6px;
             padding: 5px 8px; color: {TEXT}; }}
QComboBox QAbstractItemView {{ background: {PANEL}; color: {TEXT};
                               selection-background-color: {ACCENT_DARK}; }}
QCheckBox {{ color: {TEXT}; }}
QScrollArea {{ border: none; }}
QStatusBar {{ background: {PANEL}; color: {MUTED}; }}
QTableView {{ background: {PANEL}; gridline-color: {BORDER}; border: none;
              selection-background-color: {ACCENT_DARK}; }}
QTableView::item {{ padding: 4px; }}
QHeaderView::section {{ background: {BG}; color: {MUTED}; border: none;
                        padding: 6px; }}
QProgressBar {{ background: {PANEL}; border: none; border-radius: 5px;
                height: 10px; text-align: center; color: {MUTED}; }}
QProgressBar::chunk {{ background: {SUCCESS}; border-radius: 5px; }}
QScrollBar:vertical {{ background: {BG}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: {BG}; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QDialog {{ background: {BG}; }}
QListWidget#paths {{ background: {PANEL}; border: 1px solid {BORDER};
                     border-radius: 6px; }}
QFrame#toast {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; }}
QFrame#toastBar {{ border-radius: 3px; }}
QToolTip {{ background: {PANEL}; color: {TEXT}; border: 1px solid {BORDER}; }}
"""
