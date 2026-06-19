# -*- coding: utf-8 -*-
"""Kriging interpolation view."""

from qgis.PyQt import QtWidgets
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton, QTableWidget, QCheckBox, QSpinBox

class KrigingView(QWidget):
    """Kriging interpolation and validation view."""

    def __init__(self, tr_func, parent=None):
        super().__init__(parent)
        self.tr = tr_func
        self._setup_ui()

    def _setup_ui(self):
        """Build kriging view UI."""
        layout = QVBoxLayout()

        # Parameters
        params_group = QGroupBox(self.tr('Parâmetros de Busca'))
        params_layout = QHBoxLayout()
        params_layout.addWidget(QLabel(self.tr('Nº Vizinhos:')))
        self.lineEdit_OK_VBNumMax = QtWidgets.QLineEdit('16')
        params_layout.addWidget(self.lineEdit_OK_VBNumMax)
        params_layout.addWidget(QLabel(self.tr('Raio de Busca:')))
        self.lineEdit_OK_VBRaio = QtWidgets.QLineEdit('1000.0')
        params_layout.addWidget(self.lineEdit_OK_VBRaio)
        self.checkBox_Krigagem_Alcance = QCheckBox(self.tr('Usar Alcance'))
        params_layout.addWidget(self.checkBox_Krigagem_Alcance)
        params_layout.addStretch()
        params_group.setLayout(params_layout)
        layout.addWidget(params_group)

        # Export options
        export_group = QGroupBox(self.tr('Exportar para QGIS'))
        export_layout = QHBoxLayout()
        self.checkBox_Qgis_Raster = QCheckBox(self.tr('Raster'))
        self.checkBox_Qgis_Raster.setChecked(True)
        export_layout.addWidget(self.checkBox_Qgis_Raster)
        self.checkBox_Qgis_Vector_Points = QCheckBox(self.tr('Pontos'))
        export_layout.addWidget(self.checkBox_Qgis_Vector_Points)
        self.checkBox_Qgis_Vector_Polygons = QCheckBox(self.tr('Polígonos'))
        export_layout.addWidget(self.checkBox_Qgis_Vector_Polygons)
        self.checkBox_Krigagem_Std_Desv = QCheckBox(self.tr('Desvio Padrão'))
        export_layout.addWidget(self.checkBox_Krigagem_Std_Desv)
        export_layout.addStretch()
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)

        # Buttons
        btn_layout = QHBoxLayout()
        self.pushButton_Krigagem = QPushButton(self.tr('Executar Kriging'))
        btn_layout.addWidget(self.pushButton_Krigagem)
        self.pushButton_Validacao_Cruzada_OK = QPushButton(self.tr('Validação Cruzada'))
        btn_layout.addWidget(self.pushButton_Validacao_Cruzada_OK)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Results tabs
        self.tabs_kriging = QtWidgets.QTabWidget()

        # Interpolated points tab
        points_widget = QWidget()
        points_layout = QVBoxLayout()
        self.datatable_pontos_interpolados_OK = QTableWidget()
        points_layout.addWidget(self.datatable_pontos_interpolados_OK)
        points_widget.setLayout(points_layout)
        self.tabs_kriging.addTab(points_widget, self.tr('Pontos Interpolados'))

        # Cross-validation tab
        cv_widget = QWidget()
        cv_layout = QVBoxLayout()
        self.datatable_validacao_cruzada_OK = QTableWidget()
        cv_layout.addWidget(self.datatable_validacao_cruzada_OK)
        cv_widget.setLayout(cv_layout)
        self.tabs_kriging.addTab(cv_widget, self.tr('Validação Cruzada'))

        layout.addWidget(self.tabs_kriging)

        # Map visualization
        self.label_Krigagem = QtWidgets.QLabel(self.tr('Mapa de Kriging...'))
        self.label_Krigagem.setMinimumHeight(200)
        layout.addWidget(self.label_Krigagem)

        self.label_validacao_cruzada_OK = QtWidgets.QLabel(self.tr('Gráfico CV...'))
        self.label_validacao_cruzada_OK.setMinimumHeight(200)
        layout.addWidget(self.label_validacao_cruzada_OK)

        self.setLayout(layout)
