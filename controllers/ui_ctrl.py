# -*- coding: utf-8 -*-
"""UI and localization controller."""


class UIController:
    """Handles UI updates, language switching, and about dialog."""

    def __init__(self, dialog, plugin_dir):
        self.dialog = dialog
        self.plugin_dir = plugin_dir

    # Language management
    def on_language_pt_clicked(self, value):
        """Switch to Portuguese."""
        pass

    def on_language_usa_clicked(self, value):
        """Switch to English."""
        pass

    # About dialog
    def on_about_clicked(self, value):
        """Show about dialog."""
        pass

    # Reset UI
    def reset_gui(self):
        """Reset all UI elements to defaults."""
        pass
