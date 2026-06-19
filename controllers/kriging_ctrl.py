# -*- coding: utf-8 -*-
"""Kriging interpolation controller."""


class KrigingController:
    """Handles kriging interpolation and cross-validation."""

    def __init__(self, dialog, interpolation_manager, interpolation_worker):
        self.dialog = dialog
        self.interpolation_manager = interpolation_manager
        self.interpolation_worker = interpolation_worker

    # Kriging execution
    def on_kriging_clicked(self):
        """Execute kriging interpolation."""
        pass

    def on_kriging_all_variables_clicked(self):
        """Execute kriging for all selected variables."""
        pass

    # Results
    def on_interpolated_points_table_double_clicked(self, item):
        """Display selected interpolated point."""
        pass

    # Cross-validation
    def on_cross_validation_clicked(self):
        """Execute cross-validation."""
        pass

    def on_cross_validation_results_double_clicked(self, item):
        """Display cross-validation result."""
        pass

    def on_cross_validation_label_clicked(self, value):
        """Show cross-validation help."""
        pass

    # UI
    def on_semivariogram_checkbox_clicked(self, item):
        """Toggle semivariogram selection."""
        pass

    def on_kriging_label_clicked(self, value):
        """Show kriging help."""
        pass
