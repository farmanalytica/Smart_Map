# -*- coding: utf-8 -*-
"""Variogram and semivariogram controller."""

import os
import numpy as np
import matplotlib.pyplot as plt2

from qgis.PyQt import QtCore, QtWidgets, QtGui
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtGui import QIcon, QPixmap

from ..krig import semivariogram


class VariogramController:
    """Handles variogram calculation, tuning, and visualization."""

    def __init__(self, dialog, data_controller, icon_path, path_absolute, tr_func):
        self.dialog = dialog
        self.data_ctrl = data_controller
        self.icon_path = icon_path
        self.path_absolute = path_absolute
        self.tr = tr_func

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
                self.dialog.comboBox_Modelo.currentIndexChanged.disconnect()
            except TypeError:
                pass

            # Get parameters
            self.active_distance = float(self.dialog.lineEdit_OK_DMax.text())
            self.lag_distance = float(self.dialog.lineEdit_OK_lags_dist.text())

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
                self.dialog.comboBox_Modelo.setCurrentIndex(model_map.get(best_model, 0))
                self.model = best_model

                # Calculate theoretical semivariogram
                nugget, range_, sill = self.models[self.model][0:3]
                self.gamma_t, rss, r2 = semiv.Gamma(self.model, [nugget, range_, sill])

                rss_val = self.models[self.model][3]
                r2_val = self.models[self.model][4]

            # Update calculation - use selected model
            else:
                # Get selected model
                model_idx = self.dialog.comboBox_Modelo.currentIndex()
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
                    nugget = float(self.dialog.lineEdit_Nugget.text())
                    range_ = float(self.dialog.lineEdit_Range.text())
                    sill = float(self.dialog.lineEdit_Sill.text())

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
            self.dialog.lineEdit_OK_lags_dist.setText('%.3f' % self.lag_distance)
            self.dialog.lineEdit_Var_RMSE.setText('%.3f' % rss_val)
            self.dialog.lineEdit_Var_R2.setText('%.3f' % r2_val)

        except Exception as e:
            self._show_warning(self.tr('Erro'), str(e))
        finally:
            # Reconnect model combo
            try:
                self.dialog.comboBox_Modelo.currentIndexChanged.connect(self.on_model_combo_changed)
            except (AttributeError, TypeError):
                pass

    def plot_variogram(self):
        """Plot experimental and theoretical semivariogram."""
        if self.lag is None or self.gamma is None:
            return

        try:
            nugget = float(self.dialog.lineEdit_Nugget.text())
            rss = float(self.dialog.lineEdit_Var_RMSE.text())
            r2 = float(self.dialog.lineEdit_Var_R2.text())

            plt2.close()
            fig = plt2.figure(figsize=(10, 6))

            # Plot experimental
            plt2.scatter(self.lag, self.gamma, c=self.npoints, marker='s',
                        cmap='RdYlGn', label=self.tr('Semivariograma Experimental'))

            # Plot theoretical (starts at nugget)
            model_text = self.dialog.comboBox_Modelo.currentText()
            plt2.plot(np.insert(self.lag, 0, 0), np.insert(self.gamma_t, 0, nugget),
                     label=f'{model_text}   {self.tr("RMSE:")} {rss:.3f}   $R^2$: {r2:.3f}')

            # Plot sample variance if checked
            if self.dialog.checkBox_Variogram_Variancia.isChecked():
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
            self.dialog.label_Variograma.setPixmap(pixmap)
            self.dialog.label_Variograma.show()

            # Enable kriging UI
            self.dialog.groupBox_Variograma_Model.setEnabled(True)
            self.dialog.pushButton_VariogramaReset.setEnabled(True)
            self.dialog.lineEdit_Nugget.setEnabled(True)
            self.dialog.lineEdit_Sill.setEnabled(True)
            self.dialog.lineEdit_Range.setEnabled(True)

            self.dialog.groupBox_Krigagem.setEnabled(True)
            self.dialog.lineEdit_OK_VBNumMax.setEnabled(True)
            self.dialog.lineEdit_OK_VBRaio.setEnabled(True)
            self.dialog.checkBox_Krigagem_Alcance.setEnabled(True)
            self.dialog.pushButton_Krigagem.setEnabled(True)
            self.dialog.checkBox_Krigagem_Std_Desv.setEnabled(True)

            self.dialog.label_Krigagem.hide()
            self.dialog.label_validacao_cruzada_OK.hide()
            self.dialog.pushButton_Validacao_Cruzada_OK.setEnabled(True)

            self.dialog.datatable_pontos_interpolados_OK.setColumnCount(0)
            self.dialog.datatable_pontos_interpolados_OK.setRowCount(0)

        except Exception as e:
            self._show_warning(self.tr('Erro'), str(e))

    # Model selection
    def on_model_combo_changed(self, value):
        """Change variogram model and recalculate."""
        self.dialog.tabWidget_Interpolacao_OK.setCurrentIndex(0)
        self.calculate_variogram(initial_variogram=False, nugget_range_sill=False)
        self.plot_variogram()

    # Parameter tuning
    def on_dmax_edited(self):
        """Validate DMax and recalculate."""
        try:
            dmax = float(self.dialog.lineEdit_OK_DMax.text())

            if dmax > self.data_ctrl.max_dist:
                dmax = self.data_ctrl.max_dist

            lag_dist = float(self.dialog.lineEdit_OK_lags_dist.text())
            if dmax < lag_dist:
                dmax = lag_dist

            self.dialog.lineEdit_OK_DMax.setText('%.3f' % dmax)

            if self.Variogram:
                self.on_variogram_adjust_clicked()
        except ValueError:
            pass

    def on_lags_distance_edited(self):
        """Validate lag distance and recalculate."""
        try:
            lag_dist = float(self.dialog.lineEdit_OK_lags_dist.text())

            if lag_dist < self.data_ctrl.min_dist:
                lag_dist = self.data_ctrl.min_dist

            dmax = float(self.dialog.lineEdit_OK_DMax.text())
            if lag_dist > dmax:
                lag_dist = dmax

            self.dialog.lineEdit_OK_lags_dist.setText('%.3f' % lag_dist)

            if self.Variogram:
                self.on_variogram_adjust_clicked()
        except ValueError:
            pass

    def on_nugget_edited(self):
        """Validate nugget and recalculate."""
        try:
            nugget = float(self.dialog.lineEdit_Nugget.text())

            if nugget > self.C0_Maximum:
                nugget = self.C0_Maximum
            if nugget < self.C0_Minimum:
                nugget = self.C0_Minimum

            self.dialog.lineEdit_Nugget.setText('%.3f' % nugget)

            if not self.hide_horizontalSlider:
                try:
                    self.dialog.horizontalSlider_Nugget.valueChanged.disconnect()
                except TypeError:
                    pass
                self.dialog.horizontalSlider_Nugget.setValue(int(nugget * 1000))
                self.dialog.horizontalSlider_Nugget.valueChanged.connect(self.on_nugget_slider_changed)

            self.dialog.tabWidget_Interpolacao_OK.setCurrentIndex(0)
            self.calculate_variogram(initial_variogram=False, nugget_range_sill=True)
            self.plot_variogram()
        except ValueError:
            pass

    def on_nugget_slider_changed(self, value):
        """Update nugget from slider."""
        self.dialog.tabWidget_Interpolacao_OK.setCurrentIndex(0)
        nugget = float(value) / 1000.0
        self.dialog.lineEdit_Nugget.setText('%.3f' % nugget)
        self.calculate_variogram(initial_variogram=False, nugget_range_sill=True)
        self.plot_variogram()

    def on_sill_edited(self):
        """Validate sill and recalculate."""
        try:
            sill = float(self.dialog.lineEdit_Sill.text())

            if sill > self.C0_C_Maximum:
                sill = self.C0_C_Maximum
            if sill < self.C0_C_Minimum:
                sill = self.C0_C_Minimum

            self.dialog.lineEdit_Sill.setText('%.3f' % sill)

            if not self.hide_horizontalSlider:
                try:
                    self.dialog.horizontalSlider_Sill.valueChanged.disconnect()
                except TypeError:
                    pass
                self.dialog.horizontalSlider_Sill.setValue(int(sill * 1000))
                self.dialog.horizontalSlider_Sill.valueChanged.connect(self.on_sill_slider_changed)

            self.dialog.tabWidget_Interpolacao_OK.setCurrentIndex(0)
            self.calculate_variogram(initial_variogram=False, nugget_range_sill=True)
            self.plot_variogram()
        except ValueError:
            pass

    def on_sill_slider_changed(self, value):
        """Update sill from slider."""
        self.dialog.tabWidget_Interpolacao_OK.setCurrentIndex(0)
        sill = float(value) / 1000.0
        self.dialog.lineEdit_Sill.setText('%.3f' % sill)
        self.calculate_variogram(initial_variogram=False, nugget_range_sill=True)
        self.plot_variogram()

    def on_range_edited(self):
        """Validate range and recalculate."""
        try:
            range_ = float(self.dialog.lineEdit_Range.text())

            if range_ > self.Range_Maximum:
                range_ = self.Range_Maximum
            if range_ < self.Range_Minimum:
                range_ = self.Range_Minimum

            self.dialog.lineEdit_Range.setText('%.3f' % range_)

            if not self.hide_horizontalSlider:
                try:
                    self.dialog.horizontalSlider_Range.valueChanged.disconnect()
                except TypeError:
                    pass
                self.dialog.horizontalSlider_Range.setValue(int(range_ * 1000))
                self.dialog.horizontalSlider_Range.valueChanged.connect(self.on_range_slider_changed)

            self.dialog.tabWidget_Interpolacao_OK.setCurrentIndex(0)
            self.calculate_variogram(initial_variogram=False, nugget_range_sill=True)
            self.plot_variogram()
        except ValueError:
            pass

    def on_range_slider_changed(self, value):
        """Update range from slider."""
        self.dialog.tabWidget_Interpolacao_OK.setCurrentIndex(0)
        range_ = float(value) / 1000.0
        self.dialog.lineEdit_Range.setText('%.3f' % range_)
        self.calculate_variogram(initial_variogram=False, nugget_range_sill=True)
        self.plot_variogram()

    def on_vb_num_max_edited(self):
        """Validate kriging neighbor count."""
        try:
            vb = int(self.dialog.lineEdit_OK_VBNumMax.text())

            if vb > self.data_ctrl.VB_OK_Maximum:
                vb = self.data_ctrl.VB_OK_Maximum
            if vb < self.data_ctrl.VB_OK_Minimum:
                vb = self.data_ctrl.VB_OK_Minimum

            self.dialog.lineEdit_OK_VBNumMax.setText(str(vb))
        except ValueError:
            pass

    def on_vb_raio_edited(self):
        """Validate kriging search radius."""
        try:
            raio = float(self.dialog.lineEdit_OK_VBRaio.text())

            if raio > self.data_ctrl.max_dist:
                raio = self.data_ctrl.max_dist
            if raio < self.data_ctrl.min_dist:
                raio = self.data_ctrl.min_dist

            self.dialog.lineEdit_OK_VBRaio.setText('%.3f' % raio)
        except ValueError:
            pass

    def on_use_range_for_search_toggled(self, checked):
        """Use variogram range or max distance for search radius."""
        if checked:
            try:
                raio = float(self.dialog.lineEdit_Range.text())
            except ValueError:
                raio = self.data_ctrl.max_dist
        else:
            raio = self.data_ctrl.max_dist

        self.dialog.lineEdit_OK_VBRaio.setText('%.3f' % raio)

    def on_variogram_reset_clicked(self):
        """Reset variogram to initial calculation."""
        self.dialog.tabWidget_Interpolacao_OK.setCurrentIndex(0)

        self.dialog.lineEdit_OK_DMax.setText('%.3f' % self.data_ctrl.active_distance_ini)
        self.dialog.lineEdit_OK_lags_dist.setText('%.3f' % self.data_ctrl.lag_distance_ini)
        self.dialog.lineEdit_OK_VBRaio.setText('%.3f' % self.data_ctrl.max_dist)

        self.Variogram = False
        self.calculate_variogram(initial_variogram=True, nugget_range_sill=False)
        self.dialog.lineEdit_OK_lags_dist.setText('%.3f' % self.lag_distance)

        self.plot_variogram()

        self.dialog.pushButton_VariogramaSave.setEnabled(True)
        self.dialog.pushButton_Validacao_Cruzada_OK.setEnabled(True)

        self.Variogram = True

    def on_variogram_adjust_clicked(self):
        """Adjust variogram with current parameters."""
        if not self.Var_Selected:
            self._show_warning(
                self.tr('Mensagem'),
                self.tr('Faça a seleção de atributos(variáveis) na Tabela de Atributos e clique no botão Selecionar.')
            )
            return

        self.dialog.tabWidget_Interpolacao_OK.setCurrentIndex(0)

        if not self.Variogram:
            self.calculate_variogram(initial_variogram=True, nugget_range_sill=False)
        else:
            self.calculate_variogram(initial_variogram=False, nugget_range_sill=False)

        self.dialog.lineEdit_OK_lags_dist.setText('%.3f' % self.lag_distance)
        self.plot_variogram()

        self.dialog.pushButton_VariogramaSave.setEnabled(True)
        self.dialog.pushButton_Validacao_Cruzada_OK.setEnabled(True)

        self.Variogram = True

    def on_variogram_save_clicked(self):
        """Save variogram parameters."""
        # Save to file/config - implementation pending
        pass

    def on_variogram_label_clicked(self, value):
        """Show variogram help."""
        pass

    # Helpers
    def _show_warning(self, title, message):
        """Show warning message box."""
        msg_box = QMessageBox()
        msg_box.setWindowIcon(QIcon(self.icon_path))
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec_()
