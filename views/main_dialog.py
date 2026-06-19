# -*- coding: utf-8 -*-
"""Main dialog with tabbed interface."""

from qgis.PyQt import QtCore, QtWidgets, QtGui
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QLabel,
    QScrollArea
)
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QIcon

from .data_view import DataView
from .variogram_view import VariogramView
from .kriging_view import KrigingView
from .svm_view import SVMView
from .zones_view import ZonesView
from .styles import apply_theme, HEADER_TITLE, HEADER_SUBTITLE


class SmartMapDialog(QDialog):
    """Main Smart-Map plugin dialog with tabbed interface."""

    # Signals
    closed = pyqtSignal()

    def __init__(self, iface, plugin_dir, icon_path, tr_func, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.plugin_dir = plugin_dir
        self.icon_path = icon_path
        self.tr = tr_func

        # Store references to child views
        self.data_view = None
        self.variogram_view = None
        self.kriging_view = None
        self.svm_view = None
        self.zones_view = None

        # Setup UI
        self.setWindowTitle('Smart-Map - Kriging Interpolation and Machine Learning')
        self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(1000, 700)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowMinimizeButtonHint)

        self._setup_ui()

    def _setup_ui(self):
        """Build main dialog UI with tabs."""
        # Global theme (cards, green primary, rounded inputs, styled tabs).
        apply_theme(self)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # Header: stacked title + subtitle on the left, About on the right.
        title_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(0)

        title_label = QLabel('Smart-Map')
        title_label.setObjectName(HEADER_TITLE)
        title_box.addWidget(title_label)

        subtitle_label = QLabel(self.tr('Kriging Interpolation and Machine Learning'))
        subtitle_label.setObjectName(HEADER_SUBTITLE)
        title_box.addWidget(subtitle_label)

        title_layout.addLayout(title_box)
        title_layout.addStretch()

        # About control (handler wired by the UI controller). Language is
        # auto-detected from the QGIS locale; no manual language switcher.
        self.label_About = QLabel('ⓘ')
        self.label_About.setToolTip(self.tr('About'))
        self.label_About.setCursor(QtCore.Qt.PointingHandCursor)
        about_font = self.label_About.font()
        about_font.setPointSize(16)
        self.label_About.setFont(about_font)
        self.label_About.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignRight)
        title_layout.addWidget(self.label_About)

        layout.addLayout(title_layout)

        # Tabs. Each view is wrapped in a scroll area so tall content (params +
        # result tables + plot panels) never gets squished / clipped on smaller
        # windows — it scrolls instead.
        self.tabs = QTabWidget()

        self.data_view = DataView(self.iface, self.plugin_dir, self.icon_path, self.tr)
        self.tabs.addTab(self._scrollable(self.data_view), self.tr('Data'))

        self.variogram_view = VariogramView(self.tr)
        self.tabs.addTab(self._scrollable(self.variogram_view), self.tr('Variogram'))

        self.kriging_view = KrigingView(self.tr)
        self.tabs.addTab(self._scrollable(self.kriging_view), self.tr('Kriging'))

        self.svm_view = SVMView(self.tr)
        self.tabs.addTab(self._scrollable(self.svm_view), self.tr('SVM'))

        self.zones_view = ZonesView(self.tr)
        self.tabs.addTab(self._scrollable(self.zones_view), self.tr('Management Zones'))

        layout.addWidget(self.tabs)

        # Button bar
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton(self.tr('Close'))
        close_btn.setMinimumWidth(110)
        close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close_dialog)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _scrollable(self, view):
        """Wrap a view in a vertically-scrolling, width-resizing scroll area."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setWidget(view)
        return scroll

    def close_dialog(self):
        """Close dialog cleanly."""
        self.closed.emit()
        self.accept()

    def closeEvent(self, event):
        """Handle window close."""
        self.closed.emit()
        event.accept()

    def get_data_view(self):
        """Get data view for controller wiring."""
        return self.data_view

    def get_variogram_view(self):
        """Get variogram view for controller wiring."""
        return self.variogram_view

    def get_kriging_view(self):
        """Get kriging view for controller wiring."""
        return self.kriging_view

    def get_svm_view(self):
        """Get SVM view for controller wiring."""
        return self.svm_view

    def get_zones_view(self):
        """Get zones view for controller wiring."""
        return self.zones_view
