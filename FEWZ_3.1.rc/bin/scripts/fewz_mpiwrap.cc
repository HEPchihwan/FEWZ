#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <mpi.h>

int main(int argc, char *argv[]) {
  int numprocs, rank;
  MPI_Init(&argc, &argv);
  MPI_Comm_size(MPI_COMM_WORLD, &numprocs);
  MPI_Comm_rank(MPI_COMM_WORLD, &rank);
  char *exec, *rundir, *input, *histo, *pdfloc, *output;
  int sclvar, sectid, initsect, sectstep, lastsect;
  sclvar=0; //default for optional
  sectstep=1; // default for optional
  initsect=lastsect=-999; // negative means unassigned
  for(int k=1; k<argc; ++k) {
    if(((argv[k])[0])=='-') {
      if(!strcmp(argv[k],"-x")) { k++; exec=argv[k]; } // executable name
      else if(!strcmp(argv[k],"-d")) { k++; rundir=argv[k]; } // run directory
      else if(!strcmp(argv[k],"-i")) { k++; input=argv[k]; } // input file
      else if(!strcmp(argv[k],"-h")) { k++; histo=argv[k]; } // histogram file
      else if(!strcmp(argv[k],"-p")) { k++; pdfloc=argv[k]; } // pdf grid location
      else if(!strcmp(argv[k],"-o")) { k++; output=argv[k]; } // output file suffix
      else if(!strcmp(argv[k],"-v")) { k++; sclvar=atoi(argv[k]); } // scale variation: 0,1
      else if(!strcmp(argv[k],"-b")) { k++; initsect=atoi(argv[k]); } // initial sector
      else if(!strcmp(argv[k],"-s")) { k++; sectstep=atoi(argv[k]); } // sector step
      else if(!strcmp(argv[k],"-e")) { k++; lastsect=atoi(argv[k]); } // last sector
    }
  }
  int whichscale=0;
  sectid=rank+1;
  if ( initsect>=0 && lastsect>=initsect ) {
    int jobnum = (lastsect-initsect)/sectstep+1;
    if ( sclvar>0 ) {
      if (rank>=3*jobnum) return -999;
      else if ( rank>=2*jobnum ) { whichscale=-1; sectid=initsect+(rank-2*jobnum)*sectstep; }
      else if ( rank>=jobnum ) { whichscale=1; sectid=initsect+(rank-jobnum)*sectstep; }
      else { whichscale=0; sectid=initsect+rank*sectstep; }
    }
    else {
      if ( rank>=jobnum ) return -999;
      else { whichscale=0; sectid=initsect+rank*sectstep; }
    }
  }
  char cmd[1024];
  if (whichscale==0) {
    printf("Sector %d is running out of %d processes ...\n", sectid, numprocs);
    sprintf(cmd,"cd %s%d &&  ../%s -i ../%s -h ../%s -o %s -p ../../%s -s %d > screen.out", rundir, sectid-1, exec, input, histo, output, pdfloc, sectid-1);
  }
  else if (whichscale>0) {
    printf("Sector %d for plus scale variation is running out of %d processes ...\n", sectid, numprocs);
    sprintf(cmd,"cd %s%d/pscale &&  ../../%s -i ../../p_%s -h ../../pm_%s -o p_%s -p ../../../%s -l .. -s %d > p_screen.out",
                rundir, sectid-1, exec, input, histo, output, pdfloc, sectid-1);
  }
  else {
    printf("Sector %d for minus scale variation is running out of %d processes ...\n", sectid, numprocs);
    sprintf(cmd,"cd %s%d/mscale &&  ../../%s -i ../../m_%s -h ../../pm_%s -o m_%s -p ../../../%s -l .. -s %d > m_screen.out",
                rundir, sectid-1, exec, input, histo, output, pdfloc, sectid-1);
  }
  system(cmd);
  MPI_Finalize();
}
