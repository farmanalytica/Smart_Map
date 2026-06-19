# -*- coding: utf-8 -*-
"""Data management business logic."""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


class DataManager:
    """Handles data loading, transformation, and export."""

    def __init__(self):
        pass

    # Data loading (already handled by DataController, but kept for interface)
    def load_from_qgis_layer(self, layer):
        """Load attributes from QGIS vector layer.

        Returns:
            pandas.DataFrame: Layer attributes as dataframe
        """
        # Handled in DataController._load_layer_to_dataframe
        pass

    # Data transformation
    def resample_points(self, dataframe, resample_param):
        """Resample point data using grid-based approach.

        Returns:
            pandas.DataFrame: Resampled dataframe
        """
        # Handled in DataController.resample_points
        pass

    def normalize_data(self, dataframe, columns=None):
        """Normalize specified columns to [0, 1].

        Returns:
            tuple: (normalized_df, scaler)
        """
        if columns is None:
            columns = dataframe.columns

        scaler = StandardScaler()
        data_to_scale = dataframe[columns].values
        scaled = scaler.fit_transform(data_to_scale)

        df_normalized = dataframe.copy()
        df_normalized[columns] = scaled

        return df_normalized, scaler

    def clean_data(self, dataframe, target_col):
        """Remove rows with NaN in target column.

        Returns:
            pandas.DataFrame: Cleaned dataframe
        """
        df_clean = dataframe.dropna(subset=[target_col])
        df_clean.reset_index(drop=True, inplace=True)
        return df_clean

    def remove_outliers(self, dataframe, z_col, method='iqr'):
        """Remove outliers using IQR or z-score method.

        Returns:
            tuple: (cleaned_df, outlier_indices)
        """
        if method == 'iqr':
            Q1 = dataframe[z_col].quantile(0.25)
            Q3 = dataframe[z_col].quantile(0.75)
            IQR = Q3 - Q1

            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR

            outlier_mask = (dataframe[z_col] < lower) | (dataframe[z_col] > upper)
        else:  # z-score
            mean = dataframe[z_col].mean()
            std = dataframe[z_col].std()
            z_scores = np.abs((dataframe[z_col] - mean) / std)
            outlier_mask = z_scores > 3

        outlier_indices = list(np.where(outlier_mask)[0])
        df_clean = dataframe[~outlier_mask].copy()
        df_clean.reset_index(drop=True, inplace=True)

        return df_clean, outlier_indices

    # Export
    def export_to_csv(self, dataframe, output_path):
        """Export dataframe to CSV."""
        dataframe.to_csv(output_path, sep=',', index=False, encoding='utf-8')

    def export_to_shapefile(self, dataframe, output_path):
        """Export data to shapefile.

        Note: Actual shapefile creation handled in DataController.export_shapefile_to_qgis
        """
        pass

    def export_to_raster(self, dataframe, grid_params, output_path):
        """Export interpolated data to raster.

        Note: Actual raster export handled in DataController.export_raster_to_qgis via gdal_grid
        """
        pass

    # Validation
    def validate_coordinates(self, dataframe, x_col, y_col):
        """Check if coordinates are valid (projected, not geographic).

        Returns:
            bool: True if valid
        """
        # Check for reasonable bounds (not lat/long)
        x_range = dataframe[x_col].max() - dataframe[x_col].min()
        y_range = dataframe[y_col].max() - dataframe[y_col].min()

        # Geographic coordinates typically have small ranges
        if x_range < 360 and y_range < 180:
            return False  # Likely geographic

        return True
