# -*- coding: utf-8 -*-
"""Main dialog with tabbed interface."""

from qgis.PyQt import QtCore, QtWidgets, QtGui
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QLabel
)
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QIcon

from .data_view import DataView


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
        self.setWindowTitle('Smart-Map - Interpolação de Kriging e Machine Learning')
        self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(1000, 700)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowMinimizeButtonHint)

        self._setup_ui()

    def _setup_ui(self):
        """Build main dialog UI with tabs."""
        layout = QVBoxLayout()

        # Title bar
        title_layout = QHBoxLayout()
        title_label = QLabel('Smart-Map Plugin')
        title_font = title_label.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        layout.addLayout(title_layout)

        # Tabs
        self.tabs = QTabWidget()

        # Data tab
        self.data_view = DataView(self.iface, self.plugin_dir, self.icon_path, self.tr)
        self.tabs.addTab(self.data_view, self.tr('Dados'))

        # Variogram tab (stub)
        var_stub = self._create_stub_tab(self.tr('Variograma'))
        self.tabs.addTab(var_stub, self.tr('Variograma'))

        # Kriging tab (stub)
        krig_stub = self._create_stub_tab(self.tr('Kriging'))
        self.tabs.addTab(krig_stub, self.tr('Kriging'))

        # SVM tab (stub)
        svm_stub = self._create_stub_tab(self.tr('SVM'))
        self.tabs.addTab(svm_stub, self.tr('SVM'))

        # Zones tab (stub)
        zones_stub = self._create_stub_tab(self.tr('Zonas de Manejo'))
        self.tabs.addTab(zones_stub, self.tr('Zonas de Manejo'))

        layout.addWidget(self.tabs)

        # Button bar
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        help_btn = QPushButton(self.tr('Ajuda'))
        help_btn.setMaximumWidth(100)
        button_layout.addWidget(help_btn)

        close_btn = QPushButton(self.tr('Fechar'))
        close_btn.setMaximumWidth(100)
        close_btn.clicked.connect(self.close_dialog)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _create_stub_tab(self, title):
        """Create placeholder tab."""
        widget = QtWidgets.QWidget()
        layout = QVBoxLayout()
        label = QLabel(f'{title} - Em desenvolvimento')
        label.setAlignment(Qt.AlignCenter)
        layout.addStretch()
        layout.addWidget(label)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

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
