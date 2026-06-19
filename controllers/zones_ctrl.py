# -*- coding: utf-8 -*-
"""Management zones (clustering) controller."""

import os
import time
import numpy as np
import pandas as pd

from qgis.PyQt import QtCore, QtWidgets, QtGui
from qgis.PyQt.QtWidgets import QMessageBox, QTableWidgetItem, QProgressDialog
from qgis.PyQt.QtGui import QIcon


class ZonesController:
    """Handles management zone definition via fuzzy c-means clustering."""

    def __init__(self, dialog, data_ctrl, zones_mgr, icon_path, path_absolute, tr_func):
        self.dialog = dialog
        self.data_ctrl = data_ctrl
        self.zones_mgr = zones_mgr
        self.icon_path = icon_path
        self.path_absolute = path_absolute
        self.tr = tr_func

        # Zone state
        self.zone_variables = []
        self.df_zones_data = pd.DataFrame()
        self.zone_centers = None
        self.zone_labels = None
        self.fpi_nce_results = {}
        self.ideal_zones_count = 2

    # Map loading
    def load_maps_to_generate_zones(self):
        """Load available interpolated maps for zone generation."""
        # Scan for interpolated rasters/results
        # For now, use kriging results
        pass

    def on_zone_maps_checkbox_clicked(self, item):
        """Toggle selection of maps for zone generation."""
        pass

    # Variable management
    def on_add_var_clicked(self):
        """Add selected variable to zone clustering."""
        var_name = self.dialog.comboBox_ZM_Variables.currentText()
        if not var_name or var_name in self.zone_variables:
            return

        self.zone_variables.append(var_name)
        self._update_zone_vars_table()

    def on_add_all_selected_vars_clicked(self):
        """Add all selected variables."""
        try:
            # Get all numeric variables from data
            numeric_cols = self.data_ctrl.df.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                if col not in self.zone_variables and col not in [self.data_ctrl.Cord_X, self.data_ctrl.Cord_Y]:
                    self.zone_variables.append(col)

            self._update_zone_vars_table()
        except Exception as e:
            self._show_warning(self.tr('Erro'), str(e))

    def on_remove_var_clicked(self):
        """Remove selected variable from zones."""
        var_name = self.dialog.comboBox_ZM_Variables_Remove.currentText()
        if var_name and var_name in self.zone_variables:
            self.zone_variables.remove(var_name)
            self._update_zone_vars_table()

    def _update_zone_vars_table(self):
        """Display zone variables in table."""
        self.dialog.datatable_ZM_Variables.setColumnCount(1)
        self.dialog.datatable_ZM_Variables.setRowCount(len(self.zone_variables))
        self.dialog.datatable_ZM_Variables.setHorizontalHeaderLabels([self.tr('Variáveis')])

        for i, var in enumerate(self.zone_variables):
            self.dialog.datatable_ZM_Variables.setItem(i, 0, QTableWidgetItem(var))

        self.dialog.datatable_ZM_Variables.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)

    def on_zone_vars_table_double_clicked(self, item):
        """Show variable details."""
        pass

    # Optimal zone count
    def on_calc_ideal_zones_clicked(self):
        """Calculate ideal cluster count using FPI and NCE metrics."""
        if not self.zone_variables:
            self._show_warning(self.tr('Aviso'), self.tr('Selecione variáveis para análise.'))
            return

        try:
            progress = self._create_progress_dialog(
                self.tr('Calculando número ideal de zonas...'),
                100
            )

            # Prepare data
            self.df_zones_data = self.data_ctrl.df[self.zone_variables].copy()

            # Calculate FPI/NCE for different cluster counts
            self.fpi_nce_results = self.zones_mgr.calculate_ideal_zones(
                self.df_zones_data, max_clusters=10
            )

            progress.setValue(100)
            progress.close()

            # Display results
            self._display_fpi_nce_results()

        except Exception as e:
            self._show_warning(self.tr('Erro'), str(e))

    def _display_fpi_nce_results(self):
        """Display FPI/NCE results in table."""
        results_list = [
            (k, v['fpi'], v['nce']) for k, v in self.fpi_nce_results.items()
        ]

        self.dialog.datatable_ZM_FPI_NCE.setColumnCount(3)
        self.dialog.datatable_ZM_FPI_NCE.setRowCount(len(results_list))
        self.dialog.datatable_ZM_FPI_NCE.setHorizontalHeaderLabels(
            [self.tr('Clusters'), 'FPI', 'NCE']
        )

        for i, (clusters, fpi, nce) in enumerate(results_list):
            self.dialog.datatable_ZM_FPI_NCE.setItem(i, 0, QTableWidgetItem(str(clusters)))
            self.dialog.datatable_ZM_FPI_NCE.setItem(i, 1, QTableWidgetItem(f'{fpi:.4f}'))
            self.dialog.datatable_ZM_FPI_NCE.setItem(i, 2, QTableWidgetItem(f'{nce:.4f}'))

        self.dialog.datatable_ZM_FPI_NCE.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)

    def on_zone_count_changed(self, value):
        """Update ideal zone count."""
        self.ideal_zones_count = max(2, value)

    # Zone calculation
    def on_calculate_zones_clicked(self):
        """Execute fuzzy c-means clustering for zone generation."""
        if not self.zone_variables:
            self._show_warning(self.tr('Aviso'), self.tr('Selecione variáveis para clustering.'))
            return

        try:
            progress = self._create_progress_dialog(
                self.tr('Calculando zonas de manejo...'),
                100
            )

            # Prepare data
            self.df_zones_data = self.data_ctrl.df[self.zone_variables].copy()

            # Execute clustering
            self.zone_centers, membership, self.zone_labels = self.zones_mgr.calculate_zones(
                self.df_zones_data, self.ideal_zones_count
            )

            progress.setValue(50)

            # Get zone statistics
            zones_stats = self.zones_mgr.get_zone_statistics(self.df_zones_data, self.zone_labels)

            progress.setValue(100)
            progress.close()

            # Display results
            self._display_zone_results(zones_stats)

        except Exception as e:
            self._show_warning(self.tr('Erro'), str(e))

    def _display_zone_results(self, zones_stats):
        """Display zone cluster results."""
        # Display zone centers
        self.dialog.datatable_ZM_Centros.setColumnCount(len(self.zone_variables))
        self.dialog.datatable_ZM_Centros.setRowCount(self.ideal_zones_count)
        self.dialog.datatable_ZM_Centros.setHorizontalHeaderLabels(self.zone_variables)

        for zone_id, center in enumerate(self.zone_centers):
            for j, val in enumerate(center):
                text = f'{val:.3f}'
                self.dialog.datatable_ZM_Centros.setItem(zone_id, j, QTableWidgetItem(text))

        self.dialog.datatable_ZM_Centros.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)

        # Display zone assignments (first 100 rows)
        self.dialog.datatable_ZM_Class.setColumnCount(self.ideal_zones_count + 1)
        self.dialog.datatable_ZM_Class.setRowCount(min(100, len(self.zone_labels)))

        cols = [self.tr('ID')] + [f'{self.tr("Zona")} {i}' for i in range(self.ideal_zones_count)]
        self.dialog.datatable_ZM_Class.setHorizontalHeaderLabels(cols)

        for i in range(min(100, len(self.zone_labels))):
            self.dialog.datatable_ZM_Class.setItem(i, 0, QTableWidgetItem(str(i)))
            zone_id = self.zone_labels[i]
            for z in range(self.ideal_zones_count):
                marker = '●' if z == zone_id else '○'
                self.dialog.datatable_ZM_Class.setItem(i, z + 1, QTableWidgetItem(marker))

        self.dialog.datatable_ZM_Class.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)

        # Export zones to shapefile
        self._export_zones_shapefile()

    def _export_zones_shapefile(self):
        """Export zone assignments to shapefile."""
        try:
            df_export = self.data_ctrl.df.copy()
            df_export['Zone'] = self.zone_labels
            df_export.to_csv(
                os.path.join(self.path_absolute, '2_ZM_Classes.csv'),
                sep=',', index=False, encoding='utf-8'
            )
        except Exception as e:
            self._show_warning(self.tr('Erro na exportação'), str(e))

    # Stubs
    def on_zone_results_table_double_clicked(self, item):
        pass

    def on_fpi_nce_label_clicked(self, value):
        pass

    def on_zones_label_clicked(self, value):
        pass

    def add_coord_to_zones(self, filename):
        pass

    def add_var_to_zones(self, filename):
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
