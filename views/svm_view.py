# -*- coding: utf-8 -*-
"""SVM machine learning view."""

from qgis.PyQt import QtWidgets, QtCore
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton, QComboBox, QTableWidget, QCheckBox

class SVMView(QWidget):
    """SVM training and prediction view."""

    def __init__(self, tr_func, parent=None):
        super().__init__(parent)
        self.tr = tr_func
        self._setup_ui()

    def _setup_ui(self):
        """Build SVM view UI."""
        layout = QVBoxLayout()

        # Data source
        source_group = QGroupBox(self.tr('Fonte de Dados'))
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel(self.tr('Fonte:')))
        self.comboBox_SVM_Fonte = QComboBox()
        self.comboBox_SVM_Fonte.addItems([self.tr('Tabela de Atributos'), self.tr('Layer Densa')])
        source_layout.addWidget(self.comboBox_SVM_Fonte)
        self.mMapLayerComboBox_DenseLayer = QtWidgets.QgsMapLayerComboBox()
        source_layout.addWidget(self.mMapLayerComboBox_DenseLayer)
        source_layout.addStretch()
        source_group.setLayout(source_layout)
        layout.addWidget(source_group)

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

        # Training features
        train_group = QGroupBox(self.tr('Features de Treino'))
        train_layout = QVBoxLayout()
        self.datatable_SVM_Trainfeatures = QTableWidget()
        train_layout.addWidget(self.datatable_SVM_Trainfeatures)
        train_group.setLayout(train_layout)
        layout.addWidget(train_group)

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

        # Results tabs
        self.tabs_svm = QtWidgets.QTabWidget()

        # Interpolated points tab
        points_widget = QWidget()
        points_layout = QVBoxLayout()
        self.datatable_pontos_interpolados_SVM = QTableWidget()
        points_layout.addWidget(self.datatable_pontos_interpolados_SVM)
        points_widget.setLayout(points_layout)
        self.tabs_svm.addTab(points_widget, self.tr('Pontos Interpolados'))

        # Cross-validation tab
        cv_widget = QWidget()
        cv_layout = QVBoxLayout()
        self.datatable_validacao_cruzada_SVM = QTableWidget()
        cv_layout.addWidget(self.datatable_validacao_cruzada_SVM)
        cv_widget.setLayout(cv_layout)
        self.tabs_svm.addTab(cv_widget, self.tr('Validação Cruzada'))

        layout.addWidget(self.tabs_svm)

        self.label_SVM = QtWidgets.QLabel(self.tr('Mapa SVM...'))
        self.label_SVM.setMinimumHeight(200)
        layout.addWidget(self.label_SVM)

        self.label_validacao_cruzada_SVM = QtWidgets.QLabel(self.tr('Gráfico CV SVM...'))
        self.label_validacao_cruzada_SVM.setMinimumHeight(200)
        layout.addWidget(self.label_validacao_cruzada_SVM)

        self.setLayout(layout)
