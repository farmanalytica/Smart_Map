# -*- coding: utf-8 -*-
"""SVM machine learning view."""

from qgis.PyQt import QtWidgets, QtCore, QtGui
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QComboBox, QTableWidget, QCheckBox, QLineEdit, QDoubleSpinBox,
)


class SVMView(QWidget):
    """SVM training and prediction view."""

    def __init__(self, tr_func, parent=None):
        super().__init__(parent)
        self.tr = tr_func
        self._setup_ui()

    def _setup_ui(self):
        """Build SVM view UI."""
        layout = QVBoxLayout()

        # Target variable label
        self.label_VTargetSVM = QLabel(self.tr('Z') + ': ')
        layout.addWidget(self.label_VTargetSVM)

        # Data source
        source_group = QGroupBox(self.tr('Fonte de Dados'))
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel(self.tr('Fonte:')))
        self.comboBox_SVM_Fonte = QComboBox()
        self.comboBox_SVM_Fonte.addItems([self.tr('Tabela de Atributos'), self.tr('Layer Densa')])
        source_layout.addWidget(self.comboBox_SVM_Fonte)
        self.label_SVM_DenseLayer = QLabel(self.tr('Layer Densa:'))
        source_layout.addWidget(self.label_SVM_DenseLayer)
        self.mMapLayerComboBox_DenseLayer = QtWidgets.QgsMapLayerComboBox()
        source_layout.addWidget(self.mMapLayerComboBox_DenseLayer)
        source_layout.addStretch()
        source_group.setLayout(source_layout)
        layout.addWidget(source_group)

        # Search neighbourhood parameters (Number of neighbours / radius / IDW power)
        search_group = QGroupBox(self.tr('Vizinhança de Busca'))
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel(self.tr('Nr. Máx. Vizinhos:')))
        self.lineEdit_SVM_VBNumMax = QLineEdit()
        self.lineEdit_SVM_VBNumMax.setText('16')
        search_layout.addWidget(self.lineEdit_SVM_VBNumMax)
        search_layout.addWidget(QLabel(self.tr('Raio de Busca:')))
        self.lineEdit_SVM_VBRaio = QLineEdit()
        search_layout.addWidget(self.lineEdit_SVM_VBRaio)
        search_layout.addWidget(QLabel(self.tr('Peso IDW:')))
        self.doubleSpinBox_Weight_IDW = QDoubleSpinBox()
        self.doubleSpinBox_Weight_IDW.setDecimals(1)
        self.doubleSpinBox_Weight_IDW.setMinimum(0.1)
        self.doubleSpinBox_Weight_IDW.setMaximum(10.0)
        self.doubleSpinBox_Weight_IDW.setSingleStep(0.1)
        self.doubleSpinBox_Weight_IDW.setValue(2.0)
        search_layout.addWidget(self.doubleSpinBox_Weight_IDW)
        search_layout.addStretch()
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)

        # Feature management
        feat_group = QGroupBox(self.tr('Gerenciar Features'))
        feat_layout = QHBoxLayout()
        self.comboBox_SVM_Features = QComboBox()
        feat_layout.addWidget(QLabel(self.tr('Variáveis:')))
        feat_layout.addWidget(self.comboBox_SVM_Features)
        self.pushButton_SVM_Add_Feature = QPushButton(self.tr('Adicionar'))
        feat_layout.addWidget(self.pushButton_SVM_Add_Feature)
        self.comboBox_SVM_Features_Adds = QComboBox()
        feat_layout.addWidget(QLabel(self.tr('Remover:')))
        feat_layout.addWidget(self.comboBox_SVM_Features_Adds)
        self.pushButton_SVM_Remove_Feature = QPushButton(self.tr('Remover'))
        feat_layout.addWidget(self.pushButton_SVM_Remove_Feature)
        feat_layout.addStretch()
        feat_group.setLayout(feat_layout)
        layout.addWidget(feat_group)

        # Spatial analysis
        spatial_layout = QHBoxLayout()
        self.checkBox_Moran = QCheckBox(self.tr('Moran I'))
        spatial_layout.addWidget(self.checkBox_Moran)
        self.checkBox_RFE = QCheckBox(self.tr('RFE'))
        spatial_layout.addWidget(self.checkBox_RFE)
        spatial_layout.addStretch()
        layout.addLayout(spatial_layout)

        # Moran results
        moran_group = QGroupBox(self.tr('Correlação Espacial (Moran)'))
        moran_layout = QVBoxLayout()
        self.datatable_moran = QTableWidget()
        moran_layout.addWidget(self.datatable_moran)
        moran_group.setLayout(moran_layout)
        layout.addWidget(moran_group)

        # RFE results
        rfe_group = QGroupBox(self.tr('Recursive Feature Elimination (RFE)'))
        rfe_layout = QVBoxLayout()
        self.datatable_RFE = QTableWidget()
        rfe_layout.addWidget(self.datatable_RFE)
        rfe_group.setLayout(rfe_layout)
        layout.addWidget(rfe_group)

        # Buttons
        btn_layout = QHBoxLayout()
        self.pushButton_SVM_Add_Selected_Features = QPushButton(self.tr('Adicionar Selecionadas'))
        btn_layout.addWidget(self.pushButton_SVM_Add_Selected_Features)
        self.pushButton_SVM = QPushButton(self.tr('Executar SVM'))
        btn_layout.addWidget(self.pushButton_SVM)
        self.pushButton_Validacao_Cruzada_SVM = QPushButton(self.tr('Validação Cruzada'))
        btn_layout.addWidget(self.pushButton_Validacao_Cruzada_SVM)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Results tabs. Index order matches the legacy tabWidget_Interpolacao_SVM:
        #   0 = train features / labels, 1 = cross-validation, 2 = interpolated map.
        self.tabWidget_Interpolacao_SVM = QtWidgets.QTabWidget()
        self.tabs_svm = self.tabWidget_Interpolacao_SVM  # backwards-compatible alias

        # Tab 0: training features + labels
        train_widget = QWidget()
        train_layout = QHBoxLayout()
        self.datatable_SVM_Trainfeatures = QTableWidget()
        train_layout.addWidget(self.datatable_SVM_Trainfeatures)
        self.datatable_SVM_Trainlabels = QTableWidget()
        train_layout.addWidget(self.datatable_SVM_Trainlabels)
        train_widget.setLayout(train_layout)
        self.tabWidget_Interpolacao_SVM.addTab(train_widget, self.tr('Features de Treino'))

        # Tab 1: cross-validation
        cv_widget = QWidget()
        cv_layout = QVBoxLayout()
        self.datatable_validacao_cruzada_SVM = QTableWidget()
        cv_layout.addWidget(self.datatable_validacao_cruzada_SVM)
        self.label_validacao_cruzada_SVM = QtWidgets.QLabel(self.tr('Gráfico CV SVM...'))
        self.label_validacao_cruzada_SVM.setMinimumHeight(200)
        cv_layout.addWidget(self.label_validacao_cruzada_SVM)
        cv_widget.setLayout(cv_layout)
        self.tabWidget_Interpolacao_SVM.addTab(cv_widget, self.tr('Validação Cruzada'))

        # Tab 2: interpolated points + map
        points_widget = QWidget()
        points_layout = QVBoxLayout()
        self.datatable_pontos_interpolados_SVM = QTableWidget()
        points_layout.addWidget(self.datatable_pontos_interpolados_SVM)
        self.label_SVM = QtWidgets.QLabel(self.tr('Mapa SVM...'))
        self.label_SVM.setMinimumHeight(200)
        points_layout.addWidget(self.label_SVM)
        points_widget.setLayout(points_layout)
        self.tabWidget_Interpolacao_SVM.addTab(points_widget, self.tr('Pontos Interpolados'))

        layout.addWidget(self.tabWidget_Interpolacao_SVM)

        self.setLayout(layout)
