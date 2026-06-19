# -*- coding: utf-8 -*-
"""Kriging interpolation controller."""

import os
import time
import numpy as np
import pandas as pd

from qgis.PyQt import QtCore, QtWidgets, QtGui
from qgis.PyQt.QtWidgets import QMessageBox, QProgressDialog, QTableWidgetItem
from qgis.PyQt.QtGui import QIcon

from ..krig import kriging


class KrigingController:
    """Handles kriging interpolation and cross-validation."""

    def __init__(self, view, data_controller, variogram_controller, interp_mgr, icon_path, path_absolute, tr_func):
        self.view = view
        self.data_ctrl = data_controller
        self.variogram_ctrl = variogram_controller
        self.interp_mgr = interp_mgr
        self.icon_path = icon_path
        self.path_absolute = path_absolute
        self.tr = tr_func

        # Results storage
        self.arr_cut = None
        self.df_CV_OK = None

    # Kriging execution
    def on_kriging_clicked(self):
        """Execute ordinary kriging interpolation."""
        if not self.variogram_ctrl.Variogram:
            self._show_warning(
                self.tr('Mensagem'),
                self.tr('Ajuste do Semivariograma não realizado.')
            )
            return

        try:
            # Get parameters
            grid_x = self.dialog.SpinBox_Pixel_Size_X.value()
            grid_y = self.dialog.SpinBox_Pixel_Size_Y.value()
            n_neig = int(self.dialog.lineEdit_OK_VBNumMax.text())
            raio_busca = float(self.dialog.lineEdit_OK_VBRaio.text())

            # Get model
            model_idx = self.dialog.comboBox_Modelo.currentIndex()
            models = ['linear', 'linear-sill', 'exponential', 'spherical', 'gaussian']
            model = models[model_idx] if model_idx < len(models) else 'linear'

            # Get variogram parameters
            nugget = float(self.dialog.lineEdit_Nugget.text())
            range_ = float(self.dialog.lineEdit_Range.text())
            sill = float(self.dialog.lineEdit_Sill.text())
            var_params = [nugget, range_, sill]

            # Create kriging object
            ok = kriging.OrdinaryKriging(
                self.data_ctrl.xy, self.data_ctrl.z,
                variogram_model=model,
                variogram_parameters=var_params
            )

            # Generate grid
            has_contour = self.dialog.checkBox_Area_Contorno.isChecked()

            if has_contour:
                if self.variogram_ctrl.df_limite is not None and len(self.variogram_ctrl.df_limite) > 0:
                    xygrid = ok.Grid(grid_x, grid_y, has_contour, self.variogram_ctrl.df_limite)
                else:
                    if self.dialog.mMapLayerComboBox_AreaCont.currentIndex() >= 0:
                        self.variogram_ctrl.on_contour_apply_clicked()
                        xygrid = ok.Grid(grid_x, grid_y, has_contour, self.variogram_ctrl.df_limite)
                    else:
                        has_contour = False
                        limite = np.array([
                            [float(self.data_ctrl.Cord_X_min), float(self.data_ctrl.Cord_Y_min)],
                            [float(self.data_ctrl.Cord_X_max), float(self.data_ctrl.Cord_Y_max)]
                        ])
                        df_limite = pd.DataFrame(np.atleast_2d(limite), columns=['Coord_X', 'Coord_Y'])
                        xygrid = ok.Grid(grid_x, grid_y, has_contour, df_limite)
            else:
                limite = np.array([
                    [float(self.data_ctrl.Cord_X_min), float(self.data_ctrl.Cord_Y_min)],
                    [float(self.data_ctrl.Cord_X_max), float(self.data_ctrl.Cord_Y_max)]
                ])
                df_limite = pd.DataFrame(np.atleast_2d(limite), columns=['Coord_X', 'Coord_Y'])
                xygrid = ok.Grid(grid_x, grid_y, has_contour, df_limite)

            # Progress dialog
            maximum = (len(xygrid) * 3) + 5
            progress = self._create_progress_dialog(
                self.tr('Krigagem Ordinária') + '...',
                maximum
            )

            progress.setValue(1)
            if progress.wasCanceled():
                progress.close()
                return

            # Execute kriging
            z_est_py, ss = ok.execute(xygrid, n_closest_points=n_neig, radius=raio_busca)

            # Reshape results
            z_est_py = z_est_py.reshape(-1, 1)
            ss = ss.reshape(-1, 1)

            self.arr_cut = np.vstack((xygrid[:, 0], xygrid[:, 1], z_est_py[:, 0], ss[:, 0])).T

            progress.setValue(2)
            if progress.wasCanceled():
                progress.close()
                return

            # Save results
            df_results = pd.DataFrame(
                self.arr_cut,
                columns=[self.data_ctrl.Cord_X, self.data_ctrl.Cord_Y, self.data_ctrl.v_target, 'SD_Values']
            )

            csv_map = os.path.join(self.path_absolute, f'1_Krig_{self.data_ctrl.VTarget_FileName}_Grid_Map.csv')
            csv_sd = os.path.join(self.path_absolute, f'1_Krig_{self.data_ctrl.VTarget_FileName}_Grid_Map_SD.csv')
            csv_kri = os.path.join(self.path_absolute, f'1_Krig_{self.data_ctrl.VTarget_FileName}_Grid_Map.kri')

            df_results.to_csv(csv_map, sep=',', index=False, encoding='utf-8')
            df_results.to_csv(csv_sd, sep=',', index=False, encoding='utf-8')
            df_results.to_csv(csv_kri, sep=',', index=False, encoding='utf-8')

            # Display in table
            self.dialog.datatable_pontos_interpolados_OK.setColumnCount(len(df_results.columns))
            self.dialog.datatable_pontos_interpolados_OK.setRowCount(len(df_results.index))

            cols = list(df_results.columns.values)
            cols[2] = self.tr('Z.Predito')
            cols[3] = self.tr('Desv.Pad.')
            self.dialog.datatable_pontos_interpolados_OK.setHorizontalHeaderLabels(cols)

            cont = 3
            for i in range(len(df_results.index)):
                for j in range(len(df_results.columns)):
                    value = df_results.iloc[i, j]
                    text = f'{value:.3f}' if isinstance(value, (int, float)) else str(value)
                    item = QTableWidgetItem(text)
                    self.dialog.datatable_pontos_interpolados_OK.setItem(i, j, item)

                    cont += 1
                    progress.setValue(cont)
                    if progress.wasCanceled():
                        progress.close()
                        return

            self.dialog.datatable_pontos_interpolados_OK.resizeColumnsToContents()
            self.dialog.datatable_pontos_interpolados_OK.setEditTriggers(
                QtWidgets.QTableWidget.NoEditTriggers
            )

            self.dialog.tabWidget_Interpolacao_OK.setCurrentIndex(2)

            # Export to QGIS
            if self.dialog.checkBox_Qgis_Raster.isChecked():
                cont += 1
                progress.setValue(cont)
                if progress.wasCanceled():
                    progress.close()
                    return

                try:
                    self.dialog.mMapLayerComboBox.currentIndexChanged.disconnect()
                except TypeError:
                    pass

                input_table = f'1_Krig_{self.data_ctrl.VTarget_FileName}_Grid_Map.csv'
                output_tiff = os.path.join(
                    self.path_absolute,
                    f'1_Krig_{self.data_ctrl.VTarget_FileName}_Grid_Map.tiff'
                )
                output_name = f'1_Krig_{self.data_ctrl.VTarget_FileName}'
                z_field = self.data_ctrl.v_target

                # Export raster (stub - calls data_ctrl method)
                output_tiff = self.data_ctrl.export_raster_to_qgis(
                    input_table, output_tiff, output_name, z_field
                )

                # Export vector points
                if self.dialog.checkBox_Qgis_Vector_Points.isChecked():
                    if (self.dialog.checkBox_Area_Contorno.isChecked() and
                            self.dialog.mMapLayerComboBox_AreaCont.currentIndex() >= 0):
                        cont += 1
                        progress.setValue(cont)
                        if progress.wasCanceled():
                            progress.close()
                            return

                        self.data_ctrl.export_shapefile_to_qgis(output_tiff, "native:pixelstopoints")
                    else:
                        self.dialog.checkBox_Qgis_Vector_Points.setChecked(False)

                # Export vector polygons
                if self.dialog.checkBox_Qgis_Vector_Polygons.isChecked():
                    if (self.dialog.checkBox_Area_Contorno.isChecked() and
                            self.dialog.mMapLayerComboBox_AreaCont.currentIndex() >= 0):
                        cont += 1
                        progress.setValue(cont)
                        if progress.wasCanceled():
                            progress.close()
                            return

                        self.data_ctrl.export_shapefile_to_qgis(output_tiff, "native:pixelstopolygons")

            progress.close()

        except Exception as e:
            self._show_warning(self.tr('Erro'), f'{self.tr("Erro na Krigagem")}: {str(e)}')

    def on_kriging_all_variables_clicked(self):
        """Execute kriging for all selected semivariograms (batch)."""
        msg = QMessageBox.question(
            self.dialog,
            self.tr('Mensagem'),
            self.tr('Os mapas interpolados serão exportados para o QGIS. Deseja continuar?'),
            QMessageBox.Yes | QMessageBox.No
        )

        if msg != QMessageBox.Yes:
            return

        # Ensure raster export is enabled
        if not (self.dialog.checkBox_Qgis_Vector_Points.isChecked() or
                self.dialog.checkBox_Qgis_Raster.isChecked()):
            self.dialog.checkBox_Qgis_Raster.setChecked(True)

        # TODO: Implement batch kriging over multiple variables
        # This requires reading saved semivariogram parameters and executing kriging for each

    def on_interpolated_points_table_double_clicked(self, item):
        """Display selected interpolated point."""
        # Could show detail view or highlight on map
        pass

    # Cross-validation
    def on_cross_validation_clicked(self):
        """Execute kriging cross-validation (leave-one-out)."""
        if not self.variogram_ctrl.Variogram:
            self._show_warning(
                self.tr('Mensagem'),
                self.tr('Ajuste do Semivariograma não realizado.')
            )
            return

        try:
            # Get parameters
            n_neig = int(self.dialog.lineEdit_OK_VBNumMax.text())
            raio_busca = float(self.dialog.lineEdit_OK_VBRaio.text())

            # Get model
            model_idx = self.dialog.comboBox_Modelo.currentIndex()
            models = ['linear', 'linear-sill', 'exponential', 'spherical', 'gaussian']
            model = models[model_idx] if model_idx < len(models) else 'linear'

            # Get variogram parameters
            nugget = float(self.dialog.lineEdit_Nugget.text())
            sill = float(self.dialog.lineEdit_Sill.text())
            effective_range = float(self.dialog.lineEdit_Range.text())
            var_params = [nugget, effective_range, sill]

            # Progress
            maximum = len(self.data_ctrl.data) + (len(self.data_ctrl.data) * 4)
            progress = self._create_progress_dialog(
                self.tr('Validação Cruzada - Krigagem') + '...',
                maximum
            )

            labels_cv = []

            # Leave-one-out cross-validation
            for i in range(len(self.data_ctrl.xy)):
                coord_x = self.data_ctrl.xy.iloc[i, 0]
                coord_y = self.data_ctrl.xy.iloc[i, 1]

                # Leave out point i
                xy_loo = self.data_ctrl.xy.drop(i)
                z_loo = self.data_ctrl.z.drop(i)

                # Krige without point i
                ok = kriging.OrdinaryKriging(
                    xy_loo, z_loo,
                    variogram_model=model,
                    variogram_parameters=var_params
                )

                # Estimate at left-out point
                coordxy = [[coord_x, coord_y]]
                z_est, _ = ok.execute(coordxy, n_closest_points=n_neig, radius=raio_busca)

                labels_cv.append(z_est[0])

                progress.setValue(i)
                if progress.wasCanceled():
                    progress.close()
                    return

            # Prepare results
            labels_cv = np.array(labels_cv)
            labels_obs = self.data_ctrl.data[:, 2]

            data_cv = np.column_stack((
                self.data_ctrl.data[:, 0],
                self.data_ctrl.data[:, 1],
                labels_obs,
                labels_cv
            ))

            self.df_CV_OK = pd.DataFrame(
                data_cv,
                columns=['Coord_X', 'Coord_Y', self.tr('Z.Obs.'), self.tr('Z.Predito')]
            )

            csv_path = os.path.join(self.path_absolute, f'1_Krig_{self.data_ctrl.VTarget_FileName}_CV.csv')
            self.df_CV_OK.to_csv(csv_path, sep=',', index=False, encoding='utf-8')

            # Display in table
            self.dialog.datatable_validacao_cruzada_OK.setColumnCount(len(self.df_CV_OK.columns))
            self.dialog.datatable_validacao_cruzada_OK.setRowCount(len(self.df_CV_OK.index))

            self.dialog.datatable_validacao_cruzada_OK.setHorizontalHeaderLabels(
                list(self.df_CV_OK.columns.values)
            )

            cont = len(self.data_ctrl.data)
            for i in range(len(self.df_CV_OK.index)):
                for j in range(len(self.df_CV_OK.columns)):
                    value = self.df_CV_OK.iloc[i, j]
                    text = f'{value:.3f}' if isinstance(value, (int, float)) else str(value)
                    item = QTableWidgetItem(text)
                    self.dialog.datatable_validacao_cruzada_OK.setItem(i, j, item)

                    cont += 1
                    progress.setValue(cont)
                    if progress.wasCanceled():
                        progress.close()
                        return

            self.dialog.datatable_validacao_cruzada_OK.resizeColumnsToContents()
            self.dialog.datatable_validacao_cruzada_OK.setEditTriggers(
                QtWidgets.QTableWidget.NoEditTriggers
            )

            progress.close()

        except Exception as e:
            self._show_warning(self.tr('Erro'), f'{self.tr("Erro na Validação Cruzada")}: {str(e)}')

    def on_cross_validation_results_double_clicked(self, item):
        """Display cross-validation result details."""
        pass

    def on_cross_validation_label_clicked(self, value):
        """Show cross-validation help."""
        pass

    # UI
    def on_semivariogram_checkbox_clicked(self, item):
        """Toggle semivariogram selection for batch kriging."""
        pass

    def on_kriging_label_clicked(self, value):
        """Show kriging help."""
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
        """Show warning message box."""
        msg_box = QMessageBox()
        msg_box.setWindowIcon(QIcon(self.icon_path))
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec_()
