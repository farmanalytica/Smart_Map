# -*- coding: utf-8 -*-
"""Variogram and semivariogram controller."""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt2

from qgis.PyQt import QtCore, QtWidgets, QtGui
from qgis.PyQt.QtWidgets import QMessageBox, QTableWidgetItem
from qgis.PyQt.QtGui import QIcon, QPixmap

from ..krig import semivariogram


class VariogramController:
    """Handles variogram calculation, tuning, and visualization."""

    def __init__(self, view, data_controller, interp_mgr, icon_path, path_absolute, tr_func):
        self.view = view
        self.data_ctrl = data_controller
        self.interp_mgr = interp_mgr
        self.icon_path = icon_path
        self.path_absolute = path_absolute
        self.tr = tr_func

        # The kriging-tab widgets enabled by plot_variogram and the search-radius/
        # neighbour line edits live on the kriging view. Wired by Smart_Map after
        # the controllers are built (kept as a single owner, no duplicate state).
        self.kriging_view = None

        # Saved-semivariograms dataframe (one row per target variable, 23 columns).
        self.df_semivariograms = None
        self.list_rows_semiv = []

        # Variogram state
        self.lag = None
        self.gamma = None
        self.npoints = None
        self.gamma_t = None
        self.variancia = None
        self.models = {}
        self.model = None
        self.active_distance = None
        self.lag_distance = None

        # Parameters
        self.active_distance_ini = None  # From data_ctrl
        self.lag_distance_ini = None     # From data_ctrl
        self.max_dist = None             # From data_ctrl
        self.min_dist = None             # From data_ctrl

        # State flags
        self.Variogram = False           # Variogram calculated?
        self.Var_Selected = False        # Variables selected for interpolation?
        self.hide_horizontalSlider = False

        # Parameter bounds
        self.C0_Minimum = 0.0
        self.C0_Maximum = 1.0
        self.C0_C_Minimum = 1.0
        self.C0_C_Maximum = 10000.0
        self.Range_Minimum = 0.1
        self.Range_Maximum = 10000.0

    # Calculation (delegates to data_ctrl logic)
    def calculate_variogram(self, initial_variogram, nugget_range_sill):
        """Calculate semivariogram from data. Heavy lifting delegated to krig module."""
        if self.data_ctrl.xy is None or self.data_ctrl.z is None:
            return

        try:
            # Disconnect model combo signal
            try:
                self.view.comboBox_Modelo.currentIndexChanged.disconnect()
            except TypeError:
                pass

            # Get parameters
            self.active_distance = float(self.view.lineEdit_OK_DMax.text())
            self.lag_distance = float(self.view.lineEdit_OK_lags_dist.text())

            # Build semivariogram
            semiv = semivariogram.Semivariogram(self.data_ctrl.xy, self.data_ctrl.z)
            self.variancia = semiv.sample_variance

            # Calculate experimental semivariogram
            self.lag, self.gamma, self.npoints = semiv.Exp_Semiv(
                self.lag_distance, self.active_distance
            )

            # Ensure minimum 2 lags
            while len(self.npoints) < 2:
                self.lag_distance -= 1
                self.lag, self.gamma, self.npoints = semiv.Exp_Semiv(
                    self.lag_distance, self.active_distance
                )

            # Initial calculation - fit multiple models
            if initial_variogram:
                use_models = ['linear', 'linear-sill', 'exponential', 'spherical', 'gaussian']

                while True:
                    try:
                        self.models = semiv.Fit(use_models)
                        break
                    except ValueError as e:
                        if 'is infeasible' in str(e):
                            self.lag_distance += 1
                            self.lag, self.gamma, self.npoints = semiv.Exp_Semiv(
                                self.lag_distance, self.active_distance
                            )
                        else:
                            raise

                # Find best model (minimum RSS)
                min_rss = self.models['linear'][3]
                best_model = 'linear'

                for model_name in self.models:
                    if self.models[model_name][3] < min_rss:
                        min_rss = self.models[model_name][3]
                        best_model = model_name

                # Set model combo
                model_map = {
                    'linear': 0,
                    'linear-sill': 1,
                    'exponential': 2,
                    'spherical': 3,
                    'gaussian': 4
                }
                self.view.comboBox_Modelo.setCurrentIndex(model_map.get(best_model, 0))
                self.model = best_model

                # Calculate theoretical semivariogram
                nugget, range_, sill = self.models[self.model][0:3]
                self.gamma_t, rss, r2 = semiv.Gamma(self.model, [nugget, range_, sill])

                rss_val = self.models[self.model][3]
                r2_val = self.models[self.model][4]

                # Establish the OK neighbour-count / search-radius limits + defaults
                # (ported from the old pushButton_ImportQGIS tail; the kriging/variogram
                # edit handlers clamp against these). Stored on data_ctrl so a single
                # owner holds them, and only meaningful on the initial fit.
                n_data = len(self.data_ctrl.data)
                self.data_ctrl.VB_OK_Minimum = 4
                self.data_ctrl.VB_OK_Maximum = n_data
                self.data_ctrl.Raio_OK_Minimum = self.data_ctrl.min_dist
                self.data_ctrl.Raio_OK_Maximum = self.data_ctrl.max_dist
                if self.kriging_view is not None:
                    if n_data >= 16:
                        self.kriging_view.lineEdit_OK_VBNumMax.setText('16')
                    else:
                        self.kriging_view.lineEdit_OK_VBNumMax.setText(str(round(n_data / 2)))
                    self.kriging_view.lineEdit_OK_VBRaio.setText('%.3f' % self.data_ctrl.max_dist)

            # Update calculation - use selected model
            else:
                # Get selected model
                model_idx = self.view.comboBox_Modelo.currentIndex()
                model_names = ['linear', 'linear-sill', 'exponential', 'spherical', 'gaussian']
                use_models = [model_names[model_idx]] if model_idx < len(model_names) else ['linear']

                while True:
                    try:
                        self.models = semiv.Fit(use_models)
                        break
                    except ValueError as e:
                        if 'is infeasible' in str(e):
                            self.lag_distance += 1
                            self.lag, self.gamma, self.npoints = semiv.Exp_Semiv(
                                self.lag_distance, self.active_distance
                            )
                        else:
                            raise

                self.model = use_models[0]

                # Use user-provided parameters if set
                if nugget_range_sill:
                    nugget = float(self.view.lineEdit_Nugget.text())
                    range_ = float(self.view.lineEdit_Range.text())
                    sill = float(self.view.lineEdit_Sill.text())

                    self.models[self.model][0] = nugget
                    self.models[self.model][1] = range_
                    self.models[self.model][2] = sill
                else:
                    nugget, range_, sill = self.models[self.model][0:3]

                # Calculate theoretical
                self.gamma_t, rss, r2 = semiv.Gamma(self.model, [nugget, range_, sill])
                rss_val = rss
                r2_val = r2

            # Update UI
            self.view.lineEdit_OK_lags_dist.setText('%.3f' % self.lag_distance)
            self.view.lineEdit_Var_RMSE.setText('%.3f' % rss_val)

            # R^2 clamp to [-inf, +inf] outside [-1, 1] (ported from old logic).
            if -1 <= r2_val <= 1:
                self.view.lineEdit_Var_R2.setText('%.3f' % r2_val)
            elif r2_val < -1:
                self.view.lineEdit_Var_R2.setText('-inf')
            else:  # r2_val > 1
                self.view.lineEdit_Var_R2.setText('+inf')

            # ---- Dynamic slider / parameter-bounds block -----------------------
            # The edit handlers (on_nugget_edited, on_sill_edited, on_range_edited)
            # clamp against C0_Maximum / C0_C_Maximum / Range_Maximum, so those MUST
            # be (re)computed here every recalculation.
            self._configure_parameter_sliders(semiv, nugget, range_, sill)

        except Exception as e:
            self._show_warning(self.tr('Erro'), str(e))
        finally:
            # Reconnect model combo
            try:
                self.view.comboBox_Modelo.currentIndexChanged.connect(self.on_model_combo_changed)
            except (AttributeError, TypeError):
                pass

    def _configure_parameter_sliders(self, semiv, nugget, range_, sill):
        """Set parameter bounds and (re)configure the Nugget/Sill/Range sliders.

        Ported from the old calculate_variogram tail (~3324-3424). Computes:
          C0_Maximum  = gamma[-1]
          C0_C_Maximum = gamma[-1] * 3
          Range_Maximum = semiv.max_dist
        Hides the sliders entirely if any slider maximum would overflow Qt's int
        range (> 2147483647), otherwise shows/reconnects them with proper bounds.
        """
        gamma_last = self.gamma[len(self.gamma) - 1]

        # Overflow guard: Qt slider values are 32-bit ints scaled by 1000.
        if ((gamma_last * 1000) > 2147483647 or
                (semiv.max_dist * 1000) > 2147483647 or
                ((gamma_last * 3) * 1000) > 2147483647):
            self.hide_horizontalSlider = True
        else:
            self.hide_horizontalSlider = False

        # ---- Nugget --------------------------------------------------------
        self.C0_Maximum = gamma_last
        self.C0_Minimum = 0
        if self.hide_horizontalSlider:
            self.view.horizontalSlider_Nugget.hide()
            self.view.lineEdit_Nugget.setText('%.3f' % nugget)
        else:
            self.view.horizontalSlider_Nugget.show()
            try:
                self.view.horizontalSlider_Nugget.valueChanged.disconnect()
            except TypeError:
                pass
            self.view.horizontalSlider_Nugget.setMaximum(int(gamma_last * 1000))
            self.view.horizontalSlider_Nugget.setValue(int(nugget * 1000))
            self.view.lineEdit_Nugget.setText('%.3f' % nugget)
            self.view.horizontalSlider_Nugget.valueChanged.connect(self.on_nugget_slider_changed)

        # ---- Range ---------------------------------------------------------
        self.Range_Maximum = semiv.max_dist
        self.Range_Minimum = 0.001
        if self.hide_horizontalSlider:
            self.view.horizontalSlider_Range.hide()
            self.view.lineEdit_Range.setText('%.3f' % range_)
        else:
            self.view.horizontalSlider_Range.show()
            try:
                self.view.horizontalSlider_Range.valueChanged.disconnect()
            except TypeError:
                pass
            self.view.horizontalSlider_Range.setMaximum(int(semiv.max_dist * 1000))
            self.view.horizontalSlider_Range.setValue(int(range_ * 1000))
            self.view.lineEdit_Range.setText('%.3f' % range_)
            self.view.horizontalSlider_Range.valueChanged.connect(self.on_range_slider_changed)

        # ---- Search radius (use range when "Usar Alcance" is checked) ------
        if self.kriging_view is not None and self.kriging_view.checkBox_Krigagem_Alcance.isChecked():
            raio = float(self.view.lineEdit_Range.text())
            self.kriging_view.lineEdit_OK_VBRaio.setText('%.3f' % raio)

        # ---- Sill ----------------------------------------------------------
        self.C0_C_Maximum = gamma_last * 3
        self.C0_C_Minimum = 0
        if self.hide_horizontalSlider:
            self.view.horizontalSlider_Sill.hide()
            self.view.lineEdit_Sill.setText('%.3f' % sill)
        else:
            self.view.horizontalSlider_Sill.show()
            try:
                self.view.horizontalSlider_Sill.valueChanged.disconnect()
            except TypeError:
                pass
            self.view.horizontalSlider_Sill.setMaximum(int((gamma_last * 3) * 1000))
            self.view.horizontalSlider_Sill.setValue(int(sill * 1000))
            self.view.lineEdit_Sill.setText('%.3f' % sill)
            self.view.horizontalSlider_Sill.valueChanged.connect(self.on_sill_slider_changed)

    def plot_variogram(self):
        """Plot experimental and theoretical semivariogram."""
        if self.lag is None or self.gamma is None:
            return

        try:
            nugget = float(self.view.lineEdit_Nugget.text())
            rss = float(self.view.lineEdit_Var_RMSE.text())
            r2 = float(self.view.lineEdit_Var_R2.text())

            plt2.close()
            fig = plt2.figure(figsize=(10, 6))

            # Plot experimental
            plt2.scatter(self.lag, self.gamma, c=self.npoints, marker='s',
                        cmap='RdYlGn', label=self.tr('Semivariograma Experimental'))

            # Plot theoretical (starts at nugget)
            model_text = self.view.comboBox_Modelo.currentText()
            plt2.plot(np.insert(self.lag, 0, 0), np.insert(self.gamma_t, 0, nugget),
                     label=f'{model_text}   {self.tr("RMSE:")} {rss:.3f}   $R^2$: {r2:.3f}')

            # Plot sample variance if checked
            if self.view.checkBox_Variogram_Variancia.isChecked():
                plt2.plot(np.insert(self.lag, 0, 0),
                         np.full(len(self.lag) + 1, self.variancia),
                         linestyle=':', color='black',
                         label=self.tr('Variância Amostral'))

            plt2.xlim(0, plt2.xlim()[1])
            plt2.title(self.tr('Variograma Isotrópico'))
            plt2.ylabel(self.tr('Semivariância'))
            plt2.xlabel(self.tr('Distância') + ' (h)')

            # Colorbar
            m0 = int(np.floor(self.npoints.min()))
            m6 = int(np.ceil(self.npoints.max()))
            marks = [int(k * (m6 - m0) / 6.0 + m0) for k in range(7)]

            cbar = plt2.colorbar(aspect=30)
            cbar.ax.set_title(self.tr('Pares de') + '\n' + self.tr('pontos'))
            cbar.set_ticks(marks)
            cbar.set_ticklabels(marks)

            plt2.subplots_adjust(wspace=0.6, hspace=0.6, left=0.15, right=1.0,
                                bottom=0.1, top=0.95)

            # Save and display
            png_path = os.path.join(self.path_absolute,
                                   f'0_Variograma_{self.data_ctrl.VTarget_FileName}.png')
            plt2.savefig(png_path)

            pixmap = QPixmap(png_path)
            self.view.label_Variograma.setPixmap(pixmap)
            self.view.label_Variograma.show()

            # Enable variogram-tab widgets (owned by this view).
            self.view.groupBox_Variograma_Model.setEnabled(True)
            self.view.pushButton_VariogramaReset.setEnabled(True)
            self.view.lineEdit_Nugget.setEnabled(True)
            self.view.lineEdit_Sill.setEnabled(True)
            self.view.lineEdit_Range.setEnabled(True)

            # Enable kriging-tab widgets (owned by the kriging view).
            if self.kriging_view is not None:
                self.kriging_view.groupBox_Krigagem.setEnabled(True)
                self.kriging_view.lineEdit_OK_VBNumMax.setEnabled(True)
                self.kriging_view.lineEdit_OK_VBRaio.setEnabled(True)
                self.kriging_view.checkBox_Krigagem_Alcance.setEnabled(True)
                self.kriging_view.pushButton_Krigagem.setEnabled(True)
                self.kriging_view.checkBox_Krigagem_Std_Desv.setEnabled(True)

                self.kriging_view.label_Krigagem.hide()
                self.kriging_view.label_validacao_cruzada_OK.hide()
                self.kriging_view.pushButton_Validacao_Cruzada_OK.setEnabled(True)

                self.kriging_view.datatable_pontos_interpolados_OK.setColumnCount(0)
                self.kriging_view.datatable_pontos_interpolados_OK.setRowCount(0)

                # Also clear the cross-validation table (ported from old plot_variogram).
                self.kriging_view.datatable_validacao_cruzada_OK.setColumnCount(0)
                self.kriging_view.datatable_validacao_cruzada_OK.setRowCount(0)

            self.Variogram = True

        except Exception as e:
            self._show_warning(self.tr('Erro'), str(e))

    # Model selection
    def on_model_combo_changed(self, value):
        """Change variogram model and recalculate."""
        self._set_result_tab(0)
        self.calculate_variogram(initial_variogram=False, nugget_range_sill=False)
        self.plot_variogram()

    # Parameter tuning
    def on_dmax_edited(self):
        """Validate DMax and recalculate."""
        try:
            dmax = float(self.view.lineEdit_OK_DMax.text())

            if dmax > self.data_ctrl.max_dist:
                dmax = self.data_ctrl.max_dist

            lag_dist = float(self.view.lineEdit_OK_lags_dist.text())
            if dmax < lag_dist:
                dmax = lag_dist

            self.view.lineEdit_OK_DMax.setText('%.3f' % dmax)

            if self.Variogram:
                self.on_variogram_adjust_clicked()
        except ValueError:
            pass

    def on_lags_distance_edited(self):
        """Validate lag distance and recalculate."""
        try:
            lag_dist = float(self.view.lineEdit_OK_lags_dist.text())

            if lag_dist < self.data_ctrl.min_dist:
                lag_dist = self.data_ctrl.min_dist

            dmax = float(self.view.lineEdit_OK_DMax.text())
            if lag_dist > dmax:
                lag_dist = dmax

            self.view.lineEdit_OK_lags_dist.setText('%.3f' % lag_dist)

            if self.Variogram:
                self.on_variogram_adjust_clicked()
        except ValueError:
            pass

    def on_nugget_edited(self):
        """Validate nugget and recalculate."""
        try:
            nugget = float(self.view.lineEdit_Nugget.text())

            if nugget > self.C0_Maximum:
                nugget = self.C0_Maximum
            if nugget < self.C0_Minimum:
                nugget = self.C0_Minimum

            self.view.lineEdit_Nugget.setText('%.3f' % nugget)

            if not self.hide_horizontalSlider:
                try:
                    self.view.horizontalSlider_Nugget.valueChanged.disconnect()
                except TypeError:
                    pass
                self.view.horizontalSlider_Nugget.setValue(int(nugget * 1000))
                self.view.horizontalSlider_Nugget.valueChanged.connect(self.on_nugget_slider_changed)

            self._set_result_tab(0)
            self.calculate_variogram(initial_variogram=False, nugget_range_sill=True)
            self.plot_variogram()
        except ValueError:
            pass

    def on_nugget_slider_changed(self, value):
        """Update nugget from slider."""
        self._set_result_tab(0)
        nugget = float(value) / 1000.0
        self.view.lineEdit_Nugget.setText('%.3f' % nugget)
        self.calculate_variogram(initial_variogram=False, nugget_range_sill=True)
        self.plot_variogram()

    def on_sill_edited(self):
        """Validate sill and recalculate."""
        try:
            sill = float(self.view.lineEdit_Sill.text())

            if sill > self.C0_C_Maximum:
                sill = self.C0_C_Maximum
            if sill < self.C0_C_Minimum:
                sill = self.C0_C_Minimum

            self.view.lineEdit_Sill.setText('%.3f' % sill)

            if not self.hide_horizontalSlider:
                try:
                    self.view.horizontalSlider_Sill.valueChanged.disconnect()
                except TypeError:
                    pass
                self.view.horizontalSlider_Sill.setValue(int(sill * 1000))
                self.view.horizontalSlider_Sill.valueChanged.connect(self.on_sill_slider_changed)

            self._set_result_tab(0)
            self.calculate_variogram(initial_variogram=False, nugget_range_sill=True)
            self.plot_variogram()
        except ValueError:
            pass

    def on_sill_slider_changed(self, value):
        """Update sill from slider."""
        self._set_result_tab(0)
        sill = float(value) / 1000.0
        self.view.lineEdit_Sill.setText('%.3f' % sill)
        self.calculate_variogram(initial_variogram=False, nugget_range_sill=True)
        self.plot_variogram()

    def on_range_edited(self):
        """Validate range and recalculate."""
        try:
            range_ = float(self.view.lineEdit_Range.text())

            if range_ > self.Range_Maximum:
                range_ = self.Range_Maximum
            if range_ < self.Range_Minimum:
                range_ = self.Range_Minimum

            self.view.lineEdit_Range.setText('%.3f' % range_)

            if not self.hide_horizontalSlider:
                try:
                    self.view.horizontalSlider_Range.valueChanged.disconnect()
                except TypeError:
                    pass
                self.view.horizontalSlider_Range.setValue(int(range_ * 1000))
                self.view.horizontalSlider_Range.valueChanged.connect(self.on_range_slider_changed)

            self._set_result_tab(0)
            self.calculate_variogram(initial_variogram=False, nugget_range_sill=True)
            self.plot_variogram()
        except ValueError:
            pass

    def on_range_slider_changed(self, value):
        """Update range from slider."""
        self._set_result_tab(0)
        range_ = float(value) / 1000.0
        self.view.lineEdit_Range.setText('%.3f' % range_)
        self.calculate_variogram(initial_variogram=False, nugget_range_sill=True)
        self.plot_variogram()

    def on_vb_num_max_edited(self):
        """Validate kriging neighbor count."""
        try:
            vb = int(self.kriging_view.lineEdit_OK_VBNumMax.text())

            if vb > self.data_ctrl.VB_OK_Maximum:
                vb = self.data_ctrl.VB_OK_Maximum
            if vb < self.data_ctrl.VB_OK_Minimum:
                vb = self.data_ctrl.VB_OK_Minimum

            self.kriging_view.lineEdit_OK_VBNumMax.setText(str(vb))
        except ValueError:
            pass

    def on_vb_raio_edited(self):
        """Validate kriging search radius."""
        try:
            raio = float(self.kriging_view.lineEdit_OK_VBRaio.text())

            if raio > self.data_ctrl.max_dist:
                raio = self.data_ctrl.max_dist
            if raio < self.data_ctrl.min_dist:
                raio = self.data_ctrl.min_dist

            self.kriging_view.lineEdit_OK_VBRaio.setText('%.3f' % raio)
        except ValueError:
            pass

    def on_use_range_for_search_toggled(self, checked):
        """Use variogram range or max distance for search radius."""
        if checked:
            try:
                raio = float(self.view.lineEdit_Range.text())
            except ValueError:
                raio = self.data_ctrl.max_dist
        else:
            raio = self.data_ctrl.max_dist

        self.kriging_view.lineEdit_OK_VBRaio.setText('%.3f' % raio)

    def on_variogram_reset_clicked(self):
        """Reset variogram to initial calculation."""
        self._set_result_tab(0)

        self.view.lineEdit_OK_DMax.setText('%.3f' % self.data_ctrl.active_distance_ini)
        self.view.lineEdit_OK_lags_dist.setText('%.3f' % self.data_ctrl.lag_distance_ini)
        self.kriging_view.lineEdit_OK_VBRaio.setText('%.3f' % self.data_ctrl.max_dist)

        self.Variogram = False
        self.calculate_variogram(initial_variogram=True, nugget_range_sill=False)
        self.view.lineEdit_OK_lags_dist.setText('%.3f' % self.lag_distance)

        self.plot_variogram()

        self.view.pushButton_VariogramaSave.setEnabled(True)
        self.kriging_view.pushButton_Validacao_Cruzada_OK.setEnabled(True)

        self.Variogram = True

    def on_variogram_adjust_clicked(self):
        """Adjust variogram with current parameters."""
        if not self.Var_Selected:
            self._show_warning(
                self.tr('Mensagem'),
                self.tr('Faça a seleção de atributos(variáveis) na Tabela de Atributos e clique no botão Selecionar.')
            )
            return

        self._set_result_tab(0)

        if not self.Variogram:
            self.calculate_variogram(initial_variogram=True, nugget_range_sill=False)
        else:
            self.calculate_variogram(initial_variogram=False, nugget_range_sill=False)

        self.view.lineEdit_OK_lags_dist.setText('%.3f' % self.lag_distance)
        self.plot_variogram()

        self.view.pushButton_VariogramaSave.setEnabled(True)
        self.kriging_view.pushButton_Validacao_Cruzada_OK.setEnabled(True)

        self.Variogram = True

    def on_variogram_save_clicked(self):
        """Save the current semivariogram parameters to 0_Semivariograms_<layer>.csv.

        Ported from pushButton_VariogramaSave_clicked. Builds the 23-column row,
        replaces it if the target variable already has a saved row (asking the user
        first), otherwise appends. Then writes the CSV and refreshes the list table.
        """
        data_view = self.data_ctrl.dialog

        Z = data_view.comboBox_VTarget.currentText()
        Modelo = self.view.comboBox_Modelo.currentText()
        DMax = float(self.view.lineEdit_OK_DMax.text())
        Lag = float(self.view.lineEdit_OK_lags_dist.text())
        C0 = float(self.view.lineEdit_Nugget.text())
        C0_C = float(self.view.lineEdit_Sill.text())
        Range = float(self.view.lineEdit_Range.text())

        DMax_Maximum = self.data_ctrl.max_dist
        DMax_Minimum = self.data_ctrl.min_dist
        C0_Maximum = self.C0_Maximum
        C0_Minimum = self.C0_Minimum
        C0_C_Maximum = self.C0_C_Maximum
        C0_C_Minimum = self.C0_C_Minimum
        Range_Maximum = self.Range_Maximum
        Range_Minimum = self.Range_Minimum
        Raio_Maximum = self.data_ctrl.Raio_OK_Maximum
        Raio_Minimum = self.data_ctrl.Raio_OK_Minimum
        VB_Maximum = self.data_ctrl.VB_OK_Maximum
        VB_Minimum = self.data_ctrl.VB_OK_Minimum

        RMSE = float(self.view.lineEdit_Var_RMSE.text())
        R2 = float(self.view.lineEdit_Var_R2.text())
        Raio = float(self.kriging_view.lineEdit_OK_VBRaio.text())
        VB = int(self.kriging_view.lineEdit_OK_VBNumMax.text())

        layer_name = data_view.mMapLayerComboBox.currentLayer().name()
        filename = os.path.join(self.path_absolute, '0_Semivariograms_' + layer_name + '.csv')

        row_values = np.array([Z, Modelo, DMax, Lag, C0, C0_C, Range, RMSE, R2, Raio, VB,
                               DMax_Maximum, DMax_Minimum, C0_Maximum, C0_Minimum,
                               C0_C_Maximum, C0_C_Minimum, Range_Maximum, Range_Minimum,
                               Raio_Maximum, Raio_Minimum, VB_Maximum, VB_Minimum])

        columns = ['Z', 'modelo', 'max_dist', 'lag', 'C0', 'C0_C', 'Range', 'RMSE', 'R2',
                   'Raio', 'Vizinhos', 'DMax_Maximum', 'DMax_Minimum', 'C0_Maximum',
                   'C0_Minimum', 'C0_C_Maximum', 'C0_C_Minimum', 'Range_Maximum',
                   'Range_Minimum', 'Raio_Maximum', 'Raio_Minimum', 'VB_Maximum', 'VB_Minimum']

        if os.path.isfile(filename):
            self.df_semivariograms = pd.read_csv(filename, sep=',')

            # Replace existing row for this variable, or append a new one.
            semiv_calculated = False
            for i in range(len(self.df_semivariograms.index)):
                if Z == self.df_semivariograms.iloc[i, 0]:
                    semiv_calculated = True
                    msg = QMessageBox.question(
                        data_view, self.tr('Mensagem'),
                        self.tr('Deseja substituir o semivariograma de: ') + Z + ' ?',
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if msg == QMessageBox.Yes:
                        self.df_semivariograms.loc[i] = row_values

            if not semiv_calculated:
                self.df_semivariograms.loc[len(self.df_semivariograms)] = row_values
        else:
            self.df_semivariograms = pd.DataFrame(columns=columns)
            self.df_semivariograms.loc[len(self.df_semivariograms)] = row_values

        self.df_semivariograms.to_csv(filename, sep=',', index=False, encoding='utf-8')

        # Refresh the list of saved semivariograms in the UI.
        self.load_semivariograms()

    def load_semivariograms(self):
        """Load saved semivariograms into datatable_semivariogramas.

        Ported from the old load_semivariograms. Reads 0_Semivariograms_<layer>.csv
        and fills the table (col 0 = checkbox marker, cols 1..11 = saved parameters).
        """
        data_view = self.data_ctrl.dialog
        selected_layer = data_view.mMapLayerComboBox.currentLayer()
        if selected_layer is None:
            return
        layer_name = selected_layer.name()

        filename = os.path.join(self.path_absolute, '0_Semivariograms_' + layer_name + '.csv')

        self.list_rows_semiv = []

        cols = [self.tr('Marcar'), 'Z', self.tr('Modelo'), self.tr('Distância Máxima'),
                self.tr('Distância (h)'), self.tr('Efeito Pepita'), self.tr('Contribuição'),
                self.tr('Alcance'), self.tr('RMSE'), 'R2', self.tr('Raio'), self.tr('Vizinhos')]

        table = self.view.datatable_semivariogramas

        if os.path.isfile(filename):
            self.df_semivariograms = pd.read_csv(filename, sep=',')

            table.setColumnCount(12)
            table.setRowCount(len(self.df_semivariograms.index))

            try:
                table.setHorizontalHeaderLabels(cols)
            except AttributeError:
                self._show_warning(self.tr('Mensagem'),
                                   self.tr('Erro ao carregar tabela. Valor Inválido!'))

            try:
                for i in range(len(self.df_semivariograms.index)):
                    chk_item = QTableWidgetItem()
                    chk_item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
                    chk_item.setCheckState(QtCore.Qt.Unchecked)
                    table.setItem(i, 0, chk_item)

                    for j in range(11):
                        valor = self.df_semivariograms.iloc[i, j]
                        if j >= 2:
                            try:
                                if valor.dtype == 'float64':
                                    valor = '%.3f' % valor
                            except AttributeError:
                                pass
                        table.setItem(i, j + 1, QTableWidgetItem(str(valor)))
            except AttributeError:
                self._show_warning(self.tr('Mensagem'),
                                   self.tr('Erro ao carregar tabela. Valor Inválido!'))

            table.resizeColumnsToContents()
            table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)

        else:
            # No saved file yet: only set up the header.
            table.setColumnCount(12)
            table.setRowCount(0)
            try:
                table.setHorizontalHeaderLabels(cols)
            except AttributeError:
                self._show_warning(self.tr('Mensagem'),
                                   self.tr('Erro ao carregar tabela. Valor Inválido!'))

    def on_semivariogram_table_double_clicked(self):
        """Reload a previously-saved semivariogram for the double-clicked row.

        Ported from datatable_semivariogramas_doubleClicked.
        """
        table = self.view.datatable_semivariogramas
        row = table.currentRow()
        if row < 0:
            return

        v_target = table.item(row, 1).text()

        data_view = self.data_ctrl.dialog
        selected_layer = data_view.mMapLayerComboBox.currentLayer()
        if selected_layer is None:
            return
        layer_name = selected_layer.name()

        filename = os.path.join(self.path_absolute, '0_Semivariograms_' + layer_name + '.csv')
        if not os.path.isfile(filename):
            return

        self.df_semivariograms = pd.read_csv(filename, sep=',')

        # Locate the saved row for the chosen variable.
        semiv_calculated = -1
        for i in range(len(self.df_semivariograms.index)):
            if v_target == self.df_semivariograms.iloc[i, 0]:
                semiv_calculated = i

        if semiv_calculated < 0:
            return

        # Re-import the selected target so its data is loaded, then restore params.
        data_view.comboBox_VTarget.setCurrentText(v_target)
        self.data_ctrl.on_import_qgis_clicked()

        df = self.df_semivariograms
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

        # Restore bounds (owned by data_ctrl / this controller).
        self.data_ctrl.max_dist = float(df.iloc[semiv_calculated, 11])
        self.data_ctrl.min_dist = float(df.iloc[semiv_calculated, 12])
        self.C0_Maximum = float(df.iloc[semiv_calculated, 13])
        self.C0_Minimum = float(df.iloc[semiv_calculated, 14])
        self.C0_C_Maximum = float(df.iloc[semiv_calculated, 15])
        self.C0_C_Minimum = float(df.iloc[semiv_calculated, 16])
        self.Range_Maximum = float(df.iloc[semiv_calculated, 17])
        self.Range_Minimum = float(df.iloc[semiv_calculated, 18])
        self.data_ctrl.Raio_OK_Maximum = float(df.iloc[semiv_calculated, 19])
        self.data_ctrl.Raio_OK_Minimum = float(df.iloc[semiv_calculated, 20])
        self.data_ctrl.VB_OK_Maximum = int(df.iloc[semiv_calculated, 21])
        self.data_ctrl.VB_OK_Minimum = int(df.iloc[semiv_calculated, 22])

        # Set the model combo without triggering the change handler.
        try:
            self.view.comboBox_Modelo.currentIndexChanged.disconnect()
        except TypeError:
            pass

        model_index = {
            'Linear': 0, 'Linear to Sill': 1, 'Linear com Patamar': 1,
            'Exponential': 2, 'Exponencial': 2, 'Spherical': 3, 'Esférico': 3,
            'Gaussian': 4, 'Gaussiano': 4
        }
        self.view.comboBox_Modelo.setCurrentIndex(model_index.get(Modelo, 0))
        self.view.comboBox_Modelo.currentIndexChanged.connect(self.on_model_combo_changed)

        self.view.lineEdit_OK_DMax.setText('%.3f' % DMax)
        self.view.lineEdit_OK_lags_dist.setText('%.3f' % Lag)

        # Nugget slider/line edit
        if not self.hide_horizontalSlider:
            try:
                self.view.horizontalSlider_Nugget.valueChanged.disconnect()
            except TypeError:
                pass
            self.view.horizontalSlider_Nugget.setMinimum(int(self.C0_Minimum * 1000))
            self.view.horizontalSlider_Nugget.setMaximum(int(self.C0_Maximum * 1000))
            self.view.horizontalSlider_Nugget.setValue(int(C0 * 1000))
            self.view.horizontalSlider_Nugget.valueChanged.connect(self.on_nugget_slider_changed)
        self.view.lineEdit_Nugget.setText('%.3f' % C0)

        # Sill slider/line edit
        if not self.hide_horizontalSlider:
            try:
                self.view.horizontalSlider_Sill.valueChanged.disconnect()
            except TypeError:
                pass
            self.view.horizontalSlider_Sill.setMinimum(int(self.C0_C_Minimum * 1000))
            self.view.horizontalSlider_Sill.setMaximum(int(self.C0_C_Maximum * 1000))
            self.view.horizontalSlider_Sill.setValue(int(C0_C * 1000))
            self.view.horizontalSlider_Sill.valueChanged.connect(self.on_sill_slider_changed)
        self.view.lineEdit_Sill.setText('%.3f' % C0_C)

        # Range slider/line edit
        if not self.hide_horizontalSlider:
            try:
                self.view.horizontalSlider_Range.valueChanged.disconnect()
            except TypeError:
                pass
            self.view.horizontalSlider_Range.setMinimum(int(self.Range_Minimum * 1000))
            self.view.horizontalSlider_Range.setMaximum(int(self.Range_Maximum * 1000))
            self.view.horizontalSlider_Range.setValue(int(Range * 1000))
            self.view.horizontalSlider_Range.valueChanged.connect(self.on_range_slider_changed)
        self.view.lineEdit_Range.setText('%.3f' % Range)

        self.kriging_view.lineEdit_OK_VBRaio.setText('%.3f' % Raio)
        self.kriging_view.lineEdit_OK_VBNumMax.setText(str(VB))
        self.view.lineEdit_Var_RMSE.setText('%.3f' % RMSE)
        self.view.lineEdit_Var_R2.setText('%.3f' % R2)

        self.calculate_variogram(initial_variogram=False, nugget_range_sill=True)
        self.plot_variogram()

        self.view.pushButton_VariogramaSave.setEnabled(True)
        self.kriging_view.pushButton_Validacao_Cruzada_OK.setEnabled(True)
        self._set_result_tab(0)
        self.Variogram = True

    def on_variogram_label_clicked(self, value):
        """Show variogram help."""
        pass

    # Helpers
    def _set_result_tab(self, index):
        """Switch the kriging result tab (lives on the kriging view)."""
        if self.kriging_view is not None:
            self.kriging_view.tabWidget_Interpolacao_OK.setCurrentIndex(index)

    def _show_warning(self, title, message):
        """Show warning message box."""
        msg_box = QMessageBox()
        msg_box.setWindowIcon(QIcon(self.icon_path))
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec_()
