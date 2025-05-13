# Tools-For-OpenFOAM-Automation
## snappyHexMesh_Optimizer.py

As all Foamers know, OpenFOAM is top-tier CFD software. Nevertheless, 'ease-of-use' or even 'convenience' are words that normally do not come to mind when we speak about OpenFOAM. There are tools like pyFOAM that may achieve similar control over openFOAM, however, I wanted to do this on my own.
First of all, a good mesh is the most important input to OF. My personal mesher of choice is snappyHexMesh. There has been a lot said about sHM, I won't add to that. My experiences with it are mixed, but there is no open-source mesher that can handle multiregion or AMI better. So I have to deal with it. The problems I have with it are mostly with big meshes (5M+ cells) and the waiting time. Even with MPI and 32 cores, a waiting time of 1h+ is too long if you can't be sure your resulting mesh works. And that's the main problem with sHM: you never really can be with AMI because SHM is kind of stochastic (maybe there's a better word for it, IDK) regarding its results. What do I mean by that? Even with IDENTICAL snappyHexMeshDict, a second meshing run does not lead to exactly the same result. There are variations in the mesh, they are only 'kind of' the same. They even have different checkMesh results, that should tell you something. Normally, when meshing a new geometry, I'd start with some default parameters, look at checkMesh results and also look at the snappyHexMEsh.log. Unfortunately, checkMesh can't do it all. The most important value (in my opinion at leat) checkMesh cannot deliver us is the layerPercentage (not an official OF-name). These values, if you layer more than one patch, can only be found in sHM.log. So, therefore, one of the goals of the presented software was to aggregate important meshQualityParameters in one place. 
Currently this script can only do variations of input parameters for snappyHexMeshDict, repeatedly mesh in parallel, write logs, evaluate some results in these logs and aggregate the info for the user. Ideally, the user will then pick one of these meshes for his simulation. In that sense, it is not an optimizer. Attempts to do automated optimizations where not really fruitful, so at the moment we just kind of brute-force a better mesh with variations of important parameters and repeated meshing.

How to use this script:
First of all, you need a working snappyHexMesh case, meaning you have a (nearly) watertight .stl in triSurface, a correct surfaceFeatureExtractDict, a correct blockMeshDict, decomposeParDict and finally a working snappyHexMeshDict. This is the workflow we also use in the exec_meshing() function inside this script. After meshing, the mesh is reconstructed and processor/ folders are cleaned. Of course, if you need createBaffles or mergeOrSplitBaffles or other operations on your mesh, these can easily be included. 
An important feature of this script is, that some of the logging is done in /var/tmp/. My advice for you is to mount it as tmpfs in order to have it in RAM. It will reduce the write cycles on your SSD or NVME.
After you completed setting up the meshing, you are ready to enter data in to the script. Currently, the following parameters can be varied for automated mesh generation:

-) NUMBER_OPTIMIZATIONS: the total number of loops, then number of meshes is +1 because the original intention was to let the script optimize mesh parameters itself. This has proven to be very difficult. So at the moment, only a few parameters are varied and also this script can't to any separate meshing. Separate meshing is a popular tecnique ith snappyHexMEsh where you mesh your snapped mesh first until satisfied and THEN do the layering on this mesh. I only discovered this weeks ago, it has been a good alternative so far (although some other annoying stuff has to be done to get this mesh running in OpenFOAM, but I won't go into that.)

-) interval_maxNonOrtho: set the interval in which maxNonOrtho is varied. The following variations of maxNonOrtho can be performed: do equal steps along the given interval, do quasi-equal steps in the interval with slight randomization on the value, total uniform randomness of the value in the interval. You can comment and uncomment the appropriate lines in the code.

-) interval_maxBoundarySkewness: set the interval in which maxBoundarySkewness is varied. Same applies like above on how this parameter can be varied.

-) interval_layerFeatureAngle: set the interval in which layerFeatureAngle is varied. Same applies like above on how this parameter can be varied.


The following input parameters are also included but not varied currently in the script (this is also mentioned in the script) only their maximum value is used and written to snappyHexMeshDict:

interval_maxInternalSkewness

interval_relaxedMaxNonOrtho

interval_relaxedMaxBoundarySkewness

interval_relaxedMaxInternalSkewness


When you have entered your desired limits in these intervals, you should look at how these values are treated (equal linear steps, quasi-equal steps or uniform randomness). Just comment and uncomment the appropriate lines in the loop. You may also want to change the direction in which the intervals are stepped in case of equal and quasi-equal steps.
After that you may run the script, it should be placed in your OpenFoam case directory. After the zero mesh (Mesh_0) it will tell you an estimated meshing time, especially with big meshes this is important.

The following files are written by the script:
A folder is created for each mesh in the constant directory of your OpenFoam case with the following structure, let's assume a NUMBER_OPTIMIZATIONS = 3:

Mesh_0/ Mesh_1/ Mesh_2/ Mesh_3/

Inside each of these folders you'll find (assume we look into Mesh_0):

0/    cellVolume       faceZone       p

aspectRatio      cellVolumeRatio  k              polyMesh/

cellAspectRatio  cellZone         minPyrVolume   skewness

cellDeterminant  checkMesh_0.log  minTetVolume   snappyHexMesh_0.log

cellRegion       epsilon          nonOrthoAngle  U

cellShapes       faceWeight       nut            wallDistance


Executing paraFoam will let you look at all these data and generated meshes. All logs can be looked into for a deeper comparison.
A graph is presented in the end with the most important parameters for each mesh (again according to their number 0, 1, 2, 3, ...):
![Figure_1](https://github.com/user-attachments/assets/7741f9f3-f047-4021-abaf-adf32228e9bc)

maxNonOrtho_set, maxNonOrtho_result
maxSkewness_set, maxSkewness_result
layerFeatureAngle_set, layerPercentage_result (only the first entry from the first patch in the table is scanned)
num_cells_result

You will be able to choose the mesh you like best, very often this will be a compromise with snappyHexMesh. Even if you don't choose a mesh for your simulation, you'll know a lot more about how sHM is treating your .stl.
You can narrow one or more parameter interval(s) for additional loops, modify other parameters in sHM etc. This script is especially convenient, if you absolutely don't know where to start with your meshing.
Now, this is always work in progress. At the moment, the capabilities of this script are quite limited. However, it can be adapted to your needs in no time. The main advantage at the moment is that we can do some meshing during the night. 










