# coding: utf-8
"""
/***************************************************************************
# File: variogram_models.py

                                 A QGIS plugin

                              -------------------
        begin                : 2018-08-15
        git sha              : $Format:%H$
        copyright            : (C) 2018 by Gustavo Willam Pereira
                                           Domingos Sárvio Magalhães Valente 
                                           Daniel Marçal de Queiroz
                                           Andre Luiz de Freitas Coelho
                                           Sandro Manuel Carmelino Hurtado
        email                : gustavowillam@gmail.com
 ***************************************************************************/
"""


import numpy as np

# Every model takes:
#   d       : numpy array of lag distances (h)
#   nugget  : nugget effect
#   range_  : range
#   psill   : sill
# and returns the modeled semivariance for each lag in d.

def linear_variogram_model(d, nugget,range_,psill):
    """Linear model."""

    slope = (psill - nugget ) / range_
    return slope * d + nugget

def linear_sill_variogram_model(d, nugget,range_,psill):
    """Linear model with a sill: linear up to the range, flat afterwards."""

    slope = (psill - nugget ) / range_
    return np.where(d <=range_,slope * d + nugget,psill)


def hole_effect_variogram_model(d, nugget,range_,psill):
    """Hole-effect model (constant (sill + nugget) / 2)."""

    return np.full(len(d),(psill+nugget)/2)


def spherical_variogram_model(d,nugget,range_,psill):
    """Spherical model: spherical equation for h < range, sill beyond it."""

    return np.where(d<range_,nugget+(psill-nugget)*(1.5*d/range_-0.5*d**3/(range_**3)),psill)


def exponential_variogram_model(d,nugget,range_,psill):
    """Exponential model."""

    return  nugget+(psill-nugget)*(1-np.exp(-3.0*d/range_))


def gaussian_variogram_model(d,nugget,range_,psill):
    """Gaussian model."""

    return nugget+(psill-nugget)*(1-np.exp(-3.0*d**2/(range_**2)))


