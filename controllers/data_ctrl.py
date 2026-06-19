# -*- coding: utf-8 -*-
"""Data import, export, and layer management controller."""

import os
import time
import numpy as np
import pandas as pd
import matplotlib.path as mplPath
import matplotlib.pyplot as plt1
import subprocess
from scipy import spatial

from qgis.PyQt import QtCore, QtWidgets, QtGui
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog, QProgressDialog, QTableWidgetItem
from qgis.PyQt.QtGui import QIcon, QPixmap, QColor, QBrush
from qgis.core import QgsVectorFileWriter, QgsPointXY, QgsGeometry, QgsProject

from ..managers.data_manager import DataManager
from ..managers.export_manager import ExportManager
from ..utils import functions
from ..krig import semivariogram


class DataController:
    """Handles data import/export and QGIS layer management."""

    def __init__(self, dialog, iface, plugin_dir, path_absolute, icon_path, language, tr_func):
        self.dialog = dialog
        self.iface = iface
        self.plugin_dir = plugin_dir
        self.path_absolute = path_absolute
        self.icon_path = icon_path
        self.language = language
        self.tr = tr_func

        self.data_manager = DataManager()
        # Heavy export logic (gdal_grid, color ramp, processing.run) lives here.
        # The export_* methods below are thin delegators to this manager.
        self.export_manager = ExportManager(iface, path_absolute)

        # Back-reference to the grid controller, set by Smart_Map._initialize_controllers
        # after both controllers are constructed. grid_ctrl is the single owner of the
        # boundary state (df_limite + Contorno_Definido); data_ctrl reads it through the
        # properties below. May be None until wiring completes.
        self.grid_ctrl = None

        # Data state
        self.df = None
        self.data = None
        self.data_outlier = None
        self.xy = None
        self.z = None
        self.list_index_outlier = []
        self.v_target = None
        self.moran_index = None
        self.p_value = None

        # Grid state
        self.Cord_X = 'CoordX_SM'
        self.Cord_Y = 'CoordY_SM'
        self.Cord_X_min = None
        self.Cord_X_max = None
        self.Cord_Y_min = None
        self.Cord_Y_max = None
        self.Pixel_Size_X = None
        self.Pixel_Size_Y = None
        self.Num_Points_X = None
        self.Num_Points_Y = None

        # Boundary state is OWNED by grid_ctrl. The Contorno_Definido / df_limite
        # properties below delegate to grid_ctrl so there is a single source of truth.
        # (Fixes the old bug where resample_points read self.df_limite, which was always
        # None on data_ctrl while the real boundary lived on grid_ctrl.)

        # Variogram
        self.max_dist = None
        self.min_dist = None
        self.lag_distance_ini = None
        self.active_distance_ini = None

        # Parameters
        self.maximum_points_plugin = 5000
        self.VTarget_FileName = None
        self.cols_table_atribute = []

        # Workflow state flags
        self.ImportQGIS = False    # attribute table loaded from a QGIS layer
        self.Var_Selected = False  # target variable selected for interpolation
        self.Variogram = False     # semivariogram generated

    # Boundary state delegation (grid_ctrl is the single owner) ---------------
    @property
    def Contorno_Definido(self):
        """Whether a boundary contour has been defined (owned by grid_ctrl)."""
        if self.grid_ctrl is None:
            return False
        return self.grid_ctrl.Contorno_Definido

    @Contorno_Definido.setter
    def Contorno_Definido(self, value):
        if self.grid_ctrl is not None:
            self.grid_ctrl.Contorno_Definido = value

    @property
    def df_limite(self):
        """Boundary polygon dataframe (owned by grid_ctrl)."""
        if self.grid_ctrl is None:
            return None
        return self.grid_ctrl.df_limite

    @df_limite.setter
    def df_limite(self, value):
        if self.grid_ctrl is not None:
            self.grid_ctrl.df_limite = value

    # Layer selection & filtering
    def on_layer_combo_changed(self, index):
        """Handle attribute table layer selection (ported from mMapLayerComboBox_changed).

        Resolves the layer CRS (SAD69 -> project CRS, otherwise layer CRS), shows it in
        label_CRS_Layer, populates comboBox_VTarget with the layer field names, clears the
        attribute datatable and enables the VTarget combo + ImportQGIS button.
        """
        if self.dialog.mMapLayerComboBox.currentIndex() < 0:
            return

        selected_layer = self.dialog.mMapLayerComboBox.currentLayer()
        if selected_layer is None:
            return

        coordenate_reference = selected_layer.crs().description()

        if 'SAD69' in coordenate_reference:
            lyr_crs = QgsProject.instance().crs().authid()   # use project CRS, e.g. EPSG:32723
        else:
            lyr_crs = selected_layer.crs().authid()          # e.g. EPSG:32723

        # Boundary CRS state is owned by grid_ctrl.
        if self.grid_ctrl is not None:
            self.grid_ctrl.lyrCRS_table_atribute = lyr_crs

        self.dialog.label_CRS_Layer.show()
        self.dialog.label_CRS_Layer.setText('CRS Layer: ' + lyr_crs)

        # Field names of the selected layer (used for the target combo and SVM features).
        self.cols_table_atribute = selected_layer.fields().names()

        self.dialog.comboBox_VTarget.setEnabled(True)
        self.dialog.comboBox_VTarget.clear()
        self.dialog.comboBox_VTarget.addItems(self.cols_table_atribute)
        self.dialog.comboBox_VTarget.setCurrentIndex(0)

        # Reset the attribute table; user must (re)import.
        self.dialog.datatable_atributos.setColumnCount(0)
        self.dialog.datatable_atributos.setRowCount(0)

        self.dialog.comboBox_VTarget.setEnabled(True)
        self.dialog.pushButton_ImportQGIS.setEnabled(True)

    def on_vector_points_toggled(self, checked):
        """Filter vector point layers."""
        pass

    def on_vector_polygons_toggled(self, checked):
        """Filter vector polygon layers."""
        pass

    def on_raster_toggled(self, checked):
        """Filter raster layers."""
        pass

    # Data import - Main workflow
    def on_import_qgis_clicked(self):
        """Import data from QGIS layer (main workflow)."""
        if self.dialog.mMapLayerComboBox.currentIndex() < 0:
            return

        selected_layer = self.dialog.mMapLayerComboBox.currentLayer()

        # Validate CRS
        if not self._validate_layer_crs(selected_layer):
            return

        # Check point count, resample if needed
        if not self._check_point_count(selected_layer):
            return

        # Load data
        self._load_layer_to_dataframe(selected_layer)

        # Clean data
        self._clean_data()

        # Display in table
        self.load_attribute_table()

        # Calculate grid parameters
        self._calculate_grid_params()

        # Calculate Moran's I
        self._calculate_morans_i()

        # Plot points
        self._plot_sampled_points()

        # Initialize variogram
        self._initialize_variogram()

        # Enable the UI groups/widgets this domain owns and set workflow flags.
        self._enable_ui_after_import()

        # If the area-contour option is active, (re)apply the boundary now so the data is
        # clipped and the boundary is plotted. Boundary logic is owned by grid_ctrl.
        if self.dialog.checkBox_Area_Contorno.isChecked() and self.grid_ctrl is not None:
            self.grid_ctrl.on_contour_apply_clicked()

    def _validate_layer_crs(self, layer):
        """Check if layer is in projected coordinates (not geographic)."""
        crs = layer.crs()
        if crs.isGeographic():
            msg = (
                self.tr('O Sistema de Coordenadas Geográficas deve estar em UTM.') + '\n' +
                self.tr('Realize a conversão da layer de entrada para a projeção UTM antes de importá-la no Smart-Map.')
            )
            self._show_warning(self.tr('Mensagem'), msg)
            return False
        return True

    def _check_point_count(self, layer):
        """Check if point count exceeds limit, offer resampling."""
        if len(layer) <= self.maximum_points_plugin * 1.2:
            return True

        msg = (
            self.tr('A layer selecionada possui ') + str(len(layer)) +
            self.tr(' pontos amostrados.') + '\n' +
            self.tr('O limite máximo suportado pelo plugin para a layer de entrada é: ') +
            str(self.maximum_points_plugin) + self.tr(' pontos.') + '\n' +
            self.tr('Deseja realizar uma reamostragem de pontos?')
        )
        result = QMessageBox.question(self.dialog, self.tr('Mensagem'), msg,
                                     QMessageBox.Yes | QMessageBox.No)
        return result == QMessageBox.Yes

    def _load_layer_to_dataframe(self, layer):
        """Load QGIS layer to pandas dataframe."""
        progress = self._create_progress_dialog('Importando tabela de atributos...', 10)

        try:
            # Export layer to CSV
            csv_path = os.path.join(self.path_absolute, '0_Dados.csv')
            crs = layer.crs()
            QgsVectorFileWriter.writeAsVectorFormat(
                layer, csv_path, "utf-8", crs, "CSV"
            )
            progress.setValue(9)

            # Read CSV to dataframe
            self.df = pd.read_csv(csv_path, sep=',')
            self.df = self.df._get_numeric_data()  # Keep only numeric columns

            # Add coordinates if not present
            if self.Cord_X not in self.df.columns or self.Cord_Y not in self.df.columns:
                self._extract_coordinates(layer, progress)

            self.v_target = self.dialog.comboBox_VTarget.currentText()
        finally:
            progress.close()

    def _extract_coordinates(self, layer, progress):
        """Extract X, Y coordinates from layer geometries."""
        progress = self._create_progress_dialog('Calculando Coordenadas da Layer...', len(layer))

        coord_x = []
        coord_y = []

        for i, feat in enumerate(layer.getFeatures()):
            geom = QgsGeometry.asPoint(feat.geometry())
            pxy = QgsPointXY(geom)
            coord_x.append(pxy.x())
            coord_y.append(pxy.y())

            progress.setValue(i + 1)
            if progress.wasCanceled():
                progress.close()
                return

        progress.close()

        # Add to dataframe
        coord_x_arr = np.array(coord_x)
        coord_y_arr = np.array(coord_y)

        df_coords = pd.DataFrame({
            'CoordX_SM': coord_x_arr,
            'CoordY_SM': coord_y_arr,
            'ID_SM': np.arange(1, len(coord_x) + 1)
        })

        self.df = pd.concat([self.df, df_coords], axis=1)

        # Save updated CSV
        csv_path = os.path.join(self.path_absolute, '0_Dados.csv')
        self.df.to_csv(csv_path, sep=',', index=False, encoding='utf-8')

    def _clean_data(self):
        """Remove NaN values and clean dataframe."""
        # Sanitize target filename
        self.VTarget_FileName = self.v_target
        for ch in [' ', ')', '(', 'á', '?', '/', 'é', '.', 'í', 'ú', '-']:
            if ch in self.VTarget_FileName:
                self.VTarget_FileName = self.VTarget_FileName.replace(ch, "_")

        # Remove rows with NaN in target column
        is_nan = self.df.isnull()
        row_has_nan = is_nan.any(axis=1)
        df_with_nan = self.df[row_has_nan]

        cols_with_nan = df_with_nan.columns[df_with_nan.isnull().any()].tolist()

        if self.v_target in cols_with_nan:
            rows_to_drop = self.df[self.df[self.v_target].isnull()].index.tolist()
            self.df.drop(index=rows_to_drop, inplace=True)
            self.df.reset_index(drop=True, inplace=True)

            if rows_to_drop:
                msg = (
                    self.tr('Existem') + ': ' + str(len(rows_to_drop)) + ' ' +
                    self.tr('valores nulos na tabela.') + '\n' +
                    self.tr('Linha(s)') + ': ' + str(rows_to_drop) + ' ' +
                    self.tr('foram excluídas.')
                )
                self._show_warning(self.tr('Mensagem'), msg)

        # Resample if needed
        if len(self.df) > self.maximum_points_plugin * 1.2:
            self.df = self.resample_points(self.df)

            result = QMessageBox.question(
                self.dialog, self.tr('Mensagem'),
                self.tr('Deseja salvar os pontos reamostrados em uma nova layer Qgis?'),
                QMessageBox.Yes | QMessageBox.No
            )

            if result == QMessageBox.Yes:
                self._export_resampled_layer()

        # Detect outliers
        if self.dialog.checkBox_Eliminate_Outilier.isChecked():
            self.list_index_outlier = functions.localizar_outlier(self.df, self.v_target)

    def _export_resampled_layer(self):
        """Export resampled points to shapefile."""
        try:
            self.dialog.mMapLayerComboBox.currentIndexChanged.disconnect()
        except TypeError:
            pass

        csv_path = os.path.join(self.path_absolute, '0_Dados_Resample.csv')
        self.df.to_csv(csv_path, sep=',', index=False, encoding='utf-8')

        layer_name = self.dialog.mMapLayerComboBox.currentLayer().name()
        shp_path = os.path.join(self.path_absolute, layer_name + '_Resample.shp')

        self.export_shapefile_resampled_to_qgis(csv_path, shp_path, layer_name + '_Resample')

        try:
            self.dialog.mMapLayerComboBox.currentIndexChanged.connect(
                self.dialog.mMapLayerComboBox_changed
            )
        except (AttributeError, TypeError):
            pass

    def _calculate_grid_params(self):
        """Calculate grid extent from data."""
        # Extract data
        self.data = self.df[[self.Cord_X, self.Cord_Y, self.v_target]].values.astype(float)

        if len(self.list_index_outlier) > 0:
            self.data_outlier = self.df.loc[self.list_index_outlier,
                                           [self.Cord_X, self.Cord_Y, self.v_target]].values.astype(float)
            self.df.drop(self.df.index[self.list_index_outlier], inplace=True)
            self.df.reset_index(drop=True, inplace=True)

        # Grid params
        self.Pixel_Size_X = self.dialog.SpinBox_Pixel_Size_X.value()
        self.Pixel_Size_Y = self.dialog.SpinBox_Pixel_Size_Y.value()

        # Extent
        if not self.Contorno_Definido:
            self.Cord_X_min = self.df[self.Cord_X].min()
            self.Cord_X_max = self.df[self.Cord_X].max()
            self.Cord_Y_min = self.df[self.Cord_Y].min()
            self.Cord_Y_max = self.df[self.Cord_Y].max()

        self.dialog.lineEdit_XMin.setText('%.3f' % self.Cord_X_min)
        self.dialog.lineEdit_XMax.setText('%.3f' % self.Cord_X_max)
        self.dialog.lineEdit_YMin.setText('%.3f' % self.Cord_Y_min)
        self.dialog.lineEdit_YMax.setText('%.3f' % self.Cord_Y_max)

        self.Num_Points_X = int((self.Cord_X_max - self.Cord_X_min) / self.Pixel_Size_X)
        self.Num_Points_Y = int((self.Cord_Y_max - self.Cord_Y_min) / self.Pixel_Size_Y)

        self.dialog.lineEdit_Num_Points_X.setText(str(self.Num_Points_X))
        self.dialog.lineEdit_Num_Points_Y.setText(str(self.Num_Points_Y))

        self.dialog.label_VTargetOK.setText(self.tr('Z') + ': ' + self.v_target)
        self.dialog.label_VTargetSVM.setText(self.tr('Z') + ': ' + self.v_target)
        self.dialog.label_VTargetSVM.setEnabled(True)

    def _calculate_morans_i(self):
        """Calculate Moran's I spatial autocorrelation."""
        df_sampled = pd.DataFrame(
            self.data,
            columns=[self.Cord_X, self.Cord_Y, self.v_target]
        )

        moran_index, p_value = functions.calculate_index_moran(
            df_sampled, self.Cord_X, self.Cord_Y, self.v_target
        )

        self.moran_index = '%.3f' % moran_index
        self.p_value = '%.3f' % p_value

    def _plot_sampled_points(self):
        """Plot sampled points with Moran's I."""
        plt1.close()
        plt1.figure(figsize=(10, 8))

        title = f'I.Moran: {self.moran_index} P.Value: {self.p_value}'
        plt1.title(title)
        plt1.xlabel('Longitude (X)')
        plt1.ylabel('Latitude (Y)')

        plt1.xlim(self.Cord_X_min - 100, self.Cord_X_max + 100)
        plt1.ylim(self.Cord_Y_min - 100, self.Cord_Y_max + 100)

        # Set ticks
        interval_x = max(1, int((self.Cord_X_max - self.Cord_X_min) / 5))
        xmarks = [i for i in range(int(self.Cord_X_min), int(self.Cord_X_max), interval_x)]
        plt1.xticks(xmarks)

        interval_y = max(1, int((self.Cord_Y_max - self.Cord_Y_min) / 7))
        ymarks = [i for i in range(int(self.Cord_Y_min), int(self.Cord_Y_max), interval_y)]
        plt1.yticks(ymarks)

        # Plot outliers
        if len(self.list_index_outlier) > 0:
            plt1.scatter(self.data_outlier[:, 0], self.data_outlier[:, 1],
                        c=self.data_outlier[:, 2], marker="x", cmap='RdYlGn')

        # Plot data
        plt1.scatter(self.data[:, 0], self.data[:, 1], c=self.data[:, 2],
                    cmap='RdYlGn', vmin=min(self.data[:, 2]), vmax=max(self.data[:, 2]))

        clb = plt1.colorbar(aspect=20)
        clb.ax.set_title(self.v_target)

        plt1.subplots_adjust(wspace=0.6, hspace=0.6, left=0.15, right=0.95,
                            bottom=0.1, top=0.95)

        png_path = os.path.join(self.path_absolute, '0_Limite_Contorno.png')
        plt1.savefig(png_path)

        pixmap = QPixmap(png_path)
        self.dialog.label_pontos_limite.setPixmap(pixmap)
        self.dialog.label_pontos_limite.show()

    def _initialize_variogram(self):
        """Initialize variogram parameters."""
        self.xy = self.df[[self.Cord_X, self.Cord_Y]]
        self.z = self.df[self.v_target]

        # Build semivariogram
        semiv = semivariogram.Semivariogram(self.xy, self.z)

        self.max_dist = semiv.max_dist
        self.min_dist = semiv.min_dist

        max_dist_factor = 0.6
        self.active_distance_ini = max_dist_factor * self.max_dist
        self.lag_distance_ini = semiv.var['lag'][len(self.z)]

        if self.lag_distance_ini < self.min_dist:
            self.lag_distance_ini = self.min_dist

        # Set DMax minimum
        i = 5
        while self.max_dist < self.min_dist * i:
            i -= 1

        self.dialog.lineEdit_OK_DMax.setText('%.3f' % self.active_distance_ini)
        self.dialog.lineEdit_OK_lags_dist.setText('%.3f' % self.lag_distance_ini)

    def _enable_ui_after_import(self):
        """Enable the UI groups/widgets owned by the data+grid domain and set flags.

        Ported from the tail of pushButton_ImportQGIS_clicked. Only enables widgets in the
        Dados / Parametros-e-Contorno tabs and the variogram-enable toggles needed to start
        interpolation. Cross-domain population is intentionally NOT done here.
        """
        # --- Aba Parametros e Contorno -------------------------------------
        self.dialog.groupBox_Area_Contorno.setEnabled(True)
        self.dialog.datatable_limite.setEnabled(True)
        self.dialog.groupBox_Interv_Interp.setEnabled(True)
        self.dialog.SpinBox_Pixel_Size_X.setEnabled(True)
        self.dialog.SpinBox_Pixel_Size_Y.setEnabled(True)
        self.dialog.lineEdit_XMin.setEnabled(True)
        self.dialog.lineEdit_XMax.setEnabled(True)
        self.dialog.lineEdit_YMin.setEnabled(True)
        self.dialog.lineEdit_YMax.setEnabled(True)

        # --- Aba Interpolacao -> Krigagem (variogram-enable toggles) -------
        self.dialog.groupBox_Variograma.setEnabled(True)
        self.dialog.pushButton_VariogramaReset.setEnabled(False)
        self.dialog.pushButton_VariogramaAjust.setEnabled(True)
        self.dialog.pushButton_VariogramaSave.setEnabled(False)
        self.dialog.lineEdit_OK_DMax.setEnabled(True)
        self.dialog.lineEdit_OK_lags_dist.setEnabled(True)

        # Workflow flags owned by this domain.
        self.ImportQGIS = True       # attribute table loaded from a QGIS layer
        self.Var_Selected = True     # target variable selected for interpolation
        self.Variogram = False       # table loaded, semivariogram not yet generated

        # SVM_Add_Coord lives on grid_ctrl (SVM/grid state owner); reset it on import.
        if self.grid_ctrl is not None:
            self.grid_ctrl.SVM_Add_Coord = False

        # TODO(variogram/kriging domain): set the OK neighbours/radius limits and
        #   defaults that the old pushButton_ImportQGIS_clicked set here, e.g.
        #   VB_OK_Minimum/Maximum, lineEdit_OK_VBNumMax, Raio_OK_Minimum/Maximum,
        #   lineEdit_OK_VBRaio. Owned by the variogram/kriging controllers.
        # TODO(svm domain): enable and populate the SVM tab widgets the old method set
        #   here (groupBox_SVM*, comboBox_SVM_Features/_Adds, lineEdit_SVM_VB*,
        #   df_SVM_Trainfeatures/Trainlabels, load_datatable_SVM_*). Owned by SVMController.
        # TODO(zones domain): enable pushButton_ZM_Add_Var. Owned by ZonesController.
        # TODO(variogram/zones domains): call load_semivariograms() and
        #   load_maps_to_generate_ZM() after import. Owned by those controllers.

    # Data loading into tables
    def load_attribute_table(self):
        """Load layer attributes into datatable."""
        if self.df is None:
            return

        df_display = self.df[['ID_SM', self.Cord_X, self.Cord_Y, self.v_target]]

        progress = self._create_progress_dialog(
            'Importando tabela de atributos...',
            len(df_display.index) * len(df_display.columns)
        )

        try:
            self.dialog.datatable_atributos.setColumnCount(len(df_display.columns))
            self.dialog.datatable_atributos.setRowCount(len(df_display.index))

            headers = ['ID', 'Coord X', 'Coord Y', self.v_target]
            self.dialog.datatable_atributos.setHorizontalHeaderLabels(headers)

            cont = 1
            for i in range(len(df_display.index)):
                for j in range(len(df_display.columns)):
                    value = df_display.iloc[i, j]

                    if j == 0:
                        text = '%.0f' % value
                    else:
                        text = '%.3f' % value if isinstance(value, (int, float)) else str(value)

                    item = QTableWidgetItem(text)

                    if i in self.list_index_outlier:
                        item.setForeground(QBrush(QColor(255, 0, 0)))

                    self.dialog.datatable_atributos.setItem(i, j, item)
                    cont += 1
                    progress.setValue(cont)

                    if progress.wasCanceled():
                        progress.close()
                        return

            self.dialog.datatable_atributos.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        finally:
            progress.close()

    def load_svm_train_features(self):
        """Load SVM training features."""
        # Implemented when SVM controller is created
        pass

    def load_svm_train_labels(self):
        """Load SVM training labels."""
        # Implemented when SVM controller is created
        pass

    def resample_points(self, df):
        """Resample point data using grid-based IDW (ported from resampling_of_points).

        Builds a regular grid over the data (or boundary) extent, and for every grid node
        averages the observations of the sample points found within a search radius
        (grid_size / 2) via a cKDTree, using functions.mean with the IDW weight read from
        doubleSpinBox_Weight_IDW. Nodes with no neighbour get -1 -> NaN and are dropped.
        Returns the rebuilt, resampled dataframe (df_resample).
        """
        if 'fid' in df.columns:
            df.drop('fid', axis=1, inplace=True)

        # Remove columns that are entirely NaN (avoid wiping the whole dataframe later).
        list_cols_nan = df.columns[df.isnull().any()].tolist()
        for column_name in list_cols_nan:
            if df[column_name].isnull().sum() == len(df):
                df.drop(column_name, axis=1, inplace=True)

        # Remove rows with any remaining NaN.
        if df.isnull().sum().sum() > 0:
            df.dropna(inplace=True)
            df.reset_index(drop=True, inplace=True)

        Cord_X = self.Cord_X
        Cord_Y = self.Cord_Y
        weight_IDW = self.dialog.doubleSpinBox_Weight_IDW.value()
        cols = df.columns

        # Grid extent: data extent when no boundary, else the boundary extent.
        if not self.Contorno_Definido:
            x_min = df[Cord_X].min()
            x_max = df[Cord_X].max()
            y_min = df[Cord_Y].min()
            y_max = df[Cord_Y].max()
        else:
            x_min = self.df_limite['Coord_X'].min()
            x_max = self.df_limite['Coord_X'].max()
            y_min = self.df_limite['Coord_Y'].min()
            y_max = self.df_limite['Coord_Y'].max()

        area = (x_max - x_min) * (y_max - y_min)
        n = area / self.maximum_points_plugin
        grid_size = np.sqrt(n)

        gridx = np.arange(x_min, x_max, grid_size)
        gridy = np.arange(y_min, y_max, grid_size)

        lista_xy = []
        for i in range(len(gridx)):
            for j in range(len(gridy)):
                lista_xy.append([gridx[i], gridy[j]])

        arr_xy = np.array(lista_xy)

        # Clip grid to the boundary polygon when the contour option is active.
        if self.dialog.checkBox_Area_Contorno.isChecked():
            if self.df_limite is not None and len(self.df_limite) > 0:
                lista_cut_xy = []
                polygono = np.array(self.df_limite, dtype=float)
                bbPath = mplPath.Path(polygono)
                for i in range(len(arr_xy)):
                    ponto = (arr_xy[i, 0], arr_xy[i, 1])
                    if bbPath.contains_point(ponto):
                        lista_cut_xy.append([arr_xy[i, 0], arr_xy[i, 1]])
                arr_xy = np.array(lista_cut_xy)

        grid_xy = np.array(arr_xy)

        # Dense (observed) sample coordinates and the KDTree over them.
        features_dense = df[[Cord_X, Cord_Y]]
        features_dense = np.array(features_dense, dtype=float)
        gridxy_dense = np.c_[features_dense[:, 0], features_dense[:, 1]]
        tree_dense = spatial.cKDTree(gridxy_dense)

        maximum = (len(cols) - 3)   # discard CoordX_SM, CoordY_SM, ID_SM
        progress = self._create_progress_dialog(
            self.tr('Reamostragem da tabela de atributos...'), maximum
        )

        arr_resample = None
        try:
            for feat in range(len(cols) - 3):
                vt_dense = df.iloc[:, feat]                    # observed values of the covariate

                lista = []
                for cont in range(len(grid_xy)):
                    p = np.array([grid_xy[cont, 0], grid_xy[cont, 1]])

                    raio_busca = float(grid_size / 2)          # search radius = 50% of grid length
                    neigs = tree_dense.query_ball_point(p, raio_busca)

                    if len(neigs) > 0:
                        distances, points_idx = tree_dense.query(p, k=len(neigs))
                        vt_vals_dense = vt_dense[points_idx]
                        value = functions.mean(distances, vt_vals_dense, weight_IDW)
                    else:
                        value = -1

                    lista.append(value)

                arr = np.array(lista)

                if feat == 0:
                    arr_resample = np.copy(arr)
                else:
                    arr_resample = np.column_stack((arr_resample, arr))

                progress.setValue(feat)
                if progress.wasCanceled():
                    progress.close()
                    return df
        finally:
            progress.close()

        arr_resample = np.column_stack((arr_resample, arr_xy))

        id_sm = np.arange(1, len(arr_xy) + 1, 1)
        arr_resample = np.column_stack((arr_resample, id_sm))

        df_resample = pd.DataFrame(np.atleast_2d(arr_resample), columns=cols)

        df_resample.replace({-1: np.nan}, inplace=True)        # nodes with no neighbour -> NaN

        if df_resample.isnull().sum().sum() > 0:
            df_resample.dropna(inplace=True)
            df_resample.reset_index(drop=True, inplace=True)

        df_resample['ID_SM'] = df_resample.index
        df_resample['ID_SM'] += 1

        return df_resample

    # File management
    def on_file_save_clicked(self):
        """Save data to file."""
        if self.df is None:
            self._show_warning(self.tr('Aviso'), self.tr('Nenhum dado carregado.'))
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self.dialog, self.tr('Salvar dados'), self.path_absolute,
            self.tr('CSV files (*.csv)')
        )

        if filepath:
            self.df.to_csv(filepath, sep=',', index=False, encoding='utf-8')

    # Export to QGIS (thin delegators to ExportManager) ----------------------
    def _zm_number_classes(self):
        """Resolve the ZM color-ramp class count (zones domain widget; default 5)."""
        spin = getattr(self.dialog, 'spinBox_ZM_NrZonas', None)
        if spin is not None:
            return spin.value()
        return 5

    def export_raster_to_qgis(self, input_table, output_tiff, output_name, z_field):
        """Export interpolated raster to QGIS via gdal_grid (delegates to ExportManager)."""
        # ZM pixel sizes are owned by the zones domain and may not be set on data_ctrl
        # for kriging/SVM grids; fall back to the default pixel size when absent.
        pixel_size_x_zm = getattr(self, 'Pixel_Size_X_ZM', self.Pixel_Size_X)
        pixel_size_y_zm = getattr(self, 'Pixel_Size_Y_ZM', self.Pixel_Size_Y)

        contour_checked = self.dialog.checkBox_Area_Contorno.isChecked()
        contour_layer = None
        if self.dialog.mMapLayerComboBox_AreaCont.currentIndex() >= 0:
            contour_layer = self.dialog.mMapLayerComboBox_AreaCont.currentLayer()

        source_layer = self.dialog.mMapLayerComboBox.currentLayer()

        return self.export_manager.export_raster_to_qgis(
            input_table, output_tiff, output_name, z_field,
            self.Cord_X, self.Cord_Y,
            self.Cord_X_min, self.Cord_X_max, self.Cord_Y_min, self.Cord_Y_max,
            self.Pixel_Size_X, self.Pixel_Size_Y,
            pixel_size_x_zm, pixel_size_y_zm,
            source_layer,
            contour_checked, contour_layer,
            self._zm_number_classes(),
        )

    def define_raster_color_ramp(self, layer, layer_name):
        """Define raster color ramp (delegates to ExportManager)."""
        return self.export_manager.define_raster_color_ramp(
            layer, layer_name, self._zm_number_classes()
        )

    def export_shapefile_to_qgis(self, input_path, alg_name):
        """Export raster pixels to points/polygons (delegates to ExportManager)."""
        return self.export_manager.export_shapefile_to_qgis(
            input_path, alg_name, self.v_target
        )

    def export_shapefile_resampled_to_qgis(self, input_table, output_shp, output_name):
        """Export resampled points to shapefile (delegates to ExportManager)."""
        source_layer = self.dialog.mMapLayerComboBox.currentLayer()
        return self.export_manager.export_shapefile_resampled_to_qgis(
            input_table, output_shp, output_name,
            self.Cord_X, self.Cord_Y, source_layer
        )

    # Helpers
    def _create_progress_dialog(self, label, max_val):
        """Create QProgressDialog."""
        progress = QProgressDialog(label, self.tr('Cancelar'), 1, max_val, self.dialog)
        progress.setWindowTitle('Smart-Map')
        progress.show()
        progress.setCancelButton(None)
        progress.setWindowModality(QtCore.Qt.WindowModal)
        time.sleep(0.1)
        return progress

    def _show_warning(self, title, message):
        """Show warning message box."""
        msg_box = QMessageBox()
        msg_box.setWindowIcon(QIcon(self.icon_path))
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec_()
