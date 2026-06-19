# -*- coding: utf-8 -*-
"""Interpolation business logic (kriging, SVM)."""


class InterpolationManager:
    """Handles variogram fitting and interpolation execution."""

    def __init__(self):
        pass

    # Variogram
    def calculate_variogram(self, initial_variogram, nugget_range_sill):
        """Fit variogram to sample data."""
        pass

    # Kriging
    def execute_kriging(self, points_data, variogram, grid_params):
        """Execute ordinary kriging interpolation."""
        pass

    def execute_cross_validation_kriging(self, points_data, variogram, grid_params):
        """Execute kriging cross-validation."""
        pass

    # SVM
    def execute_svm(self, training_data, features, grid_params):
        """Execute SVM interpolation."""
        pass

    def execute_cross_validation_svm(self, training_data, features, grid_params):
        """Execute SVM cross-validation."""
        pass
