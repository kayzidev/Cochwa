"""Identité Cochwa : tokens issus de PlancheGraphique.png."""

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

BG = "#11131A"
PANEL = "#191C26"
CARD = "#222633"
CARD_HOVER = "#292D40"
BORDER = "#34394B"
ACCENT = "#7567FF"
ACCENT_DARK = "#5145BF"
SECONDARY = "#FF7867"
SUCCESS = "#5EE6B1"
WARNING = "#FFBE55"
DANGER = "#FF5D70"
TEXT = "#F4F5FA"
MUTED = "#969BAD"
TOAST_KINDS = {"info": ACCENT, "success": SUCCESS, "error": DANGER}
ROW_TINTS = {
    "running": "#26223D",
    "completed": "#19352D",
    "failed": "#3B2330",
    "cancelled": "#252634",
    "paused": "#383025",
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
    return SUCCESS if score >= 85 else WARNING if score >= 70 else DANGER


def apply(app):
    for path in (Path(__file__).parent / "assets").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(path))
    families = QFontDatabase.families()
    family = next((f for f in ("Geist", "Inter", "Noto Sans") if f in families), "Sans Serif")
    app.setFont(QFont(family, 10))
    app.setStyleSheet(QSS)


ASSETS = (Path(__file__).parent / "assets").as_posix()

QSS = f"""
QMainWindow, QDialog, QWidget {{ background: {BG}; color: {TEXT}; font-size: 13px; }}
QWidget#sidepanel {{ background: {PANEL}; border-right: 1px solid #282C3B; }}
QLabel {{ background: transparent; border: none; }}
QLabel#brand {{ font-size: 25px; font-weight: 700; letter-spacing: -1px; }}
QLabel#eyebrow {{ color: #B4AAFF; font-size: 10px; font-weight: 600; letter-spacing: 2px; }}
QLabel#heading {{ font-size: 28px; font-weight: 700; letter-spacing: -1px; }}
QLabel#sectionTitle {{ font-size: 16px; font-weight: 600; }}
QLabel#muted, QLabel#cardMeta {{ color: {MUTED}; }}
QLabel#cardMeta {{ font-size: 11px; }}
QLabel#cardSize {{ color: {MUTED}; font-size: 11px; }}
QLabel#cardTitle {{ font-weight: 600; font-size: 13px; }}
QLabel#chip {{ border-radius: 6px; padding: 3px 6px; font-size: 10px; font-weight: 600; }}
QLabel#platformBadge {{ color: #C1B8FF; background: #2D274C; border-radius: 7px;
    padding: 6px 10px; font-size: 11px; font-weight: 600; }}
QLabel#empty {{ color: {MUTED}; font-size: 14px; padding: 28px; }}
QWidget#hero {{ border: 1px solid #443C6B; border-radius: 16px;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #302951,stop:0.6 #201E35,stop:1 #292234); }}
QWidget#hero QLabel {{ background: transparent; }}
QWidget#section {{ background: {PANEL}; border: 1px solid #2C3040; border-radius: 12px; }}
QWidget#section > QWidget {{ background: transparent; }}
QListWidget#sidebar {{ background: transparent; border: none; outline: 0; padding: 6px;
    font-size: 14px; }}
QListWidget#sidebar::item {{ padding: 10px 10px; margin: 2px 2px; border-radius: 9px;
    color: {MUTED}; }}
QListWidget#sidebar::item:selected {{ background: {ACCENT}; color: {TEXT}; }}
QListWidget#sidebar::item:hover:!selected {{ background: {CARD}; color: {TEXT}; }}
QWidget#card {{ background: {PANEL}; border: 1px solid #2C3040; border-radius: 12px; }}
QWidget#card[hover="true"] {{ background: {CARD}; border-color: {ACCENT}; }}
QPushButton {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 9px 13px; color: {TEXT}; font-weight: 500; }}
QPushButton:hover {{ background: {CARD_HOVER}; border-color: #706596; }}
QPushButton:pressed {{ background: {ACCENT_DARK}; }}
QPushButton:focus, QComboBox:focus, QToolButton:focus {{ border: 2px solid #BFB6FF; }}
QPushButton:disabled {{ background: {PANEL}; color: #666B80; border-color: #2B2F3E; }}
QPushButton#primary {{ background: {ACCENT}; color: {TEXT};
    border: 1px solid {ACCENT}; font-weight: 600; }}
QPushButton#cardBtn {{ background: {CARD}; color: #C7BEFF; border-color: #423B63; }}
QPushButton#primary:hover, QPushButton#cardBtn:hover {{ background: #887CFF; }}
QPushButton#primary:disabled {{ background: #36304E; border-color: #36304E; color: {MUTED}; }}
QPushButton#secondaryAction {{ background: transparent; padding: 5px; color: #BAB0FF;
    border: none; font-size: 11px; }}
QPushButton#danger {{ color: {DANGER}; }}
QPushButton#danger:disabled {{ color: #666B80; }}
QLineEdit, QPlainTextEdit, QListWidget#paths {{ background: {PANEL}; border: 1px solid {BORDER};
    border-radius: 8px; padding: 9px 10px; color: {TEXT}; selection-background-color: {ACCENT_DARK}; }}
QLineEdit:focus, QPlainTextEdit:focus {{ border-color: {ACCENT}; }}
QComboBox {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 8px 10px; color: {TEXT}; min-width: 70px; }}
QComboBox::down-arrow {{ image: url("{ASSETS}/chevron.svg"); width: 12px; height: 12px; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {CARD}; color: {TEXT};
    selection-background-color: {ACCENT_DARK}; padding: 5px; }}
QCheckBox {{ background: transparent; spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {BORDER};
    background: {PANEL}; border-radius: 4px; }}
QCheckBox::indicator:checked {{ image: url("{ASSETS}/check.svg"); background: {ACCENT}; border-color: #B4AAFF; }}
QCheckBox::indicator:focus {{ border: 2px solid #BFB6FF; }}
QScrollArea {{ border: none; background: transparent; }}
QStatusBar {{ background: {PANEL}; color: {MUTED}; font-size: 11px; border-top: 1px solid #282C3B; }}
QStatusBar::item {{ border: none; }}
QTableView {{ background: {PANEL}; border: 1px solid #2C3040; border-radius: 10px;
    gridline-color: #303445; selection-background-color: {ACCENT_DARK}; }}
QTableView::item {{ padding: 9px; }}
QHeaderView::section {{ background: {CARD}; color: #B8BDCC; border: none; padding: 12px 9px; }}
QProgressBar {{ background: {CARD}; border: none; border-radius: 6px; min-height: 16px;
    text-align: center; color: {TEXT}; font-size: 11px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 6px; }}
QScrollBar:vertical {{ background: {BG}; width: 8px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: {BG}; height: 8px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 4px; min-width: 32px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QFrame#toast {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#toastBar {{ border-radius: 3px; }}
QToolTip, QMenu {{ background: {CARD}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px; }}
QMenu::item {{ padding: 9px 18px; border-radius: 5px; }}
QMenu::item:selected {{ background: {ACCENT_DARK}; }}
"""
