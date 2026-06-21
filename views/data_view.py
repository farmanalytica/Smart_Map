# -*- coding: utf-8 -*-
"""Data import and layer management view."""

from qgis.PyQt import QtCore, QtWidgets, QtGui
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QLabel,
    QComboBox, QCheckBox, QTableWidget, QTableWidgetItem, QSpinBox,
    QDoubleSpinBox, QTabWidget, QProgressBar
)
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QIcon, QPixmap

from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox

from .styles import tune_layout


class DataView(QWidget):
    """Data import and management view."""

    # Signals
    import_clicked = pyqtSignal()
    layer_changed = pyqtSignal(int)

    def __init__(self, iface, plugin_dir, icon_path, tr_func, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.plugin_dir = plugin_dir
        self.icon_path = icon_path
        self.tr = tr_func

        self._setup_ui()

    def _setup_ui(self):
        """Build data view UI."""
        layout = QVBoxLayout()
        tune_layout(layout)

        # Layer selection section
        layer_group = self._create_layer_selection_group()
        layout.addWidget(layer_group)

        # Data management tabs
        data_tabs = QTabWidget()
        data_tabs.setElideMode(Qt.ElideNone)
        data_tabs.setUsesScrollButtons(True)

        # Attribute table tab
        attr_tab = self._create_attribute_table_tab()
        data_tabs.addTab(attr_tab, self.tr('Attribute Table'))

        # Grid parameters tab
        grid_tab = self._create_grid_parameters_tab()
        data_tabs.addTab(grid_tab, self.tr('Grid'))

        # Area contour tab
        contour_tab = self._create_contour_tab()
        data_tabs.addTab(contour_tab, self.tr('Boundary Area'))

        layout.addWidget(data_tabs)

        # Points visualization
        self.label_pontos_limite = QtWidgets.QLabel()
        self.label_pontos_limite.setMinimumHeight(360)
        # Keep the plot's native aspect ratio (controllers scale the pixmap
        # with KeepAspectRatio); scaledContents=True would stretch it.
        self.label_pontos_limite.setScaledContents(False)
        self.label_pontos_limite.setAlignment(QtCore.Qt.AlignCenter)
        self.label_pontos_limite.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.label_pontos_limite.setStyleSheet('border: 1px solid #cccccc;')
        layout.addWidget(QLabel(self.tr('Points Visualization:')))
        layout.addWidget(self.label_pontos_limite)

        self.setLayout(layout)

    def _create_layer_selection_group(self):
        """Create layer selection and import controls."""
        group = QGroupBox(self.tr('Data Selection'))
        layout = QVBoxLayout()

        # Layer combo
        combo_layout = QHBoxLayout()
        combo_layout.addWidget(QLabel(self.tr('QGIS Layer:')))

        self.mMapLayerComboBox = QgsMapLayerComboBox()
        self.mMapLayerComboBox.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.mMapLayerComboBox.currentIndexChanged.connect(self.layer_changed.emit)
        combo_layout.addWidget(self.mMapLayerComboBox)

        layout.addLayout(combo_layout)

        # Layer type filters
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel(self.tr('Filter:')))

        self.checkBox_Qgis_Vector_Points = QCheckBox(self.tr('Points'))
        self.checkBox_Qgis_Vector_Points.setChecked(True)
        filter_layout.addWidget(self.checkBox_Qgis_Vector_Points)

        self.checkBox_Qgis_Vector_Polygons = QCheckBox(self.tr('Polygons'))
        filter_layout.addWidget(self.checkBox_Qgis_Vector_Polygons)

        self.checkBox_Qgis_Raster = QCheckBox(self.tr('Raster'))
        filter_layout.addWidget(self.checkBox_Qgis_Raster)

        filter_layout.addStretch()

        layout.addLayout(filter_layout)

        # Target variable selection
        var_layout = QHBoxLayout()
        var_layout.addWidget(QLabel(self.tr('Target Variable (Z):')))

        self.comboBox_VTarget = QComboBox()
        var_layout.addWidget(self.comboBox_VTarget)

        var_layout.addStretch()

        layout.addLayout(var_layout)

        # Import button (primary action)
        self.pushButton_ImportQGIS = QPushButton(self.tr('Import Data from QGIS'))
        self.pushButton_ImportQGIS.setObjectName('primaryButton')
        self.pushButton_ImportQGIS.setMinimumHeight(34)
        self.pushButton_ImportQGIS.setCursor(Qt.PointingHandCursor)
        self.pushButton_ImportQGIS.clicked.connect(self.import_clicked.emit)
        layout.addWidget(self.pushButton_ImportQGIS)

        # Outlier elimination
        self.checkBox_Eliminate_Outilier = QCheckBox(self.tr('Remove Outliers'))
        layout.addWidget(self.checkBox_Eliminate_Outilier)

        # IDW weight (used when resampling dense layers to the grid)
        idw_layout = QHBoxLayout()
        idw_layout.addWidget(QLabel(self.tr('IDW Weight:')))
        self.doubleSpinBox_Weight_IDW = QDoubleSpinBox()
        self.doubleSpinBox_Weight_IDW.setMinimum(0.0)
        self.doubleSpinBox_Weight_IDW.setMaximum(10.0)
        self.doubleSpinBox_Weight_IDW.setSingleStep(0.5)
        self.doubleSpinBox_Weight_IDW.setValue(2.0)
        idw_layout.addWidget(self.doubleSpinBox_Weight_IDW)
        idw_layout.addStretch()
        layout.addLayout(idw_layout)

        # Output directory (working folder for generated files)
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel(self.tr('Output Folder:')))
        self.lineEdit = QtWidgets.QLineEdit()
        self.lineEdit.setReadOnly(True)
        out_layout.addWidget(self.lineEdit)
        layout.addLayout(out_layout)

        # CRS info
        self.label_CRS_Layer = QLabel(self.tr('CRS: '))
        layout.addWidget(self.label_CRS_Layer)

        group.setLayout(layout)
        return group

    def _create_attribute_table_tab(self):
        """Create attribute table view."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Save button
        save_layout = QHBoxLayout()
        self.pushButton_File_Save = QPushButton(self.tr('Save Data'))
        save_layout.addWidget(self.pushButton_File_Save)
        save_layout.addStretch()
        layout.addLayout(save_layout)

        # Table
        self.datatable_atributos = QTableWidget()
        self.datatable_atributos.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.datatable_atributos.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.datatable_atributos.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)
        layout.addWidget(self.datatable_atributos)

        widget.setLayout(layout)
        return widget

    def _create_grid_parameters_tab(self):
        """Create grid parameter controls."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Pixel size
        pixel_layout = QHBoxLayout()
        pixel_layout.addWidget(QLabel(self.tr('Pixel Size:')))

        pixel_layout.addWidget(QLabel(self.tr('X:')))
        self.SpinBox_Pixel_Size_X = QDoubleSpinBox()
        self.SpinBox_Pixel_Size_X.setValue(5.0)
        self.SpinBox_Pixel_Size_X.setMinimum(0.1)
        self.SpinBox_Pixel_Size_X.setMaximum(10000.0)
        self.SpinBox_Pixel_Size_X.setMinimumWidth(90)
        pixel_layout.addWidget(self.SpinBox_Pixel_Size_X)

        pixel_layout.addWidget(QLabel(self.tr('Y:')))
        self.SpinBox_Pixel_Size_Y = QDoubleSpinBox()
        self.SpinBox_Pixel_Size_Y.setValue(5.0)
        self.SpinBox_Pixel_Size_Y.setMinimum(0.1)
        self.SpinBox_Pixel_Size_Y.setMaximum(10000.0)
        self.SpinBox_Pixel_Size_Y.setMinimumWidth(90)
        pixel_layout.addWidget(self.SpinBox_Pixel_Size_Y)

        pixel_layout.addStretch()
        layout.addLayout(pixel_layout)

        # Grid extent
        extent_group = QGroupBox(self.tr('Grid Extent'))
        extent_layout = QVBoxLayout()

        # X min/max
        x_layout = QHBoxLayout()
        x_layout.addWidget(QLabel(self.tr('X Min:')))
        self.lineEdit_XMin = QtWidgets.QLineEdit()
        self.lineEdit_XMin.setMinimumWidth(120)
        x_layout.addWidget(self.lineEdit_XMin)

        x_layout.addWidget(QLabel(self.tr('X Max:')))
        self.lineEdit_XMax = QtWidgets.QLineEdit()
        self.lineEdit_XMax.setMinimumWidth(120)
        x_layout.addWidget(self.lineEdit_XMax)

        x_layout.addStretch()
        extent_layout.addLayout(x_layout)

        # Y min/max
        y_layout = QHBoxLayout()
        y_layout.addWidget(QLabel(self.tr('Y Min:')))
        self.lineEdit_YMin = QtWidgets.QLineEdit()
        self.lineEdit_YMin.setMinimumWidth(120)
        y_layout.addWidget(self.lineEdit_YMin)

        y_layout.addWidget(QLabel(self.tr('Y Max:')))
        self.lineEdit_YMax = QtWidgets.QLineEdit()
        self.lineEdit_YMax.setMinimumWidth(120)
        y_layout.addWidget(self.lineEdit_YMax)

        y_layout.addStretch()
        extent_layout.addLayout(y_layout)

        # Number of points
        points_layout = QHBoxLayout()
        points_layout.addWidget(QLabel(self.tr('No. Points:')))

        points_layout.addWidget(QLabel(self.tr('X:')))
        self.lineEdit_Num_Points_X = QtWidgets.QLineEdit()
        self.lineEdit_Num_Points_X.setReadOnly(True)
        self.lineEdit_Num_Points_X.setMaximumWidth(100)
        points_layout.addWidget(self.lineEdit_Num_Points_X)

        points_layout.addWidget(QLabel(self.tr('Y:')))
        self.lineEdit_Num_Points_Y = QtWidgets.QLineEdit()
        self.lineEdit_Num_Points_Y.setReadOnly(True)
        self.lineEdit_Num_Points_Y.setMaximumWidth(100)
        points_layout.addWidget(self.lineEdit_Num_Points_Y)

        points_layout.addStretch()
        extent_layout.addLayout(points_layout)

        extent_group.setLayout(extent_layout)
        layout.addWidget(extent_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _create_contour_tab(self):
        """Create area contour controls."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Enable contour checkbox
        self.checkBox_Area_Contorno = QCheckBox(self.tr('Define Boundary Area'))
        layout.addWidget(self.checkBox_Area_Contorno)

        # Contour layer selection
        contour_group = QGroupBox(self.tr('Boundary Selection'))
        contour_layout = QVBoxLayout()

        # Layer combo
        layer_layout = QHBoxLayout()
        layer_layout.addWidget(QLabel(self.tr('Boundary Layer:')))

        self.mMapLayerComboBox_AreaCont = QgsMapLayerComboBox()
        self.mMapLayerComboBox_AreaCont.setFilters(
            QgsMapLayerProxyModel.VectorLayer | QgsMapLayerProxyModel.PolygonLayer
        )
        layer_layout.addWidget(self.mMapLayerComboBox_AreaCont)

        contour_layout.addLayout(layer_layout)

        # Coordinate fields
        coord_layout = QHBoxLayout()
        coord_layout.addWidget(QLabel(self.tr('Coord X:')))
        self.comboBox_CordX_AreaCont = QComboBox()
        coord_layout.addWidget(self.comboBox_CordX_AreaCont)

        coord_layout.addWidget(QLabel(self.tr('Coord Y:')))
        self.comboBox_CordY_AreaCont = QComboBox()
        coord_layout.addWidget(self.comboBox_CordY_AreaCont)

        contour_layout.addLayout(coord_layout)

        # Apply button
        self.pushButton_Area_Contorno = QPushButton(self.tr('Apply Boundary'))
        contour_layout.addWidget(self.pushButton_Area_Contorno)

        contour_group.setLayout(contour_layout)
        layout.addWidget(contour_group)

        # Contour table
        self.datatable_limite = QTableWidget()
        self.datatable_limite.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.datatable_limite.setMaximumHeight(150)
        layout.addWidget(QLabel(self.tr('Boundary Points:')))
        layout.addWidget(self.datatable_limite)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    # Accessors for controllers
    def get_target_variable(self):
        """Get selected target variable."""
        return self.comboBox_VTarget.currentText()

    def set_target_variables(self, variables):
        """Set available target variables."""
        self.comboBox_VTarget.clear()
        self.comboBox_VTarget.addItems(variables)

    def get_grid_params(self):
        """Get grid parameters."""
        return {
            'pixel_size_x': self.SpinBox_Pixel_Size_X.value(),
            'pixel_size_y': self.SpinBox_Pixel_Size_Y.value(),
            'x_min': float(self.lineEdit_XMin.text()) if self.lineEdit_XMin.text() else 0,
            'x_max': float(self.lineEdit_XMax.text()) if self.lineEdit_XMax.text() else 0,
            'y_min': float(self.lineEdit_YMin.text()) if self.lineEdit_YMin.text() else 0,
            'y_max': float(self.lineEdit_YMax.text()) if self.lineEdit_YMax.text() else 0,
        }
