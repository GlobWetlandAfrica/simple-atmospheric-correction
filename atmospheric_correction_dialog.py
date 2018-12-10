# -*- coding: utf-8 -*-
"""
/***************************************************************************
 atmCorrectionDialog
                                 A QGIS plugin
 Use 6S module to perform atmospheric correction on satellite imagery
                             -------------------
        begin                : 2015-12-09
        git sha              : $Format:%H$
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

import os
from PyQt4 import QtGui, uic
from atmProcessing import atmProcessingMain, saveImgByCopy

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'atmospheric_correction_dialog_base.ui'))


class atmCorrectionDialog(QtGui.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(atmCorrectionDialog, self).__init__(parent)
        self.setupUi(self)

        self.toolButton_DN.clicked.connect(self.selectDN)
        self.toolButton_meta.clicked.connect(self.selectMeta)
        self.toolButton_output.clicked.connect(self.selectOutput)
        self.pushButton_cancel.clicked.connect(self.closeWindow)
        self.pushButton_save.clicked.connect(self.runAtmCorrection)

    def selectDN(self):
        self.lineEdit_DN.setText(QtGui.QFileDialog.getOpenFileName(
                self, "Select DN file", ""))

    def selectMeta(self):
        self.lineEdit_meta.setText(QtGui.QFileDialog.getOpenFileName(
                self, "Select metadata file", ""))

    def selectOutput(self):
        self.lineEdit_output.setText(QtGui.QFileDialog.getSaveFileName(
                self, "Save corrected file", "", 'Image (*.tif)'))

    def closeWindow(self):
        self.close()

    def satellite(self):
        index = self.comboBox_satellite.currentIndex()
        sensorList = ["L8", "L7", "S2A_10m", "S2A_60m"]
        return sensorList[index]

    def method(self):
        index = self.comboBox_method.currentIndex()
        methodList = ["DOS", "TOA", "RAD"]
        return methodList[index]

    def runAtmCorrection(self):
        options = {}
        # input/output parameters
        options["sensor"] = self.satellite()
        options["dnFile"] = self.lineEdit_DN.text()
        options["metadataFile"] = self.lineEdit_meta.text()
        options["reflectanceFile"] = self.lineEdit_output.text()
        options["atmCorrMethod"] = self.method()

        reflectanceImg = atmProcessingMain(options)
        saveImgByCopy(reflectanceImg, options["reflectanceFile"])
        self.closeWindow()
