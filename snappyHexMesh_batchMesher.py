#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr 20 16:50:04 2025

@author: emefff
"""
import random
import re
from subprocess import run
from tqdm import tqdm
from datetime import datetime
import time
from time import sleep
import matplotlib.pyplot as plt

###############################################################################
# uses /var/tmp/ for writing snappyHexMesh.logs. It is advisable to make it 
# a tmpfs to reduce wear on nvme drives.
###############################################################################

NUMBER_LOOPS = 3 # >= 2


def remove_chars(string):
    """
    Removes chars from a string, keeps the '.'. The reason is, checkMesh occasionally changes the spacing
    around the number we want to detect.

    Parameters
    ----------
    string : TYPE string
        DESCRIPTION. string from a log, extracted mostly in get_mesh_quality()

    Returns
    -------
    TYPE string
        DESCRIPTION. results is a string without any alphabetic chars, keeps the dot.

    """
    return re.sub(r'[^0-9.]', '', string)

def exec_cmd(cmd):
    """
    Execute the external command and get its exitcode, stdout and stderr.
    """
    # args = shlex.split(cmd) # Popen would need a split.
    # run expects cmd NOT args like Popen
    proc = run(cmd, shell=True, executable="/bin/bash", capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def exec_meshing(number):
    """
    Execute our standard meshing script in Python, but without the checkMesh. We need
    it in a separate command.

    Parameters
    ----------
    number : TYPE int
        DESCRIPTION. A number that denotes our snappyHexMeshDict with changed parameters.

    Returns
    -------
    snappy_out_ : TYPE string
        DESCRIPTION. Stdout of snappyHexMesh.

    """
    print(f"***Meshing mesh nr. {number}....")
    # cleaning the OF case
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && ./Clean"
    exitcode, out, err = exec_cmd(cmd)
    
    # surfaceFeatureExtract
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && surfaceFeatureExtract"
    exitcode, out, err = exec_cmd(cmd)
    
    # blockMesh
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && blockMesh"
    exitcode, out, err = exec_cmd(cmd)
    # print(f"{out = }")
    # print(f"{err = }\n")
    
    # decomposePar
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && decomposePar -decomposeParDict system/decomposeParDict.meshing"
    exitcode, out, err = exec_cmd(cmd)
    # print(f"{out = }")
    # print(f"{err = }\n")
    
    # mpirun snappyHexMesh
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                numberOfSubdomains system/decomposeParDict.meshing -value"
    exitcode, out, err = exec_cmd(cmd)
    number_of_procs = int(out)
    # print(f"{number_of_procs = }")
    
    # for writing the snappyHexMesh.log we use /var/tmp/ which is a tmpfs in RAM
    # snappyHexMesh.log has a lot of IO and write cycles to a disk.
    if number == 0:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && mpirun -np {number_of_procs} snappyHexMesh \
                 -parallel -overwrite -dict system/snappyHexMeshDict -decomposeParDict system/decomposeParDict.meshing 2>&1 | tee /var/tmp/snappyHexMesh_0.log"
    elif number >= 1:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && mpirun -np {number_of_procs} snappyHexMesh \
               -parallel -overwrite -dict system/snappyHexMeshDict_{number} -decomposeParDict system/decomposeParDict.meshing 2>&1 | tee /var/tmp/snappyHexMesh_{number}.log"
    else:
        exitcode = 1
        snappy_out_ = None
        err = "###not a valid number in snappyHexMesh"
    exitcode, snappy_out_, err = exec_cmd(cmd)
    # print(f"{out = }")
    # print(f"{err = }\n")
 
     # createBaffles
    cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && mpirun -np {number_of_procs} createBaffles -parallel -overwrite"
    exitcode, out, err = exec_cmd(cmd)
    
    # mergeOrSplitBaffles
    cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && mpirun -np {number_of_procs} mergeOrSplitBaffles -parallel -split"
    exitcode, out, err = exec_cmd(cmd)
 
    # reconstructParMesh, better -withZero ?!?!
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && reconstructParMesh -constant"
    exitcode, out, err = exec_cmd(cmd)
    
    # deleting the processor* folders
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && rm -r processor*"
    exitcode, out, err = exec_cmd(cmd)
    
    # # checkMesh
    # cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && checkMesh -writeAllFields"
    # exitcode, out, err = exec_cmd(cmd)
    
    # renumberMesh
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && renumberMesh -overwrite"
    exitcode, out, err = exec_cmd(cmd)
    
    # cp -r 0.orig/ 0/ # NOT NEEDED!?!?!?
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && cp -r 0.orig/ 0/"
    exitcode, out, err = exec_cmd(cmd)
    print(f"***Meshing mesh nr. {number} finished\n")

    return snappy_out_
    
    
def exec_checkMesh(number):
    # checkMesh and write to log
    cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && checkMesh -writeAllFields 2>&1 > checkMesh_{number}.log"
    exitcode, out, err = exec_cmd(cmd)
    return out


def copy_snappyHexMeshDict(number):
    # copy the original file named snappyHexMeshDict to a new file named snappyHexMeshDict_{number}
    cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && cp system/snappyHexMeshDict system/snappyHexMeshDict_{number}"
    exitcode, out, err = exec_cmd(cmd)


def get_mesh_quality(number):
    """
    Reads a checkMesh_{number}.log and extracts important quality parameters from it.
    

    Parameters
    ----------
    number : TYPE int 
        DESCRIPTION. A number that denotes our snappyHexMeshDict with changed parameters.

    Returns
    -------
    returned_results : TYPE tuple
        DESCRIPTION. [numCells, numRegions, maxNonOrtho, averageNonOrtho,\
                            maxSkewNess, num_severly_nonOrthoFaces]

    """
    print(f"Getting mesh quality parameters of mesh nr. {number}...")
    print("-->(numCells, numRegions, maxNonOrtho, averageNonOrtho, maxSkewNess, num_severly_nonOrthoFaces, layerPercentage)")
    file_path = f"checkMesh_{number}.log"
    
    with open(file_path, 'r') as file:
        content = file.read()
    
    # find the number of cells
    search_text ="cells:"   
    chars_after = 22 # with 20 we'd find a 2 digit number in the millions
    index = content.find(search_text)
    if index != -1:
        start = index + len(search_text)
        result = remove_chars(content[start:start + chars_after])
    else:
        result = 0 # 
    try:
        numCells = int(result)
    except:
        numCells = 111111.23456
    
    # find the number of regions
    search_text ="Number of regions:"   
    chars_after = 3 
    index = content.find(search_text)
    if index != -1:
        start = index + len(search_text)
        result = remove_chars(content[start:start + chars_after])
    else:
        result = 33
    try:
        numRegions = int(result)
    except:
        numRegions = 2.12345
    
    # find the maxNonOrthogonality
    search_text ="Mesh non-orthogonality Max:"   
    chars_after = 8 
    index = content.find(search_text)
    if index != -1:
        start = index + len(search_text)
        result = remove_chars(content[start:start + chars_after])
    else:
        result = 99.12345
    try:
        maxNonOrtho = float(result)
    except:
        maxNonOrtho = 66.12345
    
    # find the average nonOrthogonality
    search_text = f"Mesh non-orthogonality Max: {maxNonOrtho} average:"   
    chars_after = 8 
    index = content.find(search_text)
    if index != -1:
        start = index + len(search_text)
        result = remove_chars(content[start:start + chars_after])
    else:
        result = 10.12345 # None will lead to Type Error
    try:
        averageNonOrtho = float(result)
    except:
        averageNonOrtho = 16.12345
    
    # find the maxSkewNess
    search_text ="Max skewness = "   
    chars_after = 8
    index = content.find(search_text)
    if index != -1:
        start = index + len(search_text)
        result = remove_chars(content[start:start + chars_after])
    else:
        result = 9.12345
    try:
        maxSkewNess = float(result)    
    except:
        maxSkewNess = 11.12345

    # find the number of severly nonOrthogonal faces
    search_text ="Number of severely non-orthogonal (> 70 degrees) faces:"   
    chars_after = 4 
    index = content.find(search_text)
    if index != -1:
        start = index + len(search_text)
        result = remove_chars(content[start:start + chars_after])
    else:
        result = 111.12345 # None does not work here, if no faces are > 70°
    try:
        num_severly_nonOrthoFaces = float(result) # sometimes . is still in, but doesn't matter.
    except:
        num_severly_nonOrthoFaces = 99.12345
    
    returned_results = (numCells, numRegions, maxNonOrtho, averageNonOrtho,\
                        maxSkewNess, num_severly_nonOrthoFaces)
    return returned_results
    

def get_maxNonOrtho(number):
    if number == 0:
        cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.maxNonOrtho system/snappyHexMeshDict -value"
    elif number >= 1:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.maxNonOrtho system/snappyHexMeshDict_{number} -value"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number in get_maxNonOrtho"
    exitcode, out, err = exec_cmd(cmd)
    return float(out)


def get_maxBoundarySkewNess(number):
    if number == 0:
        cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.maxBoundarySkewness system/snappyHexMeshDict -value"
    elif number >= 1:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.maxBoundarySkewness system/snappyHexMeshDict_{number} -value"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number in get_maxBoundarySkewNess"
    exitcode, out, err = exec_cmd(cmd)
    return float(out)


def get_maxInternalSkewNess(number):
    if number == 0:
        cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.maxInternalSkewness system/snappyHexMeshDict -value"
    elif number >= 1:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.maxInternalSkewness system/snappyHexMeshDict_{number} -value"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number in get_maxInternalSkewNess"
    exitcode, out, err = exec_cmd(cmd)
    return float(out)


def get_relaxedMaxNonOrtho(number):
    if number == 0:
        cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.relaxed.maxNonOrtho system/snappyHexMeshDict -value"
    elif number >= 1:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.relaxed.maxNonOrtho system/snappyHexMeshDict_{number} -value"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number in get_relaxedMaxNonOrtho"
    exitcode, out, err = exec_cmd(cmd)
    return float(out)


def get_relaxedMaxBoundarySkewNess(number):
    if number == 0:
        cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.relaxed.maxBoundarySkewness system/snappyHexMeshDict -value"
    elif number >= 1:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.relaxed.maxBoundarySkewness system/snappyHexMeshDict_{number} -value"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number in get_relaxedMaxBoundarySkewNess"
    exitcode, out, err = exec_cmd(cmd)
    return float(out)


def get_relaxedMaxInternalSkewNess(number):
    if number == 0:
        cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.relaxed.maxInternalSkewness system/snappyHexMeshDict -value"
    elif number >= 1:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.relaxed.maxInternalSkewness system/snappyHexMeshDict_{number} -value"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number in get_relaxedMaxInternalSkewNess"
    exitcode, out, err = exec_cmd(cmd)
    return float(out)


def set_maxNonOrtho(number, set_value):
    if number == 0:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.maxNonOrtho system/snappyHexMeshDict -set {set_value}"
    elif number >= 1:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.maxNonOrtho system/snappyHexMeshDict_{number} -set {set_value}"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number in set_maxNonOrtho"
    exitcode, out, err = exec_cmd(cmd)
    #print(f"***set_maxNonOrtho {out = }")
    #print(f"***set_maxNonOrtho {err = }")
    #print(f"***set_maxNonOrtho {exitcode = }")


def set_maxBoundarySkewNess(number, set_value):
    if number == 0:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.maxBoundarySkewness system/snappyHexMeshDict -set {set_value}"
    elif number >= 1:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.maxBoundarySkewness system/snappyHexMeshDict_{number} -set {set_value}"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number in set_maxBoundarySkewNess"
    exitcode, out, err = exec_cmd(cmd)
    #print(f"***set_maxBoundarySkewNess {err = }")


def set_maxInternalSkewNess(number, set_value):
    if number == 0:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.maxInternalSkewness system/snappyHexMeshDict -set {set_value}"
    elif number >= 1:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.maxInternalSkewness system/snappyHexMeshDict_{number} -set {set_value}"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number in set_maxInternalSkewNess"
    exitcode, out, err = exec_cmd(cmd)
    #print(f"***set_maxInternalSkewNess {err = }")


def set_relaxedMaxNonOrtho(number, set_value):
    if number == 0:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.relaxed.maxNonOrtho system/snappyHexMeshDict -set {set_value}"
    elif number >= 1:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.relaxed.maxNonOrtho system/snappyHexMeshDict_{number} -set {set_value}"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number"
    exitcode, out, err = exec_cmd(cmd)
    #print(f"***set_relaxedMaxNonOrtho {err = }")


def set_relaxedMaxBoundarySkewNess(number, set_value):
    if number == 0:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.relaxed.maxBoundarySkewness system/snappyHexMeshDict -set {set_value}"
    elif number >= 1:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.relaxed.maxBoundarySkewness system/snappyHexMeshDict_{number} -set {set_value}"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number in set_relaxedMaxBoundarySkewNess"
    exitcode, out, err = exec_cmd(cmd)
    #print(f"***set_relaxedMaxBoundarySkewNess {err = }")


def set_relaxedMaxInternalSkewNess(number, set_value):
    if number == 0:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.relaxed.maxInternalSkewness system/snappyHexMeshDict -set {set_value}"
    elif number >= 1:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                meshQualityControls.relaxed.maxInternalSkewness system/snappyHexMeshDict_{number} -set {set_value}"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number in set_relaxedMaxInternalSkewNess"
    exitcode, out, err = exec_cmd(cmd)
    #print(f"***set_relaxedMaxInternalSkewNess {err = }")


def get_layerFeatureAngle(number):
    if number == 0:
        cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                addLayersControls.featureAngle system/snappyHexMeshDict -value"
    elif number >= 1:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                addLayersControls.featureAngle system/snappyHexMeshDict_{number} -value"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number in get_layerFeatureAngle"
    exitcode, out, err = exec_cmd(cmd)
    return float(out)


def set_layerFeatureAngle(number, set_value):
    # sets the featureAnglein addLayerControls of snappyHexMeshDict to set_value.
    if number == 0:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                addLayersControls.featureAngle system/snappyHexMeshDict -set {set_value}"
    elif number >= 1:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                addLayersControls.featureAngle system/snappyHexMeshDict_{number} -set {set_value}"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number in set_layerFeatureAngle"
    exitcode, out, err = exec_cmd(cmd)


def exec_mkdir(number):
    # mkdir a new directory for a generated mesh to be stored for later use.
    # basically we just don't want to generate a good mesh once again.
    if number == 0:
        cmd = "mkdir constant/Mesh_0"
    elif number >= 1:
        cmd = f"mkdir constant/Mesh_{number}"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number in exec_mkdir"
    exitcode, out, err = exec_cmd(cmd)

def get_deltaT():
    # get deltaT from the controlDict.
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
            deltaT system/controlDict -value"
    exitcode, out, err = exec_cmd(cmd)
    deltaT_ = out
    return deltaT_

    
def exec_copyMesh(number):
    # copy a generated mesh to a separate folder named Mesh_{number}.
    print("***Copying mesh data.")
    if number == 0:
        cmd = "cp -r constant/polyMesh constant/Mesh_0"
    elif number >= 1:
        cmd = f"cp -r constant/polyMesh constant/Mesh_{number}"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number in exec_copyMesh"
    exitcode, out, err = exec_cmd(cmd)
    
    # try to copy 0/ folder
    cmd = f"cp -r 0/ constant/Mesh_{number}"
    exitcode, out, err = exec_cmd(cmd)
    
    # also try to copy deltaT/ to Mesh{number}
    deltaT = get_deltaT()
    cmd = f"cp -r {deltaT}/ constant/Mesh_{number}"
    exitcode, out, err = exec_cmd(cmd)
    

def get_mesh_parameters(number):
    # getting the most important mesh paramters from snappyHexMeshDict
    print(f"\nGetting set mesh parameters of mesh nr. {number}...")
    print("-->(maxNonOrtho, maxBoundarySkewNess, maxInternalSkewNess, relaxedMaxNonOrtho, relaxedMaxBoundarySkewNess, relaxedMaxInternalSkewNess, layerFeatureAngle)")
    maxNonOrtho = get_maxNonOrtho(number)
    maxBoundarySkewNess = get_maxBoundarySkewNess(number)
    maxInternalSkewNess = get_maxInternalSkewNess(number)
    relaxedMaxNonOrtho = get_relaxedMaxNonOrtho(number)
    relaxedMaxBoundarySkewNess = get_relaxedMaxBoundarySkewNess(number)
    relaxedMaxInternalSkewNess = get_relaxedMaxInternalSkewNess(number)
    layerFeatureAngle = get_layerFeatureAngle(number)
    results = (maxNonOrtho, maxBoundarySkewNess, maxInternalSkewNess, relaxedMaxNonOrtho, \
               relaxedMaxBoundarySkewNess, relaxedMaxInternalSkewNess, layerFeatureAngle)
    return results

def get_addLayers(number):
    # get if addLayers is true or false in snappyHexMeshDict
    # is converted to Python True or False
    if number == 0:
        cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                addLayers system/snappyHexMeshDict -value"
    elif number >= 1:
        cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                addLayers.featureAngle system/snappyHexMeshDict_{number} -value"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number in get_addLayers"
    exitcode, out, err = exec_cmd(cmd)
    return bool(out)


def get_layerPercentage(stdout_):
    # find a layer percentage in stdout of snappyHexMesh
    # with more than one group present, problems may arise
    # chars_after must be calibrated, it depends on the patch name with most chars.
    content = stdout_
    search_text ="[%]" # the only stable text in the vicinity, the '---' change.
    chars_after = 109 # this value is not always the same.
    index = content.find(search_text)
    if index != -1:
        start = index + len(search_text)
        result1 = content[start:start + chars_after]
        result2 = result1[-4:] # we need the last 4 digits
        # print("$$$",result1,"$$$")
        # print("'''",result2, "'''", type(result2))
    else:
        result2 = 1.12345 # odd value so we know what happened
    try: # sometimes above text is not recognized although it should in stdout
        layerPercentage = float(result2)
    except:
        layerPercentage = 2.12345 # in this case compare values in the snappyHexMesh.logs
    return layerPercentage
    

def param_rand_gaussian(parameter, num_opti=NUMBER_LOOPS):
    """
    Applies some Gaussian randomness to a parameter.

    Parameters
    ----------
    parameter : TYPE mostly float
        DESCRIPTION. input parameter to snappyHexMeshDict
    num_opti : TYPE, optional
        DESCRIPTION. The default is NUMBER_LOOPS.

    Returns
    -------
    new_param : TYPE float
        DESCRIPTION. input parameter with slight randomness.

    """
    sigma = 1 / (num_opti * 2)
    new_param = random.gauss(parameter, sigma)
    return new_param


def param_large_rand_gaussian(parameter, num_opti=NUMBER_LOOPS):
    """
    Applies some Gaussian randomness to a parameter, here with a larger sigma.

    Parameters
    ----------
    parameter : TYPE mostly float
        DESCRIPTION. input parameter to snappyHexMeshDict
    num_opti : TYPE, optional
        DESCRIPTION. The default is NUMBER_LOOPS.

    Returns
    -------
    new_param : TYPE float
        DESCRIPTION. input parameter with slight randomness.

    """
    sigma = 1.5 / (num_opti)
    new_param = random.gauss(parameter, sigma)
    return new_param


def exec_copyCheckMeshData(number):
    # copy generated checkMeshData to Mesh_{number} to have it later.
    # Also copying the checkMesh_{number}.log and the snappyHexMesh_{number}.log 
    # from /var/tmp to . if activated in exec_meshing()
    print("***Copying checkMesh data and logs.")
    if number == 0:  # below & replaced by ;
        cmd = "cp 0/* constant/Mesh_0/ ; cp checkMesh_0.log constant/Mesh_0/ ; \
            cp /var/tmp/snappyHexMesh_0.log . ; cp snappyHexMesh_0.log constant/Mesh_0/ "
    elif number >= 1:
        cmd = f"cp 0/* constant/Mesh_{number} ; cp checkMesh_{number}.log constant/Mesh_{number}/ ; \
                 cp /var/tmp/snappyHexMesh_{number}.log . ; cp snappyHexMesh_{number}.log constant/Mesh_{number}/"
    else:
        exitcode = 1
        out = None
        err = "###not a valid number in exec_copyCheckMeshData"
    exitcode, out, err = exec_cmd(cmd)


def param_rand_uniform(interval):
    """
    Randomly generates a new parameter from the given interval.

    Parameters
    ----------
    interval : TYPE tuple
        DESCRIPTION. interval in which we pick a random parameter

    Returns
    -------
    new_param : TYPE float
        DESCRIPTION. input parameter with uniform randomness.

    """
    a = interval[0]
    b = interval[1]
    new_param = random.uniform(a, b)
    return new_param


###############################################################################
###############################################################################
###############################################################################
# Main proggie starts here
interval_maxNonOrtho = (70, 73)
interval_maxBoundarySkewness = (7, 8)
interval_maxInternalSkewness = (3.5, 4) # CURRENTLY NOT CHANGED, ONLY MAX VALUE IS USED
interval_relaxedMaxNonOrtho = (68, 75) # (68, 75) # CURRENTLY NOT CHANGED, ONLY MAX VALUE IS USED
interval_relaxedMaxBoundarySkewness = (7, 9) # CURRENTLY NOT CHANGED, ONLY MAX VALUE IS USED
interval_relaxedMaxInternalSkewness = (4, 4) # CURRENTLY NOT CHANGED, ONLY MAX VALUE IS USED
interval_layerFeatureAngle = (181, 251) 

# TESTING THE RANDOMNESS
# plt.figure(figsize=(15,9))
# for i in range(100):
#     var1 = param_rand_uniform(interval_maxNonOrtho)
#     var2 = param_rand_uniform(interval_maxBoundarySkewness)
#     var3 = param_rand_uniform(interval_layerFeatureAngle)
#     print(var1,var2,var3)
#     plt.plot(i, var1, 'bx')
#     plt.plot(i, var2, 'ro')
#     plt.plot(i, var3, 'g.')
# plt.plot([0,99],[interval_maxNonOrtho[0], interval_maxNonOrtho[0]], 'b--' )
# plt.plot([0,99],[interval_maxNonOrtho[1], interval_maxNonOrtho[1]], 'b--' )
# plt.plot([0,99],[interval_maxBoundarySkewness[0], interval_maxBoundarySkewness[0]], 'r--' )
# plt.plot([0,99],[interval_maxBoundarySkewness[1], interval_maxBoundarySkewness[1]], 'r--' )
# plt.plot([0,99],[interval_layerFeatureAngle[0], interval_layerFeatureAngle[0]], 'g--' )
# plt.plot([0,99],[interval_layerFeatureAngle[1], interval_layerFeatureAngle[1]], 'g--' )
# plt.yscale("log")

# we need to calc approximate steps per loop to cover the interval
# these values will get a randomness to them later
step_maxNonOrtho = abs(interval_maxNonOrtho[1]-interval_maxNonOrtho[0])/NUMBER_LOOPS
step_maxBoundarySkewness = abs(interval_maxBoundarySkewness[1]-interval_maxBoundarySkewness[0])/NUMBER_LOOPS
#step_maxInternalSkewness = abs(interval_maxInternalSkewness[1]-interval_maxInternalSkewness[0])/NUMBER_LOOPS
#step_relaxedMaxNonOrtho = abs(interval_relaxedMaxNonOrtho[1]-interval_relaxedMaxNonOrtho[0])/NUMBER_LOOPS
#step_relaxedMaxBoundarySkewness = abs(interval_relaxedMaxBoundarySkewness[1]-interval_relaxedMaxBoundarySkewness[0])/NUMBER_LOOPS
#step_relaxedMaxInternalSkewness = abs(interval_relaxedMaxInternalSkewness[1]-interval_relaxedMaxInternalSkewness[0])/NUMBER_LOOPS
step_layerFeatureAngle = abs(interval_layerFeatureAngle[1]-interval_layerFeatureAngle[0])/NUMBER_LOOPS

print(f"Number of loops = {NUMBER_LOOPS}\n")

print("Searching intervals set...")
print(f"{interval_maxNonOrtho = }")
print(f"{interval_maxBoundarySkewness = }")
print(f"{interval_maxInternalSkewness = }")
print(f"{interval_relaxedMaxNonOrtho = }")
print(f"{interval_relaxedMaxBoundarySkewness = }")
print(f"{interval_relaxedMaxInternalSkewness = }")
print(f"{interval_layerFeatureAngle = }")

print("\nInitial stepping...")
print(f"{step_maxNonOrtho = }")
print(f"{step_maxBoundarySkewness = }")
#print(f"{step_maxInternalSkewness = }")
#print(f"{step_relaxedMaxNonOrtho = }")
#print(f"{step_relaxedMaxBoundarySkewness = }")
#print(f"{step_relaxedMaxInternalSkewness = }")
print(f"{step_layerFeatureAngle = }")

# setting initial values in original snappyHexMeshDict
addLayers=get_addLayers(0)
print(f"{addLayers = }")
set_maxNonOrtho(0, interval_maxNonOrtho[1])
sleep(0.2)
set_maxBoundarySkewNess(0, interval_maxBoundarySkewness[1])
sleep(0.2)
set_maxInternalSkewNess(0, interval_maxInternalSkewness[1])
sleep(0.2)
set_relaxedMaxNonOrtho(0, interval_relaxedMaxNonOrtho[1])
sleep(0.2)
set_relaxedMaxBoundarySkewNess(0, interval_relaxedMaxBoundarySkewness[1])
sleep(0.2)
set_relaxedMaxInternalSkewNess(0, interval_relaxedMaxInternalSkewness[1])
sleep(0.2)
if addLayers==True:
    set_layerFeatureAngle(0, interval_layerFeatureAngle[0])
print("\nStarting values set....")

# we need a list to collect all important results
mesh_pq_results = [] # WAS mesh_params_and_quality_results = [] but too long
    
mesh_parameters = get_mesh_parameters(0)
print(f"{mesh_parameters = }")

# GENERATING THE ZERO MESH   
start = time.time()
currentDateAndTime = datetime.now()
currentTime = currentDateAndTime.strftime("%H:%M:%S")
print("Started @", currentDateAndTime)
snappy_out = exec_meshing(0)
if addLayers==True:
    layerPercentage = get_layerPercentage(snappy_out)
else:
    layerPercentage = 0

# EXECUTING CHECKMESH ON ZERO MESH
exec_checkMesh(0)
end = time.time()
print(f"A single loop will take about {(end-start)/60:.2f} minutes.\n")

# GETTING MESH QUALITY OF ZERO MESH
mesh_quality = get_mesh_quality(0) + (layerPercentage,)
mesh_pq_results.append(mesh_parameters + mesh_quality)
print(f"Mesh nr. 0 {mesh_pq_results = }")

# COPYING THE ZERO MESH TO HAVE IT LATER
exec_mkdir(0)
sleep(0.2)
exec_copyMesh(0)
sleep(0.2)
exec_copyCheckMeshData(0)
sleep(0.2)

###############################################################################
# WE DEFINITELY NEED A FIRST MESH WITH OTHER PARAMETERS, OR 
# WE DON'T HAVE ANYTHING TO COMPARE THE ZERO MESH TO
# we are setting 2 new values for our FIRST MESH
new_maxNonOrtho = mesh_parameters[0] - step_maxNonOrtho
new_maxBoundarySkewNess = mesh_parameters[1] - step_maxBoundarySkewness
new_layerFeatureAngle = param_rand_uniform(interval_layerFeatureAngle)

new_mesh_parameters = (new_maxNonOrtho, new_maxBoundarySkewNess, mesh_parameters[2], 
                  mesh_parameters[3], mesh_parameters[4], mesh_parameters[5],
                  new_layerFeatureAngle)
print(f"\n{new_mesh_parameters = }\n")
mesh_parameters = new_mesh_parameters

# WE CREATE A NEW snappyHexMeshDict and set the new values
copy_snappyHexMeshDict(1)
set_maxNonOrtho(1, new_maxNonOrtho)
set_maxBoundarySkewNess(1, new_maxBoundarySkewNess)
set_layerFeatureAngle(1, new_layerFeatureAngle)

for i in tqdm(range(1, NUMBER_LOOPS+1)):# tqdm delay does not work.
    print("\n########################################################################")
    print(f"Batch loop nr. {i}")
    mesh_parameters = get_mesh_parameters(i)
    print(f"{mesh_parameters = }")
    currentDateAndTime = datetime.now()
    currentTime = currentDateAndTime.strftime("%H:%M:%S")
    print("Started @", currentDateAndTime)
    snappy_out = exec_meshing(i)
    if addLayers==True:
        layerPercentage = get_layerPercentage(snappy_out)
    else:
        layerPercentage = 0
    exec_checkMesh(i)
    mesh_quality = get_mesh_quality(i) + (layerPercentage,) # not pretty
    # print(f"Mesh nr. {i} {mesh_quality = }")
    mesh_pq_results.append(mesh_parameters + mesh_quality)
    print(f"Mesh nr. {i} {mesh_pq_results = }")
    exec_mkdir(i)
    exec_copyMesh(i)
    exec_copyCheckMeshData(i)

    # NOW WE HAVE TO DECIDE HOW TO GO ON FURTHER
    # maxNonOrtho, if it got better, we try further improvements, 
    # if not we search around the old value
    # if mesh_pq_results[1][9] < mesh_pq_results[0][9]:
    #     new_maxNonOrtho = param_rand_gaussian(mesh_parameters[0] - step_maxNonOrtho)
    #     print("****maxNonOrtho has improved")
    # elif mesh_pq_results[1][9] >= mesh_pq_results[0][9]:
    #     new_maxNonOrtho = param_rand_gaussian(mesh_parameters[0]) # the old value with different randomness
    
    
    # EQUAL STEPS: maxNonOrtho is decreased without randomness
    # new_maxNonOrtho = mesh_parameters[0] - step_maxNonOrtho
    
    # QUASI-EQUAL STEPS: maxNonOrtho is decreased with randomness    
    # new_maxNonOrtho = param_rand_gaussian(mesh_parameters[0] - step_maxNonOrtho)
    
    # UNIFORM RANDOMNESS: maxNonOrtho is uniformly random in the given interval
    new_maxNonOrtho = param_rand_uniform(interval_maxNonOrtho)
    
    
    # maxSkewNess, if it got better, we try further improvements, 
    # if not we search around the old value
    # if mesh_pq_results[1][11] < mesh_pq_results[0][11]:
    #     new_maxBoundarySkewNess = param_rand_gaussian(mesh_parameters[1] - step_maxBoundarySkewness)
    #     print("****maxBoundarySkewNess has improved")
    # elif mesh_pq_results[1][1] >= mesh_pq_results[0][1]:
    #     new_maxBoundarySkewNess = param_rand_gaussian(mesh_parameters[1]) # the old value with different randomness
    
    
    # EQUAL STEPS: maxBoundarySkewNess is decreased without randomness
    # new_maxBoundarySkewNess = mesh_parameters[1] - step_maxBoundarySkewness
    
    # QUASI-EQUAL STEPS: maxBoundarySkewNess is decreased with randomness.
    # new_maxBoundarySkewNess = param_rand_gaussian(mesh_parameters[1] - step_maxBoundarySkewness) # PLUS SIGN HERE, WE INCREASE IT NOW
            
    # UNIFORM RANDOMNESS: maxBoundarySkewNess is uniformly random in the given interval
    new_maxBoundarySkewNess = param_rand_uniform(interval_maxBoundarySkewness)
    
    # layerFeatureAngle
    # we get the layer percentage from snappy's stdout, as we don't want to write too much (no snappy.log)
    # if mesh_pq_results[1][13] > mesh_pq_results[0][13]:
    #     new_layerFeatureAngle = param_large_rand_gaussian(mesh_parameters[6]) # the old value with different randomness
    #     print("****layerPercentage has improved")
    # elif mesh_pq_results[1][13] <= mesh_pq_results[0][13]:
    #     new_layerFeatureAngle = param_large_rand_gaussian(mesh_parameters[6] + step_layerFeatureAngle)
    
    
    # EQUAL STEPS:new_layerFeatureAngle is increased without randomness
    # new_layerFeatureAngle = mesh_parameters[6] + step_layerFeatureAngle
    
    # QUASI-EQUAL STEPS:layerFeatureAngle is increased in every step with added randomness
    # new_layerFeatureAngle = param_large_rand_gaussian(mesh_parameters[6] + step_layerFeatureAngle)
    
    # UNIFORM RANDOMNESS: layerFeatureAngle is uniformly random in the given interval
    new_layerFeatureAngle = param_rand_uniform(interval_layerFeatureAngle)

    new_mesh_parameters = (new_maxNonOrtho, new_maxBoundarySkewNess, mesh_parameters[2], 
                      mesh_parameters[3], mesh_parameters[4], mesh_parameters[5],
                      new_layerFeatureAngle)
    
    print(f"\n{new_mesh_parameters = }\n")
    
    # WE AGAIN CREATE A NEW snappyHexMeshDict and set the new values
    if i < NUMBER_LOOPS: # prevents a last sHMD that is never used
        copy_snappyHexMeshDict(i+1)
        sleep(0.5)
        set_maxNonOrtho(i+1, new_maxNonOrtho)
        sleep(0.5)
        set_maxBoundarySkewNess(i+1, new_maxBoundarySkewNess)
        sleep(0.5)
        set_layerFeatureAngle(i+1, new_layerFeatureAngle)
    
print("\n************************************")
print(f"The final results after {NUMBER_LOOPS} loops are: ")
print(f"{mesh_pq_results = }")

# let's plot the progression of some values and see if they improved
scalefactor_cells = 1E5

loop_nr = [i for i in range(len(mesh_pq_results))]
maxNonOrtho_result_plot = []
maxNonOrtho_set_plot = []
maxSkewness_result_plot = []
maxSkewness_set_plot = []
layerPercentage_result_plot = []
layerFeatureAngle_set_plot = []
num_cells_result_plot = []

# we need separate axes for plotting
for i, row in enumerate(mesh_pq_results):
    maxNonOrtho_set = row[0]
    maxNonOrtho_result = row[9]
    maxSkewNess_set = row[1]
    maxSkewNess_result = row[11]
    layerFeatureAngle_set = row[6]
    layerPercentage_result = row[13]
    num_cells_result = row[7]

    maxNonOrtho_set_plot.append(maxNonOrtho_set)    
    maxNonOrtho_result_plot.append(maxNonOrtho_result)
    maxSkewness_set_plot.append(maxSkewNess_set)
    maxSkewness_result_plot.append(maxSkewNess_result)
    layerFeatureAngle_set_plot.append(layerFeatureAngle_set)
    layerPercentage_result_plot.append(layerPercentage_result)
    num_cells_result_plot.append(num_cells_result/scalefactor_cells)
    
plt.figure(figsize=(15,9))
plt.plot(loop_nr, maxNonOrtho_set_plot, 'b--', label='maxNonOrtho_set')
plt.plot(loop_nr, maxNonOrtho_result_plot, 'b-', label='maxNonOrtho_result')
plt.plot(loop_nr, maxSkewness_set_plot, 'r--', label='maxSkewNess_set')
plt.plot(loop_nr, maxSkewness_result_plot, 'r-', label='maxSkewNess_result')
plt.plot(loop_nr, layerFeatureAngle_set_plot, 'g--', label='LayerFeatureAngle_set')
plt.plot(loop_nr, layerPercentage_result_plot, 'g-', label='LayerPercentage_result')
plt.plot(loop_nr, num_cells_result_plot, 'c-', label='num_cells_result')
for i in range(len(mesh_pq_results)):
    plt.text(loop_nr[i], maxNonOrtho_set_plot[i], str(maxNonOrtho_set_plot[i]))
    plt.text(loop_nr[i], maxNonOrtho_result_plot[i], str(maxNonOrtho_result_plot[i]))
    plt.text(loop_nr[i], maxSkewness_set_plot[i], str(maxSkewness_set_plot[i]))
    plt.text(loop_nr[i], maxSkewness_result_plot[i], str(maxSkewness_result_plot[i]))
    plt.text(loop_nr[i], layerFeatureAngle_set_plot[i], str(layerFeatureAngle_set_plot[i]))
    plt.text(loop_nr[i], layerPercentage_result_plot[i], str(layerPercentage_result_plot[i]))
    plt.text(loop_nr[i], num_cells_result_plot[i], str(int(num_cells_result_plot[i]*scalefactor_cells)))
plt.legend()
plt.show()

# Clean the OpenFOAM folder:
cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && ./Clean"

exitcode, out, err = exec_cmd(cmd)
print("\nOpenFOAM case cleaned. Bye!")

    
