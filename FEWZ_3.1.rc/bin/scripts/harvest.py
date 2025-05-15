#!/usr/bin/env python
import os
import sys
import argparse
from shutil import copyfile

def main():
  usage = 'usage: %prog [options]'
  parser = argparse.ArgumentParser(usage)
  parser.add_argument('-s','--submit',dest='submit',help='submit condor jobs',default=False, action='store')
  parser.add_argument('-m','--merge',dest='merge',help='merge different sectors',default=False, action='store')
  parser.add_argument('-o','--order',dest='order',help='order of calculation',type=str)

  args = parser.parse_args()

  submit=args.submit
  merge=args.merge
  order=args.order

  working_dir=os.getcwd()

  if submit and merge:
    print 'These two modes can not run simultaneously, pelase run submit/merge/combine in separate steps!'
    sys.exit('Error!')

  if submit:
    if not os.path.exists('Running_scale_Dir'):
       print 'Working directory is not set, please Run steer.py firstly!'
       sys.exit('Error!')
    sub_dir=[]
    for root, dirs, files in os.walk('Running_scale_Dir'):
      for name in dirs:
        if os.path.join(root,name).count("/")==2:continue
        sub_dir.append(os.path.join(root,name))

    for ijob in range(len(sub_dir)):
      os.chdir("%s"%sub_dir[ijob])
      os.system("condor_submit job_desc")
      os.chdir(working_dir)

  if merge:
    sub_dir=[]
    if order=='NNLO': suffix='NNLO'
    if order=='LO': suffix='LO'
    for root, dirs, files in os.walk('Running_scale_Dir'):
      for name in dirs:
        if os.path.join(root,name).count("/")==2:continue
        sub_dir.append(name)

    bin_low=100000.
    bin_high=0.
    for ijob in range(len(sub_dir)):
      os.system("./finish.sh Running_scale_Dir/%s/ %s.txt"%(sub_dir[ijob],suffix))
      os.system("sed -i 's/undefined/1e-10/g' %s.txt"%(suffix))
      os.system("mv %s.txt %s%s.txt"%(suffix,suffix,str(ijob)))
      if bin_low>float(sub_dir[ijob].split("_")[1].split("-")[0]):
        bin_low=float(sub_dir[ijob].split("_")[1].split("-")[0])
      if bin_high<float(sub_dir[ijob].split("_")[1].split("-")[1]):
        bin_high=float(sub_dir[ijob].split("_")[1].split("-")[1])

    if len(sub_dir)==1:
      os.system("mv %s0.txt final.txt"%(suffix))
    if len(sub_dir)==2:
      os.system("python scripts/combine.py %s0.txt + %s1.txt final.txt"%(suffix,suffix))
    if len(sub_dir)>2:
      os.system("python scripts/combine.py %s0.txt + %s1.txt final_temp.txt"%(suffix,suffix))
      for ijob in range(2,len(sub_dir)):
        os.system("python scripts/combine.py final_temp.txt + %s%s.txt final.txt"%(suffix,str(ijob)))
        if ijob<len(sub_dir)-1:
          os.system("mv final.txt final_temp.txt")
      os.system("rm final_temp.txt")

    os.system("sed -i '4c  Factorization scale  = Running' final.txt")
    os.system("sed -i '4s/^/ /g' final.txt")
    os.system("sed -i '5c  Renormalization scale  = Running' final.txt")
    os.system("sed -i '5s/^/ /g' final.txt")
    os.system("sed -i '20c  Strong coupling  = Running' final.txt")
    os.system("sed -i '20s/^/ /g' final.txt")
    os.system("sed -i '25c  Lepton-pair invariant mass minimum = %s' final.txt"%(str(bin_low)))
    os.system("sed -i '25s/^/ /g' final.txt")
    os.system("sed -i '26c  Lepton-pair invariant mass maximum = %s' final.txt"%(str(bin_high)))
    os.system("sed -i '26s/^/ /g' final.txt")

if __name__ == "__main__":
  sys.exit(main())
