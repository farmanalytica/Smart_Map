# -*- coding: utf-8 -*-
"""Support Vector Machine (SVM) controller.

Ported faithfully from the old monolithic ``smart_map`` class (Smart_Map.py):
  - pushButton_SVM_Add_Feature_clicked          -> on_add_feature_clicked
  - pushButton_SVM_Add_Selected_Features_clicked -> on_add_selected_features_clicked
  - pushButton_SVM_Remove_Feature_clicked       -> on_remove_feature_clicked
  - pushButton_SVM_clicked                       -> on_svm_clicked
  - pushButton_Validacao_Cruzada_SVM_clicked     -> on_svm_cross_validation_clicked
  - checkBox_Moran_clicked / correlacao_Moran_BV -> on_moran_toggled
  - datatable_moran_checkbox_clicked             -> on_moran_checkbox_clicked
  - checkBox_RFE_clicked / Recursive_Feature_Elimination -> on_rfe_toggled
  - comboBox_SVM_Fonte_changed                   -> on_source_layer_combo_changed
  - mMapLayerComboBox_DenseLayer_changed         -> on_dense_layer_combo_changed
  - lineEdit_SVM_VBNumMax/VBRaio_EditingFinished -> on_vb_num_max_edited / on_vb_raio_edited
  - load_datatable_SVM_Trainfeatures/Trainlabels -> load_datatable_SVM_Trainfeatures/labels

SVM-tab widgets live on ``self.view`` (svm_view). Shared widgets (boundary contour,
attribute-table layer combo, outlier checkbox, QGIS export checkboxes) live on the
data view, reached via ``self.data_ctrl.dialog``. Boundary state (df_limite /
Contorno_Definido) lives on grid_ctrl and is read through data_ctrl delegating
properties. Raster/vector export goes through the data_ctrl delegators.
"""

import os
import time
import platform

import numpy as np
import pandas as pd
import matplotlib.path as mplPath
import matplotlib.pyplot as plt3   # SVM interpolated map
import matplotlib.pyplot as plt5   # SVM cross-validation plot

from scipy import spatial

from sklearn import svm
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from qgis.PyQt import QtCore, QtWidgets, QtGui
from qgis.PyQt.QtWidgets import QMessageBox, QTableWidgetItem, QProgressDialog
from qgis.PyQt.QtGui import QIcon, QPixmap
from qgis.core import QgsMapLayerType, QgsPointXY, QgsGeometry, QgsProject

from ..utils import functions

system = platform.system()  # [Windows, Linux, Darwin]
if system != 'Darwin':
    try:
        from PIL import Image
    except ImportError:
        Image = None
else:
    Image = None


class SVMController:
    """Handles SVM training, feature engineering, and spatial analysis."""

    def __init__(self, view, data_ctrl, interp_mgr, spatial_mgr, icon_path, path_absolute, tr_func):
        self.view = view
        self.data_ctrl = data_ctrl
        self.interp_mgr = interp_mgr
        self.spatial_mgr = spatial_mgr
        self.icon_path = icon_path
        self.path_absolute = path_absolute
        self.tr = tr_func

        # SVM grid / feature-engineering state (kept on the controller).
        self.df_SVM_Trainfeatures = pd.DataFrame()
        self.df_SVM_Trainlabels = pd.DataFrame()
        self.df_SVM_Testfeatures = pd.DataFrame()
        self.df_CV_SVM = None
        self.gridx = None
        self.gridy = None
        self.grid_xy = None
        self.features_grid = None
        self.arr_cut = None

        self.list_cov_SVM = []
        self.list_rows_moran = []
        self.cols_table_atribute_dense = []

        # SVM neighbourhood-search bounds (seeded lazily from data_ctrl state).
        self.VB_SVM_Minimum = 1
        self.VB_SVM_Maximum = None
        self.Raio_SVM_Minimum = None
        self.Raio_SVM_Maximum = None

        # ML model objects
        self.norm = None
        self.svr = None

        # Workflow flags
        self.SVM_Add_Coord = False
        self.SVM_Add_Feature = False
        self.SVM = False
        self.Validacao_Cruzada_SVM = False

    # ------------------------------------------------------------------ helpers
    @property
    def data_view(self):
        """Shared data-tab dialog (boundary contour, layer combos, export checkboxes)."""
        return self.data_ctrl.dialog

    def seed_train_state(self):
        """Seed the SVM model with coordinates (X, Y) for a freshly imported layer.

        Ported from the SVM portion of pushButton_ImportQGIS_clicked (Smart_Map.py
        ~1916). df_SVM_Trainfeatures starts as [Cord_X, Cord_Y], df_SVM_Trainlabels
        is v_target, and the SVM-search bounds / line-edit defaults are established.
        Safe to call from the data import flow once df is loaded.
        """
        if self.data_ctrl.df is None:
            return

        Cord_X = self.data_ctrl.Cord_X
        Cord_Y = self.data_ctrl.Cord_Y

        self.df_SVM_Trainfeatures = self.data_ctrl.df[[Cord_X, Cord_Y]].copy()
        self.list_cov_SVM = [Cord_X, Cord_Y]
        self.df_SVM_Trainlabels = self.data_ctrl.df[[self.data_ctrl.v_target]].copy()

        self.SVM_Add_Coord = False
        self.SVM_Add_Feature = False
        self.SVM = False
        self.Validacao_Cruzada_SVM = False
        self.list_rows_moran = []

        # Establish SVM neighbour-count / search-radius bounds and defaults.
        n_data = len(self.data_ctrl.data) if self.data_ctrl.data is not None else len(self.data_ctrl.df)
        self.VB_SVM_Minimum = 1
        self.VB_SVM_Maximum = n_data
        self.Raio_SVM_Minimum = self.data_ctrl.min_dist
        self.Raio_SVM_Maximum = self.data_ctrl.max_dist

        if n_data >= 16:
            self.view.lineEdit_SVM_VBNumMax.setText('16')
        else:
            self.view.lineEdit_SVM_VBNumMax.setText(str(round(n_data / 2)))
        if self.data_ctrl.max_dist is not None:
            self.view.lineEdit_SVM_VBRaio.setText('%.3f' % self.data_ctrl.max_dist)

        self.load_datatable_SVM_Trainfeatures()
        self.load_datatable_SVM_Trainlabels()

    def _ensure_svm_bounds(self):
        """Lazy-seed VB/Raio bounds from data_ctrl if not yet established."""
        if self.VB_SVM_Maximum is None:
            n_data = len(self.data_ctrl.data) if self.data_ctrl.data is not None else len(self.data_ctrl.df)
            self.VB_SVM_Maximum = n_data
        if self.Raio_SVM_Minimum is None:
            self.Raio_SVM_Minimum = self.data_ctrl.min_dist
        if self.Raio_SVM_Maximum is None:
            self.Raio_SVM_Maximum = self.data_ctrl.max_dist

    # ------------------------------------------------- load train tables
    def load_datatable_SVM_Trainfeatures(self):
        """Fill the train-features table (ported from load_datatable_SVM_Trainfeatures)."""
        if self.df_SVM_Trainfeatures is None or len(self.df_SVM_Trainfeatures.index) == 0:
            return

        maximum = len(self.df_SVM_Trainfeatures.index) * len(self.df_SVM_Trainfeatures.columns)
        progress = self._create_progress_dialog(self.tr('Importando tabela de atributos...'), maximum)

        self.view.datatable_SVM_Trainfeatures.setColumnCount(len(self.df_SVM_Trainfeatures.columns))
        self.view.datatable_SVM_Trainfeatures.setRowCount(len(self.df_SVM_Trainfeatures.index))

        try:
            cols = list(self.df_SVM_Trainfeatures.columns.values)
            self.view.datatable_SVM_Trainfeatures.setHorizontalHeaderLabels(cols)
        except AttributeError:
            self._show_warning(self.tr('Mensagem'), self.tr('Erro ao carregar tabela. Valor Inválido!'))

        cont = 1
        try:
            for i in range(len(self.df_SVM_Trainfeatures.index)):
                for j in range(len(self.df_SVM_Trainfeatures.columns)):
                    valor = self.df_SVM_Trainfeatures.iloc[i, j]
                    try:
                        if valor.dtype == "float64":
                            valor = '%.3f' % valor
                    except AttributeError:
                        pass
                    self.view.datatable_SVM_Trainfeatures.setItem(i, j, QTableWidgetItem(str(valor)))
                    cont += 1
                    progress.setValue(cont)
                    if progress.wasCanceled():
                        progress.close()
                        return
        except AttributeError:
            self._show_warning(self.tr('Mensagem'), self.tr('Erro ao carregar tabela. Valor Inválido!'))

        self.view.datatable_SVM_Trainfeatures.resizeColumnsToContents()
        self.view.datatable_SVM_Trainfeatures.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        progress.close()

    def load_datatable_SVM_Trainlabels(self):
        """Fill the train-labels table (ported from load_datatable_SVM_Trainlabels)."""
        if self.df_SVM_Trainlabels is None or len(self.df_SVM_Trainlabels.index) == 0:
            return

        maximum = len(self.df_SVM_Trainlabels.index) * len(self.df_SVM_Trainlabels.columns)
        progress = self._create_progress_dialog(self.tr('Importando tabela de atributos...'), maximum)

        self.view.datatable_SVM_Trainlabels.setColumnCount(len(self.df_SVM_Trainlabels.columns))
        self.view.datatable_SVM_Trainlabels.setRowCount(len(self.df_SVM_Trainlabels.index))

        try:
            cols = list(self.df_SVM_Trainlabels.columns.values)
            self.view.datatable_SVM_Trainlabels.setHorizontalHeaderLabels(cols)
        except AttributeError:
            self._show_warning(self.tr('Mensagem'), self.tr('Erro ao carregar tabela. Valor Inválido!'))

        cont = 1
        try:
            for i in range(len(self.df_SVM_Trainlabels.index)):
                for j in range(len(self.df_SVM_Trainlabels.columns)):
                    valor = self.df_SVM_Trainlabels.iloc[i, j]
                    try:
                        if valor.dtype == "float64":
                            valor = '%.3f' % valor
                    except AttributeError:
                        pass
                    self.view.datatable_SVM_Trainlabels.setItem(i, j, QTableWidgetItem(str(valor)))
                    cont += 1
                    progress.setValue(cont)
                    if progress.wasCanceled():
                        progress.close()
                        return
        except AttributeError:
            self._show_warning(self.tr('Mensagem'), self.tr('Erro ao carregar tabela. Valor Inválido!'))

        self.view.datatable_SVM_Trainlabels.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        progress.close()

    # ----------------------------------------- source layer & dense layer combos
    def on_source_layer_combo_changed(self, value):
        """Handle source-data selection (ported from comboBox_SVM_Fonte_changed)."""
        self.view.checkBox_Moran.setChecked(False)
        self.list_rows_moran = []
        self.view.pushButton_SVM_Add_Selected_Features.setEnabled(False)
        self.view.datatable_moran.setColumnCount(0)
        self.view.datatable_moran.setRowCount(0)

        if value == 0:  # Features from the attribute table
            self.view.checkBox_RFE.setEnabled(True)

            self.view.label_SVM_DenseLayer.setEnabled(False)
            self.view.mMapLayerComboBox_DenseLayer.setEnabled(False)

            self.view.comboBox_SVM_Features.setEnabled(True)
            self.view.pushButton_SVM_Add_Feature.setEnabled(True)
            self.view.comboBox_SVM_Features_Adds.setEnabled(True)
            self.view.pushButton_SVM_Remove_Feature.setEnabled(True)

            self.view.comboBox_SVM_Features.clear()
            self.view.comboBox_SVM_Features.addItems(self.data_ctrl.cols_table_atribute)
            self.view.comboBox_SVM_Features.setCurrentIndex(3)

        else:           # Features from another (dense) layer
            self.view.checkBox_RFE.setEnabled(False)
            self.view.checkBox_Moran.setEnabled(True)
            self.view.checkBox_Moran.setChecked(False)

            selectedLayer = self.view.mMapLayerComboBox_DenseLayer.currentLayer()
            if selectedLayer is None:
                return

            if selectedLayer.type() == QgsMapLayerType.RasterLayer:
                self.view.label_SVM_DenseLayer.setEnabled(True)
                self.view.mMapLayerComboBox_DenseLayer.setEnabled(True)

                self.view.comboBox_SVM_Features.setEnabled(False)
                self.view.pushButton_SVM_Add_Feature.setEnabled(True)

                self.view.comboBox_SVM_Features_Adds.setEnabled(True)
                self.view.pushButton_SVM_Remove_Feature.setEnabled(True)

                self.view.comboBox_SVM_Features.clear()

            else:  # VectorLayer
                self.cols_table_atribute_dense = selectedLayer.fields().names()

                self.view.label_SVM_DenseLayer.setEnabled(True)
                self.view.mMapLayerComboBox_DenseLayer.setEnabled(True)

                self.view.comboBox_SVM_Features.setEnabled(True)
                self.view.pushButton_SVM_Add_Feature.setEnabled(True)

                self.view.comboBox_SVM_Features_Adds.setEnabled(True)
                self.view.pushButton_SVM_Remove_Feature.setEnabled(True)

                self.view.comboBox_SVM_Features.clear()
                self.view.comboBox_SVM_Features.addItems(self.cols_table_atribute_dense)
                self.view.comboBox_SVM_Features.setCurrentIndex(3)

    def on_dense_layer_combo_changed(self, index=None):
        """Handle dense-layer selection (ported from mMapLayerComboBox_DenseLayer_changed).

        FIX: the old/new stub compared layer.crs().authid() against the Cord_X column
        name. The correct check compares the dense layer CRS against the attribute-table
        layer CRS (lyrCRS_table_atribute), honouring the SAD69 -> project-CRS special case.
        """
        if self.view.comboBox_SVM_Fonte.currentIndex() != 1:  # only for Dense Layer source
            return

        if self.view.mMapLayerComboBox_DenseLayer.currentIndex() < 0:
            return

        selectedLayer = self.view.mMapLayerComboBox_DenseLayer.currentLayer()
        if selectedLayer is None:
            return

        coordenate_reference = selectedLayer.crs().description()
        if 'SAD69' in coordenate_reference:
            lyrCRS = QgsProject.instance().crs().authid()  # project CRS, e.g. EPSG:32723
        else:
            lyrCRS = selectedLayer.crs().authid()

        # Attribute-table layer CRS is owned by grid_ctrl.
        lyrCRS_table_atribute = None
        grid_ctrl = getattr(self.data_ctrl, 'grid_ctrl', None)
        if grid_ctrl is not None:
            lyrCRS_table_atribute = getattr(grid_ctrl, 'lyrCRS_table_atribute', None)

        if (lyrCRS_table_atribute is not None) and (lyrCRS != lyrCRS_table_atribute):
            self._show_warning(
                self.tr('Mensagem'),
                self.tr('O CRS da Layer selecionada é diferente do CRS da Layer da Tabela de Atributos.')
            )
            return

        if selectedLayer.type() == QgsMapLayerType.RasterLayer:
            self.view.comboBox_SVM_Features.setEnabled(False)
            self.view.pushButton_SVM_Add_Feature.setEnabled(True)
            self.view.comboBox_SVM_Features_Adds.setEnabled(True)
            self.view.pushButton_SVM_Remove_Feature.setEnabled(True)
            self.view.comboBox_SVM_Features.clear()
        else:  # VectorLayer
            self.cols_table_atribute_dense = selectedLayer.fields().names()
            self.view.comboBox_SVM_Features.setEnabled(True)
            self.view.pushButton_SVM_Add_Feature.setEnabled(True)
            self.view.comboBox_SVM_Features_Adds.setEnabled(True)
            self.view.pushButton_SVM_Remove_Feature.setEnabled(True)
            self.view.comboBox_SVM_Features.clear()
            self.view.comboBox_SVM_Features.addItems(self.cols_table_atribute_dense)
            self.view.comboBox_SVM_Features.setCurrentIndex(3)

    # ------------------------------------------------------- lineEdit clamping
    def on_vb_num_max_edited(self):
        """Clamp the neighbour-count line edit (ported from lineEdit_SVM_VBNumMax_EditingFinished)."""
        self._ensure_svm_bounds()
        try:
            VB = int(self.view.lineEdit_SVM_VBNumMax.text())
        except ValueError:
            VB = self.VB_SVM_Minimum
        if self.VB_SVM_Maximum is not None and VB > self.VB_SVM_Maximum:
            VB = self.VB_SVM_Maximum
        if VB < self.VB_SVM_Minimum:
            VB = self.VB_SVM_Minimum
        self.view.lineEdit_SVM_VBNumMax.setText(str(VB))

    def on_vb_raio_edited(self):
        """Clamp the search-radius line edit (ported from lineEdit_SVM_VBRaio_EditingFinished)."""
        self._ensure_svm_bounds()
        try:
            Raio = float(self.view.lineEdit_SVM_VBRaio.text())
        except ValueError:
            Raio = self.Raio_SVM_Maximum if self.Raio_SVM_Maximum is not None else 0.0
        if self.data_ctrl.max_dist is not None and Raio > self.data_ctrl.max_dist:
            Raio = self.data_ctrl.max_dist
        if self.data_ctrl.min_dist is not None and Raio < self.data_ctrl.min_dist:
            Raio = self.data_ctrl.min_dist
        self.view.lineEdit_SVM_VBRaio.setText('%.3f' % Raio)

    # ============================================================== ADD FEATURE
    def on_add_feature_clicked(self):
        """Add a covariate (IDW-engineered) to the SVM model.

        Full port of pushButton_SVM_Add_Feature_clicked.
        """
        Cord_Z = self.view.comboBox_SVM_Features.currentText()

        n_neig = int(self.view.lineEdit_SVM_VBNumMax.text())
        weight_IDW = self.view.doubleSpinBox_Weight_IDW.value()

        data_view = self.data_view

        # Guard: cannot add v_target with neighbour count = 1 (nearest-neighbour method).
        if (Cord_Z == self.data_ctrl.v_target) and (int(self.view.lineEdit_SVM_VBNumMax.text()) == 1):
            self._show_warning(
                self.tr('Mensagem'),
                self.tr('O Modelo de Machine Learning não permite adicionar a variável target: ')
                + self.data_ctrl.v_target + '\n'
                + self.tr('utilizando o método de busca por vizinho mais próximo.')
            )
            return

        # ----------------------------------------- coordinate seeding (first call)
        if self.SVM_Add_Coord is False:

            # If features were already added but params changed, remove them first.
            if self.SVM_Add_Feature is True:
                for i in range(2, len(self.list_cov_SVM)):
                    self.view.comboBox_SVM_Features_Adds.setCurrentIndex(i)
                    self.on_remove_feature_clicked()

            self.view.tabWidget_Interpolacao_SVM.setCurrentIndex(0)

            self.gridx = np.arange(float(self.data_ctrl.Cord_X_min), float(self.data_ctrl.Cord_X_max), self.data_ctrl.Pixel_Size_X)
            self.gridy = np.arange(float(self.data_ctrl.Cord_Y_min), float(self.data_ctrl.Cord_Y_max), self.data_ctrl.Pixel_Size_Y)

            maximum = (len(self.gridx) * len(self.gridy))
            progress = self._create_progress_dialog(self.tr('Machine Learning - Support Vector Machine...'), maximum)

            cont = 1
            lista_xy = []
            for i in range(len(self.gridx)):
                for j in range(len(self.gridy)):
                    lista_xy.append([self.gridx[i] + (self.data_ctrl.Pixel_Size_X / 2),
                                     self.gridy[j] - (self.data_ctrl.Pixel_Size_Y / 2)])
                    cont += 1
                    progress.setValue(cont)
                    if progress.wasCanceled():
                        progress.close()
                        return
            progress.close()

            arr_xy = np.array(lista_xy)

            if data_view.checkBox_Area_Contorno.isChecked():
                if self.data_ctrl.df_limite is None or len(self.data_ctrl.df_limite) <= 0:
                    if data_view.mMapLayerComboBox_AreaCont.currentIndex() >= 0:
                        if getattr(self.data_ctrl, 'grid_ctrl', None) is not None:
                            self.data_ctrl.grid_ctrl.on_contour_apply_clicked()

                lista_cut_xy = []
                polygono = np.array(self.data_ctrl.df_limite, dtype=float)
                bbPath = mplPath.Path(polygono)

                maximum = len(arr_xy)
                progress = self._create_progress_dialog(
                    self.tr('Gerando grid para os pontos de interpolação (x, y, z): '), maximum)
                cont = 1
                for i in range(len(arr_xy)):
                    ponto = (arr_xy[i, 0], arr_xy[i, 1])
                    if bbPath.contains_point(ponto):
                        lista_cut_xy.append([arr_xy[i, 0], arr_xy[i, 1]])
                    cont += 1
                    progress.setValue(cont)
                    if progress.wasCanceled():
                        progress.close()
                        return
                progress.close()
                arr_xy = np.array(lista_cut_xy)

            self.grid_xy = np.array(arr_xy)

            self.df_SVM_Testfeatures = pd.DataFrame(
                np.atleast_2d(self.grid_xy), columns=[self.data_ctrl.Cord_X, self.data_ctrl.Cord_Y])

            self.features_grid = np.array(self.grid_xy)

            self.SVM_Add_Coord = True
            self.SVM_Add_Feature = False

            self.view.label_SVM.hide()
            self.view.datatable_pontos_interpolados_SVM.setColumnCount(0)
            self.view.datatable_pontos_interpolados_SVM.setRowCount(0)
            self.view.label_validacao_cruzada_SVM.hide()
            self.view.datatable_validacao_cruzada_SVM.setColumnCount(0)
            self.view.datatable_validacao_cruzada_SVM.setRowCount(0)

        # -------------------------------------------- resolve covariate name (Cord_Z)
        if self.view.comboBox_SVM_Fonte.currentIndex() == 1:
            selectedLayer = self.view.mMapLayerComboBox_DenseLayer.currentLayer()
            if selectedLayer is not None and selectedLayer.type() == QgsMapLayerType.RasterLayer:
                Cord_Z = selectedLayer.name()
            else:
                Cord_Z = self.view.comboBox_SVM_Features.currentText()

        if self.view.comboBox_SVM_Fonte.currentIndex() == 0:
            Cord_Z = self.view.comboBox_SVM_Features.currentText()

        # ------------------------------------------------ add an attribute to the model
        self.view.tabWidget_Interpolacao_SVM.setCurrentIndex(0)

        cols = [Cord_Z + '_' + self.view.lineEdit_SVM_VBNumMax.text()]
        self.view.comboBox_SVM_Features_Adds.addItems(cols)

        self.list_cov_SVM = [self.view.comboBox_SVM_Features_Adds.itemText(i)
                             for i in range(self.view.comboBox_SVM_Features_Adds.count())]

        # ===================================== source = attribute table
        if self.view.comboBox_SVM_Fonte.currentIndex() == 0:

            # NaN backfill on the selected column.
            is_NaN = self.data_ctrl.df.isnull()
            row_has_NaN = is_NaN.any(axis=1)
            df_with_NaN = self.data_ctrl.df[row_has_NaN]
            list_cols_NaN = df_with_NaN.columns[df_with_NaN.isnull().any()].tolist()

            if Cord_Z in list_cols_NaN:
                self.data_ctrl.df[Cord_Z].fillna(method='backfill', inplace=True)

            # Outlier substitution (KDTree + mean of neighbours).
            if data_view.checkBox_Eliminate_Outilier.isChecked():
                list_index_outlier = functions.localizar_outlier(self.data_ctrl.df, Cord_Z)

                features = np.column_stack([self.data_ctrl.df[self.data_ctrl.Cord_X],
                                            self.data_ctrl.df[self.data_ctrl.Cord_Y]])

                for cont in list_index_outlier:
                    vt2 = np.copy(np.array(self.data_ctrl.df[Cord_Z]))
                    vt2 = np.delete(vt2, (cont), axis=0)

                    features2 = np.copy(features)
                    features2 = np.delete(features2, (cont), axis=0)

                    gridxy = np.c_[features2[:, 0], features2[:, 1]]
                    tree = spatial.cKDTree(gridxy)

                    p = np.array([features[cont, 0], features[cont, 1]])
                    raio_busca = float(self.view.lineEdit_SVM_VBRaio.text())
                    neigs = tree.query_ball_point(p, raio_busca)

                    if len(neigs) > n_neig:
                        distances, points_idx = tree.query(p, k=n_neig)
                    elif len(neigs) < 2:
                        distances, points_idx = tree.query(p, k=3)
                    else:
                        distances, points_idx = tree.query(p, k=len(neigs))

                    vt_vals = vt2[points_idx]
                    value = functions.mean(distances, vt_vals, weight_IDW)
                    self.data_ctrl.df.loc[cont, Cord_Z] = value

            # ------------------------ TrainFeatures IDW engineering
            if int(self.view.lineEdit_SVM_VBNumMax.text()) == 1:
                self.df_SVM_Trainfeatures = pd.concat(
                    [self.df_SVM_Trainfeatures, self.data_ctrl.df[[Cord_Z]]], axis=1)
                self.df_SVM_Trainfeatures.rename(
                    columns={Cord_Z: Cord_Z + '_' + self.view.lineEdit_SVM_VBNumMax.text()}, inplace=True)

            elif int(self.view.lineEdit_SVM_VBNumMax.text()) > 1:
                features = np.column_stack([self.data_ctrl.df[self.data_ctrl.Cord_X],
                                            self.data_ctrl.df[self.data_ctrl.Cord_Y]])
                lista_IDW = []

                maximum = len(features)
                progress = self._create_progress_dialog(
                    self.tr('Gerando IDW em TrainFeatures: ') + Cord_Z + '...', maximum)

                for cont in range(len(features)):
                    vt2 = np.copy(np.array(self.data_ctrl.df[Cord_Z]))
                    vt2 = np.delete(vt2, (cont), axis=0)

                    features2 = np.copy(features)
                    features2 = np.delete(features2, (cont), axis=0)

                    gridxy = np.c_[features2[:, 0], features2[:, 1]]
                    tree = spatial.cKDTree(gridxy)

                    p = np.array([features[cont, 0], features[cont, 1]])
                    raio_busca = float(self.view.lineEdit_SVM_VBRaio.text())
                    neigs = tree.query_ball_point(p, raio_busca)

                    if len(neigs) > n_neig:
                        distances, points_idx = tree.query(p, k=n_neig)
                    elif len(neigs) < 2:
                        distances, points_idx = tree.query(p, k=3)
                    else:
                        distances, points_idx = tree.query(p, k=len(neigs))

                    vt_vals = vt2[points_idx]
                    value = functions.idw(distances, vt_vals, weight_IDW)
                    lista_IDW.append(value)

                    progress.setValue(cont)
                    if progress.wasCanceled():
                        progress.close()
                        return
                progress.close()

                labels_IDW = np.array(lista_IDW).reshape(-1, 1)
                labels_IDW_df = pd.DataFrame(
                    np.atleast_2d(labels_IDW),
                    columns=[Cord_Z + '_' + self.view.lineEdit_SVM_VBNumMax.text()])
                self.df_SVM_Trainfeatures = pd.concat([self.df_SVM_Trainfeatures, labels_IDW_df], axis=1)

            # ------------------------ TestFeatures IDW engineering over the grid
            maximum = (len(self.gridx) * len(self.gridy))
            progress = self._create_progress_dialog(
                self.tr('Gerando grid para os pontos de interpolação (x, y, z): ') + Cord_Z + '...', maximum)

            vt = np.array(self.df_SVM_Trainfeatures.iloc[:, len(self.df_SVM_Trainfeatures.columns) - 1])
            gridxy = np.c_[self.df_SVM_Trainfeatures.iloc[:, 0], self.df_SVM_Trainfeatures.iloc[:, 1]]
            tree = spatial.cKDTree(gridxy)

            z = np.zeros((self.gridx.shape[0], self.gridy.shape[0]), dtype=float)

            cont = 1
            for i, val1 in enumerate(self.gridx):
                for j, val2 in enumerate(self.gridy):
                    p = np.array([val1, val2])
                    raio_busca = float(self.view.lineEdit_SVM_VBRaio.text())
                    neigs = tree.query_ball_point(p, raio_busca)

                    if len(neigs) > n_neig:
                        distances, points_idx = tree.query(p, k=n_neig + 1)
                    elif len(neigs) < 2:
                        distances, points_idx = tree.query(p, k=3)
                    elif len(neigs) < len(self.df_SVM_Trainfeatures):
                        distances, points_idx = tree.query(p, k=len(neigs) + 1)
                    else:
                        distances, points_idx = tree.query(p, k=len(neigs))

                    vt_vals = vt[points_idx]

                    if int(self.view.lineEdit_SVM_VBNumMax.text()) == 1:
                        value = vt_vals[0]

                    if int(self.view.lineEdit_SVM_VBNumMax.text()) > 1:
                        if distances[0] == 0:
                            points_idx = np.delete(points_idx, 0)
                            distances = np.delete(distances, 0)
                            vt_vals = np.delete(vt_vals, 0)
                        else:
                            points_idx = np.delete(points_idx, len(points_idx) - 1)
                            distances = np.delete(distances, len(distances) - 1)
                            vt_vals = np.delete(vt_vals, len(vt_vals) - 1)
                        value = functions.idw(distances, vt_vals, weight_IDW)

                    z[i, j] = value
                    cont += 1
                    progress.setValue(cont)
                    if progress.wasCanceled():
                        progress.close()
                        return
            progress.close()

            # Apply contour and flatten the engineered covariate column.
            maximum = (len(self.gridx) * len(self.gridy))
            progress = self._create_progress_dialog(
                self.tr('Aplicando Área de Contorno ao grid dos pontos de interpolação: ') + Cord_Z + '...', maximum)

            lista = []
            if data_view.checkBox_Area_Contorno.isChecked():
                if self.data_ctrl.df_limite is None or len(self.data_ctrl.df_limite) <= 0:
                    if data_view.mMapLayerComboBox_AreaCont.currentIndex() >= 0:
                        if getattr(self.data_ctrl, 'grid_ctrl', None) is not None:
                            self.data_ctrl.grid_ctrl.on_contour_apply_clicked()

                polygono = np.array(self.data_ctrl.df_limite, dtype=float)
                bbPath = mplPath.Path(polygono)

                cont = 1
                for i in range(len(self.gridx)):
                    for j in range(len(self.gridy)):
                        ponto = (self.gridx[i] + (self.data_ctrl.Pixel_Size_X / 2),
                                 self.gridy[j] - (self.data_ctrl.Pixel_Size_Y / 2))
                        if bbPath.contains_point(ponto):
                            lista.append([z[i, j]])
                        cont += 1
                        progress.setValue(cont)
                        if progress.wasCanceled():
                            progress.close()
                            return
            else:
                cont = 1
                for i in range(len(self.gridx)):
                    for j in range(len(self.gridy)):
                        lista.append([z[i, j]])
                        cont += 1
                        progress.setValue(cont)
                        if progress.wasCanceled():
                            progress.close()
                            return
            progress.close()

            arr = np.array(lista)
            self.features_grid = np.column_stack([self.features_grid, arr])
            arr = arr.reshape(-1, 1)

            arr_df = pd.DataFrame(np.atleast_2d(arr),
                                  columns=[Cord_Z + '_' + self.view.lineEdit_SVM_VBNumMax.text()])
            self.df_SVM_Testfeatures = pd.concat([self.df_SVM_Testfeatures, arr_df], axis=1)
            self.df_SVM_Testfeatures.to_csv(
                os.path.join(self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_Test_Set.csv'),
                sep=',', index=False, encoding='utf-8')

        # ===================================== source = dense layer
        elif self.view.comboBox_SVM_Fonte.currentIndex() == 1:

            selectedLayer = self.view.mMapLayerComboBox_DenseLayer.currentLayer()

            if selectedLayer.type() == QgsMapLayerType.RasterLayer:
                dim = selectedLayer.extent().toString()
                if ' ' in dim:
                    dim = dim.replace(' ', '')
                coords = dim.split(":")
                coord_min = coords[0].split(",")
                coord_max = coords[1].split(",")

                coord_x_min = float(coord_min[0])
                coord_y_min = float(coord_min[1])
                coord_x_max = float(coord_max[0])
                coord_y_max = float(coord_max[1])

                gridx = np.arange(coord_x_min, coord_x_max, self.data_ctrl.Pixel_Size_X)
                gridy = np.arange(coord_y_min, coord_y_max, self.data_ctrl.Pixel_Size_Y)

                if data_view.checkBox_Area_Contorno.isChecked():
                    polygono = np.array(self.data_ctrl.df_limite, dtype=float)
                    bbPath = mplPath.Path(polygono)

                maximum = (len(gridx) * len(gridy))
                progress = self._create_progress_dialog(
                    self.tr('Gerando grid para os pontos de interpolação (x, y, z): ') + Cord_Z + '...', maximum)

                features_Coordx = []
                features_Coordy = []
                features_target = []

                cont = 1
                for i in range(len(gridx)):
                    for j in range(len(gridy)):
                        val, res = selectedLayer.dataProvider().sample(QgsPointXY(gridx[i], gridy[j]), 1)
                        if res is True:
                            if val >= 0.0:
                                if data_view.checkBox_Area_Contorno.isChecked():
                                    ponto = (gridx[i], gridy[j])
                                    if bbPath.contains_point(ponto):
                                        features_Coordx.append(gridx[i])
                                        features_Coordy.append(gridy[j])
                                        features_target.append(val)
                                else:
                                    features_Coordx.append(gridx[i])
                                    features_Coordy.append(gridy[j])
                                    features_target.append(val)
                        cont += 1
                        progress.setValue(cont)
                        if progress.wasCanceled():
                            progress.close()
                            return
                progress.close()

            else:  # dense layer is a vector layer
                features = selectedLayer.getFeatures()
                id_target = self.view.comboBox_SVM_Features.currentIndex()

                features_Coordx = []
                features_Coordy = []
                features_target = []
                for feat in features:
                    attrs = feat.attributes()
                    geom = QgsGeometry.asPoint(feat.geometry())
                    pxy = QgsPointXY(geom)
                    if attrs[id_target] is not None:
                        features_Coordx.append(pxy.x())
                        features_Coordy.append(pxy.y())
                        features_target.append(attrs[id_target])

                features_Coordx = np.array(features_Coordx)
                features_Coordy = np.array(features_Coordy)
                features_target = np.array(features_target)

            features_dense = np.column_stack([features_Coordx, features_Coordy, features_target])

            # ------------- TrainFeatures: project dense values onto the samples
            maximum = len(self.data_ctrl.data)
            progress = self._create_progress_dialog(
                self.tr('Gerando covariáveis em TrainFeatures: ') + Cord_Z + '...', maximum)

            vt_dense = features_dense[:, 2]
            gridxy_dense = np.c_[features_dense[:, 0], features_dense[:, 1]]
            tree_dense = spatial.cKDTree(gridxy_dense)

            lista = []
            for cont in range(len(self.data_ctrl.data)):
                p = np.array([self.data_ctrl.data[cont, 0], self.data_ctrl.data[cont, 1]])
                raio_busca = float(self.view.lineEdit_SVM_VBRaio.text())
                neigs = tree_dense.query_ball_point(p, raio_busca)

                if len(neigs) > n_neig:
                    distances, points_idx = tree_dense.query(p, k=n_neig + 1)
                elif len(neigs) < 2:
                    distances, points_idx = tree_dense.query(p, k=3)
                elif len(neigs) < len(features_dense):
                    distances, points_idx = tree_dense.query(p, k=len(neigs) + 1)
                else:
                    distances, points_idx = tree_dense.query(p, k=len(neigs))

                vt_vals_dense = vt_dense[points_idx]

                if int(self.view.lineEdit_SVM_VBNumMax.text()) == 1:
                    value = vt_vals_dense[0]

                if int(self.view.lineEdit_SVM_VBNumMax.text()) > 1:
                    if distances[0] == 0:
                        points_idx = np.delete(points_idx, 0)
                        distances = np.delete(distances, 0)
                        vt_vals_dense = np.delete(vt_vals_dense, 0)
                    else:
                        points_idx = np.delete(points_idx, len(points_idx) - 1)
                        distances = np.delete(distances, len(distances) - 1)
                        vt_vals_dense = np.delete(vt_vals_dense, len(vt_vals_dense) - 1)
                    value = functions.idw(distances, vt_vals_dense, weight_IDW)

                lista.append(value)
                progress.setValue(cont)
                if progress.wasCanceled():
                    progress.close()
                    return
            progress.close()

            arr = np.array(lista).reshape(-1, 1)
            arr_df = pd.DataFrame(np.atleast_2d(arr),
                                  columns=[Cord_Z + '_' + self.view.lineEdit_SVM_VBNumMax.text()])
            self.df_SVM_Trainfeatures = pd.concat([self.df_SVM_Trainfeatures, arr_df], axis=1)
            self.df_SVM_Trainfeatures.to_csv(
                os.path.join(self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_Train_Set.csv'),
                sep=',', index=False, encoding='utf-8')

            # ------------- TestFeatures: project dense values onto the grid
            maximum = (len(self.gridx) * len(self.gridy))
            progress = self._create_progress_dialog(
                self.tr('Gerando grid para os pontos de interpolação (x, y, z): ') + Cord_Z + '...', maximum)

            vt_dense = features_dense[:, 2]
            gridxy_dense = np.c_[features_dense[:, 0], features_dense[:, 1]]
            tree_dense = spatial.cKDTree(gridxy_dense)

            z = np.zeros((self.gridx.shape[0], self.gridy.shape[0]), dtype=float)

            cont = 1
            for i, val1 in enumerate(self.gridx):
                for j, val2 in enumerate(self.gridy):
                    p = np.array([val1, val2])
                    raio_busca = float(self.view.lineEdit_SVM_VBRaio.text())
                    neigs = tree_dense.query_ball_point(p, raio_busca)

                    if len(neigs) > n_neig:
                        distances, points_idx = tree_dense.query(p, k=n_neig + 1)
                    elif len(neigs) < 2:
                        distances, points_idx = tree_dense.query(p, k=3)
                    elif len(neigs) < len(self.df_SVM_Trainfeatures):
                        distances, points_idx = tree_dense.query(p, k=len(neigs) + 1)
                    else:
                        distances, points_idx = tree_dense.query(p, k=len(neigs))

                    vt_vals_dense = vt_dense[points_idx]

                    if int(self.view.lineEdit_SVM_VBNumMax.text()) == 1:
                        value = vt_vals_dense[0]

                    if int(self.view.lineEdit_SVM_VBNumMax.text()) > 1:
                        if distances[0] == 0:
                            points_idx = np.delete(points_idx, 0)
                            distances = np.delete(distances, 0)
                            vt_vals_dense = np.delete(vt_vals_dense, 0)
                        else:
                            points_idx = np.delete(points_idx, len(points_idx) - 1)
                            distances = np.delete(distances, len(distances) - 1)
                            vt_vals_dense = np.delete(vt_vals_dense, len(vt_vals_dense) - 1)
                        value = functions.idw(distances, vt_vals_dense, weight_IDW)

                    z[i, j] = value
                    cont += 1
                    progress.setValue(cont)
                    if progress.wasCanceled():
                        progress.close()
                        return
            progress.close()

            maximum = (len(self.gridx) * len(self.gridy))
            progress = self._create_progress_dialog(
                self.tr('Aplicando Área de Contorno ao grid dos pontos de interpolação: ') + Cord_Z + '...', maximum)

            lista = []
            if data_view.checkBox_Area_Contorno.isChecked():
                polygono = np.array(self.data_ctrl.df_limite, dtype=float)
                bbPath = mplPath.Path(polygono)
                cont = 1
                for i in range(len(self.gridx)):
                    for j in range(len(self.gridy)):
                        ponto = (self.gridx[i] + (self.data_ctrl.Pixel_Size_X / 2),
                                 self.gridy[j] - (self.data_ctrl.Pixel_Size_X / 2))
                        if bbPath.contains_point(ponto):
                            lista.append([z[i, j]])
                        cont += 1
                        progress.setValue(cont)
                        if progress.wasCanceled():
                            progress.close()
                            return
            else:
                cont = 1
                for i in range(len(self.gridx)):
                    for j in range(len(self.gridy)):
                        lista.append([z[i, j]])
                        cont += 1
                        progress.setValue(cont)
                        if progress.wasCanceled():
                            progress.close()
                            return
            progress.close()

            arr = np.array(lista)
            self.features_grid = np.column_stack([self.features_grid, arr])
            arr = arr.reshape(-1, 1)
            arr_df = pd.DataFrame(np.atleast_2d(arr),
                                  columns=[Cord_Z + '_' + self.view.lineEdit_SVM_VBNumMax.text()])
            self.df_SVM_Testfeatures = pd.concat([self.df_SVM_Testfeatures, arr_df], axis=1)
            self.df_SVM_Testfeatures.to_csv(
                os.path.join(self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_Test_Set.csv'),
                sep=',', index=False, encoding='utf-8')

        # ----------------------------------------------- fill TrainFeatures table
        maximum = len(self.df_SVM_Trainfeatures.index)
        progress = self._create_progress_dialog(self.tr('Preenchendo a Tabela TrainFeatures') + '...', maximum)

        self.view.datatable_SVM_Trainfeatures.setColumnCount(len(self.df_SVM_Trainfeatures.columns))
        self.view.datatable_SVM_Trainfeatures.setRowCount(len(self.df_SVM_Trainfeatures.index))

        try:
            cols = list(self.df_SVM_Trainfeatures.columns.values)
            self.view.datatable_SVM_Trainfeatures.setHorizontalHeaderLabels(cols)
        except AttributeError:
            self._show_warning(self.tr('Mensagem'), self.tr('Erro ao carregar tabela. Valor Inválido!'))

        cont = 1
        try:
            last_col = len(self.df_SVM_Trainfeatures.columns) - 1
            for i in range(len(self.df_SVM_Trainfeatures.index)):
                valor = self.df_SVM_Trainfeatures.iloc[i, last_col]
                try:
                    if valor.dtype == "float64":
                        valor = '%.3f' % valor
                except AttributeError:
                    pass
                self.view.datatable_SVM_Trainfeatures.setItem(i, last_col, QTableWidgetItem(str(valor)))
                cont += 1
                progress.setValue(cont)
                if progress.wasCanceled():
                    progress.close()
                    return
        except AttributeError:
            self._show_warning(self.tr('Mensagem'), self.tr('Erro ao carregar tabela. Valor Inválido!'))

        progress.close()

        self.view.datatable_SVM_Trainfeatures.resizeColumnsToContents()
        self.view.datatable_SVM_Trainfeatures.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)

        self.df_SVM_Trainfeatures.to_csv(
            os.path.join(self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_Train_Set.csv'),
            sep=',', index=False, encoding='utf-8')

        self.SVM_Add_Feature = True

        self.view.pushButton_SVM.setEnabled(True)
        self.view.label_SVM.hide()
        self.view.datatable_pontos_interpolados_SVM.setColumnCount(0)
        self.view.datatable_pontos_interpolados_SVM.setRowCount(0)

        self.view.label_validacao_cruzada_SVM.hide()
        self.view.datatable_validacao_cruzada_SVM.setColumnCount(0)
        self.view.datatable_validacao_cruzada_SVM.setRowCount(0)

        self.view.comboBox_SVM_Features_Adds.setEnabled(True)
        self.view.pushButton_SVM_Remove_Feature.setEnabled(True)

    # ====================================================== ADD SELECTED FEATURES
    def on_add_selected_features_clicked(self):
        """Re-invoke the add-feature pipeline for each Moran-selected variable.

        Full port of pushButton_SVM_Add_Selected_Features_clicked.
        """
        msg = QMessageBox.question(
            self.view, self.tr('Mensagem'),
            self.tr('As variáveis selecionadas serão adicionadas ao modelo SVM. Deseja continuar?'),
            QMessageBox.Yes | QMessageBox.No)

        if msg != QMessageBox.Yes:
            return

        for v in range(len(self.list_rows_moran)):
            row = self.list_rows_moran[v]
            v_target = self.view.datatable_moran.item(row, 1).text()
            self.view.comboBox_SVM_Features.setCurrentText(v_target)
            self.view.tabWidget_Interpolacao_SVM.setCurrentIndex(0)
            self.on_add_feature_clicked()

    # ====================================================== MORAN CHECKBOX
    def on_moran_checkbox_clicked(self, item):
        """Maintain list_rows_moran and toggle the add-selected button.

        Full port of datatable_moran_checkbox_clicked.
        """
        if item.checkState() == QtCore.Qt.Checked:
            if item.row() not in self.list_rows_moran:
                self.list_rows_moran.append(item.row())
                self.list_rows_moran.sort()
        else:
            if item.row() in self.list_rows_moran:
                self.list_rows_moran.remove(item.row())

        self.view.pushButton_SVM_Add_Selected_Features.setEnabled(len(self.list_rows_moran) > 0)

    # ====================================================== REMOVE FEATURE
    def on_remove_feature_clicked(self):
        """Remove a covariate from the SVM model.

        Full port of pushButton_SVM_Remove_Feature_clicked.
        """
        if len(self.list_cov_SVM) == 2:  # only X and Y -> cannot remove coordinates
            self._show_warning(
                self.tr('Mensagem'),
                self.tr('Todas as Covariáveis do Modelo SVM foram removidas.'))
            return

        id_col = self.view.comboBox_SVM_Features_Adds.currentIndex()

        if id_col >= 2:
            self.view.tabWidget_Interpolacao_SVM.setCurrentIndex(0)

            list_cov_SVM_Index = [i for i in range(self.view.comboBox_SVM_Features_Adds.count())]
            list_cov_SVM_Index.remove(id_col)

            self.view.comboBox_SVM_Features_Adds.removeItem(id_col)

            self.features_grid = np.delete(self.features_grid, id_col, 1)

            self.list_cov_SVM = [self.view.comboBox_SVM_Features_Adds.itemText(i)
                                 for i in range(self.view.comboBox_SVM_Features_Adds.count())]

            if len(self.list_cov_SVM) == 2:  # only coordinates (X, Y) left
                self.SVM_Add_Feature = False
                self.view.pushButton_SVM_Remove_Feature.setEnabled(False)

            self.df_SVM_Trainfeatures = self.df_SVM_Trainfeatures.iloc[:, list_cov_SVM_Index]
            self.df_SVM_Testfeatures = self.df_SVM_Testfeatures.iloc[:, list_cov_SVM_Index]

            self.view.label_SVM.hide()
            self.view.datatable_pontos_interpolados_SVM.setColumnCount(0)
            self.view.datatable_pontos_interpolados_SVM.setRowCount(0)

            self.view.label_validacao_cruzada_SVM.hide()
            self.view.datatable_validacao_cruzada_SVM.setColumnCount(0)
            self.view.datatable_validacao_cruzada_SVM.setRowCount(0)

            self.view.datatable_SVM_Trainfeatures.removeColumn(id_col)
            self.view.datatable_SVM_Trainfeatures.resizeColumnsToContents()
            self.view.datatable_SVM_Trainfeatures.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)

            self.df_SVM_Trainfeatures.to_csv(
                os.path.join(self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_Train_Set.csv'),
                sep=',', index=False, encoding='utf-8')
            self.df_SVM_Testfeatures.to_csv(
                os.path.join(self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_Test_Set.csv'),
                sep=',', index=False, encoding='utf-8')
        else:
            self._show_warning(
                self.tr('Mensagem'),
                self.tr('As Coordenadas (x, y) não podem ser removidas do Modelo SVM.'))

    # ====================================================== MORAN (spatial corr)
    def on_moran_toggled(self, checked):
        """Calculate / display Moran's I bivariate correlation.

        Ported from checkBox_Moran_clicked + correlacao_Moran_BV.
        """
        if not checked:
            self.list_rows_moran = []
            self.view.datatable_moran.setColumnCount(0)
            self.view.datatable_moran.setRowCount(0)
            return

        try:
            if self.view.comboBox_SVM_Fonte.currentIndex() == 0:
                self._correlacao_Moran_BV(self.data_ctrl.df, use_check=True)
            else:
                if len(self.list_cov_SVM) >= 2:
                    df_Trainfeatures = pd.concat(
                        [self.df_SVM_Trainfeatures, self.data_ctrl.df[[self.data_ctrl.v_target]]], axis=1)
                    self._correlacao_Moran_BV(df_Trainfeatures, use_check=False)
        except Exception as e:
            self._show_warning(self.tr('Erro'), str(e))

    def _correlacao_Moran_BV(self, dataframe, use_check):
        """Compute and render the Moran bivariate table (ported from correlacao_Moran_BV)."""
        df_moran = functions.calculate_index_moran_BV(
            dataframe, self.data_ctrl.Cord_X, self.data_ctrl.Cord_Y, self.data_ctrl.v_target)

        df_moran = df_moran[df_moran.Covariavel != 'ID']
        df_moran = df_moran[df_moran.Covariavel != 'ID_SM']

        if use_check is True:
            self.view.datatable_moran.setColumnCount(len(df_moran.columns) + 1)
        else:
            self.view.datatable_moran.setColumnCount(len(df_moran.columns))

        self.view.datatable_moran.setRowCount(len(df_moran.index))

        try:
            if use_check is True:
                cols = [self.tr('Marcar')] + list(df_moran.columns.values)
            else:
                cols = list(df_moran.columns.values)
            self.view.datatable_moran.setHorizontalHeaderLabels(cols)
        except AttributeError:
            self._show_warning(self.tr('Mensagem'), self.tr('Erro ao carregar tabela. Valor Inválido!'))

        try:
            for i in range(len(df_moran.index)):
                if use_check is True:
                    chkBoxItem = QTableWidgetItem()
                    chkBoxItem.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
                    chkBoxItem.setCheckState(QtCore.Qt.Unchecked)
                    self.view.datatable_moran.setItem(i, 0, chkBoxItem)

                for j in range(len(df_moran.columns)):
                    valor = df_moran.iloc[i, j]
                    if isinstance(valor, str):
                        valor = QTableWidgetItem(valor)
                    else:
                        try:
                            if valor.dtype == "float64":
                                valor = '%.3f' % valor
                        except AttributeError:
                            pass
                        valor = QTableWidgetItem(str(valor))

                    if use_check is True:
                        self.view.datatable_moran.setItem(i, j + 1, valor)
                    else:
                        self.view.datatable_moran.setItem(i, j, valor)
        except AttributeError:
            self._show_warning(self.tr('Mensagem'), self.tr('Erro ao carregar tabela. Valor Inválido!'))

        self.view.datatable_moran.resizeColumnsToContents()
        self.view.datatable_moran.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)

    # ====================================================== RFE
    def on_rfe_toggled(self, checked):
        """Run RFE feature selection (ported from checkBox_RFE_clicked + Recursive_Feature_Elimination)."""
        if not checked:
            self.view.datatable_RFE.setColumnCount(0)
            self.view.datatable_RFE.setRowCount(0)
            return

        try:
            progress = self._create_progress_dialog(
                self.tr('Seleção de Variáveis') + ' - ' + self.tr('Recursive Feature Elimination (RFE)') + '...', 5)
            progress.setValue(1)

            filename = os.path.join(self.path_absolute, '0_Dados.csv')
            df = pd.read_csv(filename, sep=',')
            df = functions.eliminar_outlier(df, self.data_ctrl.v_target)

            progress.setValue(3)
            if progress.wasCanceled():
                progress.close()
                return

            self._recursive_feature_elimination(df)

            progress.setValue(4)
            progress.close()
        except Exception as e:
            self._show_warning(self.tr('Erro'), str(e))

    def _recursive_feature_elimination(self, dataframe):
        """Compute and render the RFE importance table (ported from Recursive_Feature_Elimination)."""
        df_RFE = functions.selected_features_RFE(
            dataframe, self.data_ctrl.Cord_X, self.data_ctrl.Cord_Y, self.data_ctrl.v_target)

        self.view.datatable_RFE.setColumnCount(len(df_RFE.columns))
        self.view.datatable_RFE.setRowCount(len(df_RFE.index))

        try:
            cols = list(df_RFE.columns.values)
            cols[0] = self.tr(cols[0])
            cols[1] = self.tr(cols[1])
            self.view.datatable_RFE.setHorizontalHeaderLabels(cols)
        except AttributeError:
            self._show_warning(self.tr('Mensagem'), self.tr('Erro ao carregar tabela. Valor Inválido!'))

        try:
            for i in range(len(df_RFE.index)):
                for j in range(len(df_RFE.columns)):
                    valor = df_RFE.iloc[i, j]
                    if isinstance(valor, str):
                        valor = QTableWidgetItem(valor)
                    else:
                        try:
                            if valor.dtype == "float64":
                                valor = '%.3f' % valor
                        except AttributeError:
                            pass
                        valor = QTableWidgetItem(str(valor))
                    self.view.datatable_RFE.setItem(i, j, valor)
        except AttributeError:
            self._show_warning(self.tr('Mensagem'), self.tr('Erro ao carregar tabela. Valor Inválido!'))

        self.view.datatable_RFE.resizeColumnsToContents()
        self.view.datatable_RFE.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)

    # ====================================================== SVM EXECUTE
    def on_svm_clicked(self):
        """Train the SVM and predict on the engineered grid covariates.

        Full port of pushButton_SVM_clicked. Uses functions.svr_param_selection for
        C/gamma (GridSearchCV) and predicts on features_grid (engineered covariates),
        not coords-only. Exports raster/vector via the data_ctrl delegators.
        """
        try:
            self.view.tabWidget_Interpolacao_SVM.setCurrentIndex(2)
            data_view = self.data_view

            # Seed Test grid (X, Y) when the dataframe is empty.
            if len(self.df_SVM_Testfeatures) == 0:
                self.gridx = np.arange(float(self.data_ctrl.Cord_X_min), float(self.data_ctrl.Cord_X_max), self.data_ctrl.Pixel_Size_X)
                self.gridy = np.arange(float(self.data_ctrl.Cord_Y_min), float(self.data_ctrl.Cord_Y_max), self.data_ctrl.Pixel_Size_Y)

                maximum = (len(self.gridx) * len(self.gridy))
                progress = self._create_progress_dialog(self.tr('Machine Learning - Support Vector Machine...'), maximum)

                cont = 1
                lista_xy = []
                for i in range(len(self.gridx)):
                    for j in range(len(self.gridy)):
                        lista_xy.append([self.gridx[i] + (self.data_ctrl.Pixel_Size_X / 2),
                                         self.gridy[j] - (self.data_ctrl.Pixel_Size_Y / 2)])
                        cont += 1
                        progress.setValue(cont)
                        if progress.wasCanceled():
                            progress.close()
                            return
                progress.close()

                arr_xy = np.array(lista_xy)

                if data_view.checkBox_Area_Contorno.isChecked():
                    if self.data_ctrl.df_limite is None or len(self.data_ctrl.df_limite) <= 0:
                        if data_view.mMapLayerComboBox_AreaCont.currentIndex() >= 0:
                            if getattr(self.data_ctrl, 'grid_ctrl', None) is not None:
                                self.data_ctrl.grid_ctrl.on_contour_apply_clicked()

                    lista_cut_xy = []
                    polygono = np.array(self.data_ctrl.df_limite, dtype=float)
                    bbPath = mplPath.Path(polygono)

                    maximum = len(arr_xy)
                    progress = self._create_progress_dialog(
                        self.tr('Gerando grid para os pontos de interpolação (x, y, z): '), maximum)
                    cont = 1
                    for i in range(len(arr_xy)):
                        ponto = (arr_xy[i, 0], arr_xy[i, 1])
                        if bbPath.contains_point(ponto):
                            lista_cut_xy.append([arr_xy[i, 0], arr_xy[i, 1]])
                        cont += 1
                        progress.setValue(cont)
                        if progress.wasCanceled():
                            progress.close()
                            return
                    progress.close()
                    arr_xy = np.array(lista_cut_xy)

                self.grid_xy = np.array(arr_xy)
                self.df_SVM_Testfeatures = pd.DataFrame(
                    np.atleast_2d(self.grid_xy), columns=[self.data_ctrl.Cord_X, self.data_ctrl.Cord_Y])
                self.features_grid = np.array(self.grid_xy)

            # k-folds: 20 points per fold, clamped to [2, 5].
            k_folds = round(len(self.data_ctrl.data) / 20)
            if k_folds < 2:
                k_folds = 2
            elif k_folds > 5:
                k_folds = 5

            features = np.array(self.df_SVM_Trainfeatures, dtype=float)
            labels = np.array(self.df_SVM_Trainlabels, dtype=float)

            maximum = (len(self.grid_xy) * 3) + 5
            progress = self._create_progress_dialog(self.tr('Machine Learning - Support Vector Machine...'), maximum)

            cont = 1
            progress.setValue(cont)
            if progress.wasCanceled():
                progress.close()
                return

            # GridSearchCV for C / gamma.
            self.norm = StandardScaler()
            C_average, gamma_average = functions.svr_param_selection(self.norm, features, labels, k_folds)

            cont += 1
            progress.setValue(cont)
            if progress.wasCanceled():
                progress.close()
                return

            self.svr = svm.SVR(kernel='rbf', C=C_average, gamma=gamma_average)

            train_features, test_features, train_labels, test_labels = train_test_split(
                features, labels, test_size=1, random_state=42)

            train_features = np.copy(features)
            train_labels = np.copy(labels)
            test_features = np.copy(self.features_grid)

            self.norm = self.norm.fit(train_features)
            train_features = self.norm.transform(train_features)
            test_features = self.norm.transform(test_features)

            self.svr.fit(train_features, train_labels)
            predictions = self.svr.predict(test_features)

            self.arr_cut = np.column_stack([self.grid_xy[:, 0], self.grid_xy[:, 1], predictions])

            df_pontos_interpolados_SVM = pd.DataFrame(
                np.atleast_2d(self.arr_cut),
                columns=[self.data_ctrl.Cord_X, self.data_ctrl.Cord_Y, self.data_ctrl.v_target])
            df_pontos_interpolados_SVM.to_csv(
                os.path.join(self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_Grid_Map.csv'),
                sep=',', index=False, encoding='utf-8')
            df_pontos_interpolados_SVM.to_csv(
                os.path.join(self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_Grid_Map.svm'),
                sep=',', index=False, encoding='utf-8')

            self.view.datatable_pontos_interpolados_SVM.setColumnCount(len(df_pontos_interpolados_SVM.columns))
            self.view.datatable_pontos_interpolados_SVM.setRowCount(len(df_pontos_interpolados_SVM.index))

            try:
                cols = list(df_pontos_interpolados_SVM.columns.values)
                cols[2] = self.tr('Z.Predito')
                self.view.datatable_pontos_interpolados_SVM.setHorizontalHeaderLabels(cols)
            except AttributeError:
                self._show_warning(self.tr('Mensagem'), self.tr('Erro ao carregar tabela. Valor Inválido!'))

            try:
                for i in range(len(df_pontos_interpolados_SVM.index)):
                    for j in range(len(df_pontos_interpolados_SVM.columns)):
                        valor = df_pontos_interpolados_SVM.iloc[i, j]
                        try:
                            if valor.dtype == "float64":
                                valor = '%.3f' % valor
                        except AttributeError:
                            pass
                        self.view.datatable_pontos_interpolados_SVM.setItem(i, j, QTableWidgetItem(str(valor)))
                        cont += 1
                        progress.setValue(cont)
                        if progress.wasCanceled():
                            progress.close()
                            return
            except AttributeError:
                self._show_warning(self.tr('Mensagem'), self.tr('Erro ao carregar tabela. Valor Inválido!'))

            self.view.datatable_pontos_interpolados_SVM.resizeColumnsToContents()
            self.view.datatable_pontos_interpolados_SVM.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)

            # ----------------------------------------------------- raster/vector export
            cont += 1
            progress.setValue(cont)
            if progress.wasCanceled():
                progress.close()
                return

            if data_view.checkBox_Qgis_Raster.isChecked():
                Input_Table = '1_SVM_' + self.data_ctrl.VTarget_FileName + '_Grid_Map.csv'
                Output_Layer_File_tiff = os.path.join(
                    self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_Grid_Map.tiff')
                Output_Layer_Name = '1_SVM_' + self.data_ctrl.VTarget_FileName
                z_field = self.data_ctrl.v_target

                try:
                    data_view.mMapLayerComboBox.currentIndexChanged.disconnect()
                except TypeError:
                    pass

                Output_Layer_File_tiff = self.data_ctrl.export_raster_to_qgis(
                    Input_Table, Output_Layer_File_tiff, Output_Layer_Name, z_field)

                if data_view.checkBox_Qgis_Vector_Points.isChecked():
                    if (data_view.checkBox_Area_Contorno.isChecked() and
                            data_view.mMapLayerComboBox_AreaCont.currentIndex() >= 0):
                        cont += 1
                        progress.setValue(cont)
                        if progress.wasCanceled():
                            progress.close()
                            return
                        self.data_ctrl.export_shapefile_to_qgis(Output_Layer_File_tiff, "native:pixelstopoints")
                    else:
                        data_view.checkBox_Qgis_Vector_Points.setChecked(False)

                if data_view.checkBox_Qgis_Vector_Polygons.isChecked():
                    if (data_view.checkBox_Area_Contorno.isChecked() and
                            data_view.mMapLayerComboBox_AreaCont.currentIndex() >= 0):
                        cont += 1
                        progress.setValue(cont)
                        if progress.wasCanceled():
                            progress.close()
                            return
                        self.data_ctrl.export_shapefile_to_qgis(Output_Layer_File_tiff, "native:pixelstopolygons")
                    else:
                        data_view.checkBox_Qgis_Vector_Polygons.setChecked(False)

            if data_view.checkBox_Qgis_Raster.isChecked():
                try:
                    data_view.mMapLayerComboBox.currentIndexChanged.connect(
                        self.data_ctrl.on_layer_combo_changed)
                except (AttributeError, TypeError):
                    pass

            # ----------------------------------------------------- plot interpolated map
            cont += 1
            progress.setValue(cont)
            if progress.wasCanceled():
                progress.close()
                return

            self._plot_interpolated_map(predictions)

            self.SVM = True

            # TODO(zones domain): self.load_maps_to_generate_ZM() once the zones
            # controller exposes the ZM map-loading port.

            progress.close()

        except Exception as e:
            self._show_warning(self.tr('Erro'), self.tr('Erro na SVM') + ': ' + str(e))

    def _plot_interpolated_map(self, predictions):
        """Render the SVM interpolated map and set the label pixmap."""
        plt3.close()
        plt3.title(self.tr('Mapa Interpolado SVM'))
        plt3.xlabel('Longitude (X)')
        plt3.ylabel('Latitude  (Y)')

        x_min = self.data_ctrl.Cord_X_min
        x_max = self.data_ctrl.Cord_X_max
        y_min = self.data_ctrl.Cord_Y_min
        y_max = self.data_ctrl.Cord_Y_max

        plt3.xlim(float(x_min - 100), float(x_max + 100))
        plt3.ylim(float(y_min - 100), float(y_max + 100))

        interval_x = int((x_max - x_min) / 5)
        if interval_x == 0:
            interval_x = 1
        plt3.xticks([i for i in range(int(x_min), int(x_max), interval_x)])

        interval_y = int((y_max - y_min) / 7)
        if interval_y == 0:
            interval_y = 1
        plt3.yticks([i for i in range(int(y_min), int(y_max), interval_y)])

        plt3.scatter(self.grid_xy[:, 0], self.grid_xy[:, 1], c=predictions,
                     cmap='RdYlGn', vmin=min(predictions), vmax=max(predictions))

        clb = plt3.colorbar(aspect=20)
        clb.ax.set_title(self.data_ctrl.v_target)

        plt3.subplots_adjust(wspace=0.6, hspace=0.6, left=0.15, right=1.0, bottom=0.1, top=0.95)
        plt3.ticklabel_format(style='plain', useOffset=False, axis='both')
        ax = plt3.gca()
        ax.format_coord = lambda x, y: '%10d, %10d' % (x, y)

        png_path = os.path.join(self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_Grid_Map.png')
        plt3.savefig(png_path)

        pixmap = QPixmap(png_path)
        self.view.label_SVM.show()
        self.view.label_SVM.setPixmap(pixmap)

        if self._show_maps_checked():
            plt3.show()

    # ====================================================== CROSS VALIDATION
    def on_svm_cross_validation_clicked(self):
        """Leave-one-out cross-validation for the SVM.

        Full port of pushButton_Validacao_Cruzada_SVM_clicked. GridSearchCV once for
        C/gamma; k-folds = round(len/20) clamped [2,5]; statistics via
        functions.calculate_statistics; regression scatter + _CV.png + CSV export.
        """
        try:
            k_folds = round(len(self.data_ctrl.data) / 20)
            if k_folds < 2:
                k_folds = 2
            elif k_folds > 5:
                k_folds = 5

            features = np.array(self.df_SVM_Trainfeatures, dtype=float)
            labels = np.array(self.df_SVM_Trainlabels, dtype=float)

            maximum = len(features) + (len(features) * 4) + 3
            progress = self._create_progress_dialog(self.tr('Validação Cruzada - SVM'), maximum)

            progress.setValue(1)
            if progress.wasCanceled():
                progress.close()
                return

            self.norm = StandardScaler()
            C_average, gamma_average = functions.svr_param_selection(self.norm, features, labels, k_folds)

            progress.setValue(2)
            if progress.wasCanceled():
                progress.close()
                return

            self.svr = svm.SVR(kernel='rbf', C=C_average, gamma=gamma_average)

            labels_SVM_CV = None
            for cont in range(len(features)):
                train_features = np.copy(features)
                train_labels = np.copy(labels)

                test_features = train_features[cont:cont + 1, :]

                train_features = np.delete(train_features, (cont), axis=0)
                train_labels = np.delete(train_labels, (cont), axis=0)

                self.norm = self.norm.fit(train_features)
                train_features = self.norm.transform(train_features)
                test_features = self.norm.transform(test_features)

                self.svr.fit(train_features, train_labels)
                predictions = self.svr.predict(test_features)

                if cont == 0:
                    labels_SVM_CV = np.copy(predictions)
                else:
                    labels_SVM_CV = np.vstack((labels_SVM_CV, predictions))

                progress.setValue(cont + 2)
                if progress.wasCanceled():
                    progress.close()
                    return

            labels_SVM_CV = labels_SVM_CV.reshape(len(labels_SVM_CV))

            data_CV_SVM = np.column_stack((features[:, 0], features[:, 1], labels, labels_SVM_CV))

            self.df_CV_SVM = pd.DataFrame(
                np.atleast_2d(data_CV_SVM),
                columns=['Coord_X', 'Coord_Y', self.tr('Z.Obs.'), self.tr('Z.Predito')])
            self.df_CV_SVM.to_csv(
                os.path.join(self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_CV.csv'),
                sep=',', index=False, encoding='utf-8')

            self.view.datatable_validacao_cruzada_SVM.setColumnCount(len(self.df_CV_SVM.columns))
            self.view.datatable_validacao_cruzada_SVM.setRowCount(len(self.df_CV_SVM.index))

            try:
                cols = list(self.df_CV_SVM.columns.values)
                self.view.datatable_validacao_cruzada_SVM.setHorizontalHeaderLabels(cols)
            except AttributeError:
                self._show_warning(self.tr('Mensagem'), self.tr('Erro ao carregar tabela. Valor Inválido!'))

            try:
                for i in range(len(self.df_CV_SVM.index)):
                    for j in range(len(self.df_CV_SVM.columns)):
                        valor = self.df_CV_SVM.iloc[i, j]
                        try:
                            if valor.dtype == "float64":
                                valor = '%.3f' % valor
                        except AttributeError:
                            pass
                        self.view.datatable_validacao_cruzada_SVM.setItem(i, j, QTableWidgetItem(str(valor)))
                        cont += 1
                        progress.setValue(cont + 2)
                        if progress.wasCanceled():
                            progress.close()
                            return
            except AttributeError:
                self._show_warning(self.tr('Mensagem'), self.tr('Erro ao carregar tabela. Valor Inválido!'))

            self.view.datatable_validacao_cruzada_SVM.resizeColumnsToContents()
            self.view.datatable_validacao_cruzada_SVM.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)

            progress.setValue(cont + 3)
            if progress.wasCanceled():
                progress.close()
                return

            # Statistics + regression scatter plot.
            RMSE_lib, R2_RCV, regressor, R2_Elp, lccc = functions.calculate_statistics(labels_SVM_CV, labels)

            RMSE_lib = '%.3f' % RMSE_lib
            R2_RCV = '%.3f' % R2_RCV

            intercept = regressor.intercept_[0]
            slope = regressor.coef_[0][0]

            x_min = min(labels_SVM_CV.min(), labels.min())
            x_max = max(labels_SVM_CV.max(), labels.max())

            x_min = x_min - abs(intercept)
            if x_min < 0:
                x_min = 0
            x_max = x_max + abs(intercept)

            plt5.close()
            plt5.title(self.tr('Validação Cruzada - SVM') + '   ' +
                       self.tr('RMSE:') + ' ' + str(RMSE_lib) + '   $R^2$ : ' + str(R2_RCV))

            plt5.xlim(x_min, x_max)
            plt5.ylim(x_min, x_max)

            plt5.xlabel(self.tr('Valor Predito') + ' - ' + self.data_ctrl.v_target)
            plt5.ylabel(self.tr('Valor Observado') + ' - ' + self.data_ctrl.v_target)

            plt5.scatter(labels_SVM_CV, labels, marker='s', color='blue')
            plt5.plot([x_min, x_max], [x_min, x_max], linestyle=':', color='black')

            labels_SVM_CV_line = np.append(0, labels_SVM_CV)
            labels_SVM_CV_line = np.append(labels_SVM_CV_line, x_max)

            line = slope * labels_SVM_CV_line + intercept

            if intercept >= 0:
                plt5.plot(labels_SVM_CV_line, line, color='black',
                          label='y={:.3f}x+{:.3f}'.format(slope, intercept))
            else:
                plt5.plot(labels_SVM_CV_line, line, color='black',
                          label='y={:.3f}x-{:.3f}'.format(slope, abs(intercept)))

            plt5.legend(loc='upper left')
            plt5.legend()
            plt5.ticklabel_format(style='plain', useOffset=False, axis='both')
            ax = plt5.gca()
            ax.format_coord = lambda x, y: '%10d, %10d' % (x, y)

            png_path = os.path.join(self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_CV.png')
            plt5.savefig(png_path)

            pixmap = QPixmap(png_path)
            self.view.label_validacao_cruzada_SVM.show()
            self.view.label_validacao_cruzada_SVM.setPixmap(pixmap)

            if self._show_maps_checked():
                plt5.show()

            progress.close()
            self.Validacao_Cruzada_SVM = True
            self.view.tabWidget_Interpolacao_SVM.setCurrentIndex(1)

        except Exception as e:
            self._show_warning(self.tr('Erro'), self.tr('Erro na Validação Cruzada') + ': ' + str(e))

    # ====================================================== TABLE / LABEL HANDLERS
    def on_train_features_table_double_clicked(self, item=None):
        """Open the train/test CSVs (ported from datatable_SVM_Trainfeatures_doubleClicked)."""
        try:
            os.startfile(os.path.join(
                self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_Train_Set.csv'))
            os.startfile(os.path.join(
                self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_Test_Set.csv'))
        except (AttributeError, OSError):
            pass

    def on_interpolated_svm_points_table_double_clicked(self, item=None):
        """Open the interpolated-points CSV (ported from datatable_pontos_interpolados_SVM_doubleClicked)."""
        try:
            os.startfile(os.path.join(
                self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_Grid_Map.csv'))
        except (AttributeError, OSError):
            pass

    def on_svm_cross_validation_table_double_clicked(self, item=None):
        """Open the cross-validation CSV (ported from datatable_validacao_cruzada_SVM_doubleClicked)."""
        try:
            os.startfile(os.path.join(
                self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_CV.csv'))
        except (AttributeError, OSError):
            pass

    def on_svm_label_clicked(self, value):
        """Open the SVM map PNG (ported from label_SVM_clicked)."""
        if system != 'Darwin' and Image is not None and self.SVM is True:
            try:
                image = Image.open(os.path.join(
                    self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_Grid_Map.png'))
                image.show()
            except (AttributeError, OSError):
                pass

    def on_svm_cross_validation_label_clicked(self, value):
        """Open the CV PNG (ported from label_validacao_cruzada_SVM_clicked)."""
        if system != 'Darwin' and Image is not None and self.Validacao_Cruzada_SVM is True:
            try:
                image = Image.open(os.path.join(
                    self.path_absolute, '1_SVM_' + self.data_ctrl.VTarget_FileName + '_CV.png'))
                image.show()
            except (AttributeError, OSError):
                pass

    # --------------------------------------------------------------- helpers
    def _show_maps_checked(self):
        """Whether 'Exibir Mapas' is checked (the checkbox lives on the kriging tab)."""
        chk = getattr(self.data_view, 'checkBox_Qgis_Maps', None)
        if chk is not None:
            return chk.isChecked()
        return False

    def _create_progress_dialog(self, label, max_val):
        """Create progress dialog."""
        progress = QProgressDialog(label, self.tr('Cancelar'), 1, max_val, self.view)
        progress.setWindowTitle('Smart-Map')
        progress.show()
        progress.setCancelButton(None)
        progress.setWindowModality(QtCore.Qt.WindowModal)
        time.sleep(0.1)
        return progress

    def _show_warning(self, title, message):
        """Show warning message."""
        msg_box = QMessageBox()
        msg_box.setWindowIcon(QIcon(self.icon_path))
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec_()
