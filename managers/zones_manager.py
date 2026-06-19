# -*- coding: utf-8 -*-
"""Management zones business logic (clustering)."""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from ..skfuzzy.cluster import _cmeans


class ZonesManager:
    """Handles fuzzy c-means clustering for management zones."""

    def __init__(self):
        pass

    # Optimal zone count
    def calculate_ideal_zones(self, dataframe, max_clusters=10):
        """Calculate ideal cluster count using FPI/NCE metrics.

        Returns:
            dict: {cluster_count: {'fpi': value, 'nce': value}, ...}
        """
        # Normalize data
        scaler = StandardScaler()
        data_scaled = scaler.fit_transform(dataframe.values)

        results = {}

        for c in range(2, max_clusters + 1):
            # Fuzzy c-means
            cntr, u, u0, d, jm, p, fpc = _cmeans(
                data_scaled.T, c, 2, error=1e-5, maxiter=1000, init=None
            )

            # Calculate FPI (Fuzzy Partition Index)
            fpi = 1.0 - (c / (c - 1)) * (1.0 - fpc)

            # Calculate NCE (Normalized Classification Entropy)
            nce = -np.sum(u * np.log2(u + 1e-10)) / (dataframe.shape[0] * np.log2(c))

            results[c] = {'fpi': fpi, 'nce': nce}

        return results

    # Clustering
    def calculate_zones(self, dataframe, num_zones):
        """Execute fuzzy c-means clustering for zone definition.

        Returns:
            tuple: (cluster_centers, fuzzy_membership, cluster_labels)
        """
        # Normalize data
        scaler = StandardScaler()
        data_scaled = scaler.fit_transform(dataframe.values)

        # Fuzzy c-means
        cntr, u, u0, d, jm, p, fpc = _cmeans(
            data_scaled.T, num_zones, 2, error=1e-5, maxiter=1000, init=None
        )

        # Get hard labels from fuzzy membership
        labels = np.argmax(u, axis=0)

        # Transform centers back to original scale
        centers = scaler.inverse_transform(cntr.T)

        return centers, u, labels

    # Zone statistics
    def get_zone_statistics(self, dataframe, labels):
        """Calculate statistics for each zone.

        Returns:
            dict: {zone_id: {col: mean, ...}, ...}
        """
        zones_stats = {}

        for zone_id in np.unique(labels):
            zone_mask = labels == zone_id
            zone_data = dataframe[zone_mask]

            zones_stats[int(zone_id)] = {
                col: zone_data[col].mean() for col in dataframe.columns
            }

        return zones_stats
