# -*- coding: utf-8 -*-
"""Shared UI theme for Smart-Map views.

A single global stylesheet (applied to the main dialog) gives every tab a
consistent visual language inspired by farm_tools: light background, white
rounded "card" group boxes, a green primary action colour, rounded inputs with
a green focus ring, and styled tabs / tables / scrollbars. No sidebar — the
tabbed layout is kept.

Usage:
    from .styles import apply_theme, PRIMARY_BUTTON
    apply_theme(dialog)            # global stylesheet
    btn.setObjectName('primaryButton')   # opt-in green emphasis for main actions
"""

# --- Palette ---------------------------------------------------------------
BG          = '#f1f3f2'
SURFACE     = '#ffffff'
TEXT        = '#1f2421'
MUTED       = '#5f6b64'
FAINT       = '#9aa6a0'
PRIMARY     = '#1b6b39'
PRIMARY_HV  = '#1e7d42'
PRIMARY_PR  = '#155a2f'
BORDER      = '#dfe5e2'
FOCUS       = '#1b6b39'
SEL_BG      = '#e8f5e9'


# Object name for opt-in primary (green, filled) action buttons.
PRIMARY_BUTTON = 'primaryButton'
# Object names for the branded header labels.
HEADER_TITLE = 'headerTitle'
HEADER_SUBTITLE = 'headerSubtitle'


GLOBAL_QSS = """
QDialog, QWidget {{
    background-color: {bg};
    color: {text};
    font-size: 12px;
}}

/* ---- Group boxes rendered as cards ---- */
QGroupBox {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 10px;
    margin-top: 28px;
    padding: 18px 14px 14px 14px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    margin-top: 4px;
    padding: 0 6px;
    color: {primary};
}}

/* ---- Tabs ---- */
QTabWidget::pane {{
    border: 1px solid {border};
    border-radius: 10px;
    top: -1px;
    background: {surface};
}}
QTabWidget::tab-bar {{
    left: 4px;
}}
QTabBar {{
    qproperty-drawBase: 0;
}}
QTabBar::tab {{
    background: transparent;
    color: {muted};
    padding: 7px 18px;
    margin-right: 3px;
    min-height: 22px;
    border: 1px solid transparent;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: bold;
}}
QTabBar::tab:selected {{
    background: {surface};
    color: {primary};
    border: 1px solid {border};
    border-bottom-color: {surface};
}}
QTabBar::tab:hover:!selected {{
    color: {primary};
}}

/* ---- Buttons (default = secondary/outlined) ---- */
QPushButton {{
    background-color: {surface};
    color: {primary};
    border: 1px solid {border};
    border-radius: 7px;
    padding: 6px 14px;
    min-height: 22px;
    font-weight: bold;
}}
QPushButton:hover  {{ background-color: {sel}; border-color: #8db99c; }}
QPushButton:pressed {{ background-color: #d7eadb; }}
QPushButton:disabled {{ background-color: #eeeeee; color: {faint}; border-color: {border}; }}

/* ---- Primary action buttons (opt-in via objectName) ---- */
QPushButton#{primary_btn} {{
    background-color: {primary};
    color: #ffffff;
    border: none;
    padding: 8px 18px;
    border-radius: 8px;
    font-weight: bold;
}}
QPushButton#{primary_btn}:hover  {{ background-color: {primary_hv}; }}
QPushButton#{primary_btn}:pressed {{ background-color: {primary_pr}; }}
QPushButton#{primary_btn}:disabled {{ background-color: #bdbdbd; color: #f5f5f5; }}

/* ---- Text inputs ---- */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 22px;
    selection-background-color: {sel};
    selection-color: {text};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1.5px solid {focus}; }}
QLineEdit:read-only {{ background-color: #f4f6f5; color: {muted}; }}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 16px; }}

/* ---- Combo boxes (incl. QGIS layer combos) ---- */
QComboBox, QgsMapLayerComboBox {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 22px;
}}
QComboBox:focus, QgsMapLayerComboBox:focus {{ border: 1.5px solid {focus}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ width: 10px; height: 10px; }}
QComboBox QAbstractItemView {{
    background-color: {surface};
    color: {text};
    border: 1px solid #bdbdbd;
    selection-background-color: {sel};
    selection-color: {text};
    outline: 0;
}}

/* ---- Checkboxes ---- */
QCheckBox {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{ width: 15px; height: 15px; }}
QCheckBox::indicator:unchecked {{
    background-color: {surface};
    border: 1.5px solid {faint};
    border-radius: 3px;
}}
QCheckBox::indicator:unchecked:hover {{ border-color: {primary}; }}
QCheckBox::indicator:checked {{
    background-color: {primary};
    border: 1.5px solid {primary};
    border-radius: 3px;
}}

/* ---- Tables ---- */
QTableWidget, QTableView {{
    background-color: {surface};
    alternate-background-color: #f6f8f7;
    border: 1px solid {border};
    border-radius: 8px;
    gridline-color: #eceeed;
    selection-background-color: {sel};
    selection-color: {text};
}}
QHeaderView::section {{
    background-color: #eef2f0;
    color: {muted};
    border: none;
    border-right: 1px solid {border};
    border-bottom: 1px solid {border};
    padding: 6px 8px;
    font-weight: bold;
}}
QTableCornerButton::section {{ background-color: #eef2f0; border: none; }}

/* ---- Sliders ---- */
QSlider::groove:horizontal {{ height: 4px; background: {border}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {primary}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {primary};
    width: 14px; height: 14px;
    margin: -6px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{ background: {primary_hv}; }}

/* ---- Scrollbars ---- */
QScrollBar:vertical {{ background: {bg}; width: 11px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #c2ccc7; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: #a7b3ad; }}
QScrollBar:horizontal {{ background: {bg}; height: 11px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: #c2ccc7; border-radius: 5px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}

/* ---- Header labels ---- */
QLabel#{header_title} {{ color: {text}; font-size: 18px; font-weight: bold; }}
QLabel#{header_subtitle} {{ color: {muted}; font-size: 12px; }}

/* ---- Tooltips ---- */
QToolTip {{
    background-color: {surface};
    color: {text};
    border: 1px solid #c8d8ce;
    padding: 4px 6px;
}}
""".format(
    bg=BG, surface=SURFACE, text=TEXT, muted=MUTED, faint=FAINT,
    primary=PRIMARY, primary_hv=PRIMARY_HV, primary_pr=PRIMARY_PR,
    border=BORDER, focus=FOCUS, sel=SEL_BG,
    primary_btn=PRIMARY_BUTTON, header_title=HEADER_TITLE,
    header_subtitle=HEADER_SUBTITLE,
)


def apply_theme(widget):
    """Apply the global Smart-Map stylesheet to a top-level widget."""
    widget.setStyleSheet(GLOBAL_QSS)


def tune_layout(layout, margin=12, spacing=10):
    """Apply consistent margins + spacing to a view's main layout."""
    layout.setContentsMargins(margin, margin, margin, margin)
    layout.setSpacing(spacing)


def mark_primary(button):
    """Tag a button for the green, filled primary-action style."""
    button.setObjectName(PRIMARY_BUTTON)
