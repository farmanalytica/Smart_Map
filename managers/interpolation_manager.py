# -*- coding: utf-8 -*-
"""Interpolation business logic (kriging, SVM)."""

import numpy as np
import pandas as pd
from sklearn import svm
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from ..krig import kriging, semivariogram


class InterpolationManager:
    """Handles variogram fitting and interpolation execution."""

    def __init__(self):
        pass

    # Variogram fitting
    def fit_variogram(self, xy, z, lag_distance, active_distance, use_models=None):
        """Fit semivariogram to data using multiple models.

        Returns:
            dict: {model_name: [nugget, range, sill, rss, r2]}
        """
        if use_models is None:
            use_models = ['linear', 'linear-sill', 'exponential', 'spherical', 'gaussian']

        semiv = semivariogram.Semivariogram(xy, z)

        # Calculate experimental semivariogram
        lag, gamma, npoints = semiv.Exp_Semiv(lag_distance, active_distance)

        # Ensure minimum lags
        while len(npoints) < 2:
            lag_distance -= 1
            lag, gamma, npoints = semiv.Exp_Semiv(lag_distance, active_distance)

        # Fit models with retry on infeasible
        while True:
            try:
                models = semiv.Fit(use_models)
                break
            except ValueError as e:
                if 'is infeasible' in str(e):
                    lag_distance += 1
                    lag, gamma, npoints = semiv.Exp_Semiv(lag_distance, active_distance)
                else:
                    raise

        return models, lag, gamma, npoints, lag_distance, semiv.sample_variance

    def get_best_model(self, models):
        """Select model with minimum RSS."""
        min_rss = models['linear'][3]
        best_model = 'linear'

        for model_name in models:
            if models[model_name][3] < min_rss:
                min_rss = models[model_name][3]
                best_model = model_name

        return best_model

    def calculate_theoretical_variogram(self, xy, z, model_name, nugget, range_, sill):
        """Calculate theoretical semivariogram curve."""
        semiv = semivariogram.Semivariogram(xy, z)
        gamma_t, rss, r2 = semiv.Gamma(model_name, [nugget, range_, sill])
        return gamma_t, rss, r2

    # Kriging
    def execute_kriging(self, xy, z, model, variogram_params, xygrid, n_neighbors, search_radius):
        """Execute ordinary kriging interpolation.

        Returns:
            tuple: (predicted_values, standard_deviations)
        """
        ok = kriging.OrdinaryKriging(
            xy, z,
            variogram_model=model,
            variogram_parameters=variogram_params
        )

        z_est, ss = ok.execute(xygrid, n_closest_points=n_neighbors, radius=search_radius)
        return z_est, ss

    def execute_cross_validation_kriging(self, xy, z, model, variogram_params, n_neighbors, search_radius):
        """Execute leave-one-out cross-validation for kriging.

        Returns:
            array: Predicted values at left-out locations
        """
        predictions = []

        for i in range(len(xy)):
            # Leave out point i
            xy_loo = xy.drop(i)
            z_loo = z.drop(i)

            # Krige without point i
            ok = kriging.OrdinaryKriging(
                xy_loo, z_loo,
                variogram_model=model,
                variogram_parameters=variogram_params
            )

            # Predict at left-out point
            coord = [[xy.iloc[i, 0], xy.iloc[i, 1]]]
            z_est, _ = ok.execute(coord, n_closest_points=n_neighbors, radius=search_radius)
            predictions.append(z_est[0])

        return np.array(predictions)

    # SVM
    def execute_svm(self, training_data, training_labels, features, xygrid, kernel='rbf'):
        """Execute SVM interpolation.

        Returns:
            array: Predicted values at grid points
        """
        # Prepare training data
        X_train = training_data[features].values
        y_train = training_labels.values

        # Normalize
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)

        # Train SVM
        svm_model = svm.SVR(kernel=kernel, C=100, gamma='scale')
        svm_model.fit(X_train_scaled, y_train)

        # Prepare grid for prediction
        X_grid = xygrid[features].values
        X_grid_scaled = scaler.transform(X_grid)

        # Predict
        predictions = svm_model.predict(X_grid_scaled)
        return predictions

    def execute_cross_validation_svm(self, training_data, training_labels, features, kernel='rbf'):
        """Execute leave-one-out cross-validation for SVM.

        Returns:
            array: Predicted values at left-out locations
        """
        predictions = []
        X = training_data[features].values
        y = training_labels.values

        for i in range(len(X)):
            # Leave out point i
            X_loo = np.delete(X, i, axis=0)
            y_loo = np.delete(y, i)

            # Normalize
            scaler = StandardScaler()
            X_loo_scaled = scaler.fit_transform(X_loo)

            # Train
            svm_model = svm.SVR(kernel=kernel, C=100, gamma='scale')
            svm_model.fit(X_loo_scaled, y_loo)

            # Predict at left-out point
            X_point = X[i].reshape(1, -1)
            X_point_scaled = scaler.transform(X_point)
            pred = svm_model.predict(X_point_scaled)[0]
            predictions.append(pred)

        return np.array(predictions)
