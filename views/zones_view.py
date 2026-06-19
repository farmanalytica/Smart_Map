# -*- coding: utf-8 -*-
"""Management zones view."""

from qgis.PyQt import QtWidgets
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton, QComboBox, QTableWidget, QSpinBox

class ZonesView(QWidget):
    """Management zones clustering view."""

    def __init__(self, tr_func, parent=None):
        super().__init__(parent)
        self.tr = tr_func
        self._setup_ui()

    def _setup_ui(self):
        """Build zones view UI."""
        layout = QVBoxLayout()

        # Variable selection
        var_group = QGroupBox(self.tr('Selecionar Variáveis'))
        var_layout = QHBoxLayout()
        self.comboBox_ZM_Variables = QComboBox()
        var_layout.addWidget(self.comboBox_ZM_Variables)
        self.pushButton_ZM_Add_Var = QPushButton(self.tr('Adicionar'))
        var_layout.addWidget(self.pushButton_ZM_Add_Var)
        self.pushButton_ZM_Add_All_Vars = QPushButton(self.tr('Adicionar Todas'))
        var_layout.addWidget(self.pushButton_ZM_Add_All_Vars)
        self.comboBox_ZM_Variables_Remove = QComboBox()
        var_layout.addWidget(QLabel(self.tr('Remover:')))
        var_layout.addWidget(self.comboBox_ZM_Variables_Remove)
        self.pushButton_ZM_Remove_Var = QPushButton(self.tr('Remover'))
        var_layout.addWidget(self.pushButton_ZM_Remove_Var)
        var_layout.addStretch()
        var_group.setLayout(var_layout)
        layout.addWidget(var_group)

        # Selected variables table
        vars_group = QGroupBox(self.tr('Variáveis Selecionadas'))
        vars_layout = QVBoxLayout()
        self.datatable_ZM_Variables = QTableWidget()
        vars_layout.addWidget(self.datatable_ZM_Variables)
        vars_group.setLayout(vars_layout)
        layout.addWidget(vars_group)

        # Optimal zones calculation
        optimal_group = QGroupBox(self.tr('Calcular Número Ideal de Zonas'))
        optimal_layout = QHBoxLayout()
        self.pushButton_ZM_Calc_Nr_Ideal = QPushButton(self.tr('Calcular FPI/NCE'))
        optimal_layout.addWidget(self.pushButton_ZM_Calc_Nr_Ideal)
        optimal_layout.addStretch()
        optimal_group.setLayout(optimal_layout)
        layout.addWidget(optimal_group)

        # FPI/NCE results
        fpi_group = QGroupBox(self.tr('Resultados FPI/NCE'))
        fpi_layout = QVBoxLayout()
        self.datatable_ZM_FPI_NCE = QTableWidget()
        fpi_layout.addWidget(self.datatable_ZM_FPI_NCE)
        fpi_group.setLayout(fpi_layout)
        layout.addWidget(fpi_group)

        # Zone count selection
        count_group = QGroupBox(self.tr('Definir Número de Zonas'))
        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel(self.tr('Zonas:')))
        self.spinBox_ZM_NrZonas = QSpinBox()
        self.spinBox_ZM_NrZonas.setValue(2)
        self.spinBox_ZM_NrZonas.setMinimum(2)
        self.spinBox_ZM_NrZonas.setMaximum(20)
        count_layout.addWidget(self.spinBox_ZM_NrZonas)
        count_layout.addStretch()
        count_group.setLayout(count_layout)
        layout.addWidget(count_group)

        # Calculate zones button
        self.pushButton_ZM_Calcular = QPushButton(self.tr('Calcular Zonas de Manejo'))
        layout.addWidget(self.pushButton_ZM_Calcular)

        # Results tabs
        self.tabs_zones = QtWidgets.QTabWidget()

        # Centers tab
        centers_widget = QWidget()
        centers_layout = QVBoxLayout()
        self.datatable_ZM_Centros = QTableWidget()
        centers_layout.addWidget(self.datatable_ZM_Centros)
        centers_widget.setLayout(centers_layout)
        self.tabs_zones.addTab(centers_widget, self.tr('Centros das Zonas'))

        # Classes tab
        classes_widget = QWidget()
        classes_layout = QVBoxLayout()
        self.datatable_ZM_Class = QTableWidget()
        classes_layout.addWidget(self.datatable_ZM_Class)
        classes_widget.setLayout(classes_layout)
        self.tabs_zones.addTab(classes_widget, self.tr('Classificação das Zonas'))

        layout.addWidget(self.tabs_zones)

        # Zone map visualization
        self.label_ZM = QtWidgets.QLabel(self.tr('Mapa de Zonas...'))
        self.label_ZM.setMinimumHeight(200)
        layout.addWidget(self.label_ZM)

        self.setLayout(layout)
