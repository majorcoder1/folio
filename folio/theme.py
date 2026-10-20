"""A dark theme in the style of professional design apps."""

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QStyleFactory

WINDOW = "#2d2d2d"
PANEL = "#2f2f2f"
BASE = "#1f1f1f"
TEXT = "#e6e6e6"
MUTED = "#9a9a9a"
ACCENT = "#4a8fe7"
FONT_POINTS = 8.5      # the same small, tidy text pro design apps use

STYLESHEET = f"""
QMainWindow, QDialog {{ background: {WINDOW}; }}
QToolTip {{ color: {TEXT}; background: #3a3a3a; border: 1px solid #555555; padding: 3px; }}
QToolBar {{ background: {WINDOW}; border: none; spacing: 1px; padding: 2px; }}
QToolBar::separator {{ background: #454545; width: 1px; height: 1px; margin: 3px; }}
QToolButton {{ border: 1px solid transparent; border-radius: 3px; padding: 2px; color: {TEXT}; }}
QToolButton:hover {{ background: #3c3c3c; border-color: #4a4a4a; }}
QToolButton:checked {{ background: #1f1f1f; border-color: #454545; }}
QToolButton:pressed {{ background: #262626; }}
QDockWidget {{ color: {TEXT}; titlebar-close-icon: none; }}
QDockWidget::title {{ background: #262626; padding: 3px 6px; }}
QTabBar::tab {{ background: #262626; color: {MUTED}; padding: 4px 8px; border: none; }}
QTabBar::tab:selected {{ background: {PANEL}; color: {TEXT}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}
QGroupBox {{ border: 1px solid #3f3f3f; border-radius: 4px; margin-top: 11px; padding: 6px 4px 4px 4px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 6px; padding: 0 3px; color: {MUTED}; }}
QLabel#hint {{ color: {MUTED}; }}
QLabel#warn {{ color: #ffb74d; }}
QStatusBar {{ background: #262626; color: {MUTED}; }}
QStatusBar QLabel {{ color: {MUTED}; padding: 0 6px; }}
QTreeWidget, QListWidget {{ background: #2a2a2a; border: 1px solid #383838; border-radius: 2px; }}
QTreeWidget::item, QListWidget::item {{ padding: 2px 1px; }}
QTreeWidget::item:selected, QListWidget::item:selected {{ background: #3d5f8f; color: white; }}
QScrollArea {{ border: none; background: {PANEL}; }}
QScrollArea > QWidget > QWidget {{ background: {PANEL}; }}
QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit, QFontComboBox {{
    background: {BASE}; border: 1px solid #3c3c3c; border-radius: 2px; padding: 1px 4px; color: {TEXT};
}}
QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus {{ border-color: {ACCENT}; }}
QComboBox:disabled, QDoubleSpinBox:disabled, QSpinBox:disabled, QLineEdit:disabled,
QPushButton:disabled, QToolButton:disabled, QCheckBox:disabled, QLabel:disabled {{ color: #636363; }}
QPushButton {{ background: #3a3a3a; border: 1px solid #4a4a4a; border-radius: 2px; padding: 3px 10px; color: {TEXT}; }}
QPushButton:hover {{ background: #444444; }}
QPushButton:default {{ background: #3a3a3a; border-color: #5a5a5a; }}
QPushButton:checked {{ background: #1f1f1f; border-color: {ACCENT}; }}
QSlider::groove:horizontal {{ height: 3px; background: #4a4a4a; border-radius: 1px; }}
QSlider::handle:horizontal {{ background: #e6e6e6; width: 11px; margin: -5px 0; border-radius: 5px; }}
QMenu {{ background: #2b2b2b; border: 1px solid #454545; padding: 2px; }}
QMenu::item {{ padding: 4px 26px 4px 20px; border-radius: 2px; }}
QMenu::item:selected {{ background: #3d5f8f; }}
QMenu::item:disabled {{ color: #636363; }}
QMenu::separator {{ height: 1px; background: #454545; margin: 3px 6px; }}
QMenuBar {{ background: #262626; }}
QMenuBar::item {{ padding: 3px 7px; }}
QMenuBar::item:selected {{ background: #3c3c3c; }}
QCheckBox {{ spacing: 4px; }}
QListWidget#brushList {{ background: #2a2a2a; border: none; }}
QListWidget#brushList::item {{ padding: 0; }}

/* the start window (New Document) */
QWidget#startSidebar {{ background: #232326; border-right: 1px solid #1a1a1c; }}
QToolButton#sideButton {{ color: {MUTED}; border-radius: 4px; padding: 3px; }}
QToolButton#sideButton:hover {{ background: #303035; color: {TEXT}; border-color: transparent; }}
QToolButton#sideButton:checked {{ background: #3a3a40; color: {TEXT}; border-color: transparent; }}
QWidget#presetColumn {{ background: #2a2a2d; border-right: 1px solid #1d1d20; }}
QListWidget#presetList {{ background: #2a2a2d; border: none; }}
QListWidget#presetList::item, QListWidget#presetList::item:selected {{ background: transparent; padding: 0; }}
QWidget#previewArea {{ background: #303034; }}
QLabel#startTitle {{ color: #c8cad0; font-size: 15pt; }}
QWidget#detailsPane {{ background: #2b2b2e; border-top: 1px solid #1d1d20; }}
QWidget#summaryPane {{ background: #2b2b2e; border-left: 1px solid #1d1d20; }}
QLabel#summaryTitle {{ color: #c8cad0; padding: 10px; border-bottom: 1px solid #1d1d20; }}
QLabel#summaryText {{ color: {TEXT}; }}
QTabWidget#detailTabs::pane {{ border: none; background: #2b2b2e; }}
QTabWidget#detailTabs::tab-bar {{ alignment: center; }}
QLabel#contextLabel {{ font-weight: bold; padding: 0 8px; }}
QWidget#startBar {{ background: #26262a; border-top: 1px solid #1d1d20; }}
QListWidget#thumbGrid {{ background: #2a2a2d; border: none; }}
QListWidget#thumbGrid::item {{ color: {TEXT}; padding: 6px; border-radius: 6px; }}
QListWidget#thumbGrid::item:selected {{ background: #41618f; }}
"""


def apply(app):
    app.setStyle(QStyleFactory.create("Fusion"))
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(WINDOW))
    pal.setColor(QPalette.WindowText, QColor(TEXT))
    pal.setColor(QPalette.Base, QColor(BASE))
    pal.setColor(QPalette.AlternateBase, QColor(PANEL))
    pal.setColor(QPalette.ToolTipBase, QColor("#3a3a3f"))
    pal.setColor(QPalette.ToolTipText, QColor(TEXT))
    pal.setColor(QPalette.Text, QColor(TEXT))
    pal.setColor(QPalette.Button, QColor("#3b3b41"))
    pal.setColor(QPalette.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.BrightText, QColor("#ff6b6b"))
    pal.setColor(QPalette.Link, QColor(ACCENT))
    pal.setColor(QPalette.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.PlaceholderText, QColor(MUTED))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor("#6b6f76"))
    app.setPalette(pal)
    font = app.font()
    font.setPointSizeF(FONT_POINTS)
    app.setFont(font)
    app.setStyleSheet(STYLESHEET)
