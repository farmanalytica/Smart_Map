# -*- coding: utf-8 -*-
"""UI and localization controller."""

import os

from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtGui import QIcon

from ..Smart_Map_About import smart_mapAbout


class UIController:
    """Handles language switching and the about dialog.

    Ported from the monolithic label_language_PT/USA_clicked and
    label_About_clicked. The language choice is persisted to
    i18n/language.txt and applied on the next plugin start (the translator
    is installed in run()).
    """

    def __init__(self, dialog, plugin_dir, icon_path, tr_func):
        self.dialog = dialog
        self.plugin_dir = plugin_dir
        self.icon_path = icon_path
        self.tr = tr_func
        self.language = None

    # Language management ----------------------------------------------------
    def on_language_pt_clicked(self, event=None):
        """Switch to Portuguese (applied on next start)."""
        self._set_language('Portuguese')

    def on_language_usa_clicked(self, event=None):
        """Switch to English (applied on next start)."""
        self._set_language('English')

    def _set_language(self, language):
        self._warn(self.tr(
            'Feche e Abra o plugin novamente para aplicar o idioma selecionado!'
        ))
        with open(os.path.join(self.plugin_dir, 'i18n', 'language.txt'), 'w') as f:
            f.write(language)
        self.language = language

    # About dialog -----------------------------------------------------------
    def on_about_clicked(self, event=None):
        """Show the about dialog (system credits)."""
        about = smart_mapAbout()
        about.setWindowIcon(QIcon(self.icon_path))
        about.exec_()

    # Helpers ----------------------------------------------------------------
    def _warn(self, message):
        msg_box = QMessageBox()
        msg_box.setWindowIcon(QIcon(self.icon_path))
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle(self.tr('Mensagem'))
        msg_box.setText(message)
        msg_box.exec_()
