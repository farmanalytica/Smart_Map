# -*- coding: utf-8 -*-
"""Grid and extent management controller."""

import os
import numpy as np
import pandas as pd
import matplotlib.path as mplPath
import matplotlib.pyplot as plt1

from qgis.PyQt import QtCore, QtWidgets, QtGui
from qgis.PyQt.QtWidgets import QMessageBox, QTableWidgetItem
from qgis.PyQt.QtGui import QIcon, QPixmap
from qgis.core import QgsVectorFileWriter, QgsProject, QgsGeometry


class GridController:
    """Handles grid parameters and extent definition."""

    def __init__(self, dialog, data_controller, icon_path, path_absolute, tr_func):
        self.dialog = dialog
        self.data_ctrl = data_controller
        self.icon_path = icon_path
        self.path_absolute = path_absolute
        self.tr = tr_func

        # Grid state (references from data_controller)
        # Cord_X_min, Cord_X_max, Cord_Y_min, Cord_Y_max
        # Pixel_Size_X, Pixel_Size_Y
        # Num_Points_X, Num_Points_Y

        # Boundary state (grid_ctrl is the SINGLE OWNER; data_ctrl reads these via
        # delegating properties).
        self.Contorno_Definido = False
        self.df_limite = pd.DataFrame(columns=['Coord_X', 'Coord_Y'])
        self.data_limite = None
        self.list_index_out_polygon = []
        self.cols_table_area_contorno = []
        self.lyrCRS_table_atribute = None

        # SVM state (cleared when grid changes)
        self.SVM_Add_Coord = False
        self.df_SVM_Testfeatures = None

    # Pixel size changes - recalculate grid
    def on_pixel_size_x_changed(self, value):
        """Update grid X pixel size and recalculate X dimension."""
        try:
            x_min = float(self.dialog.lineEdit_XMin.text())
            x_max = float(self.dialog.lineEdit_XMax.text())
            pixel_size_x = self.dialog.SpinBox_Pixel_Size_X.value()

            self.data_ctrl.Cord_X_min = x_min
            self.data_ctrl.Cord_X_max = x_max
            self.data_ctrl.Pixel_Size_X = pixel_size_x

            num_points_x = int((x_max - x_min) / pixel_size_x)
            self.dialog.lineEdit_Num_Points_X.setText(str(num_points_x))
            self.data_ctrl.Num_Points_X = num_points_x

            self._reset_svm_state()
        except (ValueError, ZeroDivisionError):
            pass

    def on_pixel_size_y_changed(self, value):
        """Update grid Y pixel size and recalculate Y dimension."""
        try:
            y_min = float(self.dialog.lineEdit_YMin.text())
            y_max = float(self.dialog.lineEdit_YMax.text())
            pixel_size_y = self.dialog.SpinBox_Pixel_Size_Y.value()

            self.data_ctrl.Cord_Y_min = y_min
            self.data_ctrl.Cord_Y_max = y_max
            self.data_ctrl.Pixel_Size_Y = pixel_size_y

            num_points_y = int((y_max - y_min) / pixel_size_y)
            self.dialog.lineEdit_Num_Points_Y.setText(str(num_points_y))
            self.data_ctrl.Num_Points_Y = num_points_y

            self._reset_svm_state()
        except (ValueError, ZeroDivisionError):
            pass

    # Extent bounds validation
    def on_x_min_edited(self):
        """Validate X min <= X max, then recalculate."""
        try:
            x_min = float(self.dialog.lineEdit_XMin.text())
            x_max = float(self.dialog.lineEdit_XMax.text())

            if x_min > x_max:
                self.dialog.lineEdit_XMin.setText('%.3f' % x_max)
            else:
                self.dialog.lineEdit_XMin.setText('%.3f' % x_min)

            self.on_pixel_size_x_changed(None)
        except ValueError:
            pass

    def on_x_max_edited(self):
        """Validate X max >= X min, then recalculate."""
        try:
            x_min = float(self.dialog.lineEdit_XMin.text())
            x_max = float(self.dialog.lineEdit_XMax.text())

            if x_max < x_min:
                self.dialog.lineEdit_XMax.setText('%.3f' % x_min)
            else:
                self.dialog.lineEdit_XMax.setText('%.3f' % x_max)

            self.on_pixel_size_x_changed(None)
        except ValueError:
            pass

    def on_y_min_edited(self):
        """Validate Y min <= Y max, then recalculate."""
        try:
            y_min = float(self.dialog.lineEdit_YMin.text())
            y_max = float(self.dialog.lineEdit_YMax.text())

            if y_min > y_max:
                self.dialog.lineEdit_YMin.setText('%.3f' % y_max)
            else:
                self.dialog.lineEdit_YMin.setText('%.3f' % y_min)

            self.on_pixel_size_y_changed(None)
        except ValueError:
            pass

    def on_y_max_edited(self):
        """Validate Y max >= Y min, then recalculate."""
        try:
            y_min = float(self.dialog.lineEdit_YMin.text())
            y_max = float(self.dialog.lineEdit_YMax.text())

            if y_max < y_min:
                self.dialog.lineEdit_YMax.setText('%.3f' % y_min)
            else:
                self.dialog.lineEdit_YMax.setText('%.3f' % y_max)

            self.on_pixel_size_y_changed(None)
        except ValueError:
            pass

    # Area contour (boundary) management
    def on_area_contour_toggled(self, checked):
        """Enable/disable area contour UI and reset if disabled."""
        self._reset_svm_state()

        if checked:
            # Enable contour UI
            self.dialog.mMapLayerComboBox_AreaCont.setEnabled(True)
            self.dialog.pushButton_Area_Contorno.setEnabled(True)
            self.dialog.comboBox_CordX_AreaCont.setEnabled(True)
            self.dialog.comboBox_CordY_AreaCont.setEnabled(True)
        else:
            # Disable contour UI
            self.dialog.mMapLayerComboBox_AreaCont.setEnabled(False)
            self.dialog.pushButton_Area_Contorno.setEnabled(False)
            self.dialog.comboBox_CordX_AreaCont.setEnabled(False)
            self.dialog.comboBox_CordY_AreaCont.setEnabled(False)

            # Reset boundary if it was defined
            if len(self.df_limite) > 0:
                self.df_limite = pd.DataFrame(columns=['Coord_X', 'Coord_Y'])
                self.Contorno_Definido = False

                # Restore extent from data
                if self.data_ctrl.df is not None:
                    self.data_ctrl.Cord_X_min = self.data_ctrl.df[self.data_ctrl.Cord_X].min()
                    self.data_ctrl.Cord_X_max = self.data_ctrl.df[self.data_ctrl.Cord_X].max()
                    self.data_ctrl.Cord_Y_min = self.data_ctrl.df[self.data_ctrl.Cord_Y].min()
                    self.data_ctrl.Cord_Y_max = self.data_ctrl.df[self.data_ctrl.Cord_Y].max()

                    self.dialog.lineEdit_XMin.setText('%.3f' % self.data_ctrl.Cord_X_min)
                    self.dialog.lineEdit_XMax.setText('%.3f' % self.data_ctrl.Cord_X_max)
                    self.dialog.lineEdit_YMin.setText('%.3f' % self.data_ctrl.Cord_Y_min)
                    self.dialog.lineEdit_YMax.setText('%.3f' % self.data_ctrl.Cord_Y_max)

                    self.data_ctrl.Num_Points_X = int(
                        (self.data_ctrl.Cord_X_max - self.data_ctrl.Cord_X_min) /
                        self.data_ctrl.Pixel_Size_X
                    )
                    self.data_ctrl.Num_Points_Y = int(
                        (self.data_ctrl.Cord_Y_max - self.data_ctrl.Cord_Y_min) /
                        self.data_ctrl.Pixel_Size_Y
                    )

                    self.dialog.lineEdit_Num_Points_X.setText(str(self.data_ctrl.Num_Points_X))
                    self.dialog.lineEdit_Num_Points_Y.setText(str(self.data_ctrl.Num_Points_Y))

                    # Re-plot the sampled points without the boundary polygon
                    # (mirrors the re-plot in the old checkBox_Area_Contorno_clicked).
                    if self.data_ctrl.data is not None:
                        self.data_ctrl._plot_sampled_points()

    def on_contour_layer_combo_changed(self, index):
        """Populate coordinate field combos based on layer type."""
        if self.dialog.mMapLayerComboBox_AreaCont.currentIndex() < 0:
            return

        layer = self.dialog.mMapLayerComboBox_AreaCont.currentLayer()

        if layer.geometryType() == 0:  # Vector layer (points)
            cols = layer.fields().names()
            self.cols_table_area_contorno = cols

            self.dialog.comboBox_CordX_AreaCont.clear()
            self.dialog.comboBox_CordX_AreaCont.setEnabled(True)
            self.dialog.comboBox_CordX_AreaCont.addItems(cols)
            self.dialog.comboBox_CordX_AreaCont.setCurrentIndex(0)

            self.dialog.comboBox_CordY_AreaCont.clear()
            self.dialog.comboBox_CordY_AreaCont.setEnabled(True)
            self.dialog.comboBox_CordY_AreaCont.addItems(cols)
            self.dialog.comboBox_CordY_AreaCont.setCurrentIndex(min(1, len(cols) - 1))
        else:  # Polygon layer
            self.dialog.comboBox_CordX_AreaCont.clear()
            self.dialog.comboBox_CordX_AreaCont.setEnabled(False)
            self.dialog.comboBox_CordY_AreaCont.clear()
            self.dialog.comboBox_CordY_AreaCont.setEnabled(False)

    def on_contour_apply_clicked(self):
        """Load boundary from layer and apply to grid."""
        layer = self.dialog.mMapLayerComboBox_AreaCont.currentLayer()
        if layer is None:
            return

        # Validate CRS
        layer_crs = layer.crs()
        if not self._validate_contour_crs(layer_crs):
            return

        # Validate geometry type
        geom_type = layer.geometryType()
        if geom_type not in (0, 2):  # Point or Polygon
            self._show_warning(
                self.tr('Mensagem'),
                self.tr('Layer QGIS Inválida! Selecione uma Layer QGIS tipo: PointLayer ou PoligonLayer.')
            )
            return

        # Validate CRS match
        if self.lyrCRS_table_atribute is None:
            self.lyrCRS_table_atribute = layer_crs.authid()

        layer_authid = layer_crs.authid()
        if layer_authid != self.lyrCRS_table_atribute:
            if 'SAD69' not in layer_crs.description():
                self._show_warning(
                    self.tr('Mensagem'),
                    self.tr('O CRS da Layer de Contorno é diferente do CRS da Layer da Tabela de Atributos.')
                )
                return

        # Load boundary
        if geom_type == 2:  # Polygon
            self._load_polygon_boundary(layer)
        else:  # Points
            self._load_point_boundary(layer, layer_crs)

        # Apply boundary
        self._apply_boundary_to_data()
        self._plot_boundary()

        self._reset_svm_state()

    def _validate_contour_crs(self, layer_crs):
        """Check if layer CRS is projected (not geographic)."""
        if layer_crs.isGeographic():
            msg = (
                self.tr('O Sistema de Coordenadas Geográficas deve estar em UTM.') + '\n' +
                self.tr('Realize a conversão da layer de entrada para a projeção UTM antes de importá-la no Smart-Map.')
            )
            self._show_warning(self.tr('Mensagem'), msg)
            return False
        return True

    def _load_polygon_boundary(self, layer):
        """Extract polygon vertices as boundary."""
        points_x = []
        points_y = []

        for feature in layer.getFeatures():
            geom = feature.geometry()
            polygons = geom.asMultiPolygon()

            # First polygon exterior ring
            for pt in polygons[0][0]:
                points_x.append(pt.x())
                points_y.append(pt.y())

            # Additional rings (holes)
            if len(polygons) > 1:
                for pt in polygons[1][0]:
                    points_x.append(pt.x())
                    points_y.append(pt.y())

        coords = list(zip(points_x, points_y))
        self.df_limite = pd.DataFrame(coords, columns=['Coord_X', 'Coord_Y'])

        # Save to CSV
        csv_path = os.path.join(self.path_absolute, '0_Limite_Contorno.csv')
        self.df_limite.to_csv(csv_path, sep=',', index=False, encoding='utf-8')

    def _load_point_boundary(self, layer, layer_crs):
        """Extract point coordinates from point layer."""
        csv_path = os.path.join(self.path_absolute, '0_Limite_Contorno.csv')
        QgsVectorFileWriter.writeAsVectorFormat(
            layer, csv_path, "utf-8", layer_crs, "CSV"
        )

        df = pd.read_csv(csv_path, sep=',')

        cord_x = self.dialog.comboBox_CordX_AreaCont.currentText()
        cord_y = self.dialog.comboBox_CordY_AreaCont.currentText()

        df = df[[cord_x, cord_y]]

        # Clean NaN
        if df.isnull().sum().sum() > 0:
            df.dropna(inplace=True)
            df.reset_index(drop=True, inplace=True)

        # Rename columns
        cols = list(df.columns.values)
        df.rename({cols[0]: 'Coord_X', cols[1]: 'Coord_Y'}, axis=1, inplace=True)

        # Close polygon by adding first point at end
        df = pd.concat([df, df.iloc[[0]]], ignore_index=True, axis=0)

        self.df_limite = df

    def _apply_boundary_to_data(self):
        """Filter data points outside boundary polygon."""
        if self.data_ctrl.df is None:
            return

        # Update extent from boundary
        self.data_ctrl.Cord_X_min = self.df_limite['Coord_X'].min()
        self.data_ctrl.Cord_X_max = self.df_limite['Coord_X'].max()
        self.data_ctrl.Cord_Y_min = self.df_limite['Coord_Y'].min()
        self.data_ctrl.Cord_Y_max = self.df_limite['Coord_Y'].max()

        self.dialog.lineEdit_XMin.setText('%.3f' % self.data_ctrl.Cord_X_min)
        self.dialog.lineEdit_XMax.setText('%.3f' % self.data_ctrl.Cord_X_max)
        self.dialog.lineEdit_YMin.setText('%.3f' % self.data_ctrl.Cord_Y_min)
        self.dialog.lineEdit_YMax.setText('%.3f' % self.data_ctrl.Cord_Y_max)

        # Recalculate grid
        self.data_ctrl.Num_Points_X = int(
            (self.data_ctrl.Cord_X_max - self.data_ctrl.Cord_X_min) / self.data_ctrl.Pixel_Size_X
        )
        self.data_ctrl.Num_Points_Y = int(
            (self.data_ctrl.Cord_Y_max - self.data_ctrl.Cord_Y_min) / self.data_ctrl.Pixel_Size_Y
        )

        self.dialog.lineEdit_Num_Points_X.setText(str(self.data_ctrl.Num_Points_X))
        self.dialog.lineEdit_Num_Points_Y.setText(str(self.data_ctrl.Num_Points_Y))

        # Display boundary in table
        self._display_boundary_table()

        # Filter points outside polygon
        self.data_limite = np.array(self.df_limite, dtype=float)
        poly_path = mplPath.Path(self.data_limite)

        self.list_index_out_polygon = []
        for i in range(len(self.data_ctrl.df)):
            pt = (
                self.data_ctrl.df.iloc[i][self.data_ctrl.Cord_X],
                self.data_ctrl.df.iloc[i][self.data_ctrl.Cord_Y]
            )
            if not poly_path.contains_point(pt):
                self.list_index_out_polygon.append(i)

        # Drop out-of-polygon points
        if self.list_index_out_polygon:
            self.data_ctrl.df.drop(self.data_ctrl.df.index[self.list_index_out_polygon], inplace=True)
            self.data_ctrl.df.reset_index(drop=True, inplace=True)
            self.data_ctrl.load_attribute_table()

            # Also filter variogram data
            if self.data_ctrl.xy is not None:
                self.data_ctrl.xy.drop(self.data_ctrl.xy.index[self.list_index_out_polygon], inplace=True)
                self.data_ctrl.xy.reset_index(drop=True, inplace=True)

            if self.data_ctrl.z is not None:
                self.data_ctrl.z.drop(self.data_ctrl.z.index[self.list_index_out_polygon], inplace=True)
                self.data_ctrl.z.reset_index(drop=True, inplace=True)

            # TODO(svm domain): the old pushButton_Area_Contorno_clicked also filtered
            #   df_SVM_Trainfeatures / df_SVM_Trainlabels by list_index_out_polygon and
            #   reloaded their datatables. Owned by SVMController.

        # Rebuild the (x, y, z) array from the now-filtered dataframe so the boundary plot
        # reflects only the in-polygon points (mirrors the old re-assignment of self.data).
        self.data_ctrl.data = self.data_ctrl.df[
            [self.data_ctrl.Cord_X, self.data_ctrl.Cord_Y, self.data_ctrl.v_target]
        ].values.astype(float)

        self.Contorno_Definido = True

    def _display_boundary_table(self):
        """Show boundary polygon in datatable."""
        try:
            self.dialog.datatable_limite.setColumnCount(len(self.df_limite.columns))
            self.dialog.datatable_limite.setRowCount(len(self.df_limite.index))

            headers = list(self.df_limite.columns.values)
            self.dialog.datatable_limite.setHorizontalHeaderLabels(headers)

            for i in range(len(self.df_limite.index)):
                for j in range(len(self.df_limite.columns)):
                    value = self.df_limite.iloc[i, j]
                    text = '%.3f' % value if isinstance(value, (int, float)) else str(value)
                    item = QTableWidgetItem(text)
                    self.dialog.datatable_limite.setItem(i, j, item)

            self.dialog.datatable_limite.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        except (AttributeError, ValueError):
            self._show_warning(self.tr('Mensagem'), self.tr('Erro ao carregar tabela. Valor Inválido!'))

    def _plot_boundary(self):
        """Plot data points with boundary polygon."""
        if self.data_ctrl.data is None:
            return

        plt1.close()
        fig = plt1.figure(figsize=(10, 8))

        title = f'I.Moran: {self.data_ctrl.moran_index} P.Value: {self.data_ctrl.p_value}'
        plt1.title(title)
        plt1.xlabel('Longitude (X)')
        plt1.ylabel('Latitude (Y)')

        plt1.xlim(self.data_ctrl.Cord_X_min - 100, self.data_ctrl.Cord_X_max + 100)
        plt1.ylim(self.data_ctrl.Cord_Y_min - 100, self.data_ctrl.Cord_Y_max + 100)

        # Set ticks
        interval_x = max(1, int((self.data_ctrl.Cord_X_max - self.data_ctrl.Cord_X_min) / 5))
        xmarks = [i for i in range(int(self.data_ctrl.Cord_X_min), int(self.data_ctrl.Cord_X_max), interval_x)]
        plt1.xticks(xmarks)

        interval_y = max(1, int((self.data_ctrl.Cord_Y_max - self.data_ctrl.Cord_Y_min) / 7))
        ymarks = [i for i in range(int(self.data_ctrl.Cord_Y_min), int(self.data_ctrl.Cord_Y_max), interval_y)]
        plt1.yticks(ymarks)

        # Plot boundary polygon
        plt1.plot(self.data_limite[:, 0], self.data_limite[:, 1], 'k-', linewidth=2)

        # Plot outliers
        if len(self.data_ctrl.list_index_outlier) > 0:
            plt1.scatter(self.data_ctrl.data_outlier[:, 0], self.data_ctrl.data_outlier[:, 1],
                        c=self.data_ctrl.data_outlier[:, 2], marker="x", cmap='RdYlGn')

        # Plot data
        plt1.scatter(self.data_ctrl.data[:, 0], self.data_ctrl.data[:, 1],
                    c=self.data_ctrl.data[:, 2], cmap='RdYlGn',
                    vmin=min(self.data_ctrl.data[:, 2]), vmax=max(self.data_ctrl.data[:, 2]))

        clb = plt1.colorbar(aspect=20)
        clb.ax.set_title(self.data_ctrl.v_target)

        plt1.subplots_adjust(wspace=0.6, hspace=0.6, left=0.15, right=0.95, bottom=0.1, top=0.95)

        png_path = os.path.join(self.path_absolute, '0_Limite_Contorno.png')
        plt1.savefig(png_path)

        pixmap = QPixmap(png_path)
        self.dialog.label_pontos_limite.setPixmap(pixmap)
        self.dialog.label_pontos_limite.show()

    def on_contour_label_clicked(self, value):
        """Show contour help."""
        # Help text shown via label click - implementation in UI
        pass

    # Helpers
    def _reset_svm_state(self):
        """Clear SVM test features when grid changes."""
        self.SVM_Add_Coord = False
        self.df_SVM_Testfeatures = pd.DataFrame(columns=[self.data_ctrl.Cord_X, self.data_ctrl.Cord_Y])

        # Hide SVM results
        self.dialog.label_SVM.hide()
        self.dialog.datatable_pontos_interpolados_SVM.setColumnCount(0)
        self.dialog.datatable_pontos_interpolados_SVM.setRowCount(0)

        self.dialog.label_validacao_cruzada_SVM.hide()
        self.dialog.datatable_validacao_cruzada_SVM.setColumnCount(0)
        self.dialog.datatable_validacao_cruzada_SVM.setRowCount(0)

    def _show_warning(self, title, message):
        """Show warning message box."""
        msg_box = QMessageBox()
        msg_box.setWindowIcon(QIcon(self.icon_path))
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec_()
