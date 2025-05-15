cmsrel CMSSW_15_0_5
cd CMSSW_15_0_5/src
cmsenv
cd ..
# cms env set

wget http://www.hep.anl.gov/fpetriello/FEWZ_3.1.rc.tar.gz

tar -xf FEWZ_3.1.rc.tar.gz

cd FEWZ_3.1.rc 

vi makefile



LHAPDF = on
LHADIR = /cvmfs/cms.cern.ch/slc7_amd64_gcc900/external/lhapdf/6.3.0/lib 
