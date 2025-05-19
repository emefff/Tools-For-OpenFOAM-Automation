#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Apr 30 16:30:40 2025

@author: mario
"""

from bokeh.plotting import figure, show, output_file
from bokeh.io import export_png
from bokeh.models import DataRange1d
import os
import glob
import re
import time
from subprocess import run, Popen
# importing pandas
import pandas as pd

output_file('controlDict_automation_results.html', title = 'controlDict_automation_results')   

def exec_cmd(cmd):
    """
    Execute the external command and get its exitcode, stdout and stderr.
    """
    # args = shlex.split(cmd) # Popen would need a split.
    # run expects cmd NOT args like Popen
    proc = run(cmd, shell=True, executable="/bin/bash", capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def get_present_folder():
    # we have to determine pwd
    cmd = "pwd" 
    exitcode, out, err = exec_cmd(cmd)
    folder = out.replace("\n", "")
    return folder


def numerical_key(filename):
    # Extract the number part using regex
    match = re.search(r'_(\d+)\.csv$', filename)
    return int(match.group(1)) if match else -1


def find_csv_files(directory='.'):
    """
    Finds all files matching 'controlDict_automation_results.csv', 'controlDict_automation_results_1.csv', 'controlDict_automation_results_2.csv', etc. in the specified directory.

    Args:
        directory (str): The directory to search in (default is current directory).

    Returns:
        list: List of matching filenames (with path).
    """
    # Pattern matches 'controlDict_automation_results.csv', 'controlDict_automation_results_1.csv', 'controlDict_automation_results_2.csv', etc.
    pattern = os.path.join(directory, 'controlDict_automation_results*.csv')
    files = glob.glob(pattern)
    # Filter further to match only 'file.csv', 'file_1.csv', 'file_2.csv', etc.
    # Exclude files like 'fileABC.csv'
    regex = re.compile(r'controlDict_automation_results(_\d+)?\.csv$')
    matching_files = [f for f in files if regex.search(os.path.basename(f))]
    return matching_files


OF_folder = get_present_folder()
print(f"{OF_folder = }\n")
#file = "controlDict_automation_results.csv"

list_files = sorted(find_csv_files(OF_folder), key=numerical_key)
print(f"{list_files = }\n")

p = False
count = 1
last_n_points = 1000
print(f"Showing last {last_n_points} points of controlDict_automation_results\n")

# a few parameters need to be scaled
scale_achieved_deltaT = int(1E6)
scale_nOuterCorrectors = 10
scale_writeInterval = 1000

while(True):
    for i,file in enumerate(list_files): # we need data from all files, one after the other
        if i==0:
            df_results = pd.read_csv(file, sep=',', skiprows=0)
            #df_results = df_results.rename(columns={'Unnamed: 0': 'index'})
            df_results.drop(columns=df_results.columns[0], axis=1,  inplace=True)
            # print("§§§§§", df_results)
            # print("§§§§§", df_results.keys())
            # print("§§§", i, file, len(df_results))
        else:
            df = pd.read_csv(file, sep=',', skiprows=0)
            df.drop(columns=df.columns[0], axis=1,  inplace=True)
            # print("%%%%%", df)
            # print("%%%%%", df.keys())
            # print("%%%", i, file, len(df))
            df_results = pd.concat([df_results, df])

    # print("xxx",len(df_results))

    print(df_results.keys())
    # print(f"\n{df_results.columns = }\n")
    # print(f"\n{df_results['actual_kRelaxationFactor'] = }\n")
    # print(df_results)
    if not(p):
        
        p = figure(width=800, height=600, title="controlDict_automation_results", y_axis_type="log", \
                   x_range=DataRange1d(only_visible=True), y_range=DataRange1d(only_visible=True))

    line1 = p.line(df_results['actual_timeStep'].tail(last_n_points), \
                   scale_achieved_deltaT*df_results['achieved_deltaT'].abs().tail(last_n_points), \
                   legend_label=f"deltaT * {scale_achieved_deltaT}",line_width=2,color='red',line_dash='solid')
    line2 = p.line(df_results['actual_timeStep'].tail(last_n_points), \
                   df_results['actual_maxCo'].abs().tail(last_n_points), legend_label="maxCo",\
                   line_width=2,color='green',line_dash='solid')
    line3 = p.line(df_results['actual_timeStep'].tail(last_n_points), \
                   df_results['actual_nCorrectors'].abs().tail(last_n_points), legend_label="nCorrectors",\
                   line_width=2,color='goldenrod',line_dash='solid')
    line4 = p.line(df_results['actual_timeStep'].tail(last_n_points), \
                   1/scale_nOuterCorrectors*df_results['actual_nOuterCorrectors'].abs().tail(last_n_points), \
                   legend_label=f"nOuterCorrectors / {scale_nOuterCorrectors}",line_width=2,color='blue',line_dash='solid')
    line5 = p.line(df_results['actual_timeStep'].tail(last_n_points), \
                   scale_writeInterval*df_results['actual_writeInterval'].abs().tail(last_n_points), \
                   legend_label=f"writeInterval * {scale_writeInterval}",line_width=2,color='cyan',line_dash='dashed')
    line6 = p.line(df_results['actual_timeStep'].tail(last_n_points), \
                   df_results['actual_URelaxationFactor'].abs().tail(last_n_points), \
                   legend_label="URelaxationFactor",line_width=2,color='firebrick',line_dash='dashed')
    line7 = p.line(df_results['actual_timeStep'].tail(last_n_points), \
                   df_results['actual_kRelaxationFactor'].abs().tail(last_n_points), \
                   legend_label="kRelaxationFactor",line_width=2,color='greenyellow',line_dash='dashed')
    line8 = p.line(df_results['actual_timeStep'].tail(last_n_points), \
                   df_results['actual_epsilonRelaxationFactor'].abs().tail(last_n_points), \
                   legend_label="epsilonRelaxationFactor",line_width=2,color='hotpink',line_dash='dashed')
    p.legend.location = "bottom_left"
    # p.legend.orientation = "horizontal"
    p.legend.background_fill_alpha = 0.5
    p.legend.click_policy = 'hide'
    show(p)

    export_png(p, width=1600, height=1200, filename=f"controlDict_automation_{count}.png")
    print(f"Screenshot nr. {count} written...")

    time.sleep(600)
    count += 1
