#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Feb  8 10:47:22 2025

@author: emefff
"""

import matplotlib.pyplot as plt
from bokeh.plotting import figure, show, output_file
from bokeh.io import export_png
from bokeh.models import DataRange1d
from subprocess import run, Popen
import os
import re
import time
# importing pandas
import pandas as pd

OF_folder = '/media/drive2/FRANCIS_PUMP4/'

output_file('solverInfo.html', title = 'solverInfo_residuals')

####################################################################


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
    new_string = re.sub(r'[^0-9.]', '', string)
    print("%%%", new_string)
    return new_string


def exec_cmd(cmd):
    """
    Execute the external command and get its exitcode, stdout and stderr.
    """
    # args = shlex.split(cmd) # Popen would need a split.
    # run expects cmd NOT args like Popen
    proc = run(cmd, shell=True, executable="/bin/bash", capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def find_latest_folder():
    # we have to find the latest folder in solverInfo folder, cd into solverInfo and back
    # cmd = "cd postProcessing/solverInfo && ls -d */ | sed 's#/##' | sort -g | tail -n 1 && cd ../../"
    cmd = "cd postProcessing/solverInfo && bash ../../latest_folder_bash.sh"
    exitcode, out, err = exec_cmd(cmd)
    latest_folder = remove_chars(out)
    latest_folder = out.replace("\n", "")
    return latest_folder


def find_time_folders():
    #cmd = "ls -l postProcessing/solverInfo | grep ^d"
    # cmd = "find postProcessing/solverInfo/ -type d"
    # exitcode, out, err = exec_cmd(cmd)
    # list_time_folders = out
    # return list_time_folders
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
    return folders


# copy solverInfo.dat to a new file and remove # in it
def copy_and_remove_special_chars(src_file_path, dst_file_path, special_char='#'):
    try:
        # Read the original file
        with open(src_file_path, 'r') as src_file:
            content = src_file.read()

        # Remove special characters
        cleaned_content = content.replace(special_char, '')

        # Write to a new file
        with open(dst_file_path, 'w') as dst_file:
            dst_file.write(cleaned_content)

        print(f"File copied and special character '{special_char}' removed successfully.")
    except FileNotFoundError:
        print(f"Source file {src_file_path} not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

# get a list of the time folders in postProcessing/solverInfo
list_time_folders_str = find_time_folders()
list_time_folders_float = []
for string in list_time_folders_str:
    floaty = float(string)
    list_time_folders_float.append(floaty)
list_time_folders_float = sorted(list_time_folders_float)
    

print(f"{list_time_folders_float = }\n")

# make a list of filenames + path to work through later, we want to concat data from all files in /solverInfo
# still, the problem is, if the user restarts @same timeStep twice, the second file gets a name like solverInfo_{time}.dat
# the first solverInfo.dat is kept. At the moment we only look for the first file
list_files = [OF_folder+"postProcessing/solverInfo/"+str(time)+"/solverInfo.dat" for time in list_time_folders_float]
print(f"{list_files = }\n")

p = False
count = 1
last_n_points = 1000
print(f"Showing last {last_n_points} points of solverInfo\n")

while(True):
    for i,file in enumerate(list_files): # we need data from all folders, one after the other
        if i==0:
            dst_file_path = f"/var/tmp/solverInfo_copy_{i}.dat"
            copy_and_remove_special_chars(file, dst_file_path)
            df_solver = pd.read_csv(dst_file_path, sep=r'\s+', skiprows=1)
            #print("§§§", i, file, len(df_solver))
            #pd.set_option('display.max_columns', None)
            #print(df_solver.tail())
            #print("****************************")
        else:
            dst_file_path = f"/var/tmp/solverInfo_copy_{i}.dat"
            copy_and_remove_special_chars(file, dst_file_path)
            df = pd.read_csv(dst_file_path, sep=r'\s+', skiprows=1)
            #print("%%%", i, file, len(df))
            df_solver = pd.concat([df_solver, df])

    #print("xxx",len(df_solver))
    print(f"\n{df_solver.columns = }\n")
    if not(p):
        p = figure(width=800, height=600, title="solverInfo_residuals", y_axis_type="log",\
                    x_range=DataRange1d(only_visible=True),y_range=DataRange1d(only_visible=True))

    line1 = p.line(df_solver['Time'].tail(last_n_points), df_solver['Uz_initial'].abs().tail(last_n_points), legend_label="Uz_initial",line_width=2,color='green',line_dash='dashed')
    line2 = p.line(df_solver['Time'].tail(last_n_points), df_solver['Uz_final'].abs().tail(last_n_points), legend_label='Uz_final',line_width=2,color='green',line_dash='solid')
    line3 = p.line(df_solver['Time'].tail(last_n_points), df_solver['p_initial'].abs().tail(last_n_points), legend_label='p_initial',line_width=2,color='blue',line_dash='dashed')
    line4 = p.line(df_solver['Time'].tail(last_n_points), df_solver['p_final'].abs().tail(last_n_points), legend_label='p_final',line_width=2,color='blue',line_dash='solid')
    line5 = p.line(df_solver['Time'].tail(last_n_points), df_solver['Uz_iters'].abs().tail(last_n_points), legend_label='Uz_iters',line_width=2,color='firebrick',line_dash='dashed')
    line6 = p.line(df_solver['Time'].tail(last_n_points), df_solver['p_iters'].abs().tail(last_n_points), legend_label='p_iters',line_width=2,color='firebrick',line_dash='solid')
    p.legend.location = "bottom_left"
    # p.legend.orientation = "horizontal"
    p.legend.background_fill_alpha = 0.5
    p.legend.click_policy = 'hide'
    show(p)
    #pd.set_option('display.max_columns', None)
    #print(df_solver.tail())
    export_png(p, width=1600, height=1200, filename=f"solverInfo_{count}.png")
    print(f"Screenshot nr. {count} written...")

    time.sleep(600)
    count += 1
