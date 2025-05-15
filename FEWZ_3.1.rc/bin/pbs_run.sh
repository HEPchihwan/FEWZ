#!/bin/bash -e

# Sets up and starts a run using the PBS system
# Merely a wrapper of local_run.sh to submit to PBS
# Usage: pbs_run.sh w/z <run_dir> <input_file> <histo_file> <output_file_extension> <pdf_dir> [ <which_sect> ]
#    or  pbs_run.sh w/z <run_dir> <input_file> <histo_file> <output_file_extension> <pdf_dir> [ <init_sect> <last_sect> <sectloop_step> ]
#  Note: <which_sect> is optional and for advanced user only
#        <which_sect> specifies the one sector that user want to submit to condor system
#        <init_sect> <last_sect> <sectloop_step> specifies the sectors desired to run through the loop:
#                                                FOR <sect_num> FROM <init_sect> TO <last_sect> STEP <sectloop_step>

pbsusage(){
echo "Usage: `basename $0` w/z <run_dir> <input_file> <histo_file> <output_file_extension> <pdf_dir>"
exit 1
}
[ $# -lt 6 ] && pbsusage

### PBS running time limit 
TIME_LIMIT="08:00:00"
### PBS cores per node (always request mppwidth as multiples of it)
CPN=24
### mpicc complier
MPI_CC=cc
### mpirun scheduler
MPI_RUN=aprun

BOSON=$1
INFILE=$3
OUTFILE=$5
HISTFILE=$4
RUNDIR=${2%/}
PDFDIR=${6%/}
### Turn the directory into relative directory just in case
RUNDIR=`python scripts/get_relpath.py $RUNDIR ./`
PDFDIR=`python scripts/get_relpath.py $PDFDIR ./`

### check first argument, to make sure supported, and set executable
if [ $BOSON = "z" ] || [ $BOSON = "w" ]; then
   EXEC=fewz$BOSON
else
   echo "Unrecognized argument; defaulting to neutral current."
   EXEC=fewzz
fi

### some necessary info and default setting if not given
SECTORS=`python scripts/get_sects.py $3 $1`
INIT_SECT=1
LAST_SECT=$SECTORS
SECT_STEP=1

### read in optional arguments if given
[ $# -ge 7 ] && INIT_SECT=$7
[ $# -eq 7 ] && LAST_SECT=$INIT_SECT
[ $# -ge 8 ] && LAST_SECT=$8
[ $# -ge 9 ] && SECT_STEP=$9

### check the optional input arguments
if [ $SECT_STEP -eq 0 ] || \
   [ $SECT_STEP -gt 0 -a $INIT_SECT -gt $LAST_SECT ] || \
   [ $SECT_STEP -lt 0 -a $LAST_SECT -gt $INIT_SECT ]; then
   exit 2
else
   if [ $SECT_STEP -gt 0 ]; then
      if [ $INIT_SECT -gt $SECTORS ] || [ $LAST_SECT -lt 1 ]; then
         exit 2
      fi
   else
      if [ $LAST_SECT -gt $SECTORS ] || [ $INIT_SECT -lt 1 ]; then
         exit 2
      fi
   fi
fi
[ $INIT_SECT -lt 1 ] && INIT_SECT=1
[ $INIT_SECT -gt $SECTORS ] && INIT_SECT=$SECTORS
[ $LAST_SECT -lt 1 ] && LAST_SECT=1
[ $LAST_SECT -gt $SECTORS ] && LAST_SECT=$SECTORS

### figure out the number of parallel jobs
NUM_PROC=$(($LAST_SECT-$INIT_SECT))
NUM_PROC=$(($NUM_PROC/$SECT_STEP))
NUM_PROC=$(($NUM_PROC+1))
if [ `python scripts/get_scalevar.py $INFILE` = "y" ] ; then
  NUM_PROC=$(($NUM_PROC*3))
  SCLVAR=1
else
  SCLVAR=0
fi

### the number of cores need to be multiples of 24
MPP_WID=$(($NUM_PROC-1))
MPP_WID=$(($MPP_WID/$CPN))
MPP_WID=$(($MPP_WID+1))
MPP_WID=$(($MPP_WID*$CPN))

### create sector running directory and set up the structure
### ps. last three arguments for the python script below are optional and leaving them out will always be correct
python scripts/create_parallel.py $BOSON $INFILE $RUNDIR $INIT_SECT $LAST_SECT $SECT_STEP
if ! [ -e $RUNDIR/$EXEC ] ; then
    cp $EXEC $RUNDIR
fi
if ! [ -e $RUNDIR/$HISTFILE ] ; then
    python scripts/get_bin_files.py $HISTFILE $RUNDIR
    if [ -d "$RUNDIR/${RUNDIR}0/pscale" ] || [ -d "$RUNDIR/${RUNDIR}0/mscale" ] ; then
        cat $RUNDIR/$HISTFILE | sed -e "s/'\.\.\//'..\/..\//g" > $RUNDIR/pm_$HISTFILE
    fi
fi
#if ! [ -e $RUNDIR/$INFILE ] ; then ### always copy input file, in case changed
cp $INFILE $RUNDIR
#fi

### prepare mpi wrapper for aprun
$MPI_CC scripts/fewz_mpiwrap.cc -o $RUNDIR/fewz_mpiwrap -lstdc++

echo "#!/bin/bash -l
#PBS -q regular
#PBS -l mppwidth=$MPP_WID
#PBS -l walltime=$TIME_LIMIT
#PBS -N $RUNDIR
#PBS -e \$PBS_JOBID.err
#PBS -o \$PBS_JOBID.out
#PBS -V
" > $RUNDIR/$RUNDIR.pbs

echo "export CUBACORES=0" >> $RUNDIR/$RUNDIR.pbs
echo "cd \$PBS_O_WORKDIR" >> $RUNDIR/$RUNDIR.pbs
#echo "./local_run.sh $1 $2 $3 $4 $5 $6 $MPP_WID $INIT_SECT $LAST_SECT $SECT_STEP" >> $RUNDIR/$RUNDIR.pbs
echo "$MPI_RUN -n $NUM_PROC ./fewz_mpiwrap -x $EXEC -d $RUNDIR -i $INFILE -h $HISTFILE -p $PDFDIR -o $OUTFILE -v $SCLVAR -b $INIT_SECT -e $LAST_SECT -s $SECT_STEP" \
 >> $RUNDIR/$RUNDIR.pbs

cd $RUNDIR
qsub $RUNDIR.pbs

echo "Run the following to post-process output files: finish.sh $RUNDIR <order>.$OUTFILE"
