# -*- coding: utf-8 -*-
"""Management zones (clustering) controller.

Ported faithfully from the monolithic ``smart_map`` class (Smart_Map.py).
The ORIGINAL workflow is FILE-DRIVEN: interpolated maps (``*_Grid_Map.kri`` /
``*_Grid_Map.svm`` CSVs) are listed in ``datatable_ZM_Maps``; the user adds
per-variable files whose X/Y are concatenated into ``df_ZM_Coord`` and whose
3rd column is concatenated into ``df_ZM_Var`` and written to
``2_ZM_<target>_Vars.csv``. Fuzzy c-means then derives the management zones.

  - load_maps_to_generate_ZM                  -> load_maps_to_generate_zones
  - datatable_ZM_Maps_checkbox_clicked        -> on_zone_maps_checkbox_clicked
  - func_ZM_Add_Coord                         -> add_coord_to_zones
  - func_ZM_Add_Var                           -> add_var_to_zones
  - pushButton_ZM_Add_Var_clicked             -> on_add_var_clicked
  - pushButton_ZM_Add_All_Vars_Selected_clicked -> on_add_all_selected_vars_clicked
  - pushButton_ZM_Remove_Var_clicked          -> on_remove_var_clicked
  - pushButton_ZM_Calc_Nr_Ideal_ZM_clicked    -> on_calc_ideal_zones_clicked
  - spinBox_ZM_NrZonas_changed                 -> on_zone_count_changed
  - pushButton_ZM_Calcular_clicked            -> on_calculate_zones_clicked
  - label_ZM_FPI_NCE_clicked                  -> on_fpi_nce_label_clicked
  - label_ZM_clicked                          -> on_zones_label_clicked
  - datatable_ZM_doubleClicked / _Classe_     -> on_*_table_double_clicked

Zones-tab widgets live on ``self.view`` (zones_view). Shared widgets
(QGIS export checkboxes, layer combos, boundary contour) live on the data
view, reached via ``self.data_ctrl.dialog``. The Pixel_Size_X/Y_ZM derived
from the interpolated-grid spacing are stashed on data_ctrl so the raster
export delegator sizes the output grid correctly. Raster/vector export goes
through the data_ctrl delegators.
"""

import os
import time
import math
import platform

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt6   # FPI / NCE plot
import matplotlib.pyplot as plt7   # management-zones class map

from sklearn.preprocessing import scale

from qgis.PyQt import QtCore, QtWidgets, QtGui
from qgis.PyQt.QtWidgets import (
    QMessageBox, QTableWidgetItem, QProgressDialog, QFileDialog,
)
from qgis.PyQt.QtGui import QIcon, QPixmap

system = platform.system()  # [Windows, Linux, Darwin]
if system != 'Darwin':
    try:
        from PIL import Image
    except ImportError:
        Image = None
else:
    Image = None


class ZonesController:
    """Handles management zone definition via fuzzy c-means clustering."""

    def __init__(self, view, data_ctrl, zones_mgr, icon_path, path_absolute, tr_func):
        self.view = view
        self.data_ctrl = data_ctrl
        self.zones_mgr = zones_mgr
        self.icon_path = icon_path
        self.path_absolute = path_absolute
        self.tr = tr_func

        # Map-selection state (datatable_ZM_Maps).
        self.list_rows_Map_ZM = []
        self.list_Z_Map_ZM = []
        self.list_Points_Map_ZM = []

        # Added-variable state.
        self.list_cov_ZM = []
        self.list_cov_ZM_metodo = []
        self.df_ZM_Coord = pd.DataFrame()
        self.df_ZM_Var = pd.DataFrame()
        self.df_ZM = pd.DataFrame()

        # Workflow flags (mirror the old self.* flags).
        self.ZM_Add_Coord = False
        self.ZM_Add_Var = False
        self.Calc_Nr_Ideal_ZM = False
        self.ZM_Calcular = False

        # FPI / NCE sweep cache.
        self.NK = []
        self.FPI = []
        self.NCE = []
        self.fpi = ''
        self.nce = ''

        # Pixel sizes derived from the interpolated grid spacing.
        self.Pixel_Size_X_ZM = None
        self.Pixel_Size_Y_ZM = None

    # ------------------------------------------------------------ shared widgets
    @property
    def data_view(self):
        """Shared data-tab dialog (export checkboxes, layer/contour combos)."""
        return self.data_ctrl.dialog

    # ===================================================================== Maps
    def load_maps_to_generate_zones(self):
        """Scan the working directory for interpolated maps (.kri / .svm).

        Builds the 5-column ``datatable_ZM_Maps`` (checkbox / Z / method /
        points / file) and (re)initialises the selection lists. Ported from
        load_maps_to_generate_ZM.
        """
        filenames = os.listdir(os.path.join(self.path_absolute))
        lista = []
        for filename in filenames:
            if ('_Grid_Map.kri' in filename) or ('_Grid_Map.svm' in filename):
                lista.append(filename)

        self.view.datatable_ZM_Maps.setColumnCount(5)
        self.view.datatable_ZM_Maps.setRowCount(len(lista))

        try:
            cols = [self.tr('Marcar'), 'Z', self.tr('Método'),
                    self.tr('Pontos'), self.tr('Arquivo')]
            self.view.datatable_ZM_Maps.setHorizontalHeaderLabels(cols)
        except AttributeError:
            self._show_warning(self.tr('Mensagem'),
                               self.tr('Erro ao carregar tabela. Valor Inválido!'))

        for i in range(len(lista)):
            if os.path.isfile(os.path.join(self.path_absolute, lista[i])):

                if '1_Krig_' in lista[i]:
                    Metodo = 'Ordinary Kriging'
                    start = 7
                else:
                    Metodo = 'ML-SVM'
                    start = 6

                stop = len(lista[i]) - 9   # strip '_Grid_Map.kri' / '_Grid_Map.svm'
                Z = lista[i][start:stop]

                filename = os.path.join(self.path_absolute, lista[i])
                df_Map = pd.read_csv(filename, sep=',')

                try:
                    chkBoxItem = QTableWidgetItem()
                    chkBoxItem.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
                    chkBoxItem.setCheckState(QtCore.Qt.Unchecked)
                    self.view.datatable_ZM_Maps.setItem(i, 0, chkBoxItem)

                    self.view.datatable_ZM_Maps.setItem(i, 1, QTableWidgetItem(Z))
                    self.view.datatable_ZM_Maps.setItem(i, 2, QTableWidgetItem(Metodo))
                    self.view.datatable_ZM_Maps.setItem(i, 3, QTableWidgetItem(str(len(df_Map))))
                    self.view.datatable_ZM_Maps.setItem(i, 4, QTableWidgetItem(lista[i]))
                except AttributeError:
                    self._show_warning(self.tr('Mensagem'),
                                       self.tr('Erro ao carregar tabela. Valor Inválido!'))

                self.view.datatable_ZM_Maps.resizeColumnsToContents()
                self.view.datatable_ZM_Maps.setEditTriggers(
                    QtWidgets.QTableWidget.NoEditTriggers)

        # (Re)initialise the selection state every load (matches old behaviour).
        self.list_rows_Map_ZM = []
        self.list_Z_Map_ZM = []
        self.list_Points_Map_ZM = []
        self.view.pushButton_ZM_Add_All_Vars_Selected.setEnabled(False)

    def on_zone_maps_checkbox_clicked(self, item):
        """Toggle a map's selection, validating equal point counts.

        Ported from datatable_ZM_Maps_checkbox_clicked.
        """
        if item.column() != 0:
            return

        if item.checkState() == QtCore.Qt.Checked:

            Z_selected = False
            Z = self.view.datatable_ZM_Maps.item(item.row(), 1).text()

            Points_dif = False
            Points = self.view.datatable_ZM_Maps.item(item.row(), 3).text()

            for p in range(len(self.list_Points_Map_ZM)):
                if Points != self.list_Points_Map_ZM[p]:
                    Points_dif = True

            if Points_dif:
                self._show_warning(
                    self.tr('Mensagem'),
                    self.tr('O número de pontos de todos os mapas interpolados '
                            'devem ser igual para gerar Zonas de Manejo.'))
                item.setCheckState(QtCore.Qt.Unchecked)

            if (not Z_selected) and (not Points_dif):
                if item.row() not in self.list_rows_Map_ZM:
                    self.list_rows_Map_ZM.append(item.row())
                    self.list_Z_Map_ZM.append(Z)
                self.list_Points_Map_ZM.append(Points)
                self.list_rows_Map_ZM.sort()

        else:
            if item.row() in self.list_rows_Map_ZM:
                self.list_rows_Map_ZM.remove(item.row())

            Z = self.view.datatable_ZM_Maps.item(item.row(), 1).text()
            if Z in self.list_Z_Map_ZM:
                self.list_Z_Map_ZM.remove(Z)

            Points = self.view.datatable_ZM_Maps.item(item.row(), 3).text()
            if Points in self.list_Points_Map_ZM:
                self.list_Points_Map_ZM.remove(Points)

        if len(self.list_rows_Map_ZM) > 0:
            self.view.pushButton_ZM_Add_All_Vars_Selected.setEnabled(True)
        else:
            self.view.pushButton_ZM_Add_All_Vars_Selected.setEnabled(False)

    # ============================================================ Add coord/var
    def add_coord_to_zones(self, filename):
        """Read a map file and seed df_ZM_Coord with its X/Y. (func_ZM_Add_Coord)."""
        self.view.tabWidget_ZM.setCurrentIndex(1)

        self.view.comboBox_ZM_var.clear()
        self.view.datatable_ZM.setColumnCount(0)
        self.view.datatable_ZM.setRowCount(0)

        self.list_cov_ZM = []
        self.list_cov_ZM_metodo = []

        self.df_ZM_Coord = pd.read_csv(filename, sep=',')

        tot_nan = self.df_ZM_Coord.isnull().sum().sum()
        if tot_nan > 0:
            self.df_ZM_Coord = self.df_ZM_Coord.fillna(self.data_ctrl.df.mean())

        self.df_ZM_Coord = self.df_ZM_Coord.iloc[:, 0:2]   # Coord_X, Coord_Y

        self.ZM_Add_Coord = True
        self.ZM_Add_Var = False

        self.Calc_Nr_Ideal_ZM = False
        self.view.lineEdit_ZM_FPI.setText('')
        self.view.lineEdit_ZM_NCE.setText('')

        self.view.pushButton_ZM_Add_Var.setEnabled(True)

        if len(list(self.df_ZM_Coord.columns.values)) == 2:   # only X, Y so far
            self.view.groupBox_ZM_Remove_Var.setEnabled(False)
            self.view.pushButton_ZM_Remove_Var.setEnabled(False)
            self.view.groupBox_ZM_Calc_Nr_Ideal_ZM.setEnabled(False)
            self.view.pushButton_ZM_Calc_Nr_Ideal_ZM.setEnabled(False)
            self.view.pushButton_ZM_Calcular.setEnabled(False)
            self.view.groupBox_ZM_Calcular.setEnabled(False)
        else:
            self.view.groupBox_ZM_Remove_Var.setEnabled(True)
            self.view.pushButton_ZM_Remove_Var.setEnabled(True)
            self.view.groupBox_ZM_Calc_Nr_Ideal_ZM.setEnabled(True)
            self.view.pushButton_ZM_Calc_Nr_Ideal_ZM.setEnabled(True)
            self.view.pushButton_ZM_Calcular.setEnabled(True)
            self.view.groupBox_ZM_Calcular.setEnabled(True)

        self.view.label_ZM.hide()
        self.view.label_ZM_FPI_NCE.hide()

    def add_var_to_zones(self, filename):
        """Concatenate a map file's 3rd column into df_ZM_Var. (func_ZM_Add_Var)."""
        self.view.tabWidget_ZM.setCurrentIndex(1)

        df = pd.read_csv(filename, sep=',')

        tot_nan = df.isnull().sum().sum()
        if tot_nan > 0:
            df = df.fillna(self.data_ctrl.df.mean())

        if len(self.df_ZM_Coord) != len(df):
            msg = (self.tr('Variável a ser adicionada possui ') + str(len(df)) +
                   self.tr(' pontos interpolados.'))
            msg = msg + '\n' + self.tr('Tabela de ZM possui ') + str(len(self.df_ZM_Coord)) + \
                self.tr(' pontos interpolados.')
            msg = msg + '\n' + self.tr('Não é possível adicionar a variável selecionada.')
            msg = msg + '\n' + self.tr('Número de pontos interpolados são diferentes.')
            self._show_warning(self.tr('Mensagem'), msg)
            return

        if not self.ZM_Add_Var:
            self.df_ZM_Var = df.iloc[:, [2]]               # 3rd column (index 2)
        else:
            self.df_ZM_Var = pd.concat([self.df_ZM_Var, df.iloc[:, 2]], axis=1)

        tot_nan = self.df_ZM_Var.isnull().sum().sum()
        if tot_nan > 0:
            self.df_ZM_Var = self.df_ZM_Var.fillna(self.data_ctrl.df.mean())

        self.df_ZM_Var.to_csv(
            os.path.join(self.path_absolute,
                         '2_ZM_' + self.data_ctrl.VTarget_FileName + '_Vars.csv'),
            sep=',', index=False, encoding='utf-8')

        cols = [df.columns[2]]
        self.view.comboBox_ZM_var.addItems(cols)
        self.list_cov_ZM = [self.view.comboBox_ZM_var.itemText(i)
                            for i in range(self.view.comboBox_ZM_var.count())]

        if '1_Krig_' in filename:
            self.list_cov_ZM_metodo.append('Krig_' + df.columns[2])
        elif '1_SVM_' in filename:
            self.list_cov_ZM_metodo.append('SVM_' + df.columns[2])

        self.view.datatable_ZM.setColumnCount(len(self.df_ZM_Var.columns))
        self.view.datatable_ZM.setRowCount(len(self.df_ZM_Var.index))

        try:
            self.view.datatable_ZM.setHorizontalHeaderLabels(
                list(self.df_ZM_Var.columns.values))
        except AttributeError:
            self._show_warning(self.tr('Mensagem'),
                               self.tr('Erro ao carregar tabela. Valor Inválido!'))

        maximum = len(self.df_ZM_Var.index)
        progress = self._create_progress_dialog(
            self.tr('Adicionando variável para gerar Zonas de Manejo.') + ' ' +
            df.columns[2] + '...', maximum)

        cont = 1
        try:
            last_col = len(self.df_ZM_Var.columns) - 1
            for i in range(len(self.df_ZM_Var.index)):
                valor = self.df_ZM_Var.iloc[i, last_col]
                if valor.dtype == "float64":
                    valor = '%.3f' % valor
                self.view.datatable_ZM.setItem(i, last_col, QTableWidgetItem(str(valor)))
                cont = cont + 1
                progress.setValue(cont)
                if progress.wasCanceled():
                    progress.close()
                    return
        except AttributeError:
            self._show_warning(self.tr('Mensagem'),
                               self.tr('Erro ao carregar tabela. Valor Inválido!'))

        self.view.datatable_ZM.resizeColumnsToContents()
        self.view.datatable_ZM.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)

        self.ZM_Add_Var = True

        self.Calc_Nr_Ideal_ZM = False
        self.view.lineEdit_ZM_FPI.setText('')
        self.view.lineEdit_ZM_NCE.setText('')

        self.view.groupBox_ZM_Remove_Var.setEnabled(True)
        self.view.pushButton_ZM_Remove_Var.setEnabled(True)
        self.view.groupBox_ZM_Calc_Nr_Ideal_ZM.setEnabled(True)
        self.view.pushButton_ZM_Calc_Nr_Ideal_ZM.setEnabled(True)
        self.view.pushButton_ZM_Calcular.setEnabled(True)
        self.view.groupBox_ZM_Calcular.setEnabled(True)

        self.view.datatable_ZM_Classe.setColumnCount(0)
        self.view.datatable_ZM_Classe.setRowCount(0)

        self.view.label_ZM.hide()
        self.view.label_ZM_FPI_NCE.hide()

        progress.close()

    def on_add_var_clicked(self):
        """Open a file and add it as a zone variable. (pushButton_ZM_Add_Var_clicked)."""
        filename = QFileDialog.getOpenFileName(
            self.view, self.tr('Abrir Arquivo'), os.path.join(self.path_absolute),
            "Interpolated files (*.kri;*.svm)")

        if filename[0] != '':
            if not self.ZM_Add_Coord:
                self.add_coord_to_zones(filename[0])
            self.add_var_to_zones(filename[0])

    def on_add_all_selected_vars_clicked(self):
        """Add every selected map. (pushButton_ZM_Add_All_Vars_Selected_clicked)."""
        if len(self.list_rows_Map_ZM) > 0:
            for i in range(len(self.list_rows_Map_ZM)):
                row = self.list_rows_Map_ZM[i]
                filename = os.path.join(
                    self.path_absolute,
                    self.view.datatable_ZM_Maps.item(row, 4).text())
                if i == 0:   # first variable -> seed the coordinates
                    self.add_coord_to_zones(filename)
                self.add_var_to_zones(filename)

    def on_remove_var_clicked(self):
        """Remove the selected variable. (pushButton_ZM_Remove_Var_clicked)."""
        if len(self.list_cov_ZM) == 0:
            self._show_warning(self.tr('Mensagem'),
                               self.tr('Todas as variáveis foram removidas.'))
            return

        id_col = self.view.comboBox_ZM_var.currentIndex()

        if id_col >= 0:
            self.view.tabWidget_ZM.setCurrentIndex(1)

            list_cov_ZM_Index = [i for i in range(self.view.comboBox_ZM_var.count())]
            list_cov_ZM_Index.remove(id_col)

            del self.list_cov_ZM_metodo[id_col]
            self.df_ZM_Var = self.df_ZM_Var.iloc[:, list_cov_ZM_Index]

            self.df_ZM_Var.to_csv(
                os.path.join(self.path_absolute,
                             '2_ZM_' + self.data_ctrl.VTarget_FileName + '_Vars.csv'),
                sep=',', index=False, encoding='utf-8')

            self.view.comboBox_ZM_var.removeItem(id_col)
            self.list_cov_ZM = [self.view.comboBox_ZM_var.itemText(i)
                                for i in range(self.view.comboBox_ZM_var.count())]

            self.view.datatable_ZM.removeColumn(id_col)
            self.view.datatable_ZM.resizeColumnsToContents()
            self.view.datatable_ZM.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)

            if len(self.list_cov_ZM) == 0:
                self.ZM_Add_Var = False
                self.view.groupBox_ZM_Remove_Var.setEnabled(False)
                self.view.pushButton_ZM_Remove_Var.setEnabled(False)
                self.view.groupBox_ZM_Calc_Nr_Ideal_ZM.setEnabled(False)
                self.view.pushButton_ZM_Calc_Nr_Ideal_ZM.setEnabled(False)
                self.view.pushButton_ZM_Calcular.setEnabled(False)
                self.view.groupBox_ZM_Calcular.setEnabled(False)
                self.view.datatable_ZM.setColumnCount(0)
                self.view.datatable_ZM.setRowCount(0)
            else:
                self.view.groupBox_ZM_Remove_Var.setEnabled(True)
                self.view.pushButton_ZM_Remove_Var.setEnabled(True)
                self.view.groupBox_ZM_Calc_Nr_Ideal_ZM.setEnabled(True)
                self.view.pushButton_ZM_Calc_Nr_Ideal_ZM.setEnabled(True)
                self.view.pushButton_ZM_Calcular.setEnabled(True)
                self.view.groupBox_ZM_Calcular.setEnabled(True)

            self.Calc_Nr_Ideal_ZM = False
            self.view.lineEdit_ZM_FPI.setText('')
            self.view.lineEdit_ZM_NCE.setText('')

            self.view.datatable_ZM_Classe.setColumnCount(0)
            self.view.datatable_ZM_Classe.setRowCount(0)

            self.view.label_ZM.hide()
            self.view.label_ZM_FPI_NCE.hide()
        else:
            self._show_warning(
                self.tr('Mensagem'),
                self.tr('As Coordenadas (x, y) não podem ser removidas.'))

    # ================================================================ FPI / NCE
    def on_calc_ideal_zones_clicked(self):
        """Determine the ideal number of zones via FPI / NCE.

        Ported from pushButton_ZM_Calc_Nr_Ideal_ZM_clicked. Uses the user's
        spinBox_ZM_Iter / doubleSpinBox_ZM_CFuzzy values and Daniel Marçal's
        natural-log FPI / NCE.
        """
        if not self.ZM_Add_Var:
            self._show_warning(
                self.tr('Mensagem'),
                self.tr('Variável(is) deve(m) ser adicionadas para gerar Zonas de Manejo.'))
            return

        self.view.label_ZM_FPI_NCE.hide()
        self.view.tabWidget_ZM.setCurrentIndex(2)

        num_iteration = self.view.spinBox_ZM_Iter.value()
        coef_nebuloso = self.view.doubleSpinBox_ZM_CFuzzy.value()
        tol = 1.0E-5

        self.df_ZM = pd.concat([self.df_ZM_Var], axis=1)

        tot_nan = self.df_ZM.isnull().sum().sum()
        if tot_nan > 0:
            self.df_ZM.dropna(inplace=True)
            self.df_ZM.reset_index(drop=True, inplace=True)

        # Standardise by row (axis=1): X is [n_features, n_samples].
        X = np.copy(self.df_ZM)
        X = X.T
        X = scale(X, axis=1, with_mean=True, with_std=True, copy=True)

        progress = self._create_progress_dialog(
            self.tr('Calculando número ideal de Zonas de Manejo.') + '...', 10)

        def _cb(nclasses):
            progress.setValue(nclasses)
            return progress.wasCanceled()

        self.NK, self.FPI, self.NCE, num_zones = self.zones_mgr.calculate_ideal_zones(
            X, coef_nebuloso, num_iteration, tol=tol, progress_cb=_cb)

        if self.NK is None:   # user cancelled
            progress.close()
            return

        nK = self.NK.index(num_zones)

        self.fpi = '%.3f' % self.FPI[nK]
        self.view.lineEdit_ZM_FPI.setText(str(self.fpi))
        self.nce = '%.3f' % self.NCE[nK]
        self.view.lineEdit_ZM_NCE.setText(str(self.nce))

        try:
            self.view.spinBox_ZM_NrZonas.valueChanged.disconnect()
        except TypeError:
            pass
        self.view.spinBox_ZM_NrZonas.setValue(num_zones)
        self.view.spinBox_ZM_NrZonas.valueChanged.connect(self.on_zone_count_changed)

        # FPI / NCE plot.
        plt6.close()
        plt6.title(self.tr('Número de Classes') + ': ' + str(num_zones) +
                   '   FPI: ' + str(self.fpi) + '   NCE: ' + str(self.nce))
        plt6.xlabel(self.tr('Número de Classes'))
        plt6.ylabel('FPI / NCE')
        plt6.plot(self.NK, self.FPI, marker='*', label='FPI')
        plt6.plot(self.NK, self.NCE, marker='+', label='NCE')
        plt6.legend()
        plt6.subplots_adjust(wspace=0.6, hspace=0.6, left=0.15, right=0.95,
                             bottom=0.1, top=0.95)
        plt6.ticklabel_format(style='plain', useOffset=False, axis='both')
        ax = plt6.gca()
        ax.format_coord = lambda x, y: '%10d, %10d' % (x, y)

        png = os.path.join(self.path_absolute,
                           '2_ZM_' + self.data_ctrl.VTarget_FileName + '_FPI_NCE.png')
        plt6.savefig(png)
        pixmap6 = QPixmap(png)
        self.view.label_ZM_FPI_NCE.show()
        self.view.label_ZM_FPI_NCE.setPixmap(pixmap6)

        if self._show_maps_checked():
            plt6.show()

        self.Calc_Nr_Ideal_ZM = True

        self.view.datatable_ZM_Classe.setColumnCount(0)
        self.view.datatable_ZM_Classe.setRowCount(0)
        self.view.label_ZM.hide()

        progress.close()

    def on_zone_count_changed(self, value=None):
        """Re-read the cached FPI/NCE for the chosen zone count.

        Ported from spinBox_ZM_NrZonas_changed.
        """
        if self.Calc_Nr_Ideal_ZM:
            num_zones = self.view.spinBox_ZM_NrZonas.value()
            self.fpi = '%.3f' % self.FPI[num_zones - 2]
            self.view.lineEdit_ZM_FPI.setText(str(self.fpi))
            self.nce = '%.3f' % self.NCE[num_zones - 2]
            self.view.lineEdit_ZM_NCE.setText(str(self.nce))

    # =============================================================== Calculate
    def on_calculate_zones_clicked(self):
        """Generate the management zones via fuzzy c-means.

        Ported from pushButton_ZM_Calcular_clicked. Writes _Class.csv (z-field
        'Classe'), _MP.csv (membership) and _Vars.csv with CoordX_SM/CoordY_SM,
        derives the ZM pixel sizes from the coord spacing, plots the class map
        and runs the QGIS raster/points/polygons export gated on checkBox_Qgis_*.
        """
        if not self.ZM_Add_Var:
            self._show_warning(
                self.tr('Mensagem'),
                self.tr('Variável(is) deve(m) ser adicionadas para gerar Zonas de Manejo.'))
            return

        data_view = self.data_view

        num_iteration = self.view.spinBox_ZM_Iter.value()
        num_zones = self.view.spinBox_ZM_NrZonas.value()
        coef_nebuloso = self.view.doubleSpinBox_ZM_CFuzzy.value()
        tol = 1.0E-5

        self.df_ZM = pd.concat([self.df_ZM_Coord, self.df_ZM_Var], axis=1)

        tot_nan = self.df_ZM.isnull().sum().sum()
        if tot_nan > 0:
            self.df_ZM.dropna(inplace=True)
            self.df_ZM.reset_index(drop=True, inplace=True)

        data = np.array(self.df_ZM, dtype=float)

        X = np.copy(data[:, [0, 1]])           # Coord_X, Coord_Y

        n_cols = len(self.df_ZM.columns)
        if n_cols < 3 or n_cols > 22:
            self._show_warning(self.tr('Mensagem'),
                               self.tr('Número Máximo de classes excedido.'))
            return

        # Attribute columns 2..end, transposed to [n_features, n_samples]
        # (equivalent to the old per-count np.vstack ladder).
        alldata = data[:, 2:].T.copy()

        if self.view.checkBox_ZM_Normalizar.isChecked():
            alldata = scale(alldata, axis=1, with_mean=True, with_std=True, copy=True)

        cntr, u_orig, cluster_membership = self.zones_mgr.cluster(
            alldata, num_zones, coef_nebuloso, num_iteration, tol=tol)

        # --------------- _Class.csv (X, Y, Classe) + pixel sizes ---------------
        lista = []
        for i in range(len(X)):
            lista.append([X[i, 0], X[i, 1], cluster_membership[i]])
        lista = np.array(lista)

        lista_CoordX = list(set(lista[:, 0]))
        lista_CoordY = list(set(lista[:, 1]))
        lista_CoordX.sort()
        lista_CoordY.sort()

        self.Pixel_Size_X_ZM = int(lista_CoordX[1] - lista_CoordX[0])
        self.Pixel_Size_Y_ZM = int(lista_CoordY[1] - lista_CoordY[0])
        # Stash on data_ctrl so the raster export delegator sizes the grid.
        self.data_ctrl.Pixel_Size_X_ZM = self.Pixel_Size_X_ZM
        self.data_ctrl.Pixel_Size_Y_ZM = self.Pixel_Size_Y_ZM

        df_ZM_Classe = pd.DataFrame(np.atleast_2d(lista),
                                    columns=['CoordX_SM', 'CoordY_SM', 'Classe'])
        df_ZM_Classe.to_csv(
            os.path.join(self.path_absolute,
                         '2_ZM_' + self.data_ctrl.VTarget_FileName + '_Class.csv'),
            sep=',', index=False, encoding='utf-8')

        maximum = (len(df_ZM_Classe.index) * len(df_ZM_Classe.columns))
        progress = self._create_progress_dialog(
            self.tr('Gerando Zonas de Manejo.') + '...', maximum)

        self.view.datatable_ZM_Classe.setColumnCount(len(df_ZM_Classe.columns))
        self.view.datatable_ZM_Classe.setRowCount(len(df_ZM_Classe.index))

        try:
            cols = list(df_ZM_Classe.columns.values)
            cols[2] = '   ' + self.tr('Classe') + '   '
            self.view.datatable_ZM_Classe.setHorizontalHeaderLabels(cols)
        except AttributeError:
            self._show_warning(self.tr('Mensagem'),
                               self.tr('Erro ao carregar tabela. Valor Inválido!'))

        cont = 1
        try:
            for i in range(len(df_ZM_Classe.index)):
                for j in range(len(df_ZM_Classe.columns)):
                    valor = df_ZM_Classe.iloc[i, j]
                    if j == 2:
                        valor = round(valor)
                    elif valor.dtype == "float64":
                        valor = '%.3f' % valor
                    self.view.datatable_ZM_Classe.setItem(i, j, QTableWidgetItem(str(valor)))
                    cont = cont + 1
                    progress.setValue(cont)
                    if progress.wasCanceled():
                        progress.close()
                        return
        except AttributeError:
            self._show_warning(self.tr('Mensagem'),
                               self.tr('Erro ao carregar tabela. Valor Inválido!'))

        self.view.datatable_ZM_Classe.resizeColumnsToContents()
        self.view.datatable_ZM_Classe.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)

        u_orig = u_orig.T   # [K, N] -> [N, K]

        # --------------------------- FPI / NCE readouts -----------------------
        if self.Calc_Nr_Ideal_ZM:
            num_zones = self.view.spinBox_ZM_NrZonas.value()
            self.fpi = '%.3f' % self.FPI[num_zones - 2]
            self.view.lineEdit_ZM_FPI.setText(str(self.fpi))
            self.nce = '%.3f' % self.NCE[num_zones - 2]
            self.view.lineEdit_ZM_NCE.setText(str(self.nce))
        else:
            fpi, nce = self.zones_mgr.fpi_nce(u_orig, num_zones)
            self.fpi = '%.3f' % fpi
            self.view.lineEdit_ZM_FPI.setText(str(self.fpi))
            self.nce = '%.3f' % nce
            self.view.lineEdit_ZM_NCE.setText(str(self.nce))

        # ----------------------- _MP.csv (membership matrix) ------------------
        if num_zones < 1 or num_zones > 20:
            self._show_warning(self.tr('Mensagem'),
                               self.tr('Número Máximo de classes excedido.'))
            return

        self.Cord_X = 'CoordX_SM'
        self.Cord_Y = 'CoordY_SM'

        lista = []
        for i in range(len(u_orig)):
            row = [X[i, 0], X[i, 1]]
            for k in range(num_zones):
                row.append(u_orig[i, k])
            lista.append(row)
        lista = np.array(lista)

        cls_cols = ['Cls' + str(k + 1) for k in range(num_zones)]
        df_MP = pd.DataFrame(np.atleast_2d(lista),
                             columns=[self.Cord_X, self.Cord_Y] + cls_cols)
        df_MP.to_csv(
            os.path.join(self.path_absolute,
                         '2_ZM' + '_' + self.data_ctrl.VTarget_FileName + '_MP.csv'),
            sep=',', index=False, encoding='utf-8')

        # ----------------------------- _Vars.csv ------------------------------
        self.df_ZM.to_csv(
            os.path.join(self.path_absolute,
                         '2_ZM' + '_' + self.data_ctrl.VTarget_FileName + '_Vars.csv'),
            sep=',', index=False, encoding='utf-8')

        Cord_X_min_ZM = self.df_ZM['CoordX_SM'].min()
        Cord_Y_min_ZM = self.df_ZM['CoordY_SM'].min()
        Cord_X_max_ZM = self.df_ZM['CoordX_SM'].max()
        Cord_Y_max_ZM = self.df_ZM['CoordY_SM'].max()

        # If nothing is loaded on the data tab, adopt the ZM extent so the
        # raster export delegator has a valid grid bounding box.
        if (not self.data_ctrl.Var_Selected) and (not self.data_ctrl.Contorno_Definido):
            self.data_ctrl.Cord_X_min = Cord_X_min_ZM
            self.data_ctrl.Cord_Y_min = Cord_Y_min_ZM
            self.data_ctrl.Cord_X_max = Cord_X_max_ZM
            self.data_ctrl.Cord_Y_max = Cord_Y_max_ZM

        # ----------------------------- class map ------------------------------
        plt7.close()
        plt7.title(self.tr('ZM') + ': ' + str(self.data_ctrl.v_target) +
                   '   FPI: ' + str(self.fpi) + '   NCE: ' + str(self.nce))
        plt7.xlabel('Longitude (X)')
        plt7.ylabel('Latitude  (Y)')
        plt7.xlim(float(Cord_X_min_ZM - 100), float(Cord_X_max_ZM + 100))
        plt7.ylim(float(Cord_Y_min_ZM - 100), float(Cord_Y_max_ZM + 100))

        interval_x = int((self.data_ctrl.Cord_X_max - self.data_ctrl.Cord_X_min) / 5)
        if interval_x == 0:
            interval_x = 1
        xmarks = [i for i in range(int(Cord_X_min_ZM), int(Cord_X_max_ZM), interval_x)]
        plt7.xticks(xmarks)

        interval_y = int((Cord_Y_max_ZM - Cord_Y_min_ZM) / 7)
        if interval_y == 0:
            interval_y = 1
        ymarks = [i for i in range(int(Cord_Y_min_ZM), int(Cord_Y_max_ZM), interval_y)]
        plt7.yticks(ymarks)

        classes = np.arange(1, num_zones + 1)
        classes_string = [str(i) for i in classes]
        scatter = plt7.scatter(X[:, 0], X[:, 1], c=cluster_membership, cmap='RdYlGn')
        plt7.legend(handles=scatter.legend_elements()[0],
                    title=self.tr('Classe'), labels=classes_string)
        plt7.subplots_adjust(wspace=0.6, hspace=0.6, left=0.15, right=0.95,
                             bottom=0.1, top=0.95)
        plt7.ticklabel_format(style='plain', useOffset=False, axis='both')
        ax = plt7.gca()
        ax.format_coord = lambda x, y: '%10d, %10d' % (x, y)

        png = os.path.join(self.path_absolute,
                           '2_ZM_' + self.data_ctrl.VTarget_FileName + '_Class.png')
        plt7.savefig(png)
        pixmap7 = QPixmap(png)
        self.view.label_ZM.show()
        self.view.label_ZM.setPixmap(pixmap7)

        if self._show_maps_checked():
            plt7.show()

        self.view.tabWidget_ZM.setCurrentIndex(3)

        # --------------------------- QGIS export ------------------------------
        if data_view.checkBox_Qgis_Raster.isChecked():

            Input_Table = '2_ZM_' + self.data_ctrl.VTarget_FileName + '_Class.csv'
            Output_Layer_File_tiff = os.path.join(
                self.path_absolute, '2_ZM_' + self.data_ctrl.VTarget_FileName + '_Class.tiff')
            Output_Layer_Name = '2_ZM_' + self.data_ctrl.VTarget_FileName
            z_field = 'Classe'

            try:
                data_view.mMapLayerComboBox.currentIndexChanged.disconnect()
            except TypeError:
                pass

            Output_Layer_File_tiff = self.data_ctrl.export_raster_to_qgis(
                Input_Table, Output_Layer_File_tiff, Output_Layer_Name, z_field)

            # points
            if data_view.checkBox_Qgis_Vector_Points.isChecked():
                if (data_view.checkBox_Area_Contorno.isChecked() and
                        data_view.mMapLayerComboBox_AreaCont.currentIndex() >= 0):
                    cont = cont + 1
                    progress.setValue(cont)
                    if progress.wasCanceled():
                        progress.close()
                        return
                    self.data_ctrl.export_shapefile_to_qgis(
                        Output_Layer_File_tiff, "native:pixelstopoints")
                else:
                    data_view.checkBox_Qgis_Vector_Points.setChecked(False)

            # polygons
            if data_view.checkBox_Qgis_Vector_Polygons.isChecked():
                if (data_view.checkBox_Area_Contorno.isChecked() and
                        data_view.mMapLayerComboBox_AreaCont.currentIndex() >= 0):
                    cont = cont + 1
                    progress.setValue(cont)
                    if progress.wasCanceled():
                        progress.close()
                        return
                    self.data_ctrl.export_shapefile_to_qgis(
                        Output_Layer_File_tiff, "native:pixelstopolygons")
                else:
                    data_view.checkBox_Qgis_Vector_Polygons.setChecked(False)

        if data_view.checkBox_Qgis_Raster.isChecked():
            try:
                data_view.mMapLayerComboBox.currentIndexChanged.connect(
                    self.data_ctrl.on_layer_combo_changed)
            except (AttributeError, TypeError):
                pass

        self.ZM_Calcular = True
        progress.close()

    # ============================================================= preview/util
    def on_zone_vars_table_double_clicked(self, item=None):
        """Open the _Vars.csv file. (datatable_ZM_doubleClicked)."""
        try:
            os.startfile(os.path.join(
                self.path_absolute,
                '2_ZM_' + self.data_ctrl.VTarget_FileName + '_Vars.csv'))
        except (AttributeError, OSError):
            pass

    def on_zone_results_table_double_clicked(self, item=None):
        """Open the _Class.csv file. (datatable_ZM_Classe_doubleClicked)."""
        try:
            os.startfile(os.path.join(
                self.path_absolute,
                '2_ZM_' + self.data_ctrl.VTarget_FileName + '_Class.csv'))
        except (AttributeError, OSError):
            pass

    def on_fpi_nce_label_clicked(self, value=None):
        """Open the FPI/NCE plot full image. (label_ZM_FPI_NCE_clicked)."""
        if system != 'Darwin' and Image is not None:
            if self.Calc_Nr_Ideal_ZM:
                try:
                    image = Image.open(os.path.join(
                        self.path_absolute,
                        '2_ZM_' + self.data_ctrl.VTarget_FileName + '_FPI_NCE.png'))
                    image.show()
                except (AttributeError, OSError):
                    pass

    def on_zones_label_clicked(self, value=None):
        """Open the class map full image. (label_ZM_clicked)."""
        if system != 'Darwin' and Image is not None:
            if self.ZM_Calcular:
                try:
                    image = Image.open(os.path.join(
                        self.path_absolute,
                        '2_ZM_' + self.data_ctrl.VTarget_FileName + '_Class.png'))
                    image.show()
                except (AttributeError, OSError):
                    pass

    # ----------------------------------------------------------------- helpers
    def _show_maps_checked(self):
        """Whether 'Exibir Mapas' is checked (zones-local copy)."""
        chk = getattr(self.view, 'checkBox_Qgis_Maps', None)
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
