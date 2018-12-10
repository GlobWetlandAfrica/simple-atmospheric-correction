# -*- coding: utf-8 -*-

"""
/***************************************************************************
 AtmosphericCorrection
                                 A QGIS plugin
 Use 6S module to perform atmospheric correction on satellite imagery
                              -------------------
        begin                : 2015-12-17
        copyright            : (C) 2015 by DHI-GRAS
        email                : rfn@dhi-gras.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'DHI-GRAS'
__date__ = '2015-12-17'
__copyright__ = '(C) 2015 by DHI-GRAS'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.outputs import OutputRaster
from processing.core.parameters import ParameterSelection
from processing.core.parameters import ParameterRaster
from processing.core.parameters import ParameterFile

from atmProcessing import atmProcessingMain, saveImgByCopy


class AtmosphericCorrectionAlgorithm(GeoAlgorithm):

    DN_FILE = 'DN_FILE'
    METAFILE = 'METAFILE'
    METHOD = 'METHOD'
    METHODS = ['DOS', 'TOA', 'RAD']
    OUTPUT_FILE = 'OUTPUT_FILE'

    def defineCharacteristics(self):
        # The name that the user will see in the toolbox
        self.name = 'Sentinel-2 atmospheric correction'
        # The branch of the toolbox under which the algorithm will appear
        self.group = 'Sentinel Tools'

        self.addParameter(ParameterRaster(self.DN_FILE, 'DN file', showSublayersDialog=False))
        self.addParameter(ParameterFile(self.METAFILE, 'Metafile', optional=False))
        self.addParameter(ParameterSelection(self.METHOD, 'Method', self.METHODS))
        self.addOutput(OutputRaster(self.OUTPUT_FILE, 'Output file'))

    def processAlgorithm(self, progress):
        """Here is where the processing itself takes place."""
        # The first thing to do is retrieve the values of the parameters
        # entered by the user

        methodList = ["DOS", "TOA", "RAD"]

        options = {}
        # input/output parameters
        options["dnFile"] = self.getParameterValue(self.DN_FILE)
        options["metadataFile"] = self.getParameterValue(self.METAFILE)
        options["reflectanceFile"] = self.getOutputValue(self.OUTPUT_FILE)
        # Atmospheric correction parameters
        options["atmCorrMethod"] = methodList[self.getParameterValue(self.METHOD)]

        reflectanceImg = atmProcessingMain(options)
        saveImgByCopy(reflectanceImg, options["reflectanceFile"])
