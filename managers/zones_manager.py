# -*- coding: utf-8 -*-
"""Management zones business logic (fuzzy c-means clustering).

Ported faithfully from the monolithic ``smart_map`` class (Smart_Map.py):
  - the FPI / NCE sweep in pushButton_ZM_Calc_Nr_Ideal_ZM_clicked
  - the single clustering run + FPI/NCE in pushButton_ZM_Calcular_clicked

The FPI / NCE formulas are Daniel Marçal's (natural-log NCE normalised by
ln(K), NOT log2), and the fuzzy coefficient ``m`` and ``maxiter`` are the
user-supplied values (spinBox_ZM_Iter / doubleSpinBox_ZM_CFuzzy) passed in by
the controller -- they are never hardcoded here.
"""

import math

import numpy as np
from sklearn.preprocessing import scale

from ..skfuzzy.cluster import _cmeans


class ZonesManager:
    """Handles fuzzy c-means clustering for management zones."""

    def __init__(self):
        pass

    @staticmethod
    def _fpi_nce(u_orig, K):
        """FPI / NCE (Daniel Marçal) for a membership matrix.

        ``u_orig`` is the c-means membership matrix shaped [N, K] (samples x
        classes). Returns (fpi, nce).
        """
        N = u_orig.shape[0]
        sum1 = 0.0
        sum2 = 0.0
        for i in range(N):
            for j in range(K):
                sum1 = sum1 + u_orig[i, j] * u_orig[i, j]
                sum2 = sum2 + u_orig[i, j] * math.log(u_orig[i, j])
        # Fuzzy Performance Index
        fpi = 1 - (K * ((1 / N) * sum1) - 1) / (K - 1)
        # Normalised Classification Entropy (natural log, normalised by ln(K))
        nce = (-1 / N) * sum2 / math.log(K)
        return fpi, nce

    def calculate_ideal_zones(self, alldata, coef_nebuloso, num_iteration,
                              tol=1.0E-5, progress_cb=None):
        """Sweep 2..10 classes and compute FPI / NCE for each (Marçal).

        ``alldata`` is the already-assembled, already-standardised attribute
        matrix shaped [n_features, n_samples] (the c-means convention used by
        the old code: ``X`` transposed and scaled by row).

        Returns ``(NK, FPI, NCE, num_zones)`` where NK = [2..10], FPI/NCE are
        the per-class lists and num_zones = min(NK[argmin FPI], NK[argmin NCE]).

        ``progress_cb(nclasses)`` is called after each class count; if it
        returns True the sweep aborts and ``(None, None, None, None)`` is
        returned (user cancelled).
        """
        NK = []
        FPI = []
        NCE = []

        for nclasses in range(2, 11):
            cntr, u_orig, _, _, _, _, fpc = _cmeans.cmeans(
                alldata, c=nclasses, m=coef_nebuloso, error=tol, maxiter=num_iteration)

            u_orig = u_orig.T   # [K, N] -> [N, K]
            fpi, nce = self._fpi_nce(u_orig, nclasses)

            FPI.append(fpi)
            NCE.append(nce)
            NK.append(nclasses)

            if progress_cb is not None:
                if progress_cb(nclasses):
                    return None, None, None, None

        # Ideal number of classes: minimum of the FPI- and NCE-optimal counts.
        nFPI = FPI.index(min(FPI))
        nNCE = NCE.index(min(NCE))
        num_zones = min(NK[nFPI], NK[nNCE])

        return NK, FPI, NCE, num_zones

    def cluster(self, alldata, num_zones, coef_nebuloso, num_iteration, tol=1.0E-5):
        """Run a single fuzzy c-means for ``num_zones`` classes.

        ``alldata`` is the attribute matrix shaped [n_features, n_samples].
        Returns ``(cntr, u_orig, cluster_membership)`` where cluster_membership
        is the 1-based hard label per sample.
        """
        cntr, u_orig, _, _, _, _, fpi = _cmeans.cmeans(
            alldata, c=num_zones, m=coef_nebuloso, error=tol, maxiter=num_iteration)

        cluster_membership = np.argmax(u_orig, axis=0)
        cluster_membership = cluster_membership + 1   # classes start at 1

        return cntr, u_orig, cluster_membership

    def fpi_nce(self, u_orig_samples_by_class, num_zones):
        """FPI / NCE for an already-run clustering (membership [N, K])."""
        return self._fpi_nce(u_orig_samples_by_class, num_zones)
