#!/bin/bash -e
echo "TEST FIRST"
PWD=`pwd`
HOME=$PWD
echo $HOME
export SCRAM_ARCH=el9_amd64_gcc12
source /cvmfs/cms.cern.ch/cmsset_default.sh
cmsrel CMSSW_15_0_5
cd $PWD/CMSSW_15_0_5
ls -lrth
eval `scramv1 runtime -sh`
export LD_LIBRARY_PATH=/cvmfs/cms.cern.ch/slc7_amd64_gcc900/external/lhapdf/6.3.0/lib:${LD_LIBRARY_PATH}

cd #PWD

echo "TEST DIR"
pwd
STEP_NUM=$1
cd ..
./fewzz -i input_z.txt -h histograms.txt -o txt -p . -s ${STEP_NUM} > screen.out
rm -rf CMSSW_15_0_5
~
