# -*- coding: utf-8 -*-
"""Management zones view.

Rebuilt to expose the widgets the ORIGINAL file-driven zones workflow needs
(ported from the monolithic ``smart_map`` class in Smart_Map.py):

  - datatable_ZM_Maps        : 5-col table of available interpolated maps
                               (checkbox / Z / method / points / file)
  - pushButton_ZM_Add_All_Vars_Selected : add every selected map at once
  - tabWidget_ZM             : Maps | Vars | FPI/NCE | Class tabs
  - comboBox_ZM_var          : added variables (for removal)
  - datatable_ZM             : variable values table (one col per added var)
  - datatable_ZM_Classe      : CoordX_SM / CoordY_SM / Classe result table
  - spinBox_ZM_Iter          : fuzzy c-means max iterations (user-set)
  - doubleSpinBox_ZM_CFuzzy  : fuzzy coefficient m (user-set)
  - spinBox_ZM_NrZonas       : number of zones
  - lineEdit_ZM_FPI / NCE    : FPI / NCE values for the chosen number of zones
  - checkBox_ZM_Normalizar   : normalise variables before clustering
  - checkBox_Qgis_Maps       : show matplotlib windows (zones-local copy)
  - label_ZM_FPI_NCE         : FPI/NCE plot preview (click to open full image)
  - label_ZM                 : class map preview (click to open full image)
  - groupBox_* / pushButton_*: enable/disable gating used by the controller
"""

from qgis.PyQt import QtCore, QtWidgets
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QComboBox, QTableWidget, QSpinBox, QDoubleSpinBox, QLineEdit, QCheckBox,
    QTabWidget,
)

from .styles import tune_layout


class ZonesView(QWidget):
    """Management zones clustering view (file-driven workflow)."""

    def __init__(self, tr_func, parent=None):
        super().__init__(parent)
        self.tr = tr_func
        self._setup_ui()

    def _setup_ui(self):
        """Build zones view UI."""
        layout = QVBoxLayout()
        tune_layout(layout)

        # The whole zones workflow lives inside a tab widget so the controller
        # can drive the user through Maps -> Vars -> FPI/NCE -> Class.
        self.tabWidget_ZM = QTabWidget()

        # ---------------------------------------------------------- Tab 0: Maps
        maps_widget = QWidget()
        maps_layout = QVBoxLayout()

        maps_group = QGroupBox(self.tr('Available Interpolated Maps'))
        maps_group_layout = QVBoxLayout()
        self.datatable_ZM_Maps = QTableWidget()
        maps_group_layout.addWidget(self.datatable_ZM_Maps)
        self.pushButton_ZM_Add_All_Vars_Selected = QPushButton(
            self.tr('Add All Selected Variables'))
        self.pushButton_ZM_Add_All_Vars_Selected.setEnabled(False)
        maps_group_layout.addWidget(self.pushButton_ZM_Add_All_Vars_Selected)
        maps_group.setLayout(maps_group_layout)
        maps_layout.addWidget(maps_group)

        # Add a single variable from a file via QFileDialog.
        add_group = QGroupBox(self.tr('Add Variable (File)'))
        add_layout = QHBoxLayout()
        self.pushButton_ZM_Add_Var = QPushButton(self.tr('Add Variable...'))
        add_layout.addWidget(self.pushButton_ZM_Add_Var)
        add_layout.addStretch()
        add_group.setLayout(add_layout)
        maps_layout.addWidget(add_group)

        maps_widget.setLayout(maps_layout)
        self.tabWidget_ZM.addTab(maps_widget, self.tr('Maps'))

        # ---------------------------------------------------------- Tab 1: Vars
        vars_widget = QWidget()
        vars_layout = QVBoxLayout()

        self.groupBox_ZM_Remove_Var = QGroupBox(self.tr('Remove Variable'))
        remove_layout = QHBoxLayout()
        remove_layout.addWidget(QLabel(self.tr('Variable:')))
        self.comboBox_ZM_var = QComboBox()
        remove_layout.addWidget(self.comboBox_ZM_var)
        self.pushButton_ZM_Remove_Var = QPushButton(self.tr('Remove'))
        remove_layout.addWidget(self.pushButton_ZM_Remove_Var)
        remove_layout.addStretch()
        self.groupBox_ZM_Remove_Var.setLayout(remove_layout)
        self.groupBox_ZM_Remove_Var.setEnabled(False)
        self.pushButton_ZM_Remove_Var.setEnabled(False)
        vars_layout.addWidget(self.groupBox_ZM_Remove_Var)

        vars_group = QGroupBox(self.tr('Variables for Management Zones'))
        vars_group_layout = QVBoxLayout()
        self.datatable_ZM = QTableWidget()
        vars_group_layout.addWidget(self.datatable_ZM)
        vars_group.setLayout(vars_group_layout)
        vars_layout.addWidget(vars_group)

        vars_widget.setLayout(vars_layout)
        self.tabWidget_ZM.addTab(vars_widget, self.tr('Variables'))

        # ------------------------------------------------------ Tab 2: FPI/NCE
        fpi_widget = QWidget()
        fpi_layout = QVBoxLayout()

        # Fuzzy c-means parameters (user-set; NOT hardcoded in the manager).
        self.groupBox_ZM_Calc_Nr_Ideal_ZM = QGroupBox(
            self.tr('Compute Optimal Number of Zones (FPI / NCE)'))
        params_layout = QHBoxLayout()

        params_layout.addWidget(QLabel(self.tr('Iterations:')))
        self.spinBox_ZM_Iter = QSpinBox()
        self.spinBox_ZM_Iter.setMinimum(1)
        self.spinBox_ZM_Iter.setMaximum(10000)
        self.spinBox_ZM_Iter.setValue(100)
        params_layout.addWidget(self.spinBox_ZM_Iter)

        params_layout.addWidget(QLabel(self.tr('Fuzziness Coef. (m):')))
        self.doubleSpinBox_ZM_CFuzzy = QDoubleSpinBox()
        self.doubleSpinBox_ZM_CFuzzy.setMinimum(1.01)
        self.doubleSpinBox_ZM_CFuzzy.setMaximum(10.0)
        self.doubleSpinBox_ZM_CFuzzy.setSingleStep(0.05)
        self.doubleSpinBox_ZM_CFuzzy.setValue(1.30)
        params_layout.addWidget(self.doubleSpinBox_ZM_CFuzzy)

        self.checkBox_ZM_Normalizar = QCheckBox(self.tr('Normalize'))
        self.checkBox_ZM_Normalizar.setChecked(True)
        params_layout.addWidget(self.checkBox_ZM_Normalizar)

        self.checkBox_Qgis_Maps = QCheckBox(self.tr('Show Maps'))
        params_layout.addWidget(self.checkBox_Qgis_Maps)

        self.pushButton_ZM_Calc_Nr_Ideal_ZM = QPushButton(self.tr('Compute FPI/NCE'))
        params_layout.addWidget(self.pushButton_ZM_Calc_Nr_Ideal_ZM)
        params_layout.addStretch()
        self.groupBox_ZM_Calc_Nr_Ideal_ZM.setLayout(params_layout)
        self.groupBox_ZM_Calc_Nr_Ideal_ZM.setEnabled(False)
        self.pushButton_ZM_Calc_Nr_Ideal_ZM.setEnabled(False)
        fpi_layout.addWidget(self.groupBox_ZM_Calc_Nr_Ideal_ZM)

        # Number of zones + FPI/NCE readouts.
        count_group = QGroupBox(self.tr('Number of Zones'))
        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel(self.tr('Zones:')))
        self.spinBox_ZM_NrZonas = QSpinBox()
        self.spinBox_ZM_NrZonas.setMinimum(2)
        self.spinBox_ZM_NrZonas.setMaximum(20)
        self.spinBox_ZM_NrZonas.setValue(2)
        count_layout.addWidget(self.spinBox_ZM_NrZonas)
        count_layout.addWidget(QLabel('FPI:'))
        self.lineEdit_ZM_FPI = QLineEdit()
        self.lineEdit_ZM_FPI.setReadOnly(True)
        self.lineEdit_ZM_FPI.setMaximumWidth(100)
        count_layout.addWidget(self.lineEdit_ZM_FPI)
        count_layout.addWidget(QLabel('NCE:'))
        self.lineEdit_ZM_NCE = QLineEdit()
        self.lineEdit_ZM_NCE.setReadOnly(True)
        self.lineEdit_ZM_NCE.setMaximumWidth(100)
        count_layout.addWidget(self.lineEdit_ZM_NCE)
        count_layout.addStretch()
        count_group.setLayout(count_layout)
        fpi_layout.addWidget(count_group)

        # FPI/NCE plot preview.
        self.label_ZM_FPI_NCE = QLabel(self.tr('FPI / NCE Plot...'))
        self.label_ZM_FPI_NCE.setMinimumHeight(200)
        self.label_ZM_FPI_NCE.hide()
        fpi_layout.addWidget(self.label_ZM_FPI_NCE)

        fpi_widget.setLayout(fpi_layout)
        self.tabWidget_ZM.addTab(fpi_widget, self.tr('FPI / NCE'))

        # -------------------------------------------------------- Tab 3: Class
        class_widget = QWidget()
        class_layout = QVBoxLayout()

        self.groupBox_ZM_Calcular = QGroupBox(self.tr('Generate Management Zones'))
        calc_layout = QHBoxLayout()
        self.pushButton_ZM_Calcular = QPushButton(self.tr('Compute Management Zones'))
        self.pushButton_ZM_Calcular.setObjectName('primaryButton')
        self.pushButton_ZM_Calcular.setCursor(QtCore.Qt.PointingHandCursor)
        calc_layout.addWidget(self.pushButton_ZM_Calcular)
        calc_layout.addStretch()
        self.groupBox_ZM_Calcular.setLayout(calc_layout)
        self.groupBox_ZM_Calcular.setEnabled(False)
        self.pushButton_ZM_Calcular.setEnabled(False)
        class_layout.addWidget(self.groupBox_ZM_Calcular)

        result_group = QGroupBox(self.tr('Zone Classification'))
        result_layout = QVBoxLayout()
        self.datatable_ZM_Classe = QTableWidget()
        result_layout.addWidget(self.datatable_ZM_Classe)
        result_group.setLayout(result_layout)
        class_layout.addWidget(result_group)

        # Class map preview.
        self.label_ZM = QLabel(self.tr('Zones Map...'))
        self.label_ZM.setMinimumHeight(200)
        self.label_ZM.hide()
        class_layout.addWidget(self.label_ZM)

        class_widget.setLayout(class_layout)
        self.tabWidget_ZM.addTab(class_widget, self.tr('Management Zones'))

        layout.addWidget(self.tabWidget_ZM)
        self.setLayout(layout)
