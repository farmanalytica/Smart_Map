# -*- coding: utf-8 -*-
"""Kriging interpolation controller."""

import os
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt3
import matplotlib.pyplot as plt5

from qgis.PyQt import QtCore, QtWidgets, QtGui
from qgis.PyQt.QtWidgets import QMessageBox, QProgressDialog, QTableWidgetItem
from qgis.PyQt.QtGui import QIcon, QPixmap

from ..krig import kriging
from ..utils import functions


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

        # Wired by Smart_Map after construction. The model/nugget/range/sill widgets
        # live on the variogram tab; boundary (df_limite / Contorno_Definido) lives on
        # grid_ctrl (also exposed via data_ctrl delegating properties).
        self.variogram_view = None
        self.grid_ctrl = None

        # Results storage
        self.arr_cut = None
        self.df_CV_OK = None

        # Workflow flags
        self.Krigagem = False
        self.Validacao_Cruzada_OK = False

    # ------------------------------------------------------------------ helpers
    def _get_model(self):
        """Return the variogram model name from the variogram tab combo."""
        models = ['linear', 'linear-sill', 'exponential', 'spherical', 'gaussian']
        idx = self.variogram_view.comboBox_Modelo.currentIndex()
        return models[idx] if idx < len(models) else 'linear'

    def _get_variogram_params(self):
        """Return [nugget, range, sill] from the variogram tab line edits."""
        nugget = float(self.variogram_view.lineEdit_Nugget.text())
        range_ = float(self.variogram_view.lineEdit_Range.text())
        sill = float(self.variogram_view.lineEdit_Sill.text())
        return [nugget, range_, sill]

    # ----------------------------------------------------------- kriging
    def on_kriging_clicked(self):
        """Execute ordinary kriging interpolation."""
        if not self.variogram_ctrl.Variogram:
            self._show_warning(
                self.tr('Mensagem'),
                self.tr('Ajuste do Semivariograma não realizado.')
            )
            return

        try:
            data_view = self.data_ctrl.dialog

            # Grid + search parameters
            grid_x = data_view.SpinBox_Pixel_Size_X.value()
            grid_y = data_view.SpinBox_Pixel_Size_Y.value()
            n_neig = int(self.view.lineEdit_OK_VBNumMax.text())
            raio_busca = float(self.view.lineEdit_OK_VBRaio.text())

            model = self._get_model()
            var_params = self._get_variogram_params()

            # Create kriging object
            ok = kriging.OrdinaryKriging(
                self.data_ctrl.xy, self.data_ctrl.z,
                variogram_model=model,
                variogram_parameters=var_params
            )

            # Generate grid. Boundary state is owned by grid_ctrl; read it through
            # data_ctrl's delegating df_limite property.
            has_contour = data_view.checkBox_Area_Contorno.isChecked()

            if has_contour:
                if self.data_ctrl.df_limite is not None and len(self.data_ctrl.df_limite) > 0:
                    xygrid = ok.Grid(grid_x, grid_y, has_contour, self.data_ctrl.df_limite)
                elif data_view.mMapLayerComboBox_AreaCont.currentIndex() >= 0:
                    if self.grid_ctrl is not None:
                        self.grid_ctrl.on_contour_apply_clicked()
                    xygrid = ok.Grid(grid_x, grid_y, has_contour, self.data_ctrl.df_limite)
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

            cont = 1
            progress.setValue(cont)
            if progress.wasCanceled():
                progress.close()
                return

            # Execute kriging
            z_est_py, ss = ok.execute(xygrid, n_closest_points=n_neig, radius=raio_busca)

            z_est_py = z_est_py.reshape(-1, 1)
            ss = ss.reshape(-1, 1)

            self.arr_cut = np.vstack((xygrid[:, 0], xygrid[:, 1], z_est_py[:, 0], ss[:, 0])).T

            cont += 1
            progress.setValue(cont)
            if progress.wasCanceled():
                progress.close()
                return

            # Save results
            df_results = pd.DataFrame(
                np.atleast_2d(self.arr_cut),
                columns=[self.data_ctrl.Cord_X, self.data_ctrl.Cord_Y, self.data_ctrl.v_target, 'SD_Values']
            )

            csv_map = os.path.join(self.path_absolute, '1_Krig_' + self.data_ctrl.VTarget_FileName + '_Grid_Map.csv')
            csv_sd = os.path.join(self.path_absolute, '1_Krig_' + self.data_ctrl.VTarget_FileName + '_Grid_Map_SD.csv')
            csv_kri = os.path.join(self.path_absolute, '1_Krig_' + self.data_ctrl.VTarget_FileName + '_Grid_Map.kri')

            df_results.to_csv(csv_map, sep=',', index=False, encoding='utf-8')
            df_results.to_csv(csv_sd, sep=',', index=False, encoding='utf-8')
            df_results.to_csv(csv_kri, sep=',', index=False, encoding='utf-8')

            # Display in table
            self.view.datatable_pontos_interpolados_OK.setColumnCount(len(df_results.columns))
            self.view.datatable_pontos_interpolados_OK.setRowCount(len(df_results.index))

            cols = list(df_results.columns.values)
            cols[2] = self.tr('Z.Predito')
            cols[3] = self.tr('Desv.Pad.')
            self.view.datatable_pontos_interpolados_OK.setHorizontalHeaderLabels(cols)

            for i in range(len(df_results.index)):
                for j in range(len(df_results.columns)):
                    value = df_results.iloc[i, j]
                    try:
                        if value.dtype == 'float64':
                            value = '%.3f' % value
                    except AttributeError:
                        pass
                    item = QTableWidgetItem(str(value))
                    self.view.datatable_pontos_interpolados_OK.setItem(i, j, item)

                    cont += 1
                    progress.setValue(cont)
                    if progress.wasCanceled():
                        progress.close()
                        return

            self.view.datatable_pontos_interpolados_OK.resizeColumnsToContents()
            self.view.datatable_pontos_interpolados_OK.setEditTriggers(
                QtWidgets.QTableWidget.NoEditTriggers
            )

            self.view.tabWidget_Interpolacao_OK.setCurrentIndex(2)

            # Export interpolated raster/vector to QGIS
            if self.view.checkBox_Qgis_Raster.isChecked():
                cont += 1
                progress.setValue(cont)
                if progress.wasCanceled():
                    progress.close()
                    return

                try:
                    data_view.mMapLayerComboBox.currentIndexChanged.disconnect()
                except TypeError:
                    pass

                input_table = '1_Krig_' + self.data_ctrl.VTarget_FileName + '_Grid_Map.csv'
                output_tiff = os.path.join(
                    self.path_absolute,
                    '1_Krig_' + self.data_ctrl.VTarget_FileName + '_Grid_Map.tiff'
                )
                output_name = '1_Krig_' + self.data_ctrl.VTarget_FileName
                z_field = self.data_ctrl.v_target

                output_tiff = self.data_ctrl.export_raster_to_qgis(
                    input_table, output_tiff, output_name, z_field
                )

                if self.view.checkBox_Qgis_Vector_Points.isChecked():
                    if (data_view.checkBox_Area_Contorno.isChecked() and
                            data_view.mMapLayerComboBox_AreaCont.currentIndex() >= 0):
                        cont += 1
                        progress.setValue(cont)
                        if progress.wasCanceled():
                            progress.close()
                            return
                        self.data_ctrl.export_shapefile_to_qgis(output_tiff, "native:pixelstopoints")
                    else:
                        self.view.checkBox_Qgis_Vector_Points.setChecked(False)

                if self.view.checkBox_Qgis_Vector_Polygons.isChecked():
                    if (data_view.checkBox_Area_Contorno.isChecked() and
                            data_view.mMapLayerComboBox_AreaCont.currentIndex() >= 0):
                        cont += 1
                        progress.setValue(cont)
                        if progress.wasCanceled():
                            progress.close()
                            return
                        self.data_ctrl.export_shapefile_to_qgis(output_tiff, "native:pixelstopolygons")
                    else:
                        self.view.checkBox_Qgis_Vector_Polygons.setChecked(False)

            # Export standard-deviation raster/vector to QGIS
            if self.view.checkBox_Krigagem_Std_Desv.isChecked():
                cont += 1
                progress.setValue(cont)
                if progress.wasCanceled():
                    progress.close()
                    return

                input_table = '1_Krig_' + self.data_ctrl.VTarget_FileName + '_Grid_Map_SD.csv'
                output_tiff_sd = os.path.join(
                    self.path_absolute,
                    '1_Krig_' + self.data_ctrl.VTarget_FileName + '_Grid_Map_SD.tiff'
                )
                output_name = '1_Krig_' + self.data_ctrl.VTarget_FileName + '_SD'
                z_field = 'SD_Values'

                output_tiff_sd = self.data_ctrl.export_raster_to_qgis(
                    input_table, output_tiff_sd, output_name, z_field
                )

                if self.view.checkBox_Qgis_Vector_Points.isChecked():
                    if (data_view.checkBox_Area_Contorno.isChecked() and
                            data_view.mMapLayerComboBox_AreaCont.currentIndex() >= 0):
                        cont += 1
                        progress.setValue(cont)
                        if progress.wasCanceled():
                            progress.close()
                            return
                        self.data_ctrl.export_shapefile_to_qgis(output_tiff_sd, "native:pixelstopoints")
                    else:
                        self.view.checkBox_Qgis_Vector_Points.setChecked(False)

                if self.view.checkBox_Qgis_Vector_Polygons.isChecked():
                    if (data_view.checkBox_Area_Contorno.isChecked() and
                            data_view.mMapLayerComboBox_AreaCont.currentIndex() >= 0):
                        cont += 1
                        progress.setValue(cont)
                        if progress.wasCanceled():
                            progress.close()
                            return
                        self.data_ctrl.export_shapefile_to_qgis(output_tiff_sd, "native:pixelstopolygons")
                    else:
                        self.view.checkBox_Qgis_Vector_Polygons.setChecked(False)

            if self.view.checkBox_Qgis_Raster.isChecked():
                try:
                    data_view.mMapLayerComboBox.currentIndexChanged.connect(
                        self.data_ctrl.on_layer_combo_changed
                    )
                except (AttributeError, TypeError):
                    pass

            # Plot the interpolated map
            cont += 1
            progress.setValue(cont)
            if progress.wasCanceled():
                progress.close()
                return

            self._plot_interpolated_map()

            self.Krigagem = True

            # TODO(zones domain): self.load_maps_to_generate_ZM() once the zones
            # controller exposes the ZM map-loading port.

            progress.close()

        except Exception as e:
            self._show_warning(self.tr('Erro'), self.tr('Erro na Krigagem') + ': ' + str(e))

    def _plot_interpolated_map(self):
        """Render the interpolated kriging map and set the label pixmap."""
        plt3.close()
        plt3.title(self.tr('Mapa Interpolado Krigagem'))
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

        plt3.scatter(self.arr_cut[:, 0], self.arr_cut[:, 1], c=self.arr_cut[:, 2],
                     cmap='RdYlGn', vmin=min(self.arr_cut[:, 2]), vmax=max(self.arr_cut[:, 2]))

        clb = plt3.colorbar(aspect=20)
        clb.ax.set_title(self.data_ctrl.v_target)

        plt3.subplots_adjust(wspace=0.6, hspace=0.6, left=0.15, right=1.0, bottom=0.1, top=0.95)
        plt3.ticklabel_format(style='plain', useOffset=False, axis='both')
        ax = plt3.gca()
        ax.format_coord = lambda x, y: '%10d, %10d' % (x, y)

        png_path = os.path.join(self.path_absolute,
                                '1_Krig_' + self.data_ctrl.VTarget_FileName + '_Grid_Map.png')
        plt3.savefig(png_path)

        pixmap = QPixmap(png_path)
        self.view.label_Krigagem.show()
        self.view.label_Krigagem.setPixmap(pixmap)

        if self.view.checkBox_Qgis_Maps.isChecked():
            plt3.show()

    def on_kriging_all_variables_clicked(self):
        """Execute kriging for all selected semivariograms (batch).

        Ported from pushButton_Krigagem_All_Variables_clicked. Iterates over the rows
        marked in datatable_semivariogramas, reloads each saved semivariogram and runs
        kriging for it.
        """
        msg = QMessageBox.question(
            self.view,
            self.tr('Mensagem'),
            self.tr('Os mapas interpolados serão exportados para o QGIS. Deseja continuar?'),
            QMessageBox.Yes | QMessageBox.No
        )

        if msg != QMessageBox.Yes:
            return

        # Ensure at least raster export is enabled.
        if not (self.view.checkBox_Qgis_Vector_Points.isChecked() or
                self.view.checkBox_Qgis_Raster.isChecked()):
            self.view.checkBox_Qgis_Raster.setChecked(True)

        self.view.checkBox_Qgis_Maps.setChecked(False)

        data_view = self.data_ctrl.dialog
        variogram_view = self.variogram_view
        table = variogram_view.datatable_semivariogramas

        selected_layer = data_view.mMapLayerComboBox.currentLayer()
        if selected_layer is None:
            return
        layer_name = selected_layer.name()
        filename = os.path.join(self.path_absolute, '0_Semivariograms_' + layer_name + '.csv')
        if not os.path.isfile(filename):
            return

        list_rows_semiv = list(self.variogram_ctrl.list_rows_semiv)

        for row in list_rows_semiv:
            v_target = table.item(row, 1).text()

            df = pd.read_csv(filename, sep=',')

            semiv_calculated = -1
            for i in range(len(df.index)):
                if v_target == df.iloc[i, 0]:
                    semiv_calculated = i

            if semiv_calculated < 0:
                continue

            data_view.comboBox_VTarget.setCurrentText(v_target)
            self.data_ctrl.on_import_qgis_clicked()

            Modelo = df.iloc[semiv_calculated, 1]
            DMax = float(df.iloc[semiv_calculated, 2])
            Lag = float(df.iloc[semiv_calculated, 3])
            C0 = float(df.iloc[semiv_calculated, 4])
            C0_C = float(df.iloc[semiv_calculated, 5])
            Range = float(df.iloc[semiv_calculated, 6])
            RMSE = float(df.iloc[semiv_calculated, 7])
            R2 = float(df.iloc[semiv_calculated, 8])
            Raio = float(df.iloc[semiv_calculated, 9])
            VB = int(df.iloc[semiv_calculated, 10])

            self.data_ctrl.max_dist = float(df.iloc[semiv_calculated, 11])
            self.data_ctrl.min_dist = float(df.iloc[semiv_calculated, 12])
            self.variogram_ctrl.C0_Maximum = float(df.iloc[semiv_calculated, 13])
            self.variogram_ctrl.C0_Minimum = float(df.iloc[semiv_calculated, 14])
            self.variogram_ctrl.C0_C_Maximum = float(df.iloc[semiv_calculated, 15])
            self.variogram_ctrl.C0_C_Minimum = float(df.iloc[semiv_calculated, 16])
            self.variogram_ctrl.Range_Maximum = float(df.iloc[semiv_calculated, 17])
            self.variogram_ctrl.Range_Minimum = float(df.iloc[semiv_calculated, 18])
            self.data_ctrl.Raio_OK_Maximum = float(df.iloc[semiv_calculated, 19])
            self.data_ctrl.Raio_OK_Minimum = float(df.iloc[semiv_calculated, 20])
            self.data_ctrl.VB_OK_Maximum = int(df.iloc[semiv_calculated, 21])
            self.data_ctrl.VB_OK_Minimum = int(df.iloc[semiv_calculated, 22])

            try:
                variogram_view.comboBox_Modelo.currentIndexChanged.disconnect()
            except TypeError:
                pass

            model_index = {
                'Linear': 0, 'Linear to Sill': 1, 'Linear com Patamar': 1,
                'Exponential': 2, 'Exponencial': 2, 'Spherical': 3, 'Esférico': 3,
                'Gaussian': 4, 'Gaussiano': 4
            }
            variogram_view.comboBox_Modelo.setCurrentIndex(model_index.get(Modelo, 0))
            variogram_view.comboBox_Modelo.currentIndexChanged.connect(
                self.variogram_ctrl.on_model_combo_changed
            )

            variogram_view.lineEdit_OK_DMax.setText('%.3f' % DMax)
            variogram_view.lineEdit_OK_lags_dist.setText('%.3f' % Lag)

            if not self.variogram_ctrl.hide_horizontalSlider:
                try:
                    variogram_view.horizontalSlider_Nugget.valueChanged.disconnect()
                except TypeError:
                    pass
                variogram_view.horizontalSlider_Nugget.setMinimum(int(self.variogram_ctrl.C0_Minimum * 1000))
                variogram_view.horizontalSlider_Nugget.setMaximum(int(self.variogram_ctrl.C0_Maximum * 1000))
                variogram_view.horizontalSlider_Nugget.setValue(int(C0 * 1000))
                variogram_view.horizontalSlider_Nugget.valueChanged.connect(
                    self.variogram_ctrl.on_nugget_slider_changed
                )
            variogram_view.lineEdit_Nugget.setText('%.3f' % C0)

            if not self.variogram_ctrl.hide_horizontalSlider:
                try:
                    variogram_view.horizontalSlider_Sill.valueChanged.disconnect()
                except TypeError:
                    pass
                variogram_view.horizontalSlider_Sill.setMinimum(int(self.variogram_ctrl.C0_C_Minimum * 1000))
                variogram_view.horizontalSlider_Sill.setMaximum(int(self.variogram_ctrl.C0_C_Maximum * 1000))
                variogram_view.horizontalSlider_Sill.setValue(int(C0_C * 1000))
                variogram_view.horizontalSlider_Sill.valueChanged.connect(
                    self.variogram_ctrl.on_sill_slider_changed
                )
            variogram_view.lineEdit_Sill.setText('%.3f' % C0_C)

            if not self.variogram_ctrl.hide_horizontalSlider:
                try:
                    variogram_view.horizontalSlider_Range.valueChanged.disconnect()
                except TypeError:
                    pass
                variogram_view.horizontalSlider_Range.setMinimum(int(self.variogram_ctrl.Range_Minimum * 1000))
                variogram_view.horizontalSlider_Range.setMaximum(int(self.variogram_ctrl.Range_Maximum * 1000))
                variogram_view.horizontalSlider_Range.setValue(int(Range * 1000))
                variogram_view.horizontalSlider_Range.valueChanged.connect(
                    self.variogram_ctrl.on_range_slider_changed
                )
            variogram_view.lineEdit_Range.setText('%.3f' % Range)

            self.view.lineEdit_OK_VBRaio.setText('%.3f' % Raio)
            self.view.lineEdit_OK_VBNumMax.setText(str(VB))
            variogram_view.lineEdit_Var_RMSE.setText('%.3f' % RMSE)
            variogram_view.lineEdit_Var_R2.setText('%.3f' % R2)

            self.variogram_ctrl.calculate_variogram(initial_variogram=False, nugget_range_sill=True)
            self.variogram_ctrl.plot_variogram()

            self.view.tabWidget_Interpolacao_OK.setCurrentIndex(0)
            self.variogram_ctrl.Variogram = True

            self.on_kriging_clicked()

    def on_interpolated_points_table_double_clicked(self, item):
        """Open the interpolated-points CSV."""
        try:
            os.startfile(os.path.join(
                self.path_absolute,
                '1_Krig_' + self.data_ctrl.VTarget_FileName + '_Grid_Map.csv'
            ))
        except (AttributeError, OSError):
            pass

    # ---------------------------------------------------------- cross-validation
    def on_cross_validation_clicked(self):
        """Execute kriging cross-validation (leave-one-out)."""
        if not self.variogram_ctrl.Variogram:
            self._show_warning(
                self.tr('Mensagem'),
                self.tr('Ajuste do Semivariograma não realizado.')
            )
            return

        try:
            n_neig = int(self.view.lineEdit_OK_VBNumMax.text())
            raio_busca = float(self.view.lineEdit_OK_VBRaio.text())

            model = self._get_model()
            var_params = self._get_variogram_params()

            maximum = len(self.data_ctrl.data) + (len(self.data_ctrl.data) * 4)
            progress = self._create_progress_dialog(
                self.tr('Validação Cruzada - Krigagem') + '...',
                maximum
            )

            # Leave-one-out cross-validation (routed through the interpolation manager).
            labels_OK_CV = self.interp_mgr.execute_cross_validation_kriging(
                self.data_ctrl.xy, self.data_ctrl.z, model, var_params, n_neig, raio_busca
            )

            cont = len(self.data_ctrl.data)
            progress.setValue(cont)
            if progress.wasCanceled():
                progress.close()
                return

            labels_OK_CV = np.array(labels_OK_CV)
            labels = self.data_ctrl.data[:, 2]

            data_CV_OK = np.column_stack((
                self.data_ctrl.data[:, 0],
                self.data_ctrl.data[:, 1],
                labels,
                labels_OK_CV
            ))

            self.df_CV_OK = pd.DataFrame(
                np.atleast_2d(data_CV_OK),
                columns=['Coord_X', 'Coord_Y', self.tr('Z.Obs.'), self.tr('Z.Predito')]
            )

            csv_path = os.path.join(self.path_absolute,
                                    '1_Krig_' + self.data_ctrl.VTarget_FileName + '_CV.csv')
            self.df_CV_OK.to_csv(csv_path, sep=',', index=False, encoding='utf-8')

            # Display in table
            self.view.datatable_validacao_cruzada_OK.setColumnCount(len(self.df_CV_OK.columns))
            self.view.datatable_validacao_cruzada_OK.setRowCount(len(self.df_CV_OK.index))
            self.view.datatable_validacao_cruzada_OK.setHorizontalHeaderLabels(
                list(self.df_CV_OK.columns.values)
            )

            for i in range(len(self.df_CV_OK.index)):
                for j in range(len(self.df_CV_OK.columns)):
                    value = self.df_CV_OK.iloc[i, j]
                    try:
                        if value.dtype == 'float64':
                            value = '%.3f' % value
                    except AttributeError:
                        pass
                    item = QTableWidgetItem(str(value))
                    self.view.datatable_validacao_cruzada_OK.setItem(i, j, item)

                    cont += 1
                    progress.setValue(cont)
                    if progress.wasCanceled():
                        progress.close()
                        return

            self.view.datatable_validacao_cruzada_OK.resizeColumnsToContents()
            self.view.datatable_validacao_cruzada_OK.setEditTriggers(
                QtWidgets.QTableWidget.NoEditTriggers
            )

            # Statistics + regression plot
            RMSE_lib, R2_RCV, regressor, R2_Elp, lccc = functions.calculate_statistics(
                labels_OK_CV, labels
            )

            RMSE_lib = '%.3f' % RMSE_lib
            R2_RCV = '%.3f' % R2_RCV

            intercept = regressor.intercept_[0]
            slope = regressor.coef_[0][0]

            x_min = min(labels_OK_CV.min(), labels.min())
            x_max = max(labels_OK_CV.max(), labels.max())

            x_min = x_min - abs(intercept)
            if x_min < 0:
                x_min = 0
            x_max = x_max + abs(intercept)

            plt5.close()
            plt5.title(self.tr('Validação Cruzada - Krigagem') + '   ' +
                       self.tr('RMSE:') + ' ' + str(RMSE_lib) + '   $R^2$ : ' + str(R2_RCV))

            plt5.xlim(x_min, x_max)
            plt5.ylim(x_min, x_max)

            plt5.xlabel(self.tr('Valor Predito') + ' - ' + self.data_ctrl.v_target)
            plt5.ylabel(self.tr('Valor Observado') + ' - ' + self.data_ctrl.v_target)

            plt5.scatter(labels_OK_CV, labels, marker='s', color='blue')
            plt5.plot([x_min, x_max], [x_min, x_max], linestyle=':', color='black')

            labels_OK_CV_line = np.append(0, labels_OK_CV)
            labels_OK_CV_line = np.append(labels_OK_CV_line, x_max)

            line = slope * labels_OK_CV_line + intercept

            if intercept >= 0:
                plt5.plot(labels_OK_CV_line, line, color='black',
                          label='y={:.3f}x+{:.3f}'.format(slope, intercept))
            else:
                plt5.plot(labels_OK_CV_line, line, color='black',
                          label='y={:.3f}x-{:.3f}'.format(slope, abs(intercept)))

            plt5.legend(loc='upper left')
            plt5.legend()
            plt5.subplots_adjust(wspace=0.6, hspace=0.6, left=0.15, right=0.95, bottom=0.1, top=0.95)
            plt5.ticklabel_format(style='plain', useOffset=False, axis='both')
            ax = plt5.gca()
            ax.format_coord = lambda x, y: '%10d, %10d' % (x, y)

            png_path = os.path.join(self.path_absolute,
                                    '1_Krig_' + self.data_ctrl.VTarget_FileName + '_CV.png')
            plt5.savefig(png_path)

            pixmap = QPixmap(png_path)
            self.view.label_validacao_cruzada_OK.show()
            self.view.label_validacao_cruzada_OK.setPixmap(pixmap)

            if self.view.checkBox_Qgis_Maps.isChecked():
                plt5.show()

            self.Validacao_Cruzada_OK = True
            self.view.tabWidget_Interpolacao_OK.setCurrentIndex(1)

            progress.close()

        except Exception as e:
            self._show_warning(self.tr('Erro'), self.tr('Erro na Validação Cruzada') + ': ' + str(e))

    def on_cross_validation_results_double_clicked(self, item):
        """Open the cross-validation CSV."""
        try:
            os.startfile(os.path.join(
                self.path_absolute,
                '1_Krig_' + self.data_ctrl.VTarget_FileName + '_CV.csv'
            ))
        except (AttributeError, OSError):
            pass

    def on_cross_validation_label_clicked(self, value):
        """Show cross-validation help."""
        pass

    # -------------------------------------------------------------------- UI
    def on_semivariogram_checkbox_clicked(self, item):
        """Toggle semivariogram selection for batch kriging.

        Ported from datatable_semivariogramas_checkbox_clicked. Maintains the shared
        list_rows_semiv (owned by variogram_ctrl) and enables/disables the batch button.
        """
        list_rows_semiv = self.variogram_ctrl.list_rows_semiv

        if item.checkState() == QtCore.Qt.Checked:
            if item.row() not in list_rows_semiv:
                list_rows_semiv.append(item.row())
                list_rows_semiv.sort()
        else:
            if item.row() in list_rows_semiv:
                list_rows_semiv.remove(item.row())

        self.view.pushButton_Krigagem_All_Variables.setEnabled(len(list_rows_semiv) > 0)

    def on_kriging_label_clicked(self, value):
        """Show kriging help."""
        pass

    # --------------------------------------------------------------- helpers
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
        """Show warning message box."""
        msg_box = QMessageBox()
        msg_box.setWindowIcon(QIcon(self.icon_path))
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec_()
