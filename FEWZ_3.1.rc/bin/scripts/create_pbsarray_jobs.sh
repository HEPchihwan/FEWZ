"""
Produce condor submission file "job_desc"
Run "condor_submit job_desc" to submit
Used by "condor_run.sh"
Usage: python $0 z/w <outputdir> <inputfile> <histofile> <outputfile_extension> <pdfdir> [<jobdescfile> [<initsect> [<lastsect> <sectstep>]]]
Note: <outputdir> should be a directory name without a trailing '/' and a preceding path
      <pdfdir> should be a directory name or path without trailing '/'
"""

import sys
from defs import getsects
from defs import getscalevar

jobname = 'job_desc'
condor_out = 'condor_output.out'
condor_err = 'condor_error.err'
condor_log = 'condor_log.log'

try:
    if len(sys.argv) < 7:
        raise Exception

    else:
        boson = (sys.argv[1]).upper()
        if (boson == 'W'):
            fewzexec = 'fewzw'
        else:
            if (boson != 'Z'):
                print('Warning: unrecognized parameter; defaulting to neutral current\n')
            fewzexec = 'fewzz'
        outputdir = sys.argv[2]
        inputfile = sys.argv[3]
        sectors = getsects(sys.argv[3], boson)
        scalevars = getscalevar(sys.argv[3]) # see whether input file contain special scale variation instruction
        histofile = sys.argv[4]
        outputfile = sys.argv[5]
        pdfdir = sys.argv[6]
        sectornum = sectors
        if len(sys.argv) > 7:
            jobname = sys.argv[7]
        if len(sys.argv) > 8:
            initsect = int(sys.argv[8])
            if len(sys.argv) > 10:
               lastsect = int(sys.argv[9])
               sectstep = int(sys.argv[10])
            else:
               lastsect = initsect
               sectstep = 1
            sectornum = (lastsect-initsect)/sectstep+1
        else:
            initsect = 1
            lastsect = sectors
            sectstep = 1
        if len(sys.argv) > 8:
            sectorid = '$((%i*$PBS_ARRAYID+%i-1))' % (sectstep,initsect)
            psectorid = '$((%i*$PBS_ARRAYID-%i+%i-1))' % (sectstep,sectornum*sectstep,initsect)
            msectorid = '$((%i*$PBS_ARRAYID-%i+%i-1))' % (sectstep,2*sectornum*sectstep,initsect)
        else:
            sectorid = '$PBS_ARRAYID'
            psectorid = '$(($PBS_ARRAYID-%i))' % sectornum
            msectorid = '$(($PBS_ARRAYID-%i))' % (2*sectornum)

except Exception:
    print('Missing arguments.')
    raise

try:
    job_file = open(outputdir + '/' + jobname, 'w')

except IOError:
    print('Error creating job file.')
    raise

try:
    job_file.write('#!/bin/bash\n')
    job_file.write('#PBS -q regular\n')
    if not scalevars[2]:
        job_file.write('#PBS -t 0-%i\n' % (sectornum-1))
    else:
        job_file.write('#PBS -t 0-%i\n' % (3*sectornum-1))
    #job_file.write('#PBS -l walltime=08:00:00\n')
    job_file.write('#PBS -o ' + outputdir + '/$PBS_JOBID.out\n')
    job_file.write('#PBS -e ' + outputdir + '/$PBS_JOBID.err\n')
    job_file.write('\n')

    ### merely to store sector number for other python script to handle
    job_file.write('echo "\nQueue %i\n"\n\n' % sectors)

    if not scalevars[2]:
        job_file.write('cd $PBS_O_WORKDIR/' + outputdir + '/' + outputdir + sectorid + '\n')
        job_file.write('../' + fewzexec + ' -i ../' + inputfile + ' -h ../' + histofile \
                       + ' -o ' + outputfile + ' -p ../../' + pdfdir + ' -s ' + sectorid + '\n')
    else:
        job_file.write('if [ $(($PBS_ARRAYID)) -lt %i ] ; then\n' % sectornum )
        job_file.write('  cd $PBS_O_WORKDIR/' + outputdir + '/' + outputdir + sectorid + '\n')
        job_file.write('  ../' + fewzexec + ' -i ../' + inputfile + ' -h ../' + histofile \
                       + ' -o ' + outputfile + ' -p ../../' + pdfdir + ' -s ' + sectorid + '\n')
        # for scale variation plus
        job_file.write('elif [ $(($PBS_ARRAYID)) -lt %i ] ; then\n' % (2*sectornum) )
        job_file.write('  cd $PBS_O_WORKDIR/' + outputdir + '/' + outputdir + sectorid + '/pscale\n')
        job_file.write('  ../../' + fewzexec + ' -i ../../p_' + inputfile + ' -h ../../pm_' + histofile \
                       + ' -o p_' + outputfile + ' -p ../../../' + pdfdir + ' -l .. -s ' + psectorid + '\n')
        # for scale variation minus
        job_file.write('else\n')
        job_file.write('  cd $PBS_O_WORKDIR/' + outputdir + '/' + outputdir + sectorid + '/mscale\n')
        job_file.write('  ../../' + fewzexec + ' -i ../../m_' + inputfile + ' -h ../../pm_' + histofile \
                       + ' -o m_' + outputfile + ' -p ../../../' + pdfdir + ' -l .. -s ' + msectorid + '\n')
        job_file.write('fi\n')

    job_file.close()

except IOError:
    print('Error writing to job file.')
    raise
