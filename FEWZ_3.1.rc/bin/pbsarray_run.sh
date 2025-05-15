#!/bin/bash -e

### RECOMMENDED to use pbs_run.sh instead
### as pbsarray_run.sh is not fully tested

# Sets up and starts a run using the PBS system
# Usage: pbsarray_run.sh w/z <run_dir> <input_file> <histo_file> <output_file_extension> <pdf_dir> [ <which_sect> ]
#    or  pbsarray_run.sh w/z <run_dir> <input_file> <histo_file> <output_file_extension> <pdf_dir> [ <init_sect> <last_sect> <sectloop_step> ]
#  Note: <which_sect> is optional and for advanced user only
#        <which_sect> specifies the one sector that user want to submit to PBS system
#        <init_sect> <last_sect> <sectloop_step> specifies the sectors desired to run through the loop:
#                                                FOR <sect_num> FROM <init_sect> TO <last_sect> STEP <sectloop_step>

PBSusage(){
echo "Usage: `basename $0` w/z <run_dir> <input_file> <histo_file> <output_file_extension> <pdf_dir>"
exit 1
}
[ $# -lt 6 ] && PBSusage

BOSON=$1
INFILE=$3
OUTFILE=$5
HISTFILE=$4
RUNDIR=${2%/}
PDFDIR=${6%/}

### Turn the directory into relative directory just in case
RUNDIR=`python scripts/get_relpath.py $RUNDIR ./`
PDFDIR=`python scripts/get_relpath.py $PDFDIR ./`

### Check first argument, to make sure supported, and set executable
if [ $BOSON = "z" ] || [ $BOSON = "w" ]; then
   EXEC=fewz$BOSON
else
   echo "Unrecognized argument; defaulting to neutral current."
   EXEC=fewzz
fi

### Prepare the output directory structure and PBS submit file
python scripts/create_parallel.py $BOSON $INFILE $RUNDIR
if ! [ -e $RUNDIR/$EXEC ] ; then
   cp $EXEC $RUNDIR/
fi
#if ! [ -e $RUNDIR/$INFILE ] ; then ### always copy input file, in case changed
cp $INFILE $RUNDIR/
#fi
if ! [ -e $RUNDIR/$HISTFILE ] ; then
    python scripts/get_bin_files.py $HISTFILE $RUNDIR
    if [ -d "$RUNDIR/${RUNDIR}0/pscale" ] || [ -d "$RUNDIR/${RUNDIR}0/mscale" ] ; then
        cat $RUNDIR/$HISTFILE | sed -e "s/'\.\.\//'..\/..\//g" > $RUNDIR/pm_$HISTFILE
    fi
fi
python scripts/create_pbsarray_jobs.py $BOSON ${RUNDIR##*/} $INFILE $HISTFILE $OUTFILE $PDFDIR
cd $RUNDIR

### Now ready to submit PBS job
### Provide option to hack the PBS batch file if the user only want to submit for a few sectors
if [ $# -le 6 ] ; then
   ### submit all sectors at once
   qsub job_desc
else
   ### submit only job for one sector or sectors given by the loop "from `init_sect' to `last_sect' by `sectloop_step'"
   # default values of optional arguments if not given
   INIT_SECT=0
   LAST_SECT=0
   SECT_STEP=1
   # read in optional arguments if given
   # skip checking arguments to let PBS handle it (PBS wil quit if the sector doesn't exist)
   [ $# -ge 7 ] && INIT_SECT=$7
   [ $# -eq 7 ] && LAST_SECT=$INIT_SECT
   [ $# -ge 8 ] && LAST_SECT=$8
   [ $# -ge 9 ] && SECT_STEP=$9
   JOBFILE=job_part_1
   i=1
   while [ -f $JOBFILE ]; do i=$(($i+1)); JOBFILE=job_part_$i; done # don't overwrite existing job files
   cd ..
   python scripts/create_pbsarray_jobs.py $BOSON ${RUNDIR##*/} $INFILE $HISTFILE $OUTFILE $PDFDIR $JOBFILE $INIT_SECT $LAST_SECT $SECT_STEP
   cd $RUNDIR
   qsub $JOBFILE
fi

echo "Run the following to post-process output files: finish.sh $RUNDIR <order>.$OUTFILE"

