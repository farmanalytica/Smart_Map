# -*- coding: utf-8 -*-
"""Export business logic: raster (gdal_grid), color ramp, and vector export to QGIS.

This module holds the heavy export logic ported faithfully from the old monolithic
``smart_map`` class (Smart_Map.py). The DataController methods are thin delegators to
ExportManager so existing callers (kriging_ctrl, data_ctrl resample, future svm/zones)
keep working unchanged.

ExportManager methods take explicit parameters rather than reading dialog widgets, so
the controller resolves widget/state values and passes them through.
"""

import os
import subprocess

from qgis.core import (
    QgsProject,
    QgsProcessingFeedback,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsCoordinateReferenceSystem,
    QgsFields,
    QgsField,
    QgsWkbTypes,
    QgsPointXY,
    QgsGeometry,
    QgsFeature,
    QgsLayerTreeLayer,
    QgsColorRampShader,
    QgsSingleBandPseudoColorRenderer,
    QgsRasterBandStats,
    QgsRasterShader,
    QgsStyle,
)
from qgis.PyQt.QtCore import QVariant

import processing


class ExportManager:
    """Holds the export heavy logic (gdal_grid, color ramp, processing.run)."""

    def __init__(self, iface, path_absolute):
        self.iface = iface
        self.path_absolute = path_absolute

    # ------------------------------------------------------------------
    # Raster export (VRT + gdal_grid + optional clip-to-contour)
    # ------------------------------------------------------------------
    def export_raster_to_qgis(self, input_table, output_tiff, output_name, z_field,
                              cord_x, cord_y,
                              cord_x_min, cord_x_max, cord_y_min, cord_y_max,
                              pixel_size_x, pixel_size_y,
                              pixel_size_x_zm, pixel_size_y_zm,
                              source_layer,
                              contour_checked, contour_layer,
                              zm_number_classes):
        """Generate a raster from a CSV via gdal_grid and register it in QGIS.

        Ported from old smart_map.export_raster_to_qgis (Smart_Map.py ~8469).

        Args:
            input_table: CSV filename (relative to path_absolute) holding the grid points.
            output_tiff: full path of the desired output .tiff (extension stripped/renamed).
            output_name: base layer name registered in the QGIS layer tree.
            z_field: name of the value column in the CSV.
            cord_x, cord_y: longitude/latitude field names in the CSV.
            cord_x_min/max, cord_y_min/max: grid extent bounds (str/float).
            pixel_size_x/y: default pixel size (kriging/SVM grids).
            pixel_size_x_zm/y_zm: pixel size for ZM (management zones) grids.
            source_layer: layer whose CRS is used (when no contour clip happens).
            contour_checked: bool, whether the "Area de Contorno" checkbox is checked.
            contour_layer: QgsVectorLayer mask polygon (or None) for clip-to-contour.
            zm_number_classes: number of classes for the ZM color ramp (spinBox value).

        Returns:
            The final output .tiff path used.
        """
        filename = output_tiff[:-5]            # remove '.tiff' extension
        layername = output_name

        cont = 1
        output_tiff = filename + '_' + str(cont) + '.tiff'
        output_name = layername + '_' + str(cont)

        # unique-filename loop: *_1.tiff, *_2.tiff ...
        while os.path.isfile(output_tiff):
            cont = cont + 1
            output_tiff = filename + '_' + str(cont) + '.tiff'
            output_name = layername + '_' + str(cont)

        # make path_absolute the active directory (CSV/VRT are relative to it)
        dir_with_csvs = os.path.join(self.path_absolute)
        os.chdir(dir_with_csvs)

        csvfiles = [input_table]

        lon_field = cord_x
        lat_field = cord_y

        # for each CSV file, make a VRT then run gdal_grid in a subprocess
        for fn in csvfiles:
            vrt_fn = fn.replace(".csv", ".vrt")
            lyr_name = fn.replace('.csv', '')
            out_tif = fn.replace('.csv', '.tiff')
            with open(vrt_fn, 'w') as fn_vrt:
                fn_vrt.write('<OGRVRTDataSource>\n')
                fn_vrt.write('\t<OGRVRTLayer name="%s">\n' % lyr_name)
                fn_vrt.write('\t\t<SrcDataSource>%s</SrcDataSource>\n' % fn)
                fn_vrt.write('\t\t<GeometryType>wkbPoint</GeometryType>\n')
                fn_vrt.write('\t\t<GeometryField encoding="PointFromColumns" x="' + lon_field + '" y="' + lat_field + '" z="' + z_field + '"/>\n')
                fn_vrt.write('\t</OGRVRTLayer>\n')
                fn_vrt.write('</OGRVRTDataSource>\n')

                if '2_ZM_' in input_table:    # set Pixel_size of ZM Map
                    Pixel_Size_X = float(pixel_size_x_zm)
                    Pixel_Size_Y = float(pixel_size_y_zm)
                    num_points_x = int((float(cord_x_max) - float(cord_x_min)) / float(pixel_size_x_zm))
                    num_points_y = int((float(cord_y_max) - float(cord_y_min)) / float(pixel_size_y_zm))
                else:
                    Pixel_Size_X = float(pixel_size_x)
                    Pixel_Size_Y = float(pixel_size_y)
                    num_points_x = int((float(cord_x_max) - float(cord_x_min)) / float(pixel_size_x))
                    num_points_y = int((float(cord_y_max) - float(cord_y_min)) / float(pixel_size_y))

                Num_Points_X = float(num_points_x)
                Cord_X_min = cord_x_min
                Cord_X_max = (Pixel_Size_X * Num_Points_X) + Cord_X_min

                Num_Points_Y = float(num_points_y)
                Cord_Y_min = cord_y_min
                # ajustar Cord_Y_max para que o tamanho do pixel fique com valor exato
                Cord_Y_max = (Pixel_Size_Y * Num_Points_Y) + Cord_Y_min

            if '2_ZM' in output_tiff:   # ZM uses nearest-neighbour (no interpolation)
                gdal_cmd = [
                    'gdal_grid',
                    '-a', 'nearest:radius1=0.0:radius2=0.0:angle=0.0:nodata=0.0',
                    '-zfield', z_field,
                    '-txe', str(cord_x_min), str(Cord_X_max),
                    '-tye', str(cord_y_min), str(Cord_Y_max),
                    '-outsize', str(num_points_x), str(num_points_y),
                    '-ot', 'UInt16', '-of', 'GTiff',
                    '-l', lyr_name, vrt_fn, out_tif
                ]
            else:
                # kriging/SVM: default algorithm (no interpolator method)
                gdal_cmd = [
                    'gdal_grid',
                    '-zfield', z_field,
                    '-txe', str(cord_x_min), str(Cord_X_max),
                    '-tye', str(cord_y_min), str(Cord_Y_max),
                    '-outsize', str(num_points_x), str(num_points_y),
                    '-ot', 'Float64', '-of', 'GTiff',
                    '-l', lyr_name, vrt_fn, out_tif
                ]

            subprocess.call(gdal_cmd)  # create .tiff (without contour clip)

        # ------------------------------------------------------------------
        # recortar o raster de acordo com o limite de contorno
        # ------------------------------------------------------------------
        contour_index_valid = (contour_layer is not None)

        # (no contour) OR (contour checked but no contour layer defined)
        if (not contour_checked) or (contour_checked and not contour_index_valid):

            rlayer = QgsRasterLayer(out_tif, lyr_name)
            QgsProject.instance().addMapLayer(rlayer, False)
            layerTree = self.iface.layerTreeCanvasBridge().rootGroup()
            layerTree.insertChildNode(-1, QgsLayerTreeLayer(rlayer))
            # define color ramp of raster layer
            self.define_raster_color_ramp(rlayer, output_name, zm_number_classes)

            # set CRS of the RasterLayer
            coordenate_reference = source_layer.crs().description()

            if 'SAD69' in coordenate_reference:
                crs = QgsProject.instance().crs().authid()  # project CRS  ex: EPSG:32723
            else:
                crs = source_layer.crs().authid()           # ex: EPSG:32723

            crs = crs.split(':')                            # ['EPSG', '32723']
            crs = crs[1]                                    # '32723'
            CRS = QgsCoordinateReferenceSystem()
            CRS.createFromSrid(int(crs))
            rlayer.setCrs(CRS)
            rlayer.crs().postgisSrid()

        else:  # usuário marcou area de contorno

            if contour_index_valid:  # usuário definiu poligono para recorte

                Input_Layer_File_tiff = out_tif
                Input_Layer_Poligon = contour_layer

                coordenate_reference = Input_Layer_Poligon.crs().description()

                if 'SAD69' in coordenate_reference:
                    crs = QgsProject.instance().crs().authid()        # project CRS
                else:
                    crs = Input_Layer_Poligon.crs().authid()          # poligon layer CRS

                if not os.path.isfile(Input_Layer_File_tiff):
                    print("File doesn't exists", Input_Layer_File_tiff)
                    return None
                else:
                    params = {
                        'INPUT': Input_Layer_File_tiff,
                        'MASK': Input_Layer_Poligon,
                        'SOURCE_CRS': crs,
                        'TARGET_CRS': crs,
                        'NODATA': -999999999.0,
                        'ALPHA_BAND': False,
                        'CROP_TO_CUTLINE': True,
                        'OUTPUT': output_tiff,
                    }

                    feedback = QgsProcessingFeedback()
                    alg_name = 'gdal:cliprasterbymasklayer'
                    processing.run(alg_name, params, feedback=feedback)

                    rlayer = QgsRasterLayer(output_tiff, output_name)
                    QgsProject.instance().addMapLayer(rlayer, False)
                    layerTree = self.iface.layerTreeCanvasBridge().rootGroup()
                    layerTree.insertChildNode(-1, QgsLayerTreeLayer(rlayer))
                    # define color ramp of raster layer
                    self.define_raster_color_ramp(rlayer, output_name, zm_number_classes)

        return output_tiff

    # ------------------------------------------------------------------
    # Color ramp (QGIS-version-independent, uses ramp API directly)
    # ------------------------------------------------------------------
    def define_raster_color_ramp(self, layer, output_name, zm_number_classes):
        """Apply an RdYlGn pseudo-color renderer to a raster layer.

        Ported faithfully from old smart_map.define_raster_color_ramp (Smart_Map.py ~8796),
        the version-independent implementation that uses the QgsGradientColorRamp API:
          ramp.color1()  -> QColor (red, offset 0.0)
          ramp.color2()  -> QColor (green, offset 1.0)
          ramp.stops()   -> list of QgsGradientStop, each with a .color (QColor)
        This avoids string-parsing that breaks across QGIS versions.

        Args:
            layer: the QgsRasterLayer to style.
            output_name: layer name; used to detect ZM ('2_ZM') for class count.
            zm_number_classes: number of classes used when output_name is a ZM map.
        """
        provider = layer.dataProvider()
        extent = layer.extent()
        stats = provider.bandStatistics(1, QgsRasterBandStats.All, extent, 0)
        min_value = stats.minimumValue
        max_value = stats.maximumValue

        myStyle = QgsStyle().defaultStyle()
        ramp = myStyle.colorRamp('RdYlGn')

        # Colors extracted via API — independent of QGIS version internal format
        c1_color = ramp.color1()                       # QColor red (offset 0.0)
        c2_color = ramp.color2()                       # QColor green (offset 1.0)
        stop_colors = [s.color for s in ramp.stops()]  # [QColor@0.25, @0.5, @0.75]

        if '2_ZM' in output_name:
            number_classes = zm_number_classes
        else:
            number_classes = 5

        interval = (max_value - min_value) / (number_classes - 1)
        soma = min_value
        classes = []
        for i in range(number_classes):
            classes.append(round(soma, 10))
            soma += interval

        if number_classes == 2:
            color_list = [
                QgsColorRampShader.ColorRampItem(classes[0], c1_color, '%.1f' % classes[0]),
                QgsColorRampShader.ColorRampItem(classes[1], c2_color, '%.1f' % classes[1]),
            ]
        elif number_classes == 3:
            color_list = [
                QgsColorRampShader.ColorRampItem(classes[0], c1_color, '%.1f' % classes[0]),
                QgsColorRampShader.ColorRampItem(classes[1], stop_colors[0], '%.1f' % classes[1]),
                QgsColorRampShader.ColorRampItem(classes[2], c2_color, '%.1f' % classes[2]),
            ]
        elif number_classes == 4:
            color_list = [
                QgsColorRampShader.ColorRampItem(classes[0], c1_color, '%.1f' % classes[0]),
                QgsColorRampShader.ColorRampItem(classes[1], stop_colors[0], '%.1f' % classes[1]),
                QgsColorRampShader.ColorRampItem(classes[2], stop_colors[1], '%.1f' % classes[2]),
                QgsColorRampShader.ColorRampItem(classes[3], c2_color, '%.1f' % classes[3]),
            ]
        else:
            color_list = [
                QgsColorRampShader.ColorRampItem(classes[0], c1_color, '%.6f' % classes[0]),
                QgsColorRampShader.ColorRampItem(classes[1], stop_colors[0], '%.6f' % classes[1]),
                QgsColorRampShader.ColorRampItem(classes[2], stop_colors[1], '%.6f' % classes[2]),
                QgsColorRampShader.ColorRampItem(classes[3], stop_colors[2], '%.6f' % classes[3]),
                QgsColorRampShader.ColorRampItem(classes[4], c2_color, '%.6f' % classes[4]),
            ]

        myRasterShader = QgsRasterShader()
        myColorRamp = QgsColorRampShader()

        myColorRamp.setColorRampItemList(color_list)
        myColorRamp.setColorRampType(QgsColorRampShader.Interpolated)
        myRasterShader.setRasterShaderFunction(myColorRamp)

        myPseudoRenderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, myRasterShader)
        myPseudoRenderer.setClassificationMax(max_value)
        myPseudoRenderer.setClassificationMin(min_value)

        layer.setRenderer(myPseudoRenderer)
        layer.triggerRepaint()

    # ------------------------------------------------------------------
    # Vector export from raster (pixels -> points / polygons)
    # ------------------------------------------------------------------
    def export_shapefile_to_qgis(self, input_tiff, alg_name, v_target):
        """Convert a raster to points/polygons via processing and register in QGIS.

        Ported from old smart_map.export_shapefile_to_qgis (Smart_Map.py ~8867).

        Args:
            input_tiff: full path of the source raster .tiff.
            alg_name: 'native:pixelstopoints' or 'native:pixelstopolygons'.
            v_target: target variable name written into the output field.
        """
        (Input_Layer_directory, Input_Layer_filename) = os.path.split(input_tiff)

        Input_Layer_filename = Input_Layer_filename.split(".")  # name / extension

        if alg_name == "native:pixelstopoints":
            Output_Layer_File_shp = os.path.join(self.path_absolute, Input_Layer_filename[0] + '_points.shp')
        else:
            Output_Layer_File_shp = os.path.join(self.path_absolute, Input_Layer_filename[0] + '_polygons.shp')

        params = {
            'FIELD_NAME': v_target,
            'INPUT_RASTER': input_tiff,
            'OUTPUT': Output_Layer_File_shp,
            'RASTER_BAND': 1,
        }

        processing.run(alg_name, params)

        # register the VectorLayer in QGIS
        if alg_name == "native:pixelstopoints":
            vlayer = QgsVectorLayer(Output_Layer_File_shp, Input_Layer_filename[0] + '_points', "ogr")
        else:
            vlayer = QgsVectorLayer(Output_Layer_File_shp, Input_Layer_filename[0] + '_polygons', "ogr")

        QgsProject.instance().addMapLayer(vlayer, False)
        layerTree = self.iface.layerTreeCanvasBridge().rootGroup()
        layerTree.insertChildNode(-1, QgsLayerTreeLayer(vlayer))

    # ------------------------------------------------------------------
    # Resampled points: CSV -> SHP point writer
    # ------------------------------------------------------------------
    def export_shapefile_resampled_to_qgis(self, input_table, output_shp, output_name,
                                           cord_x, cord_y, source_layer):
        """Write a CSV of points to a shapefile and register the gpkg in QGIS.

        Ported from old smart_map.export_shapefile_resampled_to_qgis (Smart_Map.py ~8915).

        Args:
            input_table: full path of the input CSV.
            output_shp: full path of the desired output .shp.
            output_name: base layer name.
            cord_x, cord_y: longitude/latitude field names.
            source_layer: layer whose CRS is used (SAD69 -> project CRS).
        """
        Output_Layer_File_gpkg = output_shp + '.gpkg'

        filename = Output_Layer_File_gpkg[:-9]  # strip '.shp.gpkg'
        layername = output_name

        cont = 1
        Output_Layer_File_gpkg = filename + '_' + str(cont) + '.shp.gpkg'
        Output_Layer_File_shp = filename + '_' + str(cont) + '.shp'
        output_name = layername + '_' + str(cont)

        # unique-filename loop: *_1.shp.gpkg, *_2.shp.gpkg ...
        while os.path.isfile(Output_Layer_File_gpkg):
            cont = cont + 1
            Output_Layer_File_gpkg = filename + '_' + str(cont) + '.shp.gpkg'
            Output_Layer_File_shp = filename + '_' + str(cont) + '.shp'
            output_name = layername + '_' + str(cont)

        # convert the .csv into a .shp (shapefile)
        lon_field = cord_x
        lat_field = cord_y

        coordenate_reference = source_layer.crs().description()

        if 'SAD69' in coordenate_reference:
            crs = QgsProject.instance().crs().authid()  # project CRS  ex: EPSG:32723
        else:
            crs = source_layer.crs().authid()           # ex: EPSG:32723

        crs = crs.split(':')                            # ['EPSG', '32723']
        crs = crs[1]                                    # '32723'

        spatRef = QgsCoordinateReferenceSystem(int(crs), QgsCoordinateReferenceSystem.EpsgCrsId)

        inp_tab = QgsVectorLayer(input_table, 'Input_Table', 'ogr')
        prov = inp_tab.dataProvider()
        fields = [field.name() for field in prov.fields()]

        fields1 = QgsFields()

        for i in range(len(fields)):
            fields1.append(QgsField(fields[i], QVariant.Double))

        outLayer = QgsVectorFileWriter(Output_Layer_File_shp, None, fields1, QgsWkbTypes.Point, spatRef)

        pt = QgsPointXY()
        outFeature = QgsFeature()

        for feat in inp_tab.getFeatures():
            attrs = feat.attributes()
            pt.setX(float(feat[lon_field]))
            pt.setY(float(feat[lat_field]))
            outFeature.setAttributes(attrs)
            outFeature.setGeometry(QgsGeometry.fromPointXY(pt))
            outLayer.addFeature(outFeature)
        del outLayer

        # register the VectorLayer in QGIS
        vlayer = QgsVectorLayer(Output_Layer_File_gpkg, output_name, "ogr")
        QgsProject.instance().addMapLayer(vlayer, False)
        layerTree = self.iface.layerTreeCanvasBridge().rootGroup()
        layerTree.insertChildNode(-1, QgsLayerTreeLayer(vlayer))
