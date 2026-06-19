# -*- coding: utf-8 -*-
"""Variogram and semivariogram view."""

from qgis.PyQt import QtWidgets, QtCore
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton, QComboBox, QDoubleSpinBox, QCheckBox, QTableWidget, QSlider

class VariogramView(QWidget):
    """Variogram management and tuning view."""

    def __init__(self, tr_func, parent=None):
        super().__init__(parent)
        self.tr = tr_func
        self._setup_ui()

    def _setup_ui(self):
        """Build variogram view UI."""
        layout = QVBoxLayout()

        # Model selection
        self.groupBox_Variograma_Model = QGroupBox(self.tr('Modelo de Variograma'))
        model_group = self.groupBox_Variograma_Model
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel(self.tr('Modelo:')))
        self.comboBox_Modelo = QComboBox()
        self.comboBox_Modelo.addItems(['Linear', 'Linear-Sill', 'Exponential', 'Spherical', 'Gaussian'])
        model_layout.addWidget(self.comboBox_Modelo)
        self.checkBox_Variogram_Variancia = QCheckBox(self.tr('Variância Amostral'))
        model_layout.addWidget(self.checkBox_Variogram_Variancia)
        model_layout.addStretch()
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        # Parameters
        params_group = QGroupBox(self.tr('Parâmetros'))
        params_layout = QVBoxLayout()

        # Nugget
        nug_layout = QHBoxLayout()
        nug_layout.addWidget(QLabel(self.tr('Nugget (C₀):')))
        self.lineEdit_Nugget = QtWidgets.QLineEdit('0.0')
        nug_layout.addWidget(self.lineEdit_Nugget)
        self.horizontalSlider_Nugget = QSlider(QtCore.Qt.Horizontal)
        nug_layout.addWidget(self.horizontalSlider_Nugget)
        params_layout.addLayout(nug_layout)

        # Sill
        sill_layout = QHBoxLayout()
        sill_layout.addWidget(QLabel(self.tr('Sill (C₀+C):')))
        self.lineEdit_Sill = QtWidgets.QLineEdit('1.0')
        sill_layout.addWidget(self.lineEdit_Sill)
        self.horizontalSlider_Sill = QSlider(QtCore.Qt.Horizontal)
        sill_layout.addWidget(self.horizontalSlider_Sill)
        params_layout.addLayout(sill_layout)

        # Range
        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel(self.tr('Alcance (A):')))
        self.lineEdit_Range = QtWidgets.QLineEdit('100.0')
        range_layout.addWidget(self.lineEdit_Range)
        self.horizontalSlider_Range = QSlider(QtCore.Qt.Horizontal)
        range_layout.addWidget(self.horizontalSlider_Range)
        params_layout.addLayout(range_layout)

        params_group.setLayout(params_layout)
        layout.addWidget(params_group)

        # Grid parameters
        grid_group = QGroupBox(self.tr('Parâmetros do Grid'))
        grid_layout = QHBoxLayout()
        grid_layout.addWidget(QLabel(self.tr('DMax:')))
        self.lineEdit_OK_DMax = QtWidgets.QLineEdit('1000.0')
        grid_layout.addWidget(self.lineEdit_OK_DMax)
        grid_layout.addWidget(QLabel(self.tr('Lag Dist:')))
        self.lineEdit_OK_lags_dist = QtWidgets.QLineEdit('10.0')
        grid_layout.addWidget(self.lineEdit_OK_lags_dist)
        grid_group.setLayout(grid_layout)
        layout.addWidget(grid_group)

        # Statistics
        stats_group = QGroupBox(self.tr('Qualidade do Ajuste'))
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel(self.tr('RMSE:')))
        self.lineEdit_Var_RMSE = QtWidgets.QLineEdit('0.0')
        self.lineEdit_Var_RMSE.setReadOnly(True)
        stats_layout.addWidget(self.lineEdit_Var_RMSE)
        stats_layout.addWidget(QLabel(self.tr('R²:')))
        self.lineEdit_Var_R2 = QtWidgets.QLineEdit('0.0')
        self.lineEdit_Var_R2.setReadOnly(True)
        stats_layout.addWidget(self.lineEdit_Var_R2)
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Buttons
        btn_layout = QHBoxLayout()
        self.pushButton_VariogramaReset = QPushButton(self.tr('Reset'))
        btn_layout.addWidget(self.pushButton_VariogramaReset)
        self.pushButton_VariogramaAjust = QPushButton(self.tr('Ajustar'))
        btn_layout.addWidget(self.pushButton_VariogramaAjust)
        self.pushButton_VariogramaSave = QPushButton(self.tr('Salvar'))
        btn_layout.addWidget(self.pushButton_VariogramaSave)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Variogram plot
        self.label_Variograma = QtWidgets.QLabel(self.tr('Variograma...'))
        self.label_Variograma.setMinimumHeight(250)
        layout.addWidget(self.label_Variograma)

        # Saved semivariograms table (one row per target variable). Column 0 is a
        # checkbox used to mark variables for batch kriging; columns 1..11 hold the
        # saved parameters. Reloaded from 0_Semivariograms_<layer>.csv.
        semiv_group = QGroupBox(self.tr('Semivariogramas Salvos'))
        semiv_layout = QVBoxLayout()
        self.datatable_semivariogramas = QTableWidget()
        self.datatable_semivariogramas.setMinimumHeight(150)
        semiv_layout.addWidget(self.datatable_semivariogramas)
        semiv_group.setLayout(semiv_layout)
        layout.addWidget(semiv_group)

        self.setLayout(layout)
