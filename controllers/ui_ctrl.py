# -*- coding: utf-8 -*-
"""UI and localization controller."""

from qgis.PyQt.QtGui import QIcon

from ..Smart_Map_About import smart_mapAbout


class UIController:
    """Handles the about dialog.

    Language is auto-detected from the QGIS locale at startup (see
    smart_map._install_translator); there is no manual language switch.
    """

    def __init__(self, dialog, plugin_dir, icon_path, tr_func):
        self.dialog = dialog
        self.plugin_dir = plugin_dir
        self.icon_path = icon_path
        self.tr = tr_func

    # About dialog -----------------------------------------------------------
    def on_about_clicked(self, event=None):
        """Show the about dialog (system credits)."""
        about = smart_mapAbout()
        about.setWindowIcon(QIcon(self.icon_path))
        about.exec_()
