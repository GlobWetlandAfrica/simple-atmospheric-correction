# -*- coding: utf-8 -*-
"""
Created on Tue Sep 09 12:54:33 2014

@author: rmgu
"""
import numpy as np
import re
import os
from math import cos, radians, pi
from osgeo import gdal
from read_satellite_metadata import readMetadataS2L1C

driverOptionsGTiff = ['COMPRESS=DEFLATE', 'PREDICTOR=1', 'BIGTIFF=IF_SAFER']
###############################################################################


def atmProcessingMain(options):

    sensor = options['sensor']

    # Commonly used filenames
    dnFile = options["dnFile"]
    metadataFile = options["metadataFile"]

    # Correction options
    atmCorrMethod = options["atmCorrMethod"]

    # special case for Sentinel-2 - read metadata in to dictionary
    if sensor in ["S2A_10m", "S2A_60m"]:
        dnFileName = os.path.split(dnFile)[1]
        granule = dnFileName[len(dnFileName)-10:-4]
        metadataFile = readMetadataS2L1C(metadataFile)
        # Add current granule (used to extract relevant metadata later...)
        metadataFile.update({'current_granule': granule})

    # DN -> Radiance -> Reflectance
    if atmCorrMethod in ["DOS", "TOA"]:
        if atmCorrMethod == "DOS":
            doDOS = True
        else:
            doDOS = False
        inImg = gdal.Open(dnFile)
        if sensor not in ["S2A_10m", "S2A_60m"]:
            radianceImg = toaRadiance(inImg, metadataFile, sensor, doDOS=doDOS)
            inImg = None
            reflectanceImg = toaReflectance(radianceImg, metadataFile, sensor)
            radianceImg = None
        # S2 data is provided in L1C meaning in TOA reflectance
        else:
            reflectanceImg = toaReflectance(inImg, metadataFile, sensor, doDOS=doDOS)
            inImg = None

    elif atmCorrMethod == "RAD":
        doDOS = False
        inImg = gdal.Open(dnFile)
        radianceImg = toaRadiance(inImg, metadataFile, sensor, doDOS=doDOS)
        reflectanceImg = radianceImg

    return reflectanceImg

################################################################################################


def toaRadiance(inImg, metadataFile, sensor, doDOS):
    if sensor == "L8" or sensor == "L7":
        res = toaRadianceL8(inImg, metadataFile, doDOS, sensor)
    elif sensor == "S2A_10m" or sensor == "S2A_60m":
        res = toaRadianceS2(inImg, metadataFile)
    return res


def toaReflectance(inImg, metadataFile, sensor, doDOS=False):
    if sensor == "L8" or sensor == "L7":
        res = toaReflectanceL8(inImg, metadataFile)
    elif sensor == "S2A_10m" or sensor == "S2A_60m":
        res = toaReflectanceS2(inImg, metadataFile, doDOS)
    return res


def toaRadianceL8(inImg, metadataFile, doDOS, sensor):

    multFactorRegex = "\s*RADIANCE_MULT_BAND_\d\s*=\s*(.*)\s*"
    addFactorRegex = "\s*RADIANCE_ADD_BAND_\d\s*=\s*(.*)\s*"

    if inImg.RasterCount == 1:
        if sensor == "L8":
            # The first 5 bands in L8 are VIS/NIR
            visNirBands = range(1, 6)
        elif sensor == "L7":
            # The first 4 bands in L7 are VIS/NIR
            visNirBands = range(1, 5)
        rawData = np.zeros((inImg.RasterYSize, inImg.RasterXSize, len(visNirBands)))

        # Raw Landsat 8/7 data has each band in a separate image. Therefore first open images with
        # all the required band data.
        imgDir = os.path.dirname(inImg.GetFileList()[0])
        for _, _, files in os.walk(imgDir):
            for name in sorted(files):
                match = re.search('(([A-Z]{2}\d).+)_B(\d+)\.TIF$', name)
                if match and int(match.group(3)) in visNirBands:
                    band = int(match.group(3))
                    rawImg = gdal.Open(os.path.join(imgDir, name), gdal.GA_ReadOnly)
                    rawData[:, :, band-1] = rawImg.GetRasterBand(1).ReadAsArray()
                    rawData = np.int_(rawData)
                    rawImg = None

    # Panchromatic should only be one band but this way the isPan option can also
    # be used to processed L8 images which are stacked in one file.
    else:
        rawData = np.zeros((inImg.RasterYSize, inImg.RasterXSize, inImg.RasterCount))
        for i in range(inImg.RasterCount):
            rawData[:, :, i] = inImg.GetRasterBand(i+1).ReadAsArray()

    # get the correction factors from the metadata file, assuming the number and
    # order of bands is the same in the image and the metadata file
    multFactor = []
    addFactor = []
    with open(metadataFile, 'r') as metadata:
        for line in metadata:
            match = re.match(multFactorRegex, line)
            if match:
                multFactor.append(float(match.group(1)))
            match = re.match(addFactorRegex, line)
            if match:
                addFactor.append(float(match.group(1)))

    # perform dark object substraction
    if doDOS:
        rawImg = saveImg(rawData, inImg.GetGeoTransform(), inImg.GetProjection(), "MEM")
        dosDN = darkObjectSubstraction(rawImg)
        rawImg = None
    else:
        dosDN = list(np.zeros(rawData.shape[2]))

    # apply the radiometric correction factors to input image
    radiometricData = np.zeros((inImg.RasterYSize, inImg.RasterXSize, rawData.shape[2]))
    validMask = np.zeros((inImg.RasterYSize, inImg.RasterXSize))
    for band in range(1, rawData.shape[2]+1):
        radiometricData[:, :, band-1] =\
            np.where((rawData[:, :, band-1]-dosDN[band-1]) > 0,
                     (rawData[:, :, band-1]-dosDN[band-1])*multFactor[band-1] + addFactor[band-1],
                     0)
        validMask = validMask + radiometricData[:, :, band-1]

    # Mark the pixels which have all radiances of 0 as invalid
    invalidMask = np.where(validMask > 0, False, True)
    radiometricData[invalidMask, :] = np.nan

    res = saveImg(radiometricData, inImg.GetGeoTransform(), inImg.GetProjection(), "MEM")
    return res


def toaReflectanceL8(inImg, metadataFile):
    # for now just do nothing
    return inImg


# Method taken from the bottom of http://s2tbx.telespazio-vega.de/sen2three/html/r2rusage.html
# Assumes a L1C product which contains TOA reflectance: https://sentinel.esa.int/web/sentinel/user-guides/sentinel-2-msi/product-types
def toaRadianceS2(inImg, metadataFile):
    qv = float(metadataFile['quantification_value'])
    e0 = []
    for e in metadataFile['irradiance_values']:
        e0.append(float(e))
    z = float(metadataFile['sun_zenit'])

    visNirBands = range(1, 10)
    # Convert to radiance
    radiometricData = np.zeros((inImg.RasterYSize, inImg.RasterXSize, len(visNirBands)))
    for i in range(len(visNirBands)):
        rToa = (inImg.GetRasterBand(i+1).ReadAsArray().astype(float)) / qv
        radiometricData[:, :, i] = (rToa * e0[i] * cos(radians(z))) / pi
    res = saveImg(radiometricData, inImg.GetGeoTransform(), inImg.GetProjection(), "MEM")
    return res


# Assumes a L1C product which contains TOA reflectance: https://sentinel.esa.int/web/sentinel/user-guides/sentinel-2-msi/product-types
def toaReflectanceS2(inImg, metadataFile, doDOS=False):
    qv = float(metadataFile['quantification_value'])

    # perform dark object substraction
    if doDOS:
        dosDN = darkObjectSubstraction(inImg)
    else:
        dosDN = list(np.zeros((inImg.RasterYSize, inImg.RasterXSize)))

    # Convert to TOA reflectance
    rToa = np.zeros((inImg.RasterYSize, inImg.RasterXSize, inImg.RasterCount))
    for i in range(inImg.RasterCount):
        rawData = inImg.GetRasterBand(i+1).ReadAsArray().astype(float)
        rToa[:, :, i] = np.where((rawData-dosDN[i]) > 0,
                                 (rawData-dosDN[i]) / qv,
                                 0)

    res = saveImg(rToa, inImg.GetGeoTransform(), inImg.GetProjection(), "MEM")
    return res


def darkObjectSubstraction(inImg):
    dosDN = []
    tempData = inImg.GetRasterBand(1).ReadAsArray()
    numElements = np.size(tempData[tempData != 0])
    tempData = None
    for band in range(1, inImg.RasterCount+1):
        hist, edges = np.histogram(inImg.GetRasterBand(band).ReadAsArray(), bins=2048,
                                   range=(1, 2048), density=False)
        for i in range(1, len(hist)):
            if hist[i] - hist[i-1] > (numElements-numElements*0.999999):
                dosDN.append(i-1)
                break
    return dosDN


# save the data to geotiff or memory
def saveImg(data, geotransform, proj, outPath, noDataValue=np.nan):

    # Start the gdal driver for GeoTIFF
    if outPath == "MEM":
        driver = gdal.GetDriverByName("MEM")
        driverOpt = []
    else:
        driver = gdal.GetDriverByName("GTiff")
        driverOpt = driverOptionsGTiff

    shape = data.shape
    if len(shape) > 2:
        ds = driver.Create(outPath, shape[1], shape[0], shape[2], gdal.GDT_Float32, driverOpt)
        ds.SetProjection(proj)
        ds.SetGeoTransform(geotransform)
        for i in range(shape[2]):
            ds.GetRasterBand(i+1).WriteArray(data[:, :, i])
            ds.GetRasterBand(i+1).SetNoDataValue(noDataValue)
    else:
        ds = driver.Create(outPath, shape[1], shape[0], 1, gdal.GDT_Float32)
        ds.SetProjection(proj)
        ds.SetGeoTransform(geotransform)
        ds.GetRasterBand(1).WriteArray(data)
        ds.GetRasterBand(1).SetNoDataValue(noDataValue)

    return ds


def saveImgByCopy(outImg, outPath):

    driver = gdal.GetDriverByName("GTiff")
    savedImg = driver.CreateCopy(outPath, outImg, 0, driverOptionsGTiff)
    savedImg = None
    outImg = None

###############################################################################
