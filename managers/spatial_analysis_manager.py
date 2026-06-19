# -*- coding: utf-8 -*-
"""Spatial analysis business logic (Moran's I, RFE)."""

import numpy as np
import pandas as pd
from sklearn.feature_selection import RFE
from sklearn.ensemble import RandomForestRegressor

from ..utils import functions


class SpatialAnalysisManager:
    """Handles spatial statistics and feature selection."""

    def __init__(self):
        pass

    # Moran's I
    def calculate_moran(self, dataframe, x_col, y_col, z_col):
        """Calculate Moran's I spatial autocorrelation.

        Returns:
            tuple: (moran_index, p_value)
        """
        moran_index, p_value = functions.calculate_index_moran(
            dataframe, x_col, y_col, z_col
        )
        return moran_index, p_value

    # Feature selection
    def recursive_feature_elimination(self, training_data, training_labels, n_features_to_select=5):
        """Perform recursive feature elimination (RFE).

        Returns:
            list: Selected feature names
        """
        if len(training_data.columns) <= n_features_to_select:
            return list(training_data.columns)

        # Use random forest as estimator
        estimator = RandomForestRegressor(n_estimators=100, random_state=42)

        # RFE
        rfe = RFE(estimator, n_features_to_select=n_features_to_select, step=1)
        rfe.fit(training_data.values, training_labels.values)

        # Get selected features
        selected_mask = rfe.support_
        selected_features = list(training_data.columns[selected_mask])

        return selected_features

    # Outlier detection
    def detect_outliers(self, dataframe, z_col):
        """Detect outliers using IQR method.

        Returns:
            list: Indices of outlier rows
        """
        Q1 = dataframe[z_col].quantile(0.25)
        Q3 = dataframe[z_col].quantile(0.75)
        IQR = Q3 - Q1

        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR

        outlier_mask = (dataframe[z_col] < lower_bound) | (dataframe[z_col] > upper_bound)
        outlier_indices = list(np.where(outlier_mask)[0])

        return outlier_indices
