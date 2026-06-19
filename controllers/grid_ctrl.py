# -*- coding: utf-8 -*-
"""Grid and extent management controller."""


class GridController:
    """Handles grid parameters and extent definition."""

    def __init__(self, dialog):
        self.dialog = dialog

    # Pixel size
    def on_pixel_size_x_changed(self, value):
        """Update grid X pixel size."""
        pass

    def on_pixel_size_y_changed(self, value):
        """Update grid Y pixel size."""
        pass

    # Grid extent bounds
    def on_x_min_edited(self):
        """Update grid X minimum."""
        pass

    def on_x_max_edited(self):
        """Update grid X maximum."""
        pass

    def on_y_min_edited(self):
        """Update grid Y minimum."""
        pass

    def on_y_max_edited(self):
        """Update grid Y maximum."""
        pass

    # Area contour (boundary)
    def on_area_contour_toggled(self, checked):
        """Enable/disable area contour."""
        pass

    def on_contour_layer_combo_changed(self, index):
        """Change contour boundary layer."""
        pass

    def on_contour_apply_clicked(self):
        """Apply area contour to grid."""
        pass

    def on_contour_label_clicked(self, value):
        """Show contour help."""
        pass
