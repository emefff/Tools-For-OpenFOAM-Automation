#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 24 12:05:38 2025

@author: emefff
"""

import random
import re
import math as m
from subprocess import run, Popen
from tqdm import tqdm
from datetime import datetime
import time
from time import sleep
import os
from os.path import isfile
import bisect
import pandas as pd
import logging
# from distutils.util import strtobool

#################### NEEDS THE FOLLOWING IN YOUR controlDict ##################
"""
functions
{
    solverInfo
    {
        type            solverInfo;
        libs            ("libutilityFunctionObjects.so");
        fields          (U p);
        writeResidualFields yes;
        executeControl      timeStep;
        executeInterval     1;
        writeControl        adjustableRunTime;
        writeInterval       25;
    }
}
"""
# IF NOT PRESENT IT WILL BE ADDED.

"""
Structure of solverInfo.dat in OpenFOAM 2406 with number of arg, of course only correct
if solverInfo defined like above and the SAME SOLVER is used:
    Time $1     	U_solver $2    	Ux_initial $3   	Ux_final $4      	Ux_iters $5     	
    0.00905263    smoothSolver	    6.180440e-05	    6.944520e-08	    1	      

    Uy_initial $6    	Uy_final $7      	Uy_iters $8     	Uz_initial $9    	Uz_final $10      	
    1.007080e-04	    9.826700e-08	    1	             1.349090e-05	    1.627360e-08	    
    
    Uz_iters $11     	U_converged $12  	p_solver $13     	p_initial $14    	p_final $15
    1	             false	         GAMG           	5.615360e-01	    1.587190e-03	
    
    	p_iters $16      	p_converged $17
    2	             true
    
WE CAN USE THIS INFO TO INCREASE OR DECREASE deltaT OR maxCO ETC        
    
"""

###############################################################################

logging.basicConfig(
    level=logging.INFO,
    # format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    format='%(asctime)s - %(levelname)s - %(message)s',
    #filename='controlDict_automation.log',
    handlers=[logging.FileHandler('controlDict_automation.log'), logging.StreamHandler()],
    #filemode='a',
    force=True
)

# Each module or function can get a logger by name
logger = logging.getLogger(__name__)


def print_and_log_info(msg):
    # print(msg)
    logger.info(msg)
    
def print_and_log_warning(msg):
    # print(msg)
    logger.warning(msg)

def print_and_log_error(msg):
    # print(msg)
    logger.error(msg)

def str_to_bool(val):
    # Convert strings to Python booleans
    val = val.lower()
    if val in ('y', 'yes', 't', 'true', 'on', '1'):
        return True
    elif val in ('n', 'no', 'f', 'false', 'off', '0'):
        return False
    else:
        print_and_log_error("[ERROR] Invalid truth value: {val}")
        raise ValueError(f"[ERROR] Invalid truth value: {val}")


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


def copy_controlDict():
    # copy the original file named controlDict to a new file named controlDict_copyWithComments
    file = 'system/controlDict_copyWithComments'
    if isfile(file):
        print_and_log_info("###controlDict_copyWithComments already present")
    else:
        cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && cp system/controlDict system/controlDict_copyWithComments"
        exitcode, out, err = exec_cmd(cmd)
        print_and_log_info("***controlDict copied")


def copy_fvSolution():
    # copy the original file named fvSolution to a new file named fvSolution_copyWithComments
    file = 'system/fvSolution_copyWithComments'
    if isfile(file):
        print_and_log_info("###fvSolution_copyWithComments already present")
    else:
        cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && cp system/fvSolution system/fvSolution_copyWithComments"
        exitcode, out, err = exec_cmd(cmd)
        print_and_log_info("***fvSolution copied")


def get_maxCo():
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                maxCo system/controlDict -value"
    exitcode, out, err = exec_cmd(cmd)
    return float(out)


def check_add_solverInfo():
    """
    Checks if solverInfo is present in controlDict. If not it adds a default solverInfo
    function.

    Returns
    -------
    None.

    """
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                functions.solverInfo system/controlDict -value"
    exitcode, out, err = exec_cmd(cmd)
    if out == '':
        print_and_log_warning("###solverInfo not present in controlDict")
        print_and_log_info("***Adding solverInfo in controlDict")
        cmd = 'source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                    functions.solverInfo system/controlDict -add "{\
                        type            solverInfo;\
                        libs            ( "libutilityFunctionObjects.so" );\
                        fields          ( U p );\
                        writeResidualFields yes;\
                        executeControl  timeStep;\
                        executeInterval 1;\
                        writeControl    adjustableRunTime;\
                        writeInterval   25;\
                    }"'
        exitcode, out, err = exec_cmd(cmd)
    elif err == '':
        print_and_log_info("***solverInfo found in controlDict")
        pass

def isfloat(num):
    try:
        float(num)
        return True
    except ValueError:
        return False


def find_latest_folder_solverInfo():
    # we have to find the latest folder in solverInfo folder, cd into solverInfo and back
    # cmd = "cd postProcessing/solverInfo && ls -d */ | sed 's#/##' | sort -g | tail -n 1 && cd ../../" 
    # doesn't always work
    # the bash script below contains just:
    # for d in */; do bn="${d%/}"; python3 -c "print(float('$bn'), '$bn')" ; done | sort -n | tail -n1 | cut -d' ' -f2
    # in the OpenFOAM folder, it's needed because we get conflicts with "" and '' otherwise.
    # cmd = "cd postProcessing/solverInfo && bash ../../latest_folder_bash.sh"
    # exitcode, out, err = exec_cmd(cmd)
    # latest_folder = out.replace("\n", "")
    
    dir_path = "postProcessing/solverInfo"
    with os.scandir(dir_path) as entries:
        folders_strings = [entry.name for entry in entries if entry.is_dir()]
    folders_floats = []
    for folder_str in folders_strings: # make a list of floats from the list of strings
        try: 
            folder_float = float(folder_str)
            folders_floats.append(folder_float)
        except:
            folders_strings.remove(folder_str)
    folders_floats = sorted(folders_floats)
    # sort the folder list (strings) like the folders_float list
    folders = [x for _,x in sorted(zip(folders_strings, folders_floats))]
    latest_folder = folders[-1]
    return latest_folder


def get_actual_timeStep():
    latest_folder = find_latest_folder_solverInfo()
    file = f'postProcessing/solverInfo/{latest_folder}/solverInfo.dat'
    if isfile(file):
        cmd = f"tail -n 1 {file} | awk '{{print $1}}' " # double curly needed!!!!
        exitcode, timeStep, err = exec_cmd(cmd)
        # print(timeStep)
    else:
        print_and_log_warning("###solverInfo.dat not present")
        timeStep = 0
    return float(timeStep)


def get_2nd_to_actual_timeStep():
    latest_folder = find_latest_folder_solverInfo()
    file = f'postProcessing/solverInfo/{latest_folder}/solverInfo.dat'
    if isfile(file):
        cmd = f"tail -n 2 {file} | awk '{{print $1}}' | head -n1 " # without last head we get 'float1\nfloat2\n'
        exitcode, timeStep, err = exec_cmd(cmd)
        # print(timeStep)
    else:
        print_and_log_warning("###solverInfo.dat not present")
        timeStep = 0
    return float(timeStep)


def get_achieved_deltaT():
    second_to_actual_timeStep = get_2nd_to_actual_timeStep()
    actual_timeStep           = get_actual_timeStep()
    return actual_timeStep - second_to_actual_timeStep
   

def get_pConverged():    
    latest_folder = find_latest_folder_solverInfo()
    file = f'postProcessing/solverInfo/{latest_folder}/solverInfo.dat'
    #print("yyy" , file, latest_folder)
    if isfile(file):
        cmd = f"tail -n 1 {file} | awk '{{print $17}}' " # double curly needed!!!!
        exitcode, pConverged, err = exec_cmd(cmd)
        pConverged = pConverged.replace("\n", "")
        #print("+++",pConverged, type(pConverged))
    else:
        print_and_log_warning("###solverInfo.dat not present")
        pConverged = None
    return str_to_bool(pConverged)


def get_UConverged():
    latest_folder = find_latest_folder_solverInfo()
    file = f'postProcessing/solverInfo/{latest_folder}/solverInfo.dat'
    if isfile(file):
        cmd = f"tail -n 1 {file} | awk '{{print $12}}' " # double curly needed!!!!
        exitcode, UConverged, err = exec_cmd(cmd)
        UConverged = UConverged.replace("\n", "")
        #print("+++",UConverged, type(UConverged))
    else:
        print_and_log_warning("###solverInfo.dat not present")
        UConverged = None
    return str_to_bool(UConverged)


def get_runTimeModifiable():
    # we need a Python conformal answer like True or False
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                runTimeModifiable system/controlDict -value"
    exitcode, out, err = exec_cmd(cmd)
    out = out.replace("\n", "") # there is a /n in this string!!!
    return str_to_bool(out)


def get_deltaT():
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                deltaT system/controlDict -value"
    exitcode, out, err = exec_cmd(cmd)
    return float(out)


def get_endTime():
    # crucial for stopping this program
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                endTime system/controlDict -value"
    exitcode, out, err = exec_cmd(cmd)
    return float(out)

    
def get_maxDeltaT():
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                maxDeltaT system/controlDict -value"
    exitcode, out, err = exec_cmd(cmd)
    return float(out)


def get_writeInterval():
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                writeInterval system/controlDict -value"
    exitcode, out, err = exec_cmd(cmd)
    return float(out)


def set_maxCo(value):
    cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                maxCo system/controlDict -set {value}"
    exitcode, out, err = exec_cmd(cmd)
    maxCo = value
    print_and_log_info(f"***Setting {maxCo = }")
    return out


def set_writeInterval(value):
    cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                writeInterval system/controlDict -set {value}"
    exitcode, out, err = exec_cmd(cmd)
    writeInterval = value
    print_and_log_info(f"***Setting {writeInterval = }")
    return out


def set_deltaT(value):
    cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                deltaT system/controlDict -set {value}"
    exitcode, out, err = exec_cmd(cmd)
    deltaT = value
    print_and_log_info(f"***Setting {deltaT = }")
    return out


def get_nCorrectors():
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                PIMPLE.nCorrectors system/fvSolution -value"
    exitcode, out, err = exec_cmd(cmd)
    return int(out)


def set_nCorrectors(value):
    cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                PIMPLE.nCorrectors system/fvSolution -set {value}"
    exitcode, out, err = exec_cmd(cmd)
    nCorrectors = value
    print_and_log_info(f"***Setting {nCorrectors = }")
    return out


def increase_nCorrectors_by_1():
    actual_nCorrectors = get_nCorrectors()
    new_nCorrectors = actual_nCorrectors + 1 
    set_nCorrectors(new_nCorrectors)
    print_and_log_info("+++Increasing nCorrectors")
    

def decrease_nCorrectors_by_1():
    actual_nCorrectors = get_nCorrectors()
    new_nCorrectors = actual_nCorrectors - 1
    set_nCorrectors(new_nCorrectors)
    print_and_log_info("---Decreasing nCorrectors")


def set_maxAlphaCo(value):
    cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                maxAlphaCo system/controlDict -set {value}"
    exitcode, out, err = exec_cmd(cmd)
    maxAlphaCo = value
    print_and_log_info(f"***Setting {maxAlphaCo = }")
    return out


def last_n_true(lst, n):
    # checks if the last num elements of a list are true
    return all(lst[-n:])


def get_nOuterCorrectors():
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                PIMPLE.nOuterCorrectors system/fvSolution -value"
    exitcode, out, err = exec_cmd(cmd)
    return int(out)


def set_nOuterCorrectors(value):
    cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                PIMPLE.nOuterCorrectors system/fvSolution -set {value}"
    exitcode, out, err = exec_cmd(cmd)
    nOuterCorrectors = value
    print_and_log_info(f"***Setting {nOuterCorrectors = }")
    return out


def get_nNonOrthogonalCorrectors():
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                PIMPLE.nNonOrthogonalCorrectors system/fvSolution -value"
    exitcode, out, err = exec_cmd(cmd)
    return int(out)


def set_nOrthogonalCorrectors(value):
    cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                PIMPLE.nNonOrthogonalCorrectors system/fvSolution -set {value}"
    exitcode, out, err = exec_cmd(cmd)
    nNonOrthogonalCorrectors = value
    print_and_log_info(f"***Setting {nNonOrthogonalCorrectors = }")
    return out


def increase_nOuterCorrectors_by5():
    actual_nOuterCorrectors = get_nOuterCorrectors()
    new_nOuterCorrectors = actual_nOuterCorrectors + 5
    set_nOuterCorrectors(new_nOuterCorrectors)
    print_and_log_info("+++Increasing nOuterCorrectors")
    

def decrease_nOuterCorrectors_by5():
    actual_nOuterCorrectors = get_nOuterCorrectors()
    new_nOuterCorrectors = actual_nOuterCorrectors - 5
    set_nOuterCorrectors(new_nOuterCorrectors)
    print_and_log_info("---Decreasing nOuterCorrectors")


def get_URelaxationFactor():
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                relaxationFactors.equations.U system/fvSolution -value"
    exitcode, out, err = exec_cmd(cmd)
    return float(out)


def get_kRelaxationFactor():
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                relaxationFactors.equations.k system/fvSolution -value"
    exitcode, out, err = exec_cmd(cmd)
    return float(out)


def get_epsilonStarRelaxationFactor():
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                relaxationFactors.equations.'epsilon.*' system/fvSolution -value"
    exitcode, out, err = exec_cmd(cmd)
    return float(out)

def get_epsilonRelaxationFactor():
    cmd = "source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                relaxationFactors.equations.epsilon system/fvSolution -value"
    exitcode, out, err = exec_cmd(cmd)
    return float(out)


def set_URelaxationFactor(value):
    cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                relaxationFactors.equations.U system/fvSolution -set {value}"
    exitcode, out, err = exec_cmd(cmd)
    URelaxationFactor = value
    print_and_log_info(f"***Setting {URelaxationFactor = }")
    return out


def set_kRelaxationFactor(value):
    cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                relaxationFactors.equations.k system/fvSolution -set {value}"
    exitcode, out, err = exec_cmd(cmd)
    kRelaxationFactor = value
    print_and_log_info(f"***Setting {kRelaxationFactor = }")
    return out


def set_epsilonStarRelaxationFactors(value):
    cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                relaxationFactors.equations.'epsilon.*' system/fvSolution -set {value}"
    exitcode, out, err = exec_cmd(cmd)
    epsilonStarRelaxationFactors = value
    print_and_log_info(f"***Setting {epsilonStarRelaxationFactors = }")
    return out


def set_epsilonRelaxationFactor(value):
    cmd = f"source /usr/lib/openfoam/openfoam2406/etc/bashrc && foamDictionary -entry \
                relaxationFactors.equations.epsilon system/fvSolution -set {value}"
    exitcode, out, err = exec_cmd(cmd)
    epsilonRelaxationFactors = value
    print_and_log_info(f"***Setting {epsilonRelaxationFactors = }")
    return out


def increase_epsilonStarRelaxationFactors_by0p05():
    actual_epsilonStars = get_epsilonStarRelaxationFactor()
    new_epsilonStars = actual_epsilonStars + 0.05
    set_epsilonStarRelaxationFactors(new_epsilonStars)
    print_and_log_info("+++Increasing epsilonStars")
    

def decrease_epsilonStarRelaxationFactors_by0p05():
    actual_epsilonStars = get_epsilonStarRelaxationFactor()
    new_epsilonStars = actual_epsilonStars - 0.05
    set_epsilonStarRelaxationFactors(new_epsilonStars)
    print_and_log_info("---Decreasing epsilonStars")
   
    
def increase_kRelaxationFactor_by0p05():
    actual_kRelaxationFactor = get_kRelaxationFactor()
    new_kRelaxationFactor = actual_kRelaxationFactor + 0.05
    set_kRelaxationFactor(new_kRelaxationFactor)
    print_and_log_info("+++Increasing kRelaxationFactor")
    

def decrease_kRelaxationFactor_by0p05():
    actual_kRelaxationFactor = get_kRelaxationFactor()
    new_kRelaxationFactor = actual_kRelaxationFactor - 0.05
    set_kRelaxationFactor(new_kRelaxationFactor)
    print_and_log_info("---Decreasing kRelaxationFactor")


def increase_URelaxationFactor_by0p05():
    actual_URelaxationFactor = get_URelaxationFactor()
    new_URelaxationFactor = actual_URelaxationFactor + 0.05
    set_URelaxationFactor(new_URelaxationFactor)
    print_and_log_info("+++Increasing URelaxationFactor")


def decrease_URelaxationFactor_by0p05():
    actual_URelaxationFactor = get_URelaxationFactor()
    new_URelaxationFactor = actual_URelaxationFactor - 0.05
    set_URelaxationFactor(new_URelaxationFactor)
    print_and_log_info("---Decreasing URelaxationFactor")
    
    
def increase_epsilonRelaxationFactor_by0p05():
    actual_epsilonRelaxationFactor = get_epsilonRelaxationFactor()
    new_epsilonRelaxationFactor = actual_epsilonRelaxationFactor + 0.05
    set_epsilonRelaxationFactor(new_epsilonRelaxationFactor)
    print_and_log_info("+++Increasing epsilonRelaxationFactor")


def decrease_epsilonRelaxationFactor_by0p05():
    actual_epsilonRelaxationFactor = get_epsilonRelaxationFactor()
    new_epsilonRelaxationFactor = actual_epsilonRelaxationFactor - 0.05
    set_epsilonRelaxationFactor(new_epsilonRelaxationFactor)
    print_and_log_info("---Decreasing epsilonRelaxationFactor")

def get_next_available_filename(base_filename):
    """
    Given a base filename (e.g., 'file.csv'), returns a filename that does not exist yet,
    using the pattern 'file.csv', 'file_1.csv', 'file_2.csv', etc.
    """
    if not os.path.exists(base_filename):
        return base_filename

    name, ext = os.path.splitext(base_filename)
    counter = 1
    while True:
        new_filename = f"{name}_{counter}{ext}"
        if not os.path.exists(new_filename):
            return new_filename
        counter += 1


###############################################################################
#####IF SCRIPT NEEDS TO BE INTERRUPTED, COMMENT NEXT SECTION UNTIL NEXT """####
#"""
print_and_log_info("")
print_and_log_info("******************** STARTING controlDict_automation.py ********************")
print_and_log_info("THIS PROGRAM MUST BE LAUNCHED BEFORE THE ACTUAL OPENFOAM SIMULATION,")
print_and_log_info("BECAUSE INITIAL VALUES ARE ALSO SET IN controlDict and fvSolution")
print_and_log_info("")
print_and_log_info("find logging data in controlDict_automation.log, data will be appended")
print_and_log_info("")

controlDict_automation_results_list = []
wait_command = 0.25

# WE ONLY WORK ON A COPY OF THE ORIGINAL controlDict and fvSolution WITH COMMENTS
copy_controlDict()
sleep(wait_command)
copy_fvSolution()
sleep(wait_command)
check_add_solverInfo()
endTime = get_endTime()
actual_timeStep = 0

###############################################################################
# we want to change maxCo with progressing time (NOT timeStep, actual time!)
# we multiply the old maxCo with a factor in a geometrical series
initial_deltaT = 1e-10
initial_maxCo = 0.0001
initial_writeInterval = 1e-4

minimum_nCorrectors = 3
maximum_nCorrectors = 5
initial_nCorrectors = minimum_nCorrectors # we start with 4 here, it's a tough one.

minimum_nOuterCorrectors = 15
maximum_nOuterCorrectors = 30
initial_nOuterCorrectors = minimum_nOuterCorrectors

initial_nOrthogonalCorrectors = 4
        # Non-orthogonality between 70 and 80: nNonOrthogonalCorrectors 4; SIMSCALE
        # Non-orthogonality between 60 and 70: nNonOrthogonalCorrectors 2;
        # Non-orthogonality between 40 and 60: nNonOrthogonalCorrectors 1;
initial_URelaxationFactor = 0.7
initial_kRelaxationFactor = 0.5
initial_epsilonRelaxationFactor = 0.3

###############################################################################
maximum_MaxCo = 0.5 # for first loop

maxCo = initial_maxCo # the first maxCo
num_steps_increase = 10
factor_geom_maxCo = m.exp(m.log(maximum_MaxCo / initial_maxCo, m.exp(1))\
                            / (num_steps_increase) )# we need a step for a geometrical series of maxCos
# print_and_log_info(f"***{step_increase_geom = }")

# we set an initial deltaT, look it up in original controlDict
set_deltaT(initial_deltaT)
sleep(wait_command)

# we set an initial maxCo and here also maxAlphaCo
set_maxCo(initial_maxCo)
# set_maxAlphaCo(initial_maxCo)
sleep(wait_command)

# we set an initial writeInterval
set_writeInterval(initial_writeInterval)
sleep(wait_command)

# we set an initial nCorrectors
set_nCorrectors(initial_nCorrectors) # here we will change between 3-5
sleep(wait_command)

# we set an initial nOuterCorrectors
set_nOuterCorrectors(initial_nOuterCorrectors) # here 15-20
sleep(wait_command)

# we set an initial nOuterCorrectors
set_nOrthogonalCorrectors(initial_nOrthogonalCorrectors) # here 1-2
sleep(wait_command)

# we set an initial URelaxationFactor
set_URelaxationFactor(initial_URelaxationFactor)
sleep(wait_command)

# we set an initial kRelaxationFactor
set_kRelaxationFactor(initial_kRelaxationFactor)
sleep(wait_command)

# we set initial epsilonRelaxationFactor
set_epsilonRelaxationFactor(initial_epsilonRelaxationFactor)

wait_before = 6 # 60 # 1200
# before continuing, pimpleFOAM must actually run to fill solverinfo.dat
print_and_log_info("")
print_and_log_info("############################################################################")
print_and_log_info(f"***Simulation should be started now, waiting {wait_before/60} minutes")
print_and_log_info("############################################################################")

# At the beginning of the simulation we want to increase maxCo until 0.5 in 
# defined geometrical intervals that are independent of the actual timeStep. 
# It will be very small, anyway.
# switching of fvSchemes is done with OpenFOAM onboard stuff.
wait_loop_1 = 900 # you have to be sure how fast your pimpleFoam (or whatever solver) 
          # iterations are
# in the old script we had 6 steps à 15min = 90min. now we have 10 --> 540s per step

# we want to keep track of the pConverged in both loops.
pConverged_list = []

sleep(wait_before) # we wait until completion of initial steps of simulation (potentialFoam ect.)
print_and_log_info("")
print_and_log_info("***Starting time triggered loop......")
currentDateAndTime = datetime.now()
currentTime = currentDateAndTime.strftime("%H:%M:%S")
print_and_log_info(f"Started @{currentDateAndTime}")
for i in range(num_steps_increase+1):
    # print("***",i)
    maxCo = initial_maxCo * factor_geom_maxCo**i
    actual_timeStep = get_actual_timeStep()
    actual_nCorrectors = get_nCorrectors()
    actual_pConverged = get_pConverged()
    print_and_log_info("")
    print_and_log_info(f"***Current {actual_timeStep = }")
    achieved_deltaT = get_achieved_deltaT()
    print_and_log_info(f"***Current {achieved_deltaT = }")
    set_maxCo(maxCo) 
    # set_maxAlphaCo(maxCo)
    if i == num_steps_increase:
        print_and_log_info("***Switching to timeStep triggering soon...")
    # if pConverged is False increase nCorrectors, unless it's already at maximum_nCorrectors (=5)
    # we started @3
    pConverged_list.append(actual_pConverged)
    if (actual_pConverged == False) and (actual_nCorrectors < maximum_nCorrectors): 
        increase_nCorrectors_by_1()
    sleep(wait_loop_1)
    
#"""    
#################IF SCRIPT INTERRUPTED WE NEED THE FOLLOWING###################
actual_timeStep = get_actual_timeStep()
minimum_nCorrectors = 3
maximum_nCorrectors = 5
initial_nCorrectors = minimum_nCorrectors # we start with 4 here, it's a tough one.

minimum_nOuterCorrectors = 15
maximum_nOuterCorrectors = 30
initial_nOuterCorrectors = minimum_nOuterCorrectors

controlDict_automation_results_list = []
pConverged_list = []
endTime = get_endTime()
#################EVERYTHING BELOW REMAINS UNCHANGED############################



###############################################################################
# Now things get interesting, we don't need lightning speed, so we wait a little at the end
# we have to think in intervals.

# we define two lists, one for times and one for maxCos that are changed when 
# timeStep  is in a time interval defined by these lists
# it is very important, that after completing the first above loop,
# the actualTimeStep is nowhere near timeStep_maxCo_list[0]

timeStep_maxCo_list = [3e-4,5e-4, 8e-4, 1e-3, 2e-3, 3e-3, 5e-3, 8e-3, 9e-3, 1e-2]
maxCo_list          = [0.6,  0.7,  0.8,  0.9, 0.95, 0.95, 0.96, 0.97, 0.98, 0.99]

if len(timeStep_maxCo_list) != len(maxCo_list): 
    print_and_log_warning("############################################################################")
    print_and_log_warning("Lists timeStep_maxCo_list and maxCo_list must have same length")
    print_and_log_warning("############################################################################")
    sleep(3600)
    
# we also want to vary the writeInterval. In the beginning we want to write more.
# Later we want to increase it, because maxCo will also increase.
# This is again in relation to the actual timeStep.
timeStep_writeInterval_list = [0,     1e-3,  0.01]
writeInterval_list         =  [1e-4,  0.001, 2e-3] 

# we want to keep track of the achieved_deltaT.
achieved_deltaT_list = []

wait_loop_2 = 60 # must be quicker than actual iterations in OpenFOAM
print_and_log_info("")
print_and_log_info("***Starting timeStep triggered loop......")
print_and_log_info("You may watch simulation parameters with controlDict_automation_plot_results.py")
print_and_log_info("from now on, as soon as sufficient data is written....")
currentDateAndTime = datetime.now()
currentTime = currentDateAndTime.strftime("%H:%M:%S")
print_and_log_info(f"Started @{currentDateAndTime}")
# determining the end of our automation, one of the two is larger..
if timeStep_writeInterval_list[-1] > timeStep_maxCo_list[-1]:
    automation_endTime = timeStep_writeInterval_list[-1]
else:
    automation_endTime = timeStep_maxCo_list[-1]
counter = 1
increased_nCorrectors_by_95perc_limit = False
# decrease_nCorrectors_factor = 1.1 # decrease when timeStep 10% larger
decrease_nCorrectors_factor = 1.01 # decrease when timeStep 1% larger
while actual_timeStep < endTime: # automation_endTime: # not necessary until endTime unless we want to record the data
    # we check all relevant actual values
    actual_timeStep = get_actual_timeStep()
    actual_maxCo = get_maxCo()
    actual_pConverged = get_pConverged()
    actual_UConverged = get_UConverged()
    actual_nOuterCorrectors = get_nOuterCorrectors()
    actual_nCorrectors = get_nCorrectors()
    actual_writeInterval = get_writeInterval()
    actual_URelaxationFactor = get_URelaxationFactor()
    actual_kRelaxationFactor = get_kRelaxationFactor()
    actual_epsilonRelaxationFactor = get_epsilonRelaxationFactor()
    
    print_and_log_info("")
    print_and_log_info(f"***Current {actual_timeStep = }")
    achieved_deltaT = get_achieved_deltaT()
    achieved_deltaT_list.append(achieved_deltaT)
    print_and_log_info(f"***Current {achieved_deltaT = }")
    
    ########################COLLECTING ALL RESULTS#############################
    result = [actual_timeStep,actual_maxCo,actual_pConverged,actual_UConverged,\
              actual_nOuterCorrectors,actual_nCorrectors,actual_writeInterval,\
              actual_URelaxationFactor,actual_kRelaxationFactor,\
              actual_epsilonRelaxationFactor, achieved_deltaT]
    controlDict_automation_results_list.append(result)
    ###########################################################################
    
    if len(achieved_deltaT_list)>2: # we report relative changes of achieved_deltaT exceeding 1%
        delta_deltaT = achieved_deltaT_list[-1]-achieved_deltaT_list[-2]
        achieved_relative_change = delta_deltaT / achieved_deltaT_list[-1]
        if achieved_relative_change>0.01: print_and_log_info("+++Achieved_deltaT increasing")
        elif achieved_relative_change<=-0.01: print_and_log_info("---Achieved_deltaT decreasing")
        else: print_and_log_info("oooAchieved_deltaT not changing")
    else:
        pass
    
    # we bisect the list, we need to find the index
    # of the time that is smaller than our actual_timeStep
    # we need to find the corresponding maxCo in maxCo_list
    idx = bisect.bisect_left(timeStep_maxCo_list, actual_timeStep) - 1 # we need the index to the left
    # print("###idx_maxCo",idx)                                            # but it could be < 0
    if idx >= 0:
        future_maxCo = maxCo_list[idx]
    else:
        future_maxCo = actual_maxCo
    
    # we set this future_maxCo but only if it is not already set
    # we increase nCorrectors also
    if (future_maxCo > actual_maxCo) and (actual_nCorrectors < maximum_nCorrectors):
        set_maxCo(future_maxCo)
        # set_maxAlphaCo(future_maxCo)
        print_and_log_info(f"###Setting {future_maxCo = }")
        print_and_log_info(f"###Increasing nCorrectors @{actual_timeStep = }")
        increase_nCorrectors_by_1()
    if (future_maxCo < actual_maxCo):#  and (actual_nCorrectors > minimum_nCorrectors): # in case we change to a lower value in the table, e.g. because
        set_maxCo(future_maxCo)     # of problematic convergencebehaviour
        # set_maxAlphaCo(future_maxCo)
        print_and_log_info(f"###Setting {future_maxCo = }")
        # print_and_log_info(f"###Decreasing nCorrectors @{actual_timeStep = } if possible")
        # decrease_nCorrectors_by_1()
    elif future_maxCo == actual_maxCo:
        print_and_log_info(f"###{future_maxCo = } already set")
    
    # we increased nCorrectors when we increased maxCo (switched off now) or 95% of timeStep_maxCo_list[idx]
    # we decrease it a bit later (when timeStep is 10% larger than last timeStep
    # in timeStep_maxCo_list)
    if (actual_timeStep > decrease_nCorrectors_factor * timeStep_maxCo_list[idx]) and \
       (actual_nCorrectors > minimum_nCorrectors) and idx>=0:
        print_and_log_info(f"###Decreasing nCorrectors @{actual_timeStep = }")
        decrease_nCorrectors_by_1()
        # increased_nCorrectors_by_95perc_limit = False
    
    # we need to find the corresponding writeInterval in writeInterval_list
    idx = bisect.bisect_left(timeStep_writeInterval_list, actual_timeStep) - 1  # same here
    # print("###idx_writeInterval",idx)
    if idx >= 0:
        future_writeInterval = writeInterval_list[idx]
    else:
        future_writeInterval = -1
    # we set this future_writeInterval but only if it is not already set
    if future_writeInterval > actual_writeInterval:
        set_writeInterval(future_writeInterval)
        print_and_log_info(f"###Setting {future_writeInterval = }")
    elif future_writeInterval < actual_writeInterval: # in case we set a smaller value later in the table
            set_writeInterval(future_writeInterval)
            print_and_log_info(f"###Setting {future_writeInterval = }")
    elif future_writeInterval == actual_writeInterval:
        print_and_log_info(f"###{future_writeInterval = } already set")
    
    # if pConverged is False increase nCorrectors, unless it's already at 5
    # we started @3
    # we also increase nOuterCorrectors by 5, but want to keep it between 15-30
    # also decrease epsilonRealxationFactor
    pConverged_list.append(actual_pConverged)
    if (actual_pConverged == False) and (actual_nCorrectors < maximum_nCorrectors) and \
        (actual_nOuterCorrectors <= maximum_nOuterCorrectors) and (actual_epsilonRelaxationFactor > 0.1): 
        increase_nCorrectors_by_1()
        increase_nOuterCorrectors_by5()
        #decrease_epsilonStarRelaxationFactors_by0p05()
        decrease_epsilonRelaxationFactor_by0p05()
    # decrease nCorrectors, nOuterCorrectors if last 30 pConverged were True.
    # increase epsilonRelaxationFactor
    if (last_n_true(pConverged_list, 30) == True) and (actual_nCorrectors > minimum_nCorrectors) and\
        (actual_nOuterCorrectors > minimum_nOuterCorrectors) and (actual_epsilonRelaxationFactor < 0.5):
        decrease_nCorrectors_by_1()
        decrease_nOuterCorrectors_by5()
        #increase_epsilonStarRelaxationFactors_by0p05()
        increase_epsilonRelaxationFactor_by0p05()
    write_csv_every = 2 # how often to write results to .csv, every nth iteration
    # we write our controlDict_automation_results_list to a .csv every 2 iterations
    if counter%write_csv_every==0: # was 5
        # Create DataFrame with column names
        df = pd.DataFrame(controlDict_automation_results_list, columns=['actual_timeStep','actual_maxCo','actual_pConverged', \
                                                            'actual_UConverged','actual_nOuterCorrectors','actual_nCorrectors',\
                                                            'actual_writeInterval','actual_URelaxationFactor','actual_kRelaxationFactor',
                                                            'actual_epsilonRelaxationFactor','achieved_deltaT'])
        # Write DataFrame to CSV with the index to next available name,
        # if we interrupt and restart we'll lose old data otherwise.
        # Thus, if script is interrupted, files have to be stitched together.
        # use cat file.csv file_1.csv file_2.csv > files.csv
        if counter == write_csv_every: # was 5, len = 4 (header is not counted!) means we started over or we just started, otherwise we already have a filename
            filename = "controlDict_automation_results.csv" # same as counter == 5
            if isfile(filename): # we interrupted script and started over, we only have to check for the first bec. 
                filename = get_next_available_filename("controlDict_automation_results.csv") # get_next_avail_filename finds the last
        try: # no idea why filename could be nonexistent from above lines
            print_and_log_info(f"***Writing results to {filename}") 
            df.to_csv(filename, index=True)
        except:
            print_and_log_error("###There seems to be an error with the variable 'filename'")
            filename = "controlDict_automation_results.csv" 
            if isfile(filename): 
                filename = get_next_available_filename("controlDict_automation_results.csv") 
            print_and_log_info(f"***Setting standard {filename = } and writing results")
            df.to_csv(filename, sep ='\t', index=True)
    counter += 1
    sleep(wait_loop_2)

###############################################################################    
print_and_log_info("\ncontrolDict automation is finished for now. Bye!")

  







