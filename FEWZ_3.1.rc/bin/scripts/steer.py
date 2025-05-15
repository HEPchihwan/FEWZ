#!/usr/bin/env python
import os
import sys
import argparse
from shutil import copyfile

def main():
  usage = 'usage: %prog [options]'
  parser = argparse.ArgumentParser(usage)
  parser.add_argument('-b', '--boson',dest='boson',help='which boson type',default='z')
  parser.add_argument('-n','--name',dest='Outputname',help='working directory')
  parser.add_argument('-e', '--energy', dest='energy',help='collision energy',default=13000,type=float)
  parser.add_argument('-R','--RunS',dest='runS',help='using running scales or not', default=False, action='store')
  parser.add_argument('--muF',dest='muF',help='Factorization scale',default=91.1876)
  parser.add_argument('--muR',dest='muR',help='Renormalization scale',default=91.1876)
  parser.add_argument('-m','--mll-bins',dest='massbin',help='mass bins of mll in z boson case',nargs='+', default=[ ], action='store', type=float)
  parser.add_argument('-B','--BeamType',dest='BEAMType',help='BEAM type',default=1,type=int)
  parser.add_argument('--al',dest='alpha',help='Alpha QED for incoming photon',default=0.007297352568, type=float)
  parser.add_argument('--alEff',dest='alphaEff',help='Alpha QED effective',default=0.007756146746, type=float)
  parser.add_argument('-F','--FermiC',dest='FermiC',help='Fermi constant',default=1.166379, type=float)
  parser.add_argument('-l','--mLep',dest='mLepton',help='Lepton mass',default=1.05,type=float)
  parser.add_argument('-W','--mW',dest='massW',help='W boson mass',default=80.379,type=float)
  parser.add_argument('--wW',dest='wdW',help='width of W boson',default=2.141,type=float)
  parser.add_argument('-Z','--mZ',dest='massZ',help='Z boson mass',default=91.1876,type=float)
  parser.add_argument('--wZ',dest='wdZ',help='width of Z boson',default=2.4952,type=float)
  parser.add_argument('-t','--mTop',dest='massTop',help='Top mass',default=172.5,type=float)
  parser.add_argument('--mHiggs',dest='massHiggs',help='Higgs mass',default=125.0,type=float)
  parser.add_argument('--QCDOrder',dest='QCDOrder',help='QCD Order',default=0,type=int)
  parser.add_argument('--EWOrder',dest='EWOrder',help='EW Order',default=0,type=int)
  parser.add_argument('--Zpole', dest='Zpole',help='Z pole focus',default=1,type=int)
  parser.add_argument('--EWcontrol',dest='EWcontrol',help='EW control',default=0,type=int)
  parser.add_argument('--Aoff',dest='Aoff',help='Turn off photon',default=0,type=int)
  parser.add_argument('--mll-min',dest='mllmin',help='Lepton-pair invariant mass minimum',default=50,type=float)
  parser.add_argument('--mll-max',dest='mllmax',help='Lepton-pair invariant mass maximum',default=1000000,type=float)
  parser.add_argument('-p','--pdf',dest='pdf',help='pdf choice',default='NNPDF31_nnlo_as_0118_luxqed',type=str)

  args = parser.parse_args()
  
  name=args.Outputname
  boson=args.boson
  energy=args.energy
  runS=args.runS
  muF=args.muF
  muR=args.muR
  massbin=args.massbin
  beam=args.BEAMType
  alpha=args.alpha
  alphaEff=args.alphaEff
  FermiC=args.FermiC
  mLepton=args.mLepton
  massW=args.massW
  widthW=args.wdW
  massZ=args.massZ
  widthZ=args.wdZ
  massTop=args.massTop
  massHiggs=args.massHiggs
  QCDOrder=args.QCDOrder
  EWOrder=args.EWOrder
  mllmin=args.mllmin
  mllmax=args.mllmax
  Zpole=args.Zpole
  EWcontrol=args.EWcontrol
  Aoff=args.Aoff
  pdf=args.pdf

  if not (boson=='z' or boson=='w'):
    print 'only z or w is supported'
    sys.exit('Error!')
  if (boson=='z' and not os.path.isfile('./input_z.txt')) or (boson=='w' and not os.path.isfile('./input_w.txt')):
    print 'the boson type is not consistent with the provided input, please check!'
    sys.exit('Error!')

  if boson=='z':
    template_filein='./input_z.txt'
  if boson=='w':
    template_filein='./input_w.txt'

  copyfile(template_filein,'input_bk.txt')

  if boson=='z':
    os.system(r'sed -i "2s/14000/%s/g" %s' %(int(energy), 'input_z.txt'))
    os.system(r'sed -i "4s/91.1876/%s/g" %s' %(muF, 'input_z.txt'))
    os.system(r'sed -i "5s/91.1876/%s/g" %s' %(muR, 'input_z.txt'))
    os.system(r'sed -i "7s/ 1/ %s/g" %s' %(int(beam), 'input_z.txt'))
    os.system(r'sed -i "10s/0.007297352568/%s/g" %s' %(alpha, 'input_z.txt'))
    os.system(r'sed -i "11s/0.007756146746/%s/g" %s' %(alphaEff, 'input_z.txt'))
    os.system(r'sed -i "12s/1.16637/%s/g" %s' %(FermiC, 'input_z.txt'))
    os.system(r'sed -i "14s/1.05/%s/g" %s' %(mLepton, 'input_z.txt'))
    os.system(r'sed -i "15s/80.379/%s/g" %s' %(massW, 'input_z.txt'))
    os.system(r'sed -i "16s/2.141/%s/g" %s' %(widthW, 'input_z.txt'))
    os.system(r'sed -i "17s/91.18768/%s/g" %s' %(massZ, 'input_z.txt'))
    os.system(r'sed -i "18s/2.4952/%s/g" %s' %(widthZ, 'input_z.txt'))
    os.system(r'sed -i "19s/172.5/%s/g" %s' %(massTop, 'input_z.txt'))
    os.system(r'sed -i "20s/125/%s/g" %s' %(massHiggs, 'input_z.txt'))
    os.system(r'sed -i "44s/ 0/ %s/g" %s' %(int(QCDOrder), 'input_z.txt'))
    os.system(r'sed -i "45s/ 0/ %s/g" %s' %(int(EWOrder), 'input_z.txt'))
    os.system(r'sed -i "46s/ 1/ %s/g" %s' %(int(Zpole), 'input_z.txt'))
    os.system(r'sed -i "47s/ 0/ %s/g" %s' %(int(EWcontrol), 'input_z.txt'))
    os.system(r'sed -i "48s/ 0/ %s/g" %s' %(int(Aoff), 'input_z.txt'))
    os.system(r'sed -i "111s/MRST2004QED/ %s/g" %s' %(pdf, 'input_z.txt'))
  
    if not runS:
      os.system('./condor_prepare_cards.sh z %s input_z.txt histograms.txt _app .' %(name))
    if runS:
      if len(massbin)<2:
        print 'running scale mode is selected, please set the mass bin!'
        sys.exit('Error!')
      if os.path.exists('Running_scale_Dir'):
        os.rename('Running_scale_Dir','Running_scale_Dir_old')
      os.mkdir('Running_scale_Dir')
      for i in range(0,len(massbin)-1):
        sub_dir='mll_'+str(int(massbin[i]))+'-'+str(int(massbin[i+1]))+'-'
        os.mkdir('Running_scale_Dir/%s'%sub_dir)
        #os.system('cd Running_scale_Dir/%s'%(sub_dir))
        mass_center=0.5*(massbin[i]+massbin[i+1])
        if i==0:
          os.system(r'sed -i "4s/%s/%s/g" %s' %(muF,mass_center, 'input_z.txt'))
          os.system(r'sed -i "5s/%s/%s/g" %s' %(muR,mass_center, 'input_z.txt'))
          os.system(r'sed -i "50s/50/%s/g" %s' %(massbin[i], 'input_z.txt'))
          os.system(r'sed -i "51s/1000000/%s/g" %s' %(massbin[i+1], 'input_z.txt'))
        else:
          os.system(r'sed -i "4s/%s/%s/g" %s' %(0.5*(massbin[i-1]+massbin[i]),mass_center, 'input_z.txt'))
          os.system(r'sed -i "5s/%s/%s/g" %s' %(0.5*(massbin[i-1]+massbin[i]),mass_center, 'input_z.txt'))
          os.system(r'sed -i "50s/%s/%s/g" %s' %(massbin[i-1],massbin[i], 'input_z.txt'))
          os.system(r'sed -i "51s/%s/%s/g" %s' %(massbin[i],massbin[i+1], 'input_z.txt'))
        os.system('./condor_prepare_cards.sh z %s input_z.txt histograms.txt _app .' %(sub_dir))
      os.system('mv mll* Running_scale_Dir')
    os.system('mv input_bk.txt input_z.txt')


if __name__ == "__main__":
    sys.exit(main())
