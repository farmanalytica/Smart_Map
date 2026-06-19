# -*- coding: utf-8 -*-
"""Kriging interpolation view."""

from qgis.PyQt import QtWidgets, QtCore
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton, QTableWidget, QCheckBox, QSpinBox

from .styles import tune_layout

class KrigingView(QWidget):
    """Kriging interpolation and validation view."""

    def __init__(self, tr_func, parent=None):
        super().__init__(parent)
        self.tr = tr_func
        self._setup_ui()

    def _setup_ui(self):
        """Build kriging view UI."""
        layout = QVBoxLayout()
        tune_layout(layout)

        # Target variable label
        self.label_VTargetOK = QLabel(self.tr('Z: '))
        layout.addWidget(self.label_VTargetOK)

        # Parameters
        self.groupBox_Krigagem = QGroupBox(self.tr('Search Parameters'))
        params_group = self.groupBox_Krigagem
        params_layout = QHBoxLayout()
        params_layout.addWidget(QLabel(self.tr('Neighbors:')))
        self.lineEdit_OK_VBNumMax = QtWidgets.QLineEdit('16')
        params_layout.addWidget(self.lineEdit_OK_VBNumMax)
        params_layout.addWidget(QLabel(self.tr('Search Radius:')))
        self.lineEdit_OK_VBRaio = QtWidgets.QLineEdit('1000.0')
        params_layout.addWidget(self.lineEdit_OK_VBRaio)
        self.checkBox_Krigagem_Alcance = QCheckBox(self.tr('Use Range'))
        params_layout.addWidget(self.checkBox_Krigagem_Alcance)
        params_layout.addStretch()
        params_group.setLayout(params_layout)
        layout.addWidget(params_group)

        # Export options
        export_group = QGroupBox(self.tr('Export to QGIS'))
        export_layout = QHBoxLayout()
        self.checkBox_Qgis_Raster = QCheckBox(self.tr('Raster'))
        self.checkBox_Qgis_Raster.setChecked(True)
        export_layout.addWidget(self.checkBox_Qgis_Raster)
        self.checkBox_Qgis_Vector_Points = QCheckBox(self.tr('Points'))
        export_layout.addWidget(self.checkBox_Qgis_Vector_Points)
        self.checkBox_Qgis_Vector_Polygons = QCheckBox(self.tr('Polygons'))
        export_layout.addWidget(self.checkBox_Qgis_Vector_Polygons)
        self.checkBox_Krigagem_Std_Desv = QCheckBox(self.tr('Standard Deviation'))
        export_layout.addWidget(self.checkBox_Krigagem_Std_Desv)
        export_layout.addStretch()
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)

        # Buttons
        btn_layout = QHBoxLayout()
        self.pushButton_Krigagem = QPushButton(self.tr('Run Kriging'))
        self.pushButton_Krigagem.setObjectName('primaryButton')
        self.pushButton_Krigagem.setCursor(QtCore.Qt.PointingHandCursor)
        btn_layout.addWidget(self.pushButton_Krigagem)
        self.pushButton_Validacao_Cruzada_OK = QPushButton(self.tr('Cross-Validation'))
        btn_layout.addWidget(self.pushButton_Validacao_Cruzada_OK)
        self.pushButton_Krigagem_All_Variables = QPushButton(self.tr('Krige All Variables'))
        self.pushButton_Krigagem_All_Variables.setEnabled(False)
        btn_layout.addWidget(self.pushButton_Krigagem_All_Variables)
        # Show interpolated maps in a matplotlib window when checked.
        self.checkBox_Qgis_Maps = QCheckBox(self.tr('Show Maps'))
        btn_layout.addWidget(self.checkBox_Qgis_Maps)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Results tabs. Index order matches the legacy tabWidget_Interpolacao_OK:
        #   0 = variogram / kriging map, 1 = cross-validation, 2 = interpolated points.
        self.tabWidget_Interpolacao_OK = QtWidgets.QTabWidget()
        self.tabs_kriging = self.tabWidget_Interpolacao_OK  # backwards-compatible alias

        # Tab 0: kriging map visualization
        map_widget = QWidget()
        map_layout = QVBoxLayout()
        self.label_Krigagem = QtWidgets.QLabel(self.tr('Kriging Map...'))
        self.label_Krigagem.setMinimumHeight(200)
        map_layout.addWidget(self.label_Krigagem)
        map_widget.setLayout(map_layout)
        self.tabWidget_Interpolacao_OK.addTab(map_widget, self.tr('Interpolated Map'))

        # Tab 1: cross-validation
        cv_widget = QWidget()
        cv_layout = QVBoxLayout()
        self.datatable_validacao_cruzada_OK = QTableWidget()
        cv_layout.addWidget(self.datatable_validacao_cruzada_OK)
        self.label_validacao_cruzada_OK = QtWidgets.QLabel(self.tr('CV Plot...'))
        self.label_validacao_cruzada_OK.setMinimumHeight(200)
        cv_layout.addWidget(self.label_validacao_cruzada_OK)
        cv_widget.setLayout(cv_layout)
        self.tabWidget_Interpolacao_OK.addTab(cv_widget, self.tr('Cross-Validation'))

        # Tab 2: interpolated points
        points_widget = QWidget()
        points_layout = QVBoxLayout()
        self.datatable_pontos_interpolados_OK = QTableWidget()
        points_layout.addWidget(self.datatable_pontos_interpolados_OK)
        points_widget.setLayout(points_layout)
        self.tabWidget_Interpolacao_OK.addTab(points_widget, self.tr('Interpolated Points'))

        layout.addWidget(self.tabWidget_Interpolacao_OK)

        self.setLayout(layout)
