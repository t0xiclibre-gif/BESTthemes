"""Feuille de style de l'application (clair/sombre, couleur d'accent)."""
from bestthemes.core import colors as C

LIGHT = {"bg": "#f3f3f3", "side": "#ebebeb", "card": "#fbfbfb", "card_hover": "#ffffff",
         "border": "#e0e0e0", "fg": "#1b1b1b", "fg2": "#5f5f5f", "input": "#ffffff",
         "pill": "#e6e6e6"}
DARK = {"bg": "#202020", "side": "#1a1a1a", "card": "#2b2b2b", "card_hover": "#323232",
        "border": "#3a3a3a", "fg": "#f3f3f3", "fg2": "#a8a8a8", "input": "#2d2d2d",
        "pill": "#3a3a3a"}


def stylesheet(dark, accent="#0078d4"):
    c = DARK if dark else LIGHT
    acc_fg = C.readable_on(accent)
    acc_hover = C.shade(accent, 0.1)
    acc_soft = C.mix(c["card"], accent, 0.18)
    return f"""
* {{ font-family: "Segoe UI Variable Text", "Segoe UI", "Ubuntu", sans-serif; font-size: 10pt; color: {c['fg']}; }}
QMainWindow, QWidget#root {{ background: {c['bg']}; }}
QWidget[cls="page"] {{ background: {c['bg']}; }}
QScrollArea {{ background: {c['bg']}; border: none; }}
QScrollArea > QWidget > QWidget {{ background: {c['bg']}; }}
QWidget#sidebar {{ background: {c['side']}; }}
QLabel[cls="logo"] {{ font-size: 19pt; font-weight: 800; color: {accent}; }}
QLabel[cls="title"] {{ font-size: 22pt; font-weight: 700; }}
QLabel[cls="subtitle"] {{ color: {c['fg2']}; font-size: 10.5pt; }}
QLabel[cls="section"] {{ font-size: 13pt; font-weight: 700; margin-top: 8px; }}
QLabel[cls="card-title"] {{ font-weight: 700; font-size: 10.5pt; }}
QLabel[cls="card-sub"], QLabel[cls="hint"] {{ color: {c['fg2']}; font-size: 9pt; }}
QLabel[cls="pill"] {{ background: {c['pill']}; border-radius: 9px; padding: 2px 9px; font-size: 8.5pt; }}
QLabel[cls="badge"] {{ background: {accent}; color: {acc_fg}; border-radius: 9px; padding: 2px 9px; font-size: 8.5pt; font-weight: 700; }}
QLabel[cls="dim"] {{ color: {c['fg2']}; font-size: 8.5pt; }}
QFrame[cls="card"] {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; }}
QFrame[cls="card"]:hover {{ background: {c['card_hover']}; border-color: {C.mix(c['border'], accent, 0.5)}; }}
QFrame[cls="card"][active="true"] {{ border: 2px solid {accent}; background: {acc_soft}; }}
QFrame[cls="box"] {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; }}
QFrame[cls="info"] {{ background: {acc_soft}; border-radius: 12px; }}
QFrame[cls="hero"] {{ border-radius: 16px; background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {accent}, stop:1 {C.darken(accent, 0.45)}); }}
QFrame[cls="hero"] QLabel {{ color: #ffffff; }}
QFrame[cls="hero"] QPushButton {{ background: rgba(255,255,255,0.2); color: #ffffff; border: none; border-radius: 16px; padding: 7px 16px; font-weight: 700; }}
QFrame[cls="hero"] QPushButton:hover {{ background: rgba(255,255,255,0.32); }}
QListWidget#nav {{ background: transparent; border: none; outline: 0; }}
QListWidget#nav::item {{ padding: 9px 12px; margin: 2px 8px; border-radius: 8px; }}
QListWidget#nav::item:hover {{ background: {C.mix(c['side'], c['fg'], 0.06)}; }}
QListWidget#nav::item:selected {{ background: {accent}; color: {acc_fg}; }}
QPushButton {{ background: {c['input']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 6px 14px; }}
QPushButton:hover {{ background: {c['card_hover']}; border-color: {C.mix(c['border'], c['fg'], 0.2)}; }}
QPushButton:disabled {{ color: {c['fg2']}; }}
QPushButton[kind="primary"] {{ background: {accent}; color: {acc_fg}; border: 1px solid {accent}; font-weight: 600; }}
QPushButton[kind="primary"]:hover {{ background: {acc_hover}; }}
QPushButton[kind="flat"] {{ background: transparent; border: none; }}
QPushButton[kind="flat"]:hover {{ background: {c['pill']}; }}
QPushButton[kind="tab"] {{ border-radius: 15px; padding: 6px 16px; }}
QPushButton[kind="tab"]:checked {{ background: {accent}; color: {acc_fg}; border-color: {accent}; }}
QLineEdit, QComboBox, QSpinBox {{ background: {c['input']}; border: 1px solid {c['border']}; border-bottom: 2px solid {C.mix(c['border'], c['fg'], 0.25)}; border-radius: 6px; padding: 5px 8px; }}
QLineEdit:focus, QComboBox:focus {{ border-bottom: 2px solid {accent}; }}
QComboBox QAbstractItemView {{ background: {c['card']}; selection-background-color: {accent}; selection-color: {acc_fg}; }}
QCheckBox::indicator {{ width: 18px; height: 18px; }}
QSlider::groove:horizontal {{ height: 4px; background: {c['pill']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {accent}; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; border: 3px solid {c['card']}; }}
QProgressBar {{ background: {c['pill']}; border: none; border-radius: 3px; height: 6px; text-align: center; font-size: 8pt; }}
QProgressBar::chunk {{ background: {accent}; border-radius: 3px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {C.mix(c['bg'], c['fg'], 0.25)}; border-radius: 4px; min-height: 30px; margin: 2px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QFrame#toast {{ background: rgba(32,32,36,0.97); border-radius: 18px; }}
QFrame#toast QLabel {{ color: #ffffff; font-weight: 600; }}
QFrame#toast QPushButton {{ background: transparent; border: none; color: #8cc8ff; font-weight: 700; }}
QToolTip {{ background: {c['card']}; color: {c['fg']}; border: 1px solid {c['border']}; padding: 4px; }}
"""
