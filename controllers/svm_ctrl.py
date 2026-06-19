# -*- coding: utf-8 -*-
"""Support Vector Machine (SVM) controller."""

import os
import time
import numpy as np
import pandas as pd
import matplotlib.path as mplPath

from qgis.PyQt import QtCore, QtWidgets, QtGui
from qgis.PyQt.QtWidgets import QMessageBox, QTableWidgetItem, QProgressDialog
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsMapLayerType


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

        # SVM state
        self.df_SVM_Trainfeatures = pd.DataFrame()
        self.df_SVM_Testfeatures = pd.DataFrame()
        self.df_moran = None
        self.list_cov_SVM = [self.data_ctrl.Cord_X, self.data_ctrl.Cord_Y]  # Start with coords
        self.list_rows_moran = []
        self.SVM_Add_Coord = False
        self.cols_table_atribute_dense = []

    # Source layer & feature selection
    def on_source_layer_combo_changed(self, index):
        """Handle source data layer selection (training vs dense layer)."""
        if index == 0:  # Training data from attribute table
            self.dialog.mMapLayerComboBox_DenseLayer.setEnabled(False)
        else:  # Dense layer for additional features
            self.dialog.mMapLayerComboBox_DenseLayer.setEnabled(True)
            self.on_dense_layer_combo_changed(0)

    def on_dense_layer_combo_changed(self, index):
        """Load features from selected dense layer."""
        if self.dialog.comboBox_SVM_Fonte.currentIndex() != 1:
            return

        if self.dialog.mMapLayerComboBox_DenseLayer.currentIndex() < 0:
            return

        layer = self.dialog.mMapLayerComboBox_DenseLayer.currentLayer()

        # Validate CRS
        if layer.crs().authid() != self.data_ctrl.Cord_X:  # Simplified - use actual CRS check
            self._show_warning(
                self.tr('Mensagem'),
                self.tr('O CRS da Layer selecionada é diferente do CRS da Layer da Tabela de Atributos.')
            )
            return

        # Load fields based on layer type
        if layer.type() == QgsMapLayerType.RasterLayer:
            self.dialog.comboBox_SVM_Features.clear()
            self.dialog.comboBox_SVM_Features.setEnabled(False)
        else:  # Vector layer
            self.cols_table_atribute_dense = layer.fields().names()
            self.dialog.comboBox_SVM_Features.clear()
            self.dialog.comboBox_SVM_Features.addItems(self.cols_table_atribute_dense)
            self.dialog.comboBox_SVM_Features.setEnabled(True)

    # Feature management
    def on_add_feature_clicked(self):
        """Add selected feature to SVM training set."""
        feature_name = self.dialog.comboBox_SVM_Features.currentText()
        if not feature_name:
            return

        if feature_name not in self.list_cov_SVM:
            self.list_cov_SVM.append(feature_name)
            self._update_train_features()

    def on_add_selected_features_clicked(self):
        """Add selected features (from Moran table) to model."""
        selected_rows = self.dialog.datatable_moran.selectedIndexes()
        for index in selected_rows:
            row = index.row()
            if row in self.list_rows_moran:
                feature_name = self.dialog.datatable_moran.item(row, 1).text()
                if feature_name not in self.list_cov_SVM:
                    self.list_cov_SVM.append(feature_name)

        self._update_train_features()

    def on_remove_feature_clicked(self):
        """Remove selected feature from model."""
        feature_name = self.dialog.comboBox_SVM_Features_Adds.currentText()
        if not feature_name or feature_name in [self.data_ctrl.Cord_X, self.data_ctrl.Cord_Y]:
            self._show_warning(
                self.tr('Aviso'),
                self.tr('As Coordenadas (x, y) não podem ser removidas do Modelo SVM.')
            )
            return

        if feature_name in self.list_cov_SVM:
            self.list_cov_SVM.remove(feature_name)
            self._update_train_features()

    def _update_train_features(self):
        """Rebuild training feature set from current feature list."""
        try:
            self.df_SVM_Trainfeatures = self.data_ctrl.df[self.list_cov_SVM].copy()
            self.df_SVM_Testfeatures = self.df_SVM_Trainfeatures.copy()

            # Display in table
            self.dialog.datatable_SVM_Trainfeatures.setColumnCount(len(self.list_cov_SVM))
            self.dialog.datatable_SVM_Trainfeatures.setRowCount(min(10, len(self.df_SVM_Trainfeatures)))
            self.dialog.datatable_SVM_Trainfeatures.setHorizontalHeaderLabels(self.list_cov_SVM)

            for i in range(min(10, len(self.df_SVM_Trainfeatures))):
                for j, col in enumerate(self.list_cov_SVM):
                    value = self.df_SVM_Trainfeatures.iloc[i, j]
                    text = f'{value:.3f}' if isinstance(value, (int, float)) else str(value)
                    self.dialog.datatable_SVM_Trainfeatures.setItem(i, j, QTableWidgetItem(text))

            self.dialog.datatable_SVM_Trainfeatures.setEditTriggers(
                QtWidgets.QTableWidget.NoEditTriggers
            )

            # Save to CSV
            csv_path = os.path.join(self.path_absolute, f'1_SVM_{self.data_ctrl.VTarget_FileName}_Train_Set.csv')
            self.df_SVM_Trainfeatures.to_csv(csv_path, sep=',', index=False, encoding='utf-8')

        except Exception as e:
            self._show_warning(self.tr('Erro'), str(e))

    # Spatial analysis
    def on_moran_toggled(self, checked):
        """Calculate Moran's I for feature selection."""
        if not checked:
            self.dialog.datatable_moran.setColumnCount(0)
            self.dialog.datatable_moran.setRowCount(0)
            return

        try:
            if self.dialog.comboBox_SVM_Fonte.currentIndex() == 0:  # Attribute table
                df_analysis = self.data_ctrl.df
            else:  # Dense layer features
                if len(self.df_SVM_Trainfeatures) == 0:
                    return
                df_analysis = pd.concat(
                    [self.df_SVM_Trainfeatures, self.data_ctrl.df[[self.data_ctrl.v_target]]],
                    axis=1
                )

            # Calculate Moran's I for each variable
            from ..utils import functions
            self.df_moran = functions.calculate_index_moran_BV(
                df_analysis, self.data_ctrl.Cord_X, self.data_ctrl.Cord_Y, self.data_ctrl.v_target
            )

            # Filter out ID columns
            self.df_moran = self.df_moran[self.df_moran.Covariavel != 'ID']
            self.df_moran = self.df_moran[self.df_moran.Covariavel != 'ID_SM']

            # Display in table
            self._display_moran_table()

        except Exception as e:
            self._show_warning(self.tr('Erro'), str(e))

    def _display_moran_table(self):
        """Display Moran results in table."""
        self.dialog.datatable_moran.setColumnCount(len(self.df_moran.columns) + 1)
        self.dialog.datatable_moran.setRowCount(len(self.df_moran.index))

        cols = ['Marcar'] + list(self.df_moran.columns.values)
        self.dialog.datatable_moran.setHorizontalHeaderLabels(cols)

        for i in range(len(self.df_moran.index)):
            # Checkbox in first column
            chk = QtWidgets.QTableWidgetItem()
            chk.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            chk.setCheckState(QtCore.Qt.Unchecked)
            self.dialog.datatable_moran.setItem(i, 0, chk)

            # Values in other columns
            for j in range(len(self.df_moran.columns)):
                value = self.df_moran.iloc[i, j]
                text = f'{value:.3f}' if isinstance(value, (int, float)) else str(value)
                self.dialog.datatable_moran.setItem(i, j + 1, QTableWidgetItem(text))

        self.dialog.datatable_moran.resizeColumnsToContents()
        self.dialog.datatable_moran.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)

    # Feature selection
    def on_rfe_toggled(self, checked):
        """Execute RFE for automatic feature selection."""
        if not checked:
            return

        try:
            progress = self._create_progress_dialog(
                self.tr('Seleção de Variáveis - Recursive Feature Elimination...'),
                100
            )

            # Select features using RFE
            selected = self.spatial_mgr.recursive_feature_elimination(
                self.df_SVM_Trainfeatures,
                self.data_ctrl.z,
                n_features_to_select=max(2, len(self.list_cov_SVM) // 2)
            )

            progress.setValue(100)
            progress.close()

            # Update model with selected features
            for feat in selected:
                if feat not in self.list_cov_SVM:
                    self.list_cov_SVM.append(feat)

            self._update_train_features()

        except Exception as e:
            self._show_warning(self.tr('Erro'), str(e))

    # SVM execution
    def on_svm_clicked(self):
        """Execute SVM interpolation."""
        if len(self.list_cov_SVM) < 2:
            self._show_warning(
                self.tr('Aviso'),
                self.tr('Modelo incompleto. Adicione features ao modelo.')
            )
            return

        try:
            progress = self._create_progress_dialog(
                self.tr('Machine Learning - Support Vector Machine...'),
                100
            )

            # Create grid
            grid_x = np.arange(self.data_ctrl.Cord_X_min, self.data_ctrl.Cord_X_max, self.data_ctrl.Pixel_Size_X)
            grid_y = np.arange(self.data_ctrl.Cord_Y_min, self.data_ctrl.Cord_Y_max, self.data_ctrl.Pixel_Size_Y)

            grid_points = []
            for x in grid_x:
                for y in grid_y:
                    grid_points.append([x + self.data_ctrl.Pixel_Size_X / 2, y - self.data_ctrl.Pixel_Size_Y / 2])

            grid_array = np.array(grid_points)

            # Apply contour if defined
            if self.dialog.checkBox_Area_Contorno.isChecked() and len(self.data_ctrl.df_limite) > 0:
                poly = np.array(self.data_ctrl.df_limite, dtype=float)
                bbox_path = mplPath.Path(poly)
                grid_array = np.array([pt for pt in grid_array if bbox_path.contains_point(pt)])

            progress.setValue(50)

            # Create test grid with features (for now just coords)
            df_test = pd.DataFrame(grid_array, columns=[self.data_ctrl.Cord_X, self.data_ctrl.Cord_Y])

            # Execute SVM
            predictions = self.interp_mgr.execute_svm(
                self.df_SVM_Trainfeatures,
                self.data_ctrl.z,
                self.list_cov_SVM,
                df_test
            )

            # Display results
            df_results = pd.DataFrame({
                self.data_ctrl.Cord_X: grid_array[:, 0],
                self.data_ctrl.Cord_Y: grid_array[:, 1],
                'Z_Predito': predictions
            })

            self._display_svm_results(df_results)

            progress.setValue(100)
            progress.close()

        except Exception as e:
            self._show_warning(self.tr('Erro'), f'{self.tr("Erro na SVM")}: {str(e)}')

    def _display_svm_results(self, df_results):
        """Display SVM prediction results."""
        self.dialog.datatable_pontos_interpolados_SVM.setColumnCount(len(df_results.columns))
        self.dialog.datatable_pontos_interpolados_SVM.setRowCount(min(100, len(df_results)))

        self.dialog.datatable_pontos_interpolados_SVM.setHorizontalHeaderLabels(df_results.columns)

        for i in range(min(100, len(df_results))):
            for j, col in enumerate(df_results.columns):
                value = df_results.iloc[i, j]
                text = f'{value:.3f}' if isinstance(value, (int, float)) else str(value)
                self.dialog.datatable_pontos_interpolados_SVM.setItem(i, j, QTableWidgetItem(text))

        self.dialog.datatable_pontos_interpolados_SVM.resizeColumnsToContents()
        self.dialog.datatable_pontos_interpolados_SVM.setEditTriggers(
            QtWidgets.QTableWidget.NoEditTriggers
        )

        self.dialog.label_SVM.show()

    # Cross-validation
    def on_svm_cross_validation_clicked(self):
        """Execute SVM cross-validation."""
        if len(self.list_cov_SVM) < 2:
            return

        try:
            progress = self._create_progress_dialog(
                self.tr('Validação Cruzada - SVM...'),
                len(self.data_ctrl.z)
            )

            # Cross-validation
            cv_predictions = self.interp_mgr.execute_cross_validation_svm(
                self.df_SVM_Trainfeatures,
                self.data_ctrl.z,
                self.list_cov_SVM
            )

            # Prepare results
            df_cv = pd.DataFrame({
                self.tr('Z.Obs.'): self.data_ctrl.z.values,
                self.tr('Z.Predito'): cv_predictions
            })

            # Display
            self.dialog.datatable_validacao_cruzada_SVM.setColumnCount(len(df_cv.columns))
            self.dialog.datatable_validacao_cruzada_SVM.setRowCount(len(df_cv))

            self.dialog.datatable_validacao_cruzada_SVM.setHorizontalHeaderLabels(df_cv.columns)

            for i in range(len(df_cv)):
                for j in range(len(df_cv.columns)):
                    value = df_cv.iloc[i, j]
                    text = f'{value:.3f}' if isinstance(value, (int, float)) else str(value)
                    self.dialog.datatable_validacao_cruzada_SVM.setItem(i, j, QTableWidgetItem(text))

                progress.setValue(i)
                if progress.wasCanceled():
                    progress.close()
                    return

            self.dialog.datatable_validacao_cruzada_SVM.resizeColumnsToContents()
            self.dialog.datatable_validacao_cruzada_SVM.setEditTriggers(
                QtWidgets.QTableWidget.NoEditTriggers
            )

            self.dialog.label_validacao_cruzada_SVM.show()
            progress.close()

        except Exception as e:
            self._show_warning(self.tr('Erro'), str(e))

    # Stubs
    def on_train_features_table_double_clicked(self, item):
        pass

    def on_moran_checkbox_clicked(self, item):
        pass

    def on_interpolated_svm_points_table_double_clicked(self, item):
        pass

    def on_svm_cross_validation_table_double_clicked(self, item):
        pass

    def on_svm_label_clicked(self, value):
        pass

    def on_svm_cross_validation_label_clicked(self, value):
        pass

    # Helpers
    def _create_progress_dialog(self, label, max_val):
        """Create progress dialog."""
        progress = QProgressDialog(label, self.tr('Cancelar'), 1, max_val, self.dialog)
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
