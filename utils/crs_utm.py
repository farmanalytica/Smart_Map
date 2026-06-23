# -*- coding: utf-8 -*-
"""Automatic UTM detection and reprojection helpers.

Smart-Map runs every distance-based step (semivariogram lags, kriging grid,
neighbour search radius) in the layer's own coordinate units, so the input must
be projected in metres. Instead of forcing the user to reproject by hand, these
helpers detect the UTM zone that contains the layer's extent centre and
reproject the layer into that zone on the fly.

Detection mirrors what GeoPandas' ``estimate_utm_crs`` does: take the extent
centre, express it in geographic degrees, then derive the WGS84 UTM EPSG code
from the longitude (zone) and latitude (hemisphere).
"""

import math

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsPointXY,
    QgsRasterLayer,
)
import processing


def estimate_utm_crs(layer):
    """Return the WGS84 UTM CRS whose zone contains the layer extent centre."""
    src_crs = layer.crs()
    extent = layer.extent()
    centre = extent.center()
    x, y = centre.x(), centre.y()

    if src_crs.isGeographic():
        lon, lat = x, y
    else:
        wgs84 = QgsCoordinateReferenceSystem('EPSG:4326')
        transform = QgsCoordinateTransform(src_crs, wgs84, QgsProject.instance())
        point = transform.transform(QgsPointXY(x, y))
        lon, lat = point.x(), point.y()

    # Zone 1..60; EPSG 326## (north) / 327## (south).
    zone = int(math.floor((lon + 180.0) / 6.0) + 1)
    zone = max(1, min(60, zone))
    epsg = (32600 if lat >= 0 else 32700) + zone
    return QgsCoordinateReferenceSystem('EPSG:{}'.format(epsg))


def reproject_vector(layer, target_crs):
    """Reproject a vector layer to ``target_crs`` (in-memory).

    Returns the original layer untouched when it is already in ``target_crs``.
    """
    if layer.crs().authid() == target_crs.authid():
        return layer

    result = processing.run(
        'native:reprojectlayer',
        {'INPUT': layer, 'TARGET_CRS': target_crs, 'OUTPUT': 'memory:'},
    )
    reprojected = result['OUTPUT']
    reprojected.setName(layer.name())
    return reprojected


def reproject_raster(layer, target_crs):
    """Warp a raster layer to ``target_crs`` (temporary output).

    Returns the original layer untouched when it is already in ``target_crs``.
    """
    if layer.crs().authid() == target_crs.authid():
        return layer

    result = processing.run(
        'gdal:warpreproject',
        {
            'INPUT': layer,
            'SOURCE_CRS': layer.crs(),
            'TARGET_CRS': target_crs,
            'RESAMPLING': 0,  # nearest neighbour
            'OUTPUT': 'TEMPORARY_OUTPUT',
        },
    )
    return QgsRasterLayer(result['OUTPUT'], layer.name())


def to_utm_if_needed(layer, target_crs=None):
    """Return ``(working_layer, working_crs)`` ready for metre-based analysis.

    When ``target_crs`` is given the layer is reprojected to it (used to keep the
    boundary and dense layers aligned with the attribute-table layer). Otherwise
    the layer is left as-is when already projected, or reprojected to its
    estimated UTM zone when it is in a geographic CRS.
    """
    if target_crs is not None:
        return reproject_vector(layer, target_crs), target_crs

    if not layer.crs().isGeographic():
        return layer, layer.crs()

    target_crs = estimate_utm_crs(layer)
    return reproject_vector(layer, target_crs), target_crs
