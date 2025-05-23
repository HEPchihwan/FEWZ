import SCRAM
from SCRAM.BuildSystem.TemplateStash import TemplateStash
from SCRAM.BuildSystem import get_safename
from os import environ, symlink, listdir, makedirs, unlink, stat
from os.path import normpath, exists, join, isdir, islink, dirname, basename, splitext
from os.path import sep as dirsep
from shutil import move
import importlib
import re


class BuildRules(object):

    def __init__(self, toolmanager):
        self.make_dir = join(toolmanager.area.archdir(), "MakeData")
        self.project_bf = None
        self.cache = {"toolcache": toolmanager}
        self.cache["SUPPORTED_ALPAKA_BACKENDS"] = {"cuda": "CudaAsync", "serial": "SerialSync", "tbb": "TbbAsync", "rocm": "ROCmAsync"}
        for x in ["ToolVariables", "Compilers", "ProductTypes", "SourceExtensions", "CacheData",
                  "RemakeDir", "SymLinks", "SupportedPlugins", "BuildFileMap"]:
            self.cache[x] = {}
        self.cache["BuildFile"] = "BuildFile.xml"
        self.data = {}
        for e in ["SCRAM_PROJECTNAME", "LOCALTOP", "SCRAM_ARCH", "SCRAM_INTwork", "SCRAM_CONFIGDIR",
                  "THISDIR", "SCRAM_SOURCEDIR"]:
            if e not in environ or len(environ[e].replace(" ", "")) == 0:
                SCRAM.scramerror('Environment variable "%s" does not exist.' % e)
        self.cache["SourceExtensions"] = {
            "fortran": {"f": 1, "f77": 1, "F": 1, "F77": 1},
            "cxx": {"cc": 1, "cpp": 1, "cxx": 1, "C": 1},
            "c": {"c": 1},
            "cuda": {"cu": 1},
            "rocm": {"hip.cc": 1},
            "alpaka_device": {"dev.cc": 1},
        }
        environ["LOCALTOP"] = normpath(environ["LOCALTOP"])
        self.init = False
        self.core = None
        return

    def process(self, name, data, dir_cache):
        if data.branch["suffix"]:
            return
        self.data = {}
        self.cache["directory_cache"] = dir_cache
        if data.branch["safepath"] == environ['SCRAM_CONFIGDIR']:
            data.branch["safepath"] = environ['SCRAM_SOURCEDIR']
            data.branch["path"] = environ['SCRAM_SOURCEDIR']
        ofile = join(self.make_dir, "DirCache", data.branch["safepath"] + ".mk")
        remake = True
        if data.branch["path"] == environ['SCRAM_SOURCEDIR']:
            ofile = join(self.make_dir, environ['SCRAM_SOURCEDIR'] + ".mk")
            remake = False
        self.data["DirCache"] = {}
        self.data["makefile"] = ofile
        self.data["data"] = data
        self.data["FH"] = open(ofile, "w")
        self.data["context"] = TemplateStash()
        self.data["context"].stash(data.branch)
        self.data["swap_prod_mkfile"] = False
        self.data["context"].pushstash()
        self.set("allow_empty_file_list",False)
        self.core = data.branch["context"]
        self.data["product"] = {}
        if not self.init:
            self.initTemplate_PROJECT()
            self.init = True
        ret = self.runTemplate("%s_template" % name)
        self.data["context"].popstash()
        self.data["FH"].close()
        if stat(ofile).st_size == 0:
            unlink(ofile)
        elif self.data["swap_prod_mkfile"]:
            nfile = ofile.replace(self.cache["toolcache"].area.admindir(), environ["SCRAM_TMP"])
            move(ofile, nfile)
            ofile = nfile
        if remake:
            self.addRemakeDirectory(dirname(ofile))
        return ret

    def getExtension(self, file_type):
        return self.cache["SourceExtensions"][file_type].keys() if file_type in self.cache["SourceExtensions"] else []

    def hasAnySources(self, files):
        for file_type in self.cache["SourceExtensions"]:
            if self.hasFileTypes(files, file_type):
                return True
        return False

    def hasFileTypes(self, files, file_type):
        if not file_type in self.cache["SourceExtensions"]: return False
        for f in files:
            for ext in self.cache["SourceExtensions"][file_type]:
                if f.endswith("."+ext): return True
        return False

    def addRemakeDirectory(self, dir):
        self.cache["RemakeDir"][dir] = 1

    def filehandle(self):
        return self.data["FH"]

    def core(self):
        return self.data['core']

    def swapMakefile(self, swap_flag=True):
        self.data["swap_prod_mkfile"] = swap_flag

    def startRules(self):
        mk_dir = join(self.make_dir, "DirCache")
        if not exists(mk_dir):
            makedirs(mk_dir, exist_ok=True)
        mk_dir = mk_dir.replace(self.cache["toolcache"].area.admindir(), environ["SCRAM_TMP"])
        if not exists(mk_dir):
            makedirs(mk_dir, exist_ok=True)
        return

    def endRules(self):
        for mk_dir in self.cache["RemakeDir"]:
            with open(mk_dir + ".mk", "w"):
                pass
            SCRAM.run_command("cd %s; find . -name \"*.mk\" -type f | xargs -n 2000 cat >> %s.mk" % (mk_dir, mk_dir))
        if 'ReleaseArea' not in self.cache:
            return
        arch = environ['SCRAM_ARCH']
        ext_arch = join(environ['LOCALTOP'], 'external', arch)
        if not exists(ext_arch):
            SCRAM.run_command("%s/SCRAM/linkexternal.py --arch %s" %
                              (join(environ['LOCALTOP'], environ['SCRAM_CONFIGDIR']), arch))
            makedirs(ext_arch, exist_ok=True)

        if not self.cache['ReleaseArea']:
            env = self.get('environment')
            relobj = join(env['RELEASETOP'], 'objs', arch)
            locobj = join(ext_arch, 'objs-base')
            if isdir(relobj) and (not islink(locobj)):
                symlink(relobj, locobj)
        proj_name = self.cache['ProjectName']
        pj = self.getTool(proj_name)
        if pj:
            relobj = join(pj["%s_BASE" % proj_name.upper()], "objs", arch)
            locobj = join(ext_arch, "objs-full")
            if isdir(relobj) and (not islink(locobj)):
                symlink(relobj, locobj)

#################################################

    def get(self, key, default=""):
        return self.data["context"].get(key, default)

    def set(self, key, value):
        return self.data["context"].set(key, value)

    def stash(self):
        return self.data["context"]

    def pushstash(self):
        return self.data["context"].pushstash()

    def popstash(self):
        return self.data["context"].popstash()

    def getSafeSubPaths(self, path):
        if path in self.cache["directory_cache"]:
            return " ".join([get_safename(d) for d in self.cache["directory_cache"][path][1:]])
        return ""

#################################################

    def hasData(self, data, key):
        return key in data

    def getTool(self, tool):
        if self.cache['toolcache'].hastool(tool):
            return self.cache['toolcache'].gettool(tool)
        return {}

    def getTools(self):
        return self.cache['toolcache'].loadtools()

    def isDependentOnTool(self, tool):
        data = self.core.get_data('USE')
        if data and type(data) is list:
            for dep in data:
                if tool == dep.lower():
                    return True
        return False

    def isToolAvailable(self, tool):
        return self.cache['toolcache'].hastool(tool.lower())

#############################################

    def setRootReflex(self, tool):
        self.cache['RootRflx'] = tool

    def getRootReflex(self):
        return self.cache['RootRflx']

    def addSymLinks(self, dir):
        if dir:
            self.cache['SymLinks'][dir] = 1
        return

    def removeSymLinks(self, dir):
        if dir in self.cache['SymLinks']:
            del self.cache['SymLinks'][dir]
        return

    def getSymLinks(self):
        return self.cache['SymLinks'].keys()

    def createSymLinks(self):
        fh = self.filehandle()
        fh.write("")
        symMk = """CONFIGDEPS += $(COMMON_WORKINGDIR)/cache/project_links
$(COMMON_WORKINGDIR)/cache/project_links: FORCE_TARGET
\t@echo '>> Creating project symlinks';\\
\t[ -d $(@D) ] ||  $(CMD_mkdir) -p $(@D) &&\\
"""
        fh.write(symMk)
        for d in self.getSymLinks():
            fh.write("\t%s/SCRAM/createSymLinks.sh %s &&\\\n" % (self.cache['ProjectConfig'], d))
        fh.write("\tif [ ! -f $@ ] ; then touch $@; fi\n\n")
        return

##############################################

    def processTemplate(self, name, *args):
        return self.doTheTemplateProcessing("process", name, *args)

    def includeTemplate(self, name, *args):
        self.doTheTemplateProcessing("include", name, *args)

    def doTheTemplateProcessing(self, type, name, *args):
        plugin = self.getProjectPlugin()
        ret = None
        if plugin is not None:
            if type == "include":
                self.pushstash()
            templateFunction = getattr(plugin, name, None)
            if templateFunction is not None:
                ret = templateFunction(*args)
            if type == "include":
                self.popstash()
        return ret

    def getProjectPlugin(self):
        return self.cache['ProjectPlugin']

    def getFiles(self, dir):
        data = {}
        for item in listdir(dir):
            if item.startswith('.'):
                continue
            item = join(dir, item)
            data[item] = isdir(item)
        return data

    def readDir(self, dir, type=0, depth=1, data=None):
        if data is None:
            data = []
        if dir not in self.data["DirCache"]:
            self.data["DirCache"][dir] = self.getFiles(dir)
        xdir = self.data["DirCache"][dir]
        for sdir in xdir:
            dirflag = xdir[sdir]
            if depth > 1 and dirflag:
                self.readDir(sdir, type, depth - 1, data)
            if (type == 0) or ((type == 1) and dirflag):
                data.append(sdir)
            elif (type == 2) and not dirflag:
                data.append(sdir)
        return data

    def runToolFunction(self, func, tool, *args):
        if tool == "self":
            tool = environ['SCRAM_PROJECTNAME']
        funcRef = getattr(self, "%s_%s" % (func, tool.lower()), None)
        if funcRef is not None:
            return funcRef(*args)
        return ""

    def runTemplate(self, func, *args):
        plugin = self.getProjectPlugin()
        if plugin is not None:
            funcRef = getattr(plugin, func, None)
            if funcRef is not None:
                return funcRef(*args)
        funcRef = getattr(self, func, None)
        if funcRef is not None:
            return funcRef(*args)
        SCRAM.printerror('****ERROR:Unable to run %s. Template/Function not found.' % func)
        return False

    def unsupportedProductType(self):
        path = self.get('path')
        type = self.get('type')
        SCRAM.printerror('WARNING: Product type "%s" not supported yet from "%s".' % (type, path))
        if path.endswith("/src"):
            SCRAM.printerror('WARNING: You are only suppose to build a single library from "%s".' % path)
        return

    def getSubdirIfEnabled(self):
        val = self.core.get_flag_value("ADD_SUBDIR")
        if val not in ['yes', '1']:
            return ""
        path = self.get('path')
        subdirs = " ".join(sorted(self.readDir(path, 1, 1)))
        if not subdirs:
            SCRAM.printerror("ERROR: You requested to compile files under '%s' sub-directories but none found."
                             " Please cleanup BuildFile and remove 'ADD_SUBDIR' flag." % path)
        return subdirs

#######################################
# Various functions
#######################################

    def isPublictype(self):
        plugin = self.getProjectPlugin()
        if plugin is not None:
            return plugin.isPublic(self.get('class'))
        return (self.get("template") == "library")

    def isLibSymLoadChecking(self):
        flag = self.core.get_flag_value("NO_LIB_CHECKING")
        if flag in ["yes", "1"]:
            return "no"
        return ""

    def getLocalBuildFile(self):
        bf = self.get("buildfile_path")
        if bf: return bf
        path = self.get("path")
        if path in self.cache["BuildFileMap"]:
            return self.cache["BuildFileMap"][path]
        bn = self.cache["BuildFile"]
        bf = join(path, bn)
        if not exists(bf):
            if self.isPublictype():
                bf = join(dirname(path), bn)
        if not exists(bf):
            bf = ""
        self.cache["BuildFileMap"][path] = bf
        return bf

    def hasPythonscripts(self):
        path = self.get("path")
        pythonprod = {}
        flags = self.core.get_flags()
        if "PYTHONPRODUCT" in flags:
            bfile = self.getLocalBuildFile()
            xfiles = []
            xdirs = []
            for p in flags["PYTHONPRODUCT"]:
                files = p.split(",")
                count = len(files)
                if count == 1:
                    files.append("")
                    count += 1
                if count == 0:
                    SCRAM.printerror("ERROR: Invalid use of 'PYTHONPRODUCT' flag in '%s' file. Please correct it." %
                                     bfile)
                else:
                    des = join(self.cache["PythonProductStore"], files[-1])
                    des = des.rstrip("/")
                    files.pop()
                    for fs in files:
                        for f in fs.split(" "):
                            f = normpath(join(path, f))
                            if not exists(f):
                                SCRAM.printerror("ERROR: No such file '%s' for 'PYTHONPRODUCT' flag in "
                                                 "'%s' file. Please correct it." % (f, bfile))
                            else:
                                pythonprod[f] = 1
                                xfiles.append(f)
                                xdirs.append(des)
            self.set("xpythonfiles", xfiles)
            self.set("xpythondirs", xdirs)
        scripts = 0
        if not self.cache["SymLinkPython"]:
            for f in self.readDir(path, 2, -1):
                if f in pythonprod:
                    continue
                if f.endswith(".py"):
                    scripts = 1
                    break
        else:
            scripts = 1
        self.set("hasscripts", scripts)
        return scripts

    def symlinkPythonDirectory(self, value):
        self.cache['SymLinkPython'] = value

    def isSymlinkPythonDirectory(self):
        return self.cache['SymLinkPython']

    def setLibPath(self):
        path = self.get('path')
        if path[:4] == 'src/' and path[-4:] == 'src/':
            self.set('libpath', 1)
        else:
            self.set('libpath', 0)
        return

    def autoGenerateClassesH(self, value):
        self.cache['AutoGenerateClassesHeader'] = value

    def isAutoGenerateClassesH(self):
        return self.cache['AutoGenerateClassesHeader']

    def addCacheData(self, name, value=""):
        self.cache['CacheData'][name] = value

    def getCacheData(self, name):
        if name in self.cache['CacheData']:
            return self.cache['CacheData'][name]
        return ""

    def updateEnvVarMK(self):
        mkfile = join(self.make_dir, "variables.mk")
        ref = open(mkfile, "w")
        ref.write("############## All Tools Variables ################\n")
        ref.write("TOOLS_OVERRIDABLE_FLAGS:=\nALL_LIB_TYPES:=\n")
        for var in self.addAllVariables():
            ref.write("%s\n" % var)
        env = self.get('environment')
        ref.write("############## All SCRAM ENV variables ################\n")
        for key in env:
            if key.startswith('SCRAMV1_'):
                continue
            if key in ["SCRAM_BUILDVERBOSE", "SCRAM_NOPLUGINREFRESH", "SCRAM_NOSYMCHECK", "SCRAM_NOLOADCHECK",
                       "SCRAM", "SCRAM_TOOL_HOME", "SCRAM_VERSION", "SCRAM_LOOKUPDB", "SCRAM_SYMLINKS",
                       "SCRAM_TEST_RUNNER_PREFIX", "SCRAM_NOEDM_CHECKS", "LOCALTOP"]:
                continue
            if not self.shouldAddToolVariables(key):
                continue
            ref.write("%s:=%s\n" % (key, env[key]))
        ref.write("################ ALL SCRAM Stores #######################\n")
        ref.write("ALL_PRODUCT_STORES:=\n")
        arch = environ["SCRAM_ARCH"]
        for store in self.core.get_data("PRODUCTSTORE", True):
            storename = None
            if ('type' in store) and (store['type'] == 'arch'):
                if ('swap' in store) and (store['swap'] == 'true'):
                    storename = join(store['name'], arch)
                else:
                    storename = join(arch, store['name'])
            else:
                storename = store['name']
            sname = store['name'].upper().replace("/", "_")
            ref.write("SCRAMSTORENAME_%s:=%s\n" % (sname, storename))
            ref.write("ALL_PRODUCT_STORES+=$(SCRAMSTORENAME_%s)\n" % sname)
        ref.write("ALPAKA_SELECTED_BACKENDS:=%s\n" % self.cache['SELECTED_ALPAKA_BACKENDS'])
        for bend in self.cache['SELECTED_ALPAKA_BACKENDS'].split(' '):
          if not bend: continue
          ref.write("ALPAKA_BACKEND_SUFFIX_%s:=%s\n" % (bend,self.cache["SUPPORTED_ALPAKA_BACKENDS"][bend]))
        ref.close()
        return

    def addAllVariables(self):
        keys = []
        skipTools = {}
        cuda = self.isToolAvailable("cuda")
        if cuda:
            keys.append("CUDA_TYPE_COMPILER        := cuda")
            keys.append("CUDASRC_FILES_SUFFIXES := %s" % " ".join(self.getSourceExtensions("cuda")))
        else:
            keys.append("CUDASRC_FILES_SUFFIXES := ")
        rocm = self.isToolAvailable("rocm")
        if rocm:
            keys.append("ROCM_TYPE_COMPILER        := rocm")
            keys.append("ROCMSRC_FILES_SUFFIXES    := %s" % " ".join(self.getSourceExtensions("rocm")))
        else:
            keys.append("ROCMSRC_FILES_SUFFIXES := ")

        keys.append("CXXSRC_FILES_SUFFIXES     := %s" % " ".join(self.getSourceExtensions("cxx")))
        keys.append("CSRC_FILES_SUFFIXES       := %s" % " ".join(self.getSourceExtensions("c")))
        keys.append("FORTRANSRC_FILES_SUFFIXES := %s" % " ".join(self.getSourceExtensions("fortran")))
        keys.append("SRC_FILES_SUFFIXES        := $(CXXSRC_FILES_SUFFIXES) $(CSRC_FILES_SUFFIXES) "
                    "$(FORTRANSRC_FILES_SUFFIXES) $(CUDASRC_FILES_SUFFIXES)")
        keys.append("SCRAM_ADMIN_DIR           := .SCRAM/$(SCRAM_ARCH)")
        keys.append("SCRAM_TOOLS_DIR           := $(SCRAM_ADMIN_DIR)/tools")
        keys.append("SCRAM_SCRIPT_EXT          := .py")
        self.dumpCompilersFlags(keys)
        if self.isMultipleCompilerSupport():
            keys.append("SCRAM_MULTIPLE_COMPILERS := yes")
            keys.append("SCRAM_DEFAULT_COMPILER    := %s" % self.getCompiler(""))
            keys.append("SCRAM_COMPILER            := $(SCRAM_DEFAULT_COMPILER)")
            keys.append("ifdef COMPILER")
            keys.append("SCRAM_COMPILER            := $(COMPILER)")
            keys.append("endif")
            for f in self.getCompilerTypes():
                keys.append("%s_TYPE_COMPILER := %s" % (f, self.getCompiler(f)))
            keys.append("ifndef SCRAM_IGNORE_MISSING_COMPILERS")
            for f in self.getCompilerTypes():
                c = self.getCompiler(f)
                keys.append("$(if $(wildcard $(SCRAM_TOOLS_DIR)/$(SCRAM_COMPILER)-$({0}_TYPE_COMPILER)),,"
                            "$(info ****WARNING: You have selected $(SCRAM_COMPILER) as compiler but there "
                            "is no $(SCRAM_COMPILER)-$({0}_TYPE_COMPILER) tool setup. Default compiler "
                            "$(SCRAM_DEFAULT_COMPILER)-$({0}_TYPE_COMPILER) will be used to "
                            "compile {0} files))".format(f))
            keys.append("endif")
            defCompiler = self.getCompiler("")
            for f in self.getCompilerTypes():
                c = "%s-%s" % (defCompiler, self.getCompiler(f))
                if self.isToolAvailable(c):
                    self.addVariables(c, keys, False, True)
                skipTools[c] = 1
            self.addVirtualCompilers(keys)
        selfbase = "%s_BASE" % environ['SCRAM_PROJECTNAME']
        self.shouldAddToolVariables(selfbase)
        self.addVariables("self", keys, True)
        skipTools['self'] = 1
        for t in self.getTools():
            if t not in skipTools:
                self.addVariables(t, keys)
        return keys

    def addVariables(self, tool, keys, force=False, skipCompilerCheck=False):
        type = "global"
        basevar = "%s_BASE" % tool.upper()
        basevar = basevar.replace("-", "_")
        tools = self.getTools()
        if 'VARIABLES' not in tools[tool]:
            return
        if type not in self.cache['ToolVariables']:
            self.cache['ToolVariables'][type] = {}
        if basevar in tools[tool]['VARIABLES']:
            basedir = tools[tool][basevar]
            if tool == environ['SCRAM_PROJECTNAME'].lower():
                keys.append("%s_FULL_RELEASE:=%s" % (basevar, basedir))
            else:
                keys.append("%s:=%s" % (basevar, basedir))
            self.cache['ToolVariables'][type][basevar] = 1
        ctool = tool
        ctool = '-'.join(tool.split('-')[:-1])
        toolPrefix = ""
        if self.isMultipleCompilerSupport() and (not skipCompilerCheck) and ('SCRAM_COMPILER' in tools[tool]):
            type = tool
            toolPrefix = "%s_" % ctool
            keys.append("ifeq ($(strip $(SCRAM_COMPILER)),%s)" % ctool)
        elif skipCompilerCheck:
            toolPrefix = "%s_" % ctool
        xkeys = []
        for v in tools[tool]['VARIABLES']:
            if v in ["INCLUDE", "LIBDIR", "BINDIR"]:
                continue
            if (v == basevar) or (v not in tools[tool]):
                continue
            if force or self.shouldAddToolVariables(v, type):
                val = tools[tool][v]
                if v.startswith("BUILDENV_"):
                    val = "export %s:=%s" % (v[9:], val)
                else:
                    if toolPrefix:
                        xkeys.append("%s%s:=%s" % (toolPrefix, v, val))
                    val = "%s:=%s" % (v, val)
                keys.append(val)
        if type == tool:
            keys.append("endif")
        keys += xkeys

    def shouldAddToolVariables(self, var, type="global"):
        if type not in self.cache["ToolVariables"]:
            self.cache["ToolVariables"][type] = {}
        if var in self.cache["ToolVariables"][type]:
            return False
        self.cache["ToolVariables"][type][var] = 1
        return True

    def dumpCompilersFlags(self, keys):
        allFlagsHash = {}
        for flag in self.cache["DefaultCompilerFlags"]:
            allFlagsHash[flag] = 1
        for toolname in self.getCompilerTypes():
            compilers = self.getCompilers(toolname)
            for compiler in compilers:
                ctool = self.getTool(compiler)
                if 'FLAGS' not in ctool:
                    continue
                for flag in ctool['FLAGS']:
                    if flag.startswith("SCRAM_") or flag.startswith("REM_") or flag in ["SHAREDSUFFIX", "CCCOMPILER"]:
                        continue
                    allFlagsHash[flag] = 1
        allFlags = ""
        for flag in sorted(allFlagsHash.keys()):
            allFlags += "%s " % flag
            for type in ["", "REM_"]:
                for var in ["", "LIBRARY_", "TEST_", "BINARY_", "EDM_", "LCGDICT_", "ROOTDICT_", "PRECOMPILE_",
                            "DEV_", "RELEASE_"]:
                    keys.append("%s%s%s:=" % (type, var, flag))
        keys.append("ALL_COMPILER_FLAGS := %s" % allFlags)

    def fixData(self, data, type, bf, section="non-export"):
        ndata = []
        if not isinstance(data, list):
            return ndata
        if not len(data):
            return ndata
        if section:
            section = "export"
        udata = {}
        if type == "INCLUDE":
            ldir = dirname(bf)
            ltop = self.cache["LocalTop"]
            for d in [j for i in data for j in i]:
                x = d.strip()
                if x.startswith(dirsep):
                    x = join(ltop, ldir, x)
                x = normpath(x)
                if x not in udata:
                    udata[x] = 1
                    ndata.append(x)
                else:
                    SCRAM.printerror('***WARNING: Multiple usage of "%s". Please cleanup "include" in "%s" '
                                     'section of "%s"' % (d, section, bf))
        elif type == "USE":
            for u in [j for i in data for j in i]:
                x = u.strip()
                lx = x.lower()
                if lx in self.cache["InvalidUses"]:
                    SCRAM.printerror('***WARNING: Invalid direct dependency on tool "%s". Please cleanup "%s"' %
                                     (lx, bf))
                if not self.isToolAvailable(lx):
                    lx = x
                if x not in udata:
                    udata[lx] = 1
                    ndata.append(lx)
                else:
                    SCRAM.printerror('***WARNING: Multiple usage of "%s". Please cleanup "use" in "%s" '
                                     'section of "%s"' % (lx, section, bf))
        elif type == "LIB":
            for l in [j for i in data for j in i]:
                x = l.strip()
                if x == "1":
                    x = self.get("safename")
                if x not in udata:
                    udata[x] = 1
                    ndata.append(x)
                else:
                    SCRAM.printerror('***WARNING: Multiple usage of "%s". Please cleanup "lib" in "%s" '
                                     'section of "%s"' % (l, section, bf))
        return ndata

    def fixProductName(self, name):
        if dirsep in name:
            xname = basename(name)
            SCRAM.printerror('WARNING: Product name should not have "%s" in it. '
                             'Setting %s=>%s' % (dirsep, name, xname))
            name = xname
        return name

    def getGenReflexPath(self):
        for t in ["ROOTRFLX", "ROOTCORE"]:
            tb = "%s_BASE" % t
            if tb in self.cache["ToolVariables"]["global"]:
                return "$(%s)/bin/genreflex" % tb
        return ""

    def getRootClingPath(self):
        for t in ["ROOTRFLX", "ROOTCORE"]:
            tb = "%s_BASE" % t
            if tb in self.cache["ToolVariables"]["global"]:
                return "$(%s)/bin/rootcling" % tb
        return ""

#######################################
# Product Types Dir/Maps
#######################################

    def allProductDirs(self):
        return list(self.cache['ProductTypes'].keys())

    def addProductDirMap(self, type, reg, dir, index=100):
        type = type.lower()
        if (not type) or (not reg) or (not dir):
            return
        if type not in self.cache['ProductTypes']:
            self.cache['ProductTypes'][type] = {'DirMap': {}}
        if index not in self.cache['ProductTypes'][type]['DirMap']:
            self.cache['ProductTypes'][type]['DirMap'][index] = {}
        self.cache['ProductTypes'][type]['DirMap'][index][reg] = dir
        return

    def resetProductDirMap(self, type):
        type = type.lower()
        if type in self.cache['ProductTypes']:
            del self.cache['ProductTypes'][type]

    def getProductStore(self, type="", path=""):
        if not type:
            type = self.get('type')
        if not path:
            path = self.get('path')
        if type in self.cache['ProductTypes']:
            for idx in sorted(self.cache['ProductTypes'][type]['DirMap'].keys()):
                for reg in self.cache['ProductTypes'][type]['DirMap'][idx]:
                    if re.match(reg, path):
                        return self.cache['ProductTypes'][type]['DirMap'][idx][reg]
        else:
            SCRAM.printerror("****ERROR: Product store '%s' not available. Please fix the build template "
                             "loaded for '%s'" % (type, path))
        return ""

#######################################
# BuildFile and compilers
#######################################

    def setBuildFileName(self, bf):
        if not bf:
            return
        self.cache['BuildFile'] = bf

    def getBuildFileName(self):
        return self.cache['BuildFile']

    def isMultipleCompilerSupport(self):
        return self.cache['MultipleCompilerSupport']

    def setCompiler(self, type, compiler):
        self.cache["%sCompiler" % type.upper()] = compiler.lower()

    def getCompiler(self, type):
        type = "%sCompiler" % type.upper()
        if type in self.cache:
            return self.cache[type]
        return ""

    def getCompilers(self, type):
        type = type.upper()
        if type in self.cache['Compilers']:
            return self.cache['Compilers'][type]
        defCompiler = self.getCompiler(type)
        self.cache['Compilers'][type] = {}
        if self.isMultipleCompilerSupport():
            defCompiler = '-%s' % defCompiler
            tools = self.getTools()
            for t in tools:
                if 'SCRAM_COMPILER' in tools[t] and t.endswith(defCompiler):
                    self.cache['Compilers'][type][t] = t.replace(defCompiler, '')
        else:
            self.cache['Compilers'][type][defCompiler] = ""
        return self.cache['Compilers'][type]

    def getCompilerTypes(self):
        return self.cache['CompilerTypes']

    def addVirtualCompilers(self, keys):
        for t in self.getCompilerTypes():
            c = self.getCompiler(t)
            keys.append('ALL_TOOLS  += %s' % c)
            keys.append("{0}_EX_USE    := $(if $(strip $(wildcard $(LOCALTOP)/$(SCRAM_TOOLS_DIR)/"
                        "$(SCRAM_COMPILER)-{0})),$(SCRAM_COMPILER)-{0},$(SCRAM_DEFAULT_COMPILER)-{0})".format(c))
        return

    def isReleaseArea(self):
        return self.cache['ReleaseArea']

###########################################
# Plugin Support
###########################################

    def addPluginSupport(self, type, flag, refresh, reg="", dir='SCRAMSTORENAME_MODULE',
                         cache='.cache', name='$name="${name}.reg"', ncopylib=""):
        type = type.lower()
        flag = flag.upper()
        if (not type) or (not flag) or (not refresh):
            return
        err = False
        for t in self.cache['SupportedPlugins'].keys():
            if t == type:
                continue
            c = self.cache['SupportedPlugins'][t]['Cache']
            r = self.cache['SupportedPlugins'][t]['Refresh']
            if r == refresh:
                SCRAM.printerror("****ERROR: Can not have two plugins type ('%s' and '%s') using the same plugin "
                                 "refresh command '%s" % (t, type, r))
                err = True
            if c == cache:
                SCRAM.printerror("****ERROR: Can not have two plugins type ('%s' and '%s') using the same plugin "
                                 "cache file '%s" % (t, type, c))
                err = True
        if err:
            return
        self.cache['SupportedPlugins'][type] = {}
        self.cache['SupportedPlugins'][type]['Refresh'] = refresh
        self.cache['SupportedPlugins'][type]['Cache'] = cache
        self.cache['SupportedPlugins'][type]['DefaultDirName'] = reg
        self.cache['SupportedPlugins'][type]['Dir'] = dir
        self.cache['SupportedPlugins'][type]['Name'] = name
        self.cache['SupportedPlugins'][type]['NoSharedLibCopy'] = ncopylib
        self.cache['SupportedPlugins'][type]['DirMap'] = {}
        self.cache['SupportedPlugins'][type]['Flag'] = flag.split(":")

    def addPluginDirMap(self, type, reg, dir, index=100):
        type = type.lower()
        if (not type) or (not reg) or (not dir):
            return
        if type not in self.cache['SupportedPlugins']:
            SCRAM.printerror("****ERROR: Not a valid plugin type '%s'. Available plugin "
                             "types are: %s" % (type, ", ".join(self.getSupportedPlugins())))
        else:
            if index not in self.cache['SupportedPlugins'][type]['DirMap']:
                self.cache['SupportedPlugins'][type]['DirMap'][index] = {}
            self.cache['SupportedPlugins'][type]['DirMap'][index][reg] = dir
        return

    def removePluginSupport(self, type):
        type = type.lower()
        if (not type) or (type not in self.cache['SupportedPlugins']):
            return
        del self.cache['SupportedPlugins'][type]
        if self.cache['DefaultPluginType'] == type:
            self.cache['DefaultPluginType'] = ""
        return

    def getPluginProductDirs(self, type):
        type = type.lower()
        dirs = {}
        if (not type) or (type not in self.cache['SupportedPlugins']):
            return dirs
        dirs[self.cache['SupportedPlugins'][type]['Dir']] = 1
        for idx in self.cache['SupportedPlugins'][type]['DirMap']:
            for x in self.cache['SupportedPlugins'][type]['DirMap'][idx]:
                dirs[self.cache['SupportedPlugins'][type]['DirMap'][idx][x]] = 1
        return list(dirs.keys())

    def getPluginData(self, key, type):
        type = type.lower()
        if (not type) or (type not in self.cache['SupportedPlugins']):
            return ""
        if key not in self.cache['SupportedPlugins'][type]:
            return ""
        return self.cache['SupportedPlugins'][type][key]

    def getPluginTypes(self):
        return list(self.cache['SupportedPlugins'].keys())

    def setProjectDefaultPluginType(self, type):
        type = type.lower()
        if not type:
            type = self.cache['DefaultPluginType']
        if type not in self.cache['SupportedPlugins']:
            SCRAM.printerror("****ERROR: Invalid plugin type '%s'. Currently supported plugins are: %s",
                             (type, ", ".join(self.getSupportedPlugins())))
        else:
            self.cache['DefaultPluginType'] = type
        return

    def setDefaultPluginType(self, type):
        type = type.lower()
        if not type:
            type = self.cache['DefaultPluginType']
        if type and (type not in self.cache['SupportedPlugins']):
            bf = self.get('metabf')[0]
            SCRAM.printerror("****ERROR: Invalid plugin type '%s'. Currently supported plugins are: %s" %
                             (type, ", ".join(self.getSupportedPlugins())))
            SCRAM.printerror("           Please fix the '%s' file first. For now no plugin will be generated "
                             "for this product." % bf)
        else:
            self.set('plugin_type', type)
        return

    def getDefaultPluginType(self):
        type = ""
        if 'DefaultPluginType' in self.cache:
            type = self.cache['DefaultPluginType']
        return type

    def getSupportedPlugins(self):
        return sorted(list(self.cache['SupportedPlugins'].keys()))

#############################################
# Source Extenstions
#############################################

    def setPythonProductStore(self, val):
        self.cache['PythonProductStore'] = val

    def setValidSourceExtensions(self):
        cls = self.get('class')
        exts = {}
        exttypes = self.getSourceExtensionsTypes()
        for t in exttypes:
            exts[t] = []
        if cls == "LIBRARY":
            for t in exttypes:
                for e in self.getSourceExtensions(t):
                    exts[t].append(e)
        elif cls == "PYTHON":
            for e in self.getSourceExtensions("cxx"):
                exts["cxx"].append(e)
        for t in exttypes:
            self.set("%sExtensions" % t, exts[t])
        self.set("unknownExtensions", [])
        return

    def addSourceExtensionsType(self, type):
        type = type.lower()
        if type not in self.cache['SourceExtensions']:
            self.cache['SourceExtensions'][type] = {}

    def removeSourceExtensionsType(self, type):
        type = type.lower()
        if type in self.cache['SourceExtensions']:
            del self.cache['SourceExtensions'][type]

    def getSourceExtensionsTypes(self):
        return self.cache['SourceExtensions'].keys()

    def addSourceExtensions(self, type, exts=[]):
        type = type.lower()
        self.addSourceExtensionsType(type)
        for ext in exts:
            self.cache['SourceExtensions'][type][ext] = 1

    def removeSourceExtensions(self, type, exts):
        type = type.lower()
        if type not in self.cache['SourceExtensions']:
            return
        for ext in exts:
            if ext in self.cache['SourceExtensions'][type]:
                del self.cache['SourceExtensions'][type][ext]

    def getSourceExtensions(self, type):
        type = type.lower()
        if type not in self.cache['SourceExtensions']:
            return []
        return self.cache['SourceExtensions'][type].keys()

    def getSourceExtensionsStr(self, type):
        " ".join(self.getSourceExtensions(type))

#############################################
# generating library safe name for a package
#############################################

    def safename_coral(self, path):
        return self.safename_CMSProjects("safename_SubsystemPackageBased", path)

    def safename_cmssw(self, path):
        return self.safename_CMSProjects("safename_SubsystemPackageBased", path)

    def safename_default(self, path):
        return self.safename_CMSProjects("safename_JoinAll", path)

    def safename_CMSProjects(self, func, path):
        cls = self.get("class")
        name = ""
        if (cls == "LIBRARY") or (cls == "PYTHON"):
            name = self.runTemplate(func, path[len(environ['SCRAM_SOURCEDIR']) + 1:])
            if cls == "PYTHON":
                name = "Py" + name
        return name

    def safename_PackageBased(self, path):
        parts = path.split("/")
        if len(parts) == 2:
            return parts[1]
        return ""

    def safename_SubsystemPackageBased(self, path):
        name = ""
        parts = path.split("/")
        if len(parts) > 2:
            if parts[0] == 'LCG':
                name = "lcg_" + parts[1]
            else:
                name = parts[0] + parts[1]
        return name

    def safename_JoinAll(self, path):
        return path.replace(dirsep, "")

    def alpaka_safename(self, backend):
        return self.cache["SUPPORTED_ALPAKA_BACKENDS"][backend] if (backend in self.cache["SUPPORTED_ALPAKA_BACKENDS"]) else ""

###############################################
######################################
# Template initialization for different levels

    def initTemplate_LIBRARY(self):
        self.initTemplate_common2all()
        if self.get('safename'):
            return
        path = self.get('path')
        sname = self.runToolFunction("safename", "self", path)
        if not sname:
            self.processTemplate("Safename_generator")
            sname = self.get('safename')
            if not sname:
                sname = self.runToolFunction("safename", "default", path)
        if sname:
            self.set("safename", sname)
        else:
            SCRAM.die("*** ERROR: Unable to generate library safename for package '%s' "
                      "of project %s\n    Please send email to 'hn-cms-sw-develtools@cern.ch" %
                      (path, environ["SCRAM_PROJECTNAME"]))
        return

    def initTemplate_PYTHON(self):
        self.initTemplate_LIBRARY()

    def initTemplate_common2all(self):
        self.set("ProjectName", self.cache['ProjectName'])
        self.set("ProjectConfig", self.cache['ProjectConfig'])

    def initTemplate_PROJECT(self):
        self.init = True
        ltop = environ['LOCALTOP']
        odir = ltop
        proj_name = environ['SCRAM_PROJECTNAME']
        stool = self.getTool('self')
        if 'LOCALRT' in stool['RUNTIME']:
            odir1 = stool['RUNTIME']['LOCALRT']
            if odir1:
                odir = odir1[0]
        defcompiler = "gcc"
        comFlags = {}
        for flag in ["CXXFLAGS", "CFLAGS", "FFLAGS", "CPPDEFINES", "LDFLAGS", "CPPFLAGS"]:
            comFlags[flag] = 1
        if ("cuda" in self.cache["SUPPORTED_ALPAKA_BACKENDS"]) and (not self.isToolAvailable("cuda-gcc-support")):
            del self.cache["SUPPORTED_ALPAKA_BACKENDS"]["cuda"]
        if ("rocm" in self.cache["SUPPORTED_ALPAKA_BACKENDS"]) and (not self.isToolAvailable("rocm")):
            del self.cache["SUPPORTED_ALPAKA_BACKENDS"]["rocm"]
        self.cache['SELECTED_ALPAKA_BACKENDS'] = ""
        if 'FLAGS' in stool:
            if 'DEFAULT_COMPILER' in stool['FLAGS']:
                defcompiler = stool['FLAGS']['DEFAULT_COMPILER'][0]
            if 'OVERRIDABLE_FLAGS' in stool['FLAGS']:
                for flag in stool['FLAGS']['OVERRIDABLE_FLAGS']:
                    comFlags[flag] = 1
            if 'ALPAKA_BACKENDS' in stool['FLAGS']:
                self.cache['SELECTED_ALPAKA_BACKENDS'] = " ".join([bend for bend in stool['FLAGS']['ALPAKA_BACKENDS'] if bend in self.cache["SUPPORTED_ALPAKA_BACKENDS"]])
        self.cache['Compiler'] = defcompiler
        self.cache['CompilerTypes'] = ["CXX", "C", "F77"]
        self.cache['DefaultCompilerFlags'] = []
        self.cache['DefaultBuildFileFlagsToDump'] = []
        self.cache['DefaultCompilerFlags'].extend(comFlags.keys())
        for comp in self.cache['CompilerTypes']:
            self.cache['%sCompiler' % comp] = '%scompiler' % comp.lower()
        self.cache['MultipleCompilerSupport'] = True
        self.cache['SymLinkPython'] = False
        self.cache['ProjectName'] = proj_name
        self.cache['LocalTop'] = ltop
        self.cache['ProjectConfig'] = environ['SCRAM_CONFIGDIR']
        self.cache['AutoGenerateClassesHeader'] = False
        self.initTemplate_common2all()
        self.set('ProjectLOCALTOP', ltop)
        self.set('ProjectOldPath', odir)
        env = self.get('environment')
        env['SCRAM_INIT_LOCALTOP'] = odir
        bdir = join(ltop, environ['SCRAM_INTwork'], 'cache')
        for d in ["prod", "bf", "log"]:
            makedirs(join(bdir, d), exist_ok=True)
        if ('RELEASETOP' in env) and (env['RELEASETOP'] != ""):
            self.set('releasearea', False)
            self.cache['ReleaseArea'] = False
        else:
            self.set('releasearea', True)
            self.cache['ReleaseArea'] = True
        self.cache['LCGProjectLibPrefix'] = "lcg_"
        self.setRootReflex('rootrflx')
        self.setPythonProductStore('$(SCRAMSTORENAME_PYTHON)')
        for type in ["lib", "bin", "test", "python", "logs", "include"]:
            self.addProductDirMap(type, '.+', "SCRAMSTORENAME_%s" % type.upper())
        self.addProductDirMap("scripts", '.+', "SCRAMSTORENAME_BIN")
        f77deps = self.getCompiler("F77")
        self.cache['InvalidUses'] = {}
        for f in self.getCompilerTypes():
            c = self.getCompiler(f)
            if c != f77deps:
                self.cache['InvalidUses'][c] = 1
            compilers = self.getCompilers(f)
            for c in compilers:
                if c != f77deps:
                    self.cache['InvalidUses'][c] = 1
        proj = self.cache['ProjectName'].lower()
        if not self.isToolAvailable(proj):
            proj = ""
        xdata = self.core
        if self.get("path") != environ["SCRAM_SOURCEDIR"]:
            self.core = self.project_bf
        self.cache["LCGDICT_PACKAGE"] = self.core.get_flag_value("LCGDICT_PACKAGE", False)
        for var in ["LIB", "INCLUDE", "USE"]:
            val = self.fixData(self.core.get_data(var), var, "")
            if var == "USE" and ("self" not in val):
                if not val:
                    val = ["self"]
                else:
                    val.append("self")
            if val:
                if var == "USE":
                    val.append(proj)
                vals = " ".join(val)
                self.addCacheData(var, vals)
        self.core = xdata
        try:
            extraRules = 'SCRAM.Plugins.{0}.ExtraBuildRule'.format(environ['SCRAM_PROJECTNAME'])
            self.cache['ProjectPlugin'] = importlib.import_module(extraRules).ExtraBuildRule(self)
        except Exception:
            self.cache['ProjectPlugin'] = None
        return

    def SubSystem_template(self):
        self.data["swap_prod_mkfile"] = True
        self.initTemplate_common2all()
        fh = self.data["FH"]
        src = environ["SCRAM_SOURCEDIR"] + dirsep
        path = self.get("path")
        subdirs = self.getSafeSubPaths(path)
        path = path[len(src):]
        fh.write("ALL_SUBSYSTEMS+=%s\n" % path)
        fh.write("subdirs_%s = %s\n" % (self.get("safepath"), subdirs))
        fh.write("subdirs_%s += %s\n" % (src[:-1], self.get("safepath")))

    def Package_template(self):
        self.initTemplate_common2all()
        fh = self.data["FH"]
        path = self.get("path")
        if self.get('metabf'):
            self.depsOnlyBuildFile()
        else:
            subdirs = self.getSafeSubPaths(path)
            src = environ["SCRAM_SOURCEDIR"] + dirsep
            self.data["swap_prod_mkfile"] = True
            fh.write("ALL_PACKAGES += %s\n" % path[len(src):])
            fh.write("subdirs_%s := %s\n" % (self.get("safepath"), subdirs))

    def Documentation_template(self):
        return self.SubSystem_template()

    def Project_template(self):
        path = self.get("path")
        safepath = self.get("safepath")
        fh = self.data["FH"]
        self.updateEnvVarMK()
        for var in ["LIB", "INCLUDE", "USE"]:
            fh.write('%s :=\n' % var)
            val = self.getCacheData(var)
            if val:
                fh.write("%s += %s\n" % (var, val))
        for tn in self.getCompilerTypes():
            c = self.getCompiler(tn)
            fh.write("$(foreach f,$(ALL_COMPILER_FLAGS),$(eval $f += $(%s_EX_FLAGS_$f_ALL)))\n" % c)
            fh.write("$(foreach f,$(ALL_COMPILER_FLAGS),$(eval REM_$f += $(%s_EX_FLAGS_REM_$f_ALL)))\n" % c)
        rflx = self.getRootReflex()
        if rflx:
            fh.write("LCGDICT_DEPS := %s\n" % rflx)
            tool = self.getTool(rflx)
            if "FLAGS" in tool:
                for flag in tool["FLAGS"]:
                    if not flag.startswith("GENREFLEX_"):
                        continue
                    if flag == "GENREFLEX_GCCXMLOPT":
                        fh.write('{0} := $(if $(strip $({1}_EX_FLAGS_{0})),--gccxmlopt=\\"$({1}_EX_FLAGS_{0})\\")\n'.
                                 format(flag, rflx))
                    else:
                        fh.write("{0} := $({1}_EX_FLAGS_{0})\n".format(flag, rflx))
        # All flags from top level BuildFile
        flags = self.core.get_flags()
        for flag in flags:
            val = " ".join(flags[flag])
            if flag.startswith("HOOK_"):
                fh.write("%s:=%s\n" % (flag, val))
            elif flag.endswith("FLAGS"):
                fh.write("self_EX_FLAGS_%s+=%s\n" % (flag, val))
            else:
                fh.write("%s+=%s\n" % (flag, val))
        fh.write("\n\nifeq ($(strip $(GENREFLEX)),)\n"
                 "GENREFLEX:={}\n"
                 "endif\n"
                 "ifeq ($(strip $(GENREFLEX_CPPFLAGS)),)\n"
                 "GENREFLEX_CPPFLAGS:=-DCMS_DICT_IMPL -D_REENTRANT -DGNU_SOURCE\n"
                 "endif\n"
                 "ifeq ($(strip $(ROOTCLING)),)\n"
                 "ROOTCLING:={}\n"
                 "endif\n\n"
                 "LIBDIR+=$(self_EX_LIBDIR)\n"
                 "ifdef RELEASETOP\n"
                 "ifeq ($(strip $(wildcard $(RELEASETOP)/$(PUB_DIRCACHE_MKDIR)/DirCache.mk)),)\n"
                 "$(error Release area has been removed/modified as $(RELEASETOP)/$(PUB_DIRCACHE_MKDIR)/DirCache.mk "
                 "is missing.)\n"
                 "endif\n"
                 "endif\n\n".format(
                     self.getGenReflexPath(), self.getRootClingPath()))

        self.processTemplate("Project")
        self.createSymLinks()
        generatedDirs = []
        for ptype in self.getPluginTypes():
            pluginDir="GENERATED_%sPLUGIN_DIR" % ptype.upper()
            for dir in self.getPluginProductDirs(ptype):
                if pluginDir in generatedDirs: continue
                generatedDirs.append(pluginDir)
                fh.write("{0}:=$(if $(strip $(_BUILD_TIME_MICROARCH)),$({1})/$(_BUILD_TIME_MICROARCH),$({1}))\n".format(pluginDir, dir))
            refreshcmd = self.getPluginData("Refresh", ptype)
            cachefile = self.getPluginData("Cache", ptype)
            fh.write("PLUGIN_REFRESH_CMDS += {0}\n"
                     "define do_{0}\n"
                     "  $(CMD_echo) \"@@@@ Refreshing Plugins:{0} for $(1)\" &&\\\n"
                     "$(EDM_TOOLS_PREFIX) {0} $(1)\n"
                     "endef\n".format(refreshcmd))
            for dir in self.getPluginProductDirs(ptype):
                fh.write("$({4})/{0}: $(SCRAM_INTwork)/cache/{1}_{2} "
                         "$(SCRAM_INTwork)/cache/prod/{2}\n"
                         "\t$(call run_plugin_refresh_cmd,{2})\n"
                         "{2}_cache := $({3})/{0}\n".format(cachefile, ptype, refreshcmd, dir, pluginDir))
            fh.write("$(SCRAM_INTwork)/cache/{0}_{1}: \n"
                     "\t@:\n"
                     "-include $(SCRAM_CONFIGDIR)/SCRAM/GMake/Makefile.{0}plugin\n".format(ptype, refreshcmd))
        fh.write("###############################################################################\n\n")
        self.processTemplate("Common_rules")
        return

    def checkPluginFlag(self):
        path = self.get('path')
        libname = self.get('safename')
        bf = self.get('metabf')[-1]
        plugintype = self.get('plugin_type')
        err = False
        plugin = 0
        flags = self.core.get_flags()
        if plugintype:
            plugin = 1
            plugintype = plugintype.lower()
            if plugintype not in self.cache["SupportedPlugins"]:
                err = True
                SCRAM.printerror('****ERROR: Plugin type "%s" not supported. Currently available '
                                 'plugins are: %s' % (plugintype,
                                                      ",".join(sorted(self.cache["SupportedPlugins"].keys()))))
                plugintype = ""
        else:
            xflags = []
            for ptype in self.cache["SupportedPlugins"]:
                for pflag in self.cache["SupportedPlugins"][ptype]["Flag"]:
                    if pflag in flags:
                        xflags.append(pflag)
                        plugin = flags[pflag][0]
                        plugintype = ptype
                        if plugin not in ["0", "1"]:
                            err = True
                            SCRAM.printerror('****ERROR: Only allowed values for "%s" flag are "0|1". '
                                             'Please fix this for "%s" library in "%s" file' % (pflag, libname, bf))
                        else:
                            plugin = int(plugin)
            if len(xflags) > 1:
                SCRAM.printerror('****ERROR: More than one plugin flags')
                for f in xflags:
                    SCRAM.printerror('             %s' % f)
                SCRAM.printerror('           are set for "%s" library in "%s" file.' % (libname, bf))
                SCRAM.printerror('           You only need to provide one flag. Please fix this first '
                                 'otherwise plugin will not be registered.')
                err = True
            if not plugintype:
                for t in self.cache["SupportedPlugins"]:
                    exp = self.cache["SupportedPlugins"][t]["DefaultDirName"]
                    if re.search(exp, path):
                        if "DEFAULT_PLUGIN" in flags:
                            self.setDefaultPluginType(flags["DEFAULT_PLUGIN"])
                            plugintype = self.get('plugin_type')
                            if not plugintype:
                                err = True
                        else:
                            plugintype = self.cache["DefaultPluginType"]
                        plugin = 1
                        break
            if not plugintype and ("DEFAULT_PLUGIN" in flags):
                self.setDefaultPluginType(flags["DEFAULT_PLUGIN"])
                plugintype = self.get('plugin_type')
                if not plugintype:
                    err = True
        pnf = self.get('plugin_name_force')
        pn = self.get('plugin_name')
        if (not plugintype) and pn:
            plugintype = self.cache["DefaultPluginType"]
            plugin = 1
        if plugin and (not pn):
            pn = libname
        if pn and (not pnf) and (libname != pn):
            SCRAM.printerror('****ERROR: Plugin name should be same as the library name. '
                             'Please fix the "%s" file and replace "%s" with "%s"' % (bf, pn, libname))
            SCRAM.printerror('           Please fix the above error otherwise library "%s" '
                             'will not be registered as plugin.' % libname)
            err = True
        if err:
            if not self.isReleaseArea():
                SCRAM.die("Please fix the above error first.")
            self.set('plugin_name', pn)
            return
        self.set('plugin_name', pn)
        if not pn:
            return
        pd = self.cache["SupportedPlugins"][plugintype]["Dir"]
        flag = False
        for ind in sorted(self.cache["SupportedPlugins"][plugintype]["DirMap"].keys()):
            for reg in self.cache["SupportedPlugins"][plugintype]["DirMap"][ind]:
                if re.match(reg, path):
                    pd = self.cache["SupportedPlugins"][plugintype]["DirMap"][ind][reg]
                    flag = True
                    break
            if flag:
                break
        self.set('plugin_type', plugintype)
        self.set('plugin_dir', pd)
        name = pn
        self.set('plugin_product', name)
        self.set("no_shared_lib_copy", self.cache["SupportedPlugins"][plugintype]["NoSharedLibCopy"])
        return

    def plugin_template(self):
        self.checkPluginFlag()
        if self.get("plugin_name"):
            self.data["FH"].write("{0}_PRE_INIT_FUNC += $$(eval $$(call {1}Plugin,{2},{0},$({3}),{4}))\n".format(
                self.get("safename"), self.get("plugin_type"), self.get("plugin_name"),
                self.get("plugin_dir"), self.get("path")))
        return

    def dnn_template(self):
        dnn_name = self.core.get_flag_value("DNN_NAME")
        if dnn_name:
            self.data["FH"].write("%s_DNN_NAME   := %s\n" % (self.get("safename"), dnn_name))
        return

    def opencl_template(self):
        cl_name = self.core.get_flag_value("OPENCL_DEVICE_FILES")
        if cl_name:
            self.data["FH"].write("%s_OPENCL_DEVICE_FILES   := %s\n" % (self.get("safename"), cl_name))
        return

    def dict_template(self):
        self.searchForSpecialFiles()
        if self.get("classes_h"):
            self.pushstash()
            self.lcgdict_template()
            self.popstash()
        if self.get("cond_serialization"):
            self.pushstash()
            self.cond_serialization_template()
            self.popstash()
        if self.get("precompile_header"):
            self.pushstash()
            self.precompile_header_template()
            self.popstash()
        return

    def cond_serialization_template(self):
        self.data["FH"].write("{0}_PRE_INIT_FUNC += $$(eval $$(call CondSerialization,{0},{1},{2}))\n".format(
            self.get("safename"), self.get("path"), self.get("cond_serialization")))
        return

    def precompile_header_template(self):
        self.data["FH"].write("{0}_PRE_INIT_FUNC += $$(eval $$(call PreCompileHeader,{0},{1},{2},"
                              "$(patsubst $(SCRAM_SOURCEDIR)/%,%,{1})))\n".
                              format(self.get("safename"), self.get("path"), self.get("precompile_header")))

    def lcgdict_template(self):
        self.cache["HAS_LCGDICT"] = True
        safename = self.get("safename")
        lcgdict = self.get("classes_h")
        xr = "x "
        for i in range(1, len(lcgdict)):
            xr += "x%s " % i
        fh = self.data["FH"]
        fh.write("%s_LCGDICTS  := %s\n" % (safename, xr))
        fh.write("{0}_PRE_INIT_FUNC += $$(eval $$(call LCGDict,{0},{1},{2},$({3}),{4}))\n".format(
            safename, " ".join(lcgdict), " ".join(self.get("classes_def_xml")),
            self.getProductStore("lib"), self.get("genreflex_args")))

    def src2store_copy(self, filter, store):
        self.initTemplate_common2all()
        fh = self.data["FH"]
        safepath = self.get("safepath")
        path = self.get("path")
        fh.write("{0}_files := $(filter-out \\#% %\\#,$(notdir $(wildcard "
                 "$(foreach dir,$(LOCALTOP)/{1},$(dir)/{2}))))\n".format(safepath, path, filter))
        for f in ["SKIP_FILES", "INSTALL_SCRIPTS"]:
            val = self.core.get_flag_value(f)
            if val:
                fh.write("%s_%s := %s\n" % (safepath, f, val))
        fh.write("$(eval $(call Src2StoreCopy,{0},{1},{2},{3}))\n".format(
            safepath, path, store, filter))

    def scripts_template(self):
        self.swapMakefile()
        self.src2store_copy("*", "$(%s)" % self.getProductStore("scripts"))

    def library_template_generic(self, check_alpaka=True):
        self.searchPackageFiles()
        self.dumpBuildFileData(True, check_alpaka)

    def alpaka_extra_flags(self, bend):
        self.set('use_private', 'alpaka-%s' % bend)
        extra_use = [self.get("parent")]
        for f in ["USE_ALPAKA", "USE_ALPAKA_" + bend.upper()]:
            for u in [d for d in self.core.get_flag_value(f).split(" ") if d]:
                if u=="1": continue
                if not u in extra_use: extra_use.append(u)
        self.set('use_public',  '%s' % " ".join(extra_use))
        return

    def alpaka_template_generic(self):
        if not self.cache["SELECTED_ALPAKA_BACKENDS"]: return
        fh = self.data["FH"]
        path = join(self.get("path"),"alpaka")
        if not exists(path): return
        backend = self.core.get_flag_value("ALPAKA_BACKENDS")
        if backend=="1": backend = self.cache["SELECTED_ALPAKA_BACKENDS"]
        else:
            sel_bends = [bend for bend in self.cache["SELECTED_ALPAKA_BACKENDS"].split(" ") if bend]
            if backend.startswith('!'):
                rej_bends = [bend for bend in backend[1:].split(" ") if bend]
                backend = " ".join([bend for bend in sel_bends if not bend in rej_bends]).strip()
            else:
                backend = " ".join([bend for bend in backend.split(" ") if bend in sel_bends]).strip()
        if not backend: return
        parent = self.get("parent")
        pname = self.get("safename")
        self.pushstash()
        self.set('buildfile_path',self.getLocalBuildFile())
        self.set('path', path)
        self.set('use', "$(if $(strip $(filter $(%s),$(ALL_LIBRARIES))),%s,)" %  (parent, parent))
        self.searchPackageFiles()
        for bend in backend.split(" "):
            bend_name = self.alpaka_safename(bend)
            if not bend_name: continue
            safename = pname+bend_name
            fh.write("{0} := self/{1}/alpaka/{3}\n"
                     "{1}/alpaka/{3} := {0}\n"
                     "{0}_PRODUCT_TYPE:=alpaka/{3}\n"
                     "{0}_files := $(patsubst {2}/%,%,$(wildcard $(foreach dir,{2},"
                     "$(foreach ext,$(SRC_FILES_SUFFIXES),$(dir)/*.$(ext)))))\n".
                     format(safename, parent, path, bend))
            self.pushstash()
            self.set('safename',safename)
            if bend=="rocm":
                self.set("check_rocm_files",False)
                self.check_rocm_files("alpaka_device")
            self.alpaka_extra_flags(bend)
            self.set("classes_file", "classes_%s" % bend)
            self.set("classes_file_type", "ALPAKA_%s_LCG" % bend.upper())
            self.dumpBuildFileData(True, check_alpaka=False)
            self.popstash()
        self.popstash()
        return

    def binary_template_generic(self):
        self.searchPackageFiles()
        self.dumpBuildFileData()

    def donothing_template(self):
        self.swapMakefile()
        self.initTemplate_common2all()
        self.data["FH"].write(".PHONY : all_{0} {0}\n{0} all_{0}:\n".format(self.get("safepath")))
        return

    def plugins_template(self):
        autoPlugin = 0
        skip = self.core.get_flag_value("SKIP_FILES")
        if skip in ["*", "%"]:
            return
        if self.getLocalBuildFile() and (not self.core.get_data("BUILDPRODUCTS", True)):
            if not self.core.get_data("USE", True):
                return
            flags = self.core.get_flags()
            for ptype in self.cache["SupportedPlugins"]:
                for pflag in self.cache["SupportedPlugins"][ptype]:
                    if (pflag in flags) and (flags[pflag][0] == "0"):
                        return
            name = self.get("parent") + "Auto"
            self.core.add_build_product(name.replace("/", ""), "", "lib", "LIBRARY")
            autoPlugin = 1
        self.binary_rules(autoPlugin)

    def check_rocm_files(self, rocm_type="rocm"):
        if self.get("check_rocm_files"): return
        files = self.core.get_product_files()
        if files and ([f for f in files if f.endswith("*.cc")]):
            rocm_ext = ["."+e for e in self.getExtension(rocm_type)]
            for f in self.get("all_files"):
                done=False
                for e in rocm_ext:
                    if f.endswith(e):
                        files.append(f)
                        done=True
                        break
                if done:break
        if (not files) and (not self.get("allow_empty_file_list")): files = self.get("all_files")
        if self.hasFileTypes(files,rocm_type):
            self.set("check_rocm_files",True)
            self.data["FH"].write(
                "{0}_DROP_DEP+=sanitizer-flags-%\n"
                "{0}_rocm:=1\n"
                "{0}_linker:=$(HIPCC)\n".format(self.get("safename")))
        return

    def library_template(self):
        self.initTemplate_LIBRARY()
        safename = self.get("safename")
        self.core.contents["NAME"] = safename
        ex = self.core.get_data("EXPORT", True)
        parent = self.get("parent")
        if ex:
            libs = []
            if "LIB" in ex:
                libs = ex["LIB"]
            if (len(libs) == 1) and (libs[0] != "1"):
                self.set("safename", libs[0])
        elif self.getLocalBuildFile() and (not self.core.get_data("USE")) and (not self.core.get_flag_value("USE_SOURCE_ONLY")) and (parent not in self.cache["LCGDICT_PACKAGE"]):
            return
        types = self.core.get_build_products()
        if types:
            for type in types:
                self.set("type", type)
                self.unsupportedProductType()
        path = self.get("path")
        safepath = self.get("safepath")
        safename = self.get("safename")
        self.core.contents["NAME"] = safename
        fh = self.data["FH"]
        self.data["data"].branch["name"] = safename
        fh.write("ifeq ($(strip $({2})),)\n"
                 "ALL_COMMONRULES += {1}\n"
                 "{1}_parent := {2}\n"
                 "{1}_INIT_FUNC := $$(eval $$(call CommonProductRules,{1},{3},{4}))\n"
                 "{0} := self/{2}\n"
                 "{2} := {0}\n"
                 "{0}_files := $(patsubst {3}/%,%,$(wildcard $(foreach dir,{3} {5},"
                 "$(foreach ext,$(SRC_FILES_SUFFIXES),$(dir)/*.$(ext)))))\n".
                 format(safename, safepath, parent, path, self.get("class"), self.getSubdirIfEnabled()))
        if parent.startswith("LCG/"):
            fh.write("%s := %s\n" % (parent[4:], safename))
        self.cache["HAS_LCGDICT"] = False
        self.library_template_generic(check_alpaka=False)
        if ex and (not self.hasAnySources(self.get("all_files"))) and (not self.cache["HAS_LCGDICT"]):
            fh.write("%s_EX_LIB   :=\n" % safename)
        self.alpaka_template_generic()
        fh.write("endif\n")
        return

    def python_template(self):
        self.swapMakefile()
        self.initTemplate_PYTHON()
        types = self.core.get_build_products()
        if types:
            for type in types:
                self.set("type", type)
                self.unsupportedProductType()
        path = self.get("path")
        safepath = self.get("safepath")
        safename = self.get("safename")
        fh = self.data["FH"]
        self.data["data"].branch["name"] = safename
        fh.write("ifeq ($(strip $({0})),)\n"
                 "{0} := self/{1}\n"
                 "{2}_parent := {4}\n"
                 "ALL_PYTHON_DIRS += $(patsubst src/%,%,{1})\n"
                 "{0}_files := $(patsubst {1}/%,%,$(wildcard $(foreach dir,{1} {3},$(foreach ext,"
                 "$(SRC_FILES_SUFFIXES),$(dir)/*.$(ext)))))\n".
                 format(safename, path, safepath, self.getSubdirIfEnabled(), self.get("parent")))
        self.dumpBuildFileData()
        fh.write("else\n"
                 "$(eval $(call MultipleWarningMsg,{0},{1}))\n"
                 "endif\n"
                 "ALL_COMMONRULES += {2}\n"
                 "{2}_INIT_FUNC += $$(eval $$(call CommonProductRules,{2},{1},{3}))\n".
                 format(safename, path, safepath, self.get("class")))
        return

    def test_template(self):
        self.binary_template()

    def dumpBuildFileLOC(self, localbf, safename, path, no_export, lib):
        fh = self.data["FH"]
        self.check_rocm_files()
        locuse = ""
        if localbf:
            fh.write("%s_BuildFile    := $(WORKINGDIR)/cache/bf/%s\n" % (safename, localbf[:-4]))
            flags_added = {}
            for f in ['ADD_SUBDIR', 'DD4HEP_PLUGIN', 'EDM_PLUGIN', 'EDM_PLUGIN',
                      'GENREFLEX_ARGS', 'LCG_DICT_HEADER', 'LCG_DICT_XML',
                      'NO_LIB_CHECKING', 'RIVET_PLUGIN', 'SKIP_FILE', 'DNN_NAME',
                      'NO_TESTRUN', 'PRE_TEST', 'SETENV', 'TEST_RUNNER_ARGS',
                      'ALPAKA_BACKENDS']:
                flags_added[f] = 1
            for backend in self.cache["SUPPORTED_ALPAKA_BACKENDS"]:
              for d in ["LCG_DICT_HEADER", "LCG_DICT_XML"]:
                flags_added["ALPAKA_%s_%s" % (backend.upper(), d)] = 1
            for xpre in ["", "_REM"]:
                for xflag in self.cache["DefaultCompilerFlags"] + self.cache["DefaultBuildFileFlagsToDump"]:
                    flag = "%s%s" % (xpre, xflag)
                    v = self.core.get_flag_value(flag)
                    if v:
                        fh.write("%s_LOC_FLAGS_%s   := %s\n" % (safename, flag, v))
                    flags_added[flag] = 1
            flags = self.core.get_flags()
            for flag in flags:
                for xflag in self.cache["DefaultCompilerFlags"] + self.cache["DefaultBuildFileFlagsToDump"]:
                    m = re.match('^(FILE.+?)_((REM_|)%s)$' % xflag, flag)
                    if m:
                        v = self.core.get_flag_value(flag)
                        if v:
                            fh.write("%s_%s_LOC_FLAGS_%s   := %s\n" % (safename, m.group(1), m.group(2), v))
                        flags_added[flag] = 1
            for flag in flags:
                if flag.startswith('USE_ALPAKA'): continue
                if flag not in flags_added:
                    v = self.core.get_flag_value(flag)
                    fh.write("%s_LOC_FLAGS_%s   := %s\n" % (safename, flag, v))
            for data in ["INCLUDE"]:
                val = self.fixData(self.core.get_data(data), data, localbf)
                if val:
                    fh.write("%s_LOC_%s   := %s\n" % (safename, data, " ".join(val)))
            if lib:
                for d in self.core.get_flag_value("NO_EXPORT", False):
                    for x in d.split(" "):
                        no_export[x] = 0
            for data in ["LIB"]:
                val = self.fixData(self.core.get_data(data), data, localbf)
                if val:
                    fh.write("%s_LOC_%s   := %s\n" % (safename, data, " ".join(val)))
            ex_use = self.get("use_public") + self.get("use")
            val = self.fixData(self.core.get_data("USE"), "USE", localbf) + [u for u in ex_use.split(" ") if u]
            if val:
                locuse = " ".join(val)
                if lib:
                    for d in val:
                        if d in no_export:
                            no_export[d] = 1
            if lib:
                flag = self.isLibSymLoadChecking()
                if flag:
                    fh.write("%s_libcheck     := %s\n" % (safename, flag))
            flag = self.core.get_flag_value("SKIP_FILES")
            if flag:
                fh.write("%s_SKIP_FILES   := %s\n" % (safename, flag))
        fh.write("%s_LOC_USE := %s  %s\n" % (safename, self.getCacheData("USE"), locuse))

    def dumpBuildFileData(self, lib=False, check_alpaka=True):
        fh = self.data["FH"]
        safename = self.get("safename")
        path = self.get("path")
        if check_alpaka and self.cache["SELECTED_ALPAKA_BACKENDS"]:
            backend = self.core.get_flag_value("ALPAKA_BACKENDS")
            if backend=="1": backend =  self.cache["SELECTED_ALPAKA_BACKENDS"]
            else: backend = " ".join([bend for bend in backend.split(" ") if bend in self.cache["SUPPORTED_ALPAKA_BACKENDS"]]).strip()
            if backend:
                psafename = safename
                ptype = self.get("ptype")
                alpaka_names = []
                for bend in backend.split(" "):
                    self.pushstash()
                    safename = psafename+self.alpaka_safename(bend)
                    alpaka_names.append(safename)
                    self.set("safename", safename)
                    self.alpaka_extra_flags(bend)
                    fh.write("%s := self/%s\n" % (safename, path))
                    fh.write("%s_CLASS := %s\n" % (safename, ptype))
                    fh.write("%s_PRODUCT_TYPE:=alpaka/%s\n" % (safename, bend))
                    fh.write("%s_files := $(%s_files)\n" % (safename, psafename))
                    if bend in ["rocm"]:
                        self.set("check_rocm_files",False)
                        self.check_rocm_files("alpaka_device")
                    self.dumpBuildFileData(lib, False)
                    self.popstash()
                self.set("alpaka_names"," ".join(alpaka_names))
                return
        localbf = self.getLocalBuildFile()
        no_export = {}
        self.dumpBuildFileLOC(localbf, safename, path, no_export, lib)
        if lib:
            self.processTemplate("Extra_template")
        self.dnn_template()
        self.opencl_template()
        if lib and localbf:
            if self.isPublictype():
                ex = self.core.get_data("EXPORT", True)
                if not self.get("plugin_type"):
                    fvars = [ "INCLUES"]
                    if ex:
                        fvars.append("LIB")
                    for data in fvars:
                        val = ""
                        if data in ex:
                            val = self.fixData([ex[data]], data, localbf, 1)
                        if val:
                            xval = ""
                            if data == "INCLUDE":
                                xval = " ".join(val)
                            else:
                                for x in val:
                                    if x == safename:
                                        xval = x
                                    else:
                                        SCRAM.printerror("***ERROR: Exporting library '%s' from %s is wrong. "
                                                         "Please remove this lib from export section of this "
                                                         "BuildFile." % (x, localbf))
                            fh.write("%s_EX_%s   := %s\n" % (safename, data, xval))
                    noexpstr = ""
                    for d in no_export:
                        if no_export[d] == 1:
                            noexpstr += " %s" % d
                        else:
                            SCRAM.printerror("****WARNING: {0} is not defined as direct dependency in {1}.\n"
                                             "****WARNING: Please remove {0} from the NO_EXPORT "
                                             "flag in {1}\n".format(d, localbf))
                    exptools = "$(%s_LOC_USE)" % safename
                    if noexpstr:
                        exptools = "$(filter-out %s,%s)" % (noexpstr, exptools)
                    fh.write("%s_EX_USE   := $(foreach d,%s,$(if $($(d)_EX_FLAGS_NO_RECURSIVE_EXPORT),,$d))\n" %
                             (safename, exptools))
                elif ex:
                    SCRAM.printerror("****WARNING: No need to export library once you have declared your "
                                     "library as plugin. Please cleanup %s by removing the "
                                     "<export></export> section.\n" % localbf)
        private_dep = self.get("use_private")
        if private_dep:
            fh.write("%s_LOC_USE   += %s\n" % (safename, private_dep))
        self.setValidSourceExtensions()
        fh.write("{0}_PACKAGE := self/{1}\nALL_PRODS += {0}\n".format(safename, path))
        safepath = self.get("safepath")
        store1 = self.getProductStore("scripts")
        store2 = self.getProductStore("logs")
        ins_script = self.core.get_flag_value("INSTALL_SCRIPTS")
        xclass = self.get("class")
        if xclass == "LIBRARY":
            fh.write("%s_CLASS := %s\n" % (safename, xclass))
        if lib:
            store3 = self.getProductStore("lib")
            parent = self.get("parent")
            if xclass in ["PLUGINS", "LIBRARY"]:
                fh.write("%s_forbigobj+=%s\n" % (parent, safename))
            fh.write("{0}_INIT_FUNC        += $$(eval $$(call Library,{0},{1},{2},$({3}),{4},$({5}),$({6}),{7}))\n".
                     format(safename, path, safepath, store1, ins_script, store3, store2, self.get("plugin_type")))
        elif xclass != "PYTHON":
            type = self.get("type")
            store3 = self.getProductStore(type)
            fh.write("{0}_INIT_FUNC        += $$(eval $$(call Binary,{0},{1},{2},$({3}),{4},$({5}),{6},$({7})))\n".
                     format(safename, path, safepath, store1, ins_script, store3, type, store2))
        else:
            fh.write("{0}_INIT_FUNC        += $$(eval $$(call PythonProduct,{0},{1},{2}))\n".
                     format(safename, path, safepath))
        return

    def searchPackageFiles(self):
        stubdir = ""
        path = self.get('path')
        files = self.core.get_product_files()
        if files:
            if dirsep in files[0]:
                stubdir = dirname(files[0])
                dir = join(path, stubdir)
                if not isdir(dir):
                    SCRAM.die("ERROR: Can not open '%s' directory. BuildFile in '%s' is refering "
                              "to files in this directory" % (dir, path))
                path = dir
        self.set("stubdir", stubdir)
        self.set("all_files", self.readDir(path, 2, 1))
        return

    def searchForSpecialFiles(self):
        stubdir = self.get("stubdir")
        all_files = self.get("all_files")
        lcgheader = []
        lcgxml = []
        genreflex_args = "$(GENREFLEX_ARGS)"
        path = self.get('path')
        class_file_type = self.get("classes_file_type", "LCG")
        hfile = self.core.get_flag_value("%s_DICT_HEADER" % class_file_type)
        xfile = self.core.get_flag_value("%s_DICT_XML" % class_file_type)
        xmldef = {}
        class_file = self.get("classes_file","classes")
        if not hfile:
            hfile = class_file+".h"
            if stubdir:
                hfile = join(stubdir, hfile)
        if not xfile:
            xfile = class_file+"_def.xml"
            if stubdir:
                xfile = join(stubdir, xfile)
        h = [join(path, x) for x in hfile.split(" ")]
        x = [join(path, x) for x in xfile.split(" ")]
        xc = len(x)
        xclass = self.get('class')
        if (len(h) == xc) and (xc > 0):
            for i in range(xc):
                xf = x[i]
                if xf in all_files:
                    if h[i] in all_files:
                        xmldef[xf] = h[i]
                    elif self.isAutoGenerateClassesH():
                        xmldef[xf] = "$(WORKINGDIR)/classes/%s.h" % xf
                    else:
                        xmldef[xf] = ""
                if (xf not in xmldef) or (xmldef[xf] == ""):
                    if (xclass == "LIBRARY") and (self.get("parent") in self.cache["LCGDICT_PACKAGE"]):
                        xmldef["$(WORKINGDIR)/classes/classes_def.xml"] = "$(WORKINGDIR)/classes/classes.h"
        h = []
        x = []
        for f in xmldef:
            x.append(f)
            f = xmldef[f]
            if f:
                h.append(f)
        xc = len(x)
        if (len(h) == xc) and (xc > 0):
            for i in range(xc):
                lcgheader.append(h[i])
                lcgxml.append(x[i])
            tmp = self.core.get_flag_value("GENREFLEX_ARGS").strip()
            if tmp == "--":
                genreflex_args = ""
            elif tmp:
                genreflex_args = tmp
            tmp = self.core.get_flag_value("GENREFLEX_FAILES_ON_WARNS").lower()
            if tmp not in ["no", "0"]:
                genreflex_args += " $(root_EX_FLAGS_GENREFLEX_FAILES_ON_WARNS)"
            plugin = self.get('plugin_name')
            libname = self.get('safename')
            if plugin and (plugin != libname):
                bf = self.get('metabf')[0]
                SCRAM.printerror("****ERROR: One should not set EDM_PLUGIN flag for a library which "
                                 "is also going to generate LCG dictionaries.\n"
                                 "  Please take appropriate action to fix this by either removing the\n"
                                 "  EDM_PLUGIN flag from the '%s' file for library '%s'\n"
                                 "  OR LCG DICT header/xml files for this edm plugin library.\n" %
                                 (bf, libname))
                if not self.get('releasearea'):
                    SCRAM.die("Please fix the above error first.")
        elif(xc > 0):
            SCRAM.printerror("****WARNING: Not going to generate LCG DICT from '%s' because "
                             "NO. of .h (%s) does not match NO. of .xml (%s) files.\n" % (path, hfile, xfile))
        self.set('classes_def_xml', lcgxml)
        self.set('classes_h', lcgheader)
        self.set('genreflex_args', genreflex_args)
        serial_file = "headers.h"
        precomp_file = "precompile.h"
        if stubdir:
            serial_file = join(stubdir, serial_file)
            precomp_file = join(stubdir, precomp_file)
        if xclass == "LIBRARY":
            serial_file = "headers.h"
            precomp_file = "precompile.h"
            if stubdir:
                serial_file = join(stubdir, serial_file)
                precomp_file = join(stubdir, precomp_file)
            serial_file = join(path, serial_file)
            if serial_file in all_files:
                self.set('cond_serialization', serial_file)
            if join(path, precomp_file) in all_files:
                self.set('precompile_header', precomp_file)
        return

    def BigProduct_template(self):
        localbf = self.getLocalBuildFile()
        if not localbf:
            return
        fh = self.data["FH"]
        subsys = self.get("parent")
        path = self.get("path")
        safename = basename(path)
        self.set("safename", safename)
        safepath = self.get("safepath")
        self.data["data"].branch["name"] = safename
        fh.write("ifeq ($(strip $({0})),)\n{0}:={0}\n"
                 "{0}_BuildFile    := $(WORKINGDIR)/cache/bf/{1}\n"
                 "ALL_BIGPRODS += {0}\n{0}_SUBSYSTEM:={2}\n".format(safename, localbf[:-4], subsys))
        for xpre in ["", "REM_", "BIGOBJ_", "REM_BIGOBJ_"]:
            for xflag in self.cache["DefaultCompilerFlags"] + self.cache["DefaultBuildFileFlagsToDump"]:
                flag = "%s%s" % (xpre, xflag)
                v = self.core.get_flag_value(flag)
                if v:
                    fh.write("%s_LOC_FLAGS_%s   := %s\n" % (safename, flag, v))
        for data in ["LIB"]:
            val = self.fixData(self.core.get_data(data), data, localbf)
            if val:
                fh.write("%s_LOC_%s   := %s\n" % (safename, data, " ".join(val)))
        locuse = ""
        val = self.fixData(self.core.get_data("USE"), "USE", localbf)
        if val:
            locuse = " ".join(val)
            fh.write("%s_PACKAGES := %s\n" % (safename, locuse))
        val = self.core.get_flag_value("DROP_DEP")
        if val:
            fh.write("%s_DROP_DEP := %s\n" % (safename, val))
        fh.write("%s_LOC_USE := %s  %s\n" % (safename, self.getCacheData("USE"), locuse))
        fh.write("{0}_INIT_FUNC += $$(eval $$(call BigProductRule,{0},{1},{2}))\n".format(safename, path, safepath))
        fh.write("endif\n")

    def depsOnlyBuildFile(self):
        if not self.core:
            return
        sname = self.get("safepath")
        src = environ["SCRAM_SOURCEDIR"]
        path = self.get("path")
        pack = path[len(src):].strip("/")
        localbf = self.getLocalBuildFile()
        fh = self.data["FH"]
        fh.write("ifeq ($(strip $({1})),)\n"
                 "{0} := self/{1}\n"
                 "{1}  := {0}\n"
                 "{0}_BuildFile    := $(WORKINGDIR)/cache/bf/{2}\n".
                 format(sname, pack, localbf[:-4]))
        ex = self.core.get_data("EXPORT", True)
        for data in ["INCLUDE", "USE"]:
            udata = []
            for d in self.getCacheData(data).split(" "):
                udata.append(d)
            for d in self.fixData(self.core.get_data(data), data, localbf, 1):
                if d not in udata:
                    udata.append(d)
            if ex and data in ex:
                for d in self.fixData([ex[data]], data, localbf):
                    if d not in udata:
                        udata.append(d)
            val = " ".join(udata)
            if val:
                fh.write("%s_LOC_%s := %s\n" % (sname, data, val))
        fh.write("{0}_EX_USE   := $(foreach d,$({0}_LOC_USE),$(if $($(d)_EX_FLAGS_NO_RECURSIVE_EXPORT),,$d))\n"
                 "ALL_EXTERNAL_PRODS += {0}\n"
                 "{0}_INIT_FUNC += $$(eval $$(call EmptyPackage,{0},{1}))\nendif\n\n".format(sname, path))
        return

    def binary_template(self):
        if not self.core:
            return
        self.swapMakefile()
        self.binary_rules()

    def binary_rules(self, autoPlugin=0):
        if self.core.get_flag_value("SKIP_FILES") in ["*", "%"]:
            return
        self.initTemplate_common2all()
        safepath = self.get("safepath")
        path = self.get("path")
        fh = self.data["FH"]
        xclass = self.get("class")
        types = self.core.get_build_products()
        localbf = self.getLocalBuildFile()
        for ptype in sorted(types.keys()):
            if ptype == "LIBRARY":
                for prod in sorted(types[ptype].keys()):
                    safename = self.fixProductName(prod)
                    self.set("safename", safename)
                    self.core.set_build_product(ptype, prod)
                    fh.write("ifeq ($(strip $(%s)),)\n%s := self/%s\n" % (safename, safename, path))
                    if xclass == "PLUGINS":
                        fh.write("PLUGINS:=yes\n")
                    if autoPlugin:
                        fh.write("{0}_files := $(patsubst {1}/%,%,$(wildcard $(foreach dir,{1} {2},"
                                 "$(foreach ext,$(SRC_FILES_SUFFIXES),$(dir)/*.$(ext)))))\n".
                                 format(safename, path, self.getSubdirIfEnabled()))
                    else:
                        prodfiles = " ".join(self.core.get_product_files())
                        fh.write("{0}_files := $(patsubst {1}/%,%,$(foreach file,{2},$(eval "
                                 "xfile:=$(wildcard {1}/$(file)))$(if $(xfile),$(xfile),"
                                 "$(warning No such file exists: {1}/$(file). Please fix {3}.))))\n".
                                 format(safename, path, prodfiles, localbf[:-4]))
                    self.set("type", types[ptype][prod]["TYPE"])
                    self.pushstash()
                    self.set("allow_empty_file_list",True)
                    self.set("ptype",ptype)
                    self.library_template_generic()
                    xnames = self.get("alpaka_names")
                    if not xnames: xnames = safename
                    for sname in xnames.split(" "):
                        if xclass == "TEST":
                            fh.write("%s_CLASS := TEST_%s\n" % (sname, ptype))
                        else:
                            fh.write("%s_CLASS := %s\n" % (sname, ptype))
                    self.popstash()
                    fh.write("else\n$(eval $(call MultipleWarningMsg,%s,%s))\nendif\n" % (safename, path))
            elif ptype == "BIN":
                for prod in sorted(types[ptype].keys()):
                    safename = self.fixProductName(prod)
                    self.set("safename", safename)
                    self.core.set_build_product(ptype, prod)
                    cmd = ""
                    if "COMMAND" in types[ptype][prod]:
                        cmd = types[ptype][prod]["COMMAND"]
                    prodfiles = "1"
                    if not cmd:
                        prodfiles = " ".join(self.core.get_product_files())
                    elif xclass != "TEST":
                        SCRAM.printerror("****WARNING: '<test name=.../>' tag is only valid for test directories. "
                                         "Ignoring test '%s' from %s\n" % (safename, localbf))
                        continue
                    if prodfiles:
                        fh.write("ifeq ($(strip $({0})),)\n"
                                 "{0} := self/{1}\n".format(safename, path))
                        if prodfiles == "1":
                            fh.write("%s_files := 1\n" % safename)
                        else:
                            fh.write("{0}_files := $(patsubst {1}/%,%,$(foreach file,{2},$(eval "
                                     "xfile:=$(wildcard {1}/$(file)))$(if $(xfile),$(xfile),"
                                     "$(warning No such file exists: {1}/$(file). Please fix {3}.))))\n".
                                     format(safename, path, prodfiles, localbf[:-4]))
                        if xclass == "TEST":
                            self.set("type", "test")
                        else:
                            self.set("type", types[ptype][prod]["TYPE"])
                        self.pushstash()
                        self.binary_template_generic()
                        xnames = self.get("alpaka_names")
                        if not xnames: xnames = safename
                        for sname in xnames.split(" "):
                            if xclass == "TEST":
                                fh.write("%s_CLASS := TEST\n" % sname)
                                if self.core.get_flag_value("NO_TESTRUN").lower() in ["yes", "1"]:
                                    fh.write("{0}_TEST_RUNNER_CMD := echo\n{0}_NO_TESTRUN := yes\n{0}_TEST_SKIP_MSG := Disabled via BuildFile\n".format(sname))
                                else:
                                    val = cmd if cmd else self.core.get_flag_value("TEST_RUNNER_CMD")
                                    if not val: val = "%s %s" % (sname, self.core.get_flag_value("TEST_RUNNER_ARGS"))
                                    fh.write("%s_TEST_RUNNER_CMD :=  %s\n" % (sname, val))
                                    for val in self.core.get_flag_value("SETENV_SCRIPT", False):
                                        if val: fh.write("%s_TEST_ENV += source %s && \n" % (sname, val))
                                    for val in self.core.get_flag_value("SETENV", False):
                                        if val: fh.write("%s_TEST_ENV += export %s && \n" % (sname, val))
                                val = self.core.get_flag_value("PRE_TEST")
                                if val:
                                    fh.write("%s_PRE_TEST := %s\n" % (sname, val))
                            else:
                                fh.write("%s_CLASS := BINARY\n" % sname)
                        self.popstash()
                        fh.write("else\n$(eval $(call MultipleWarningMsg,%s,%s))\nendif\n" % (safename, path))
            else:
                self.set("type", ptype.lower())
                self.unsupportedProductType()
        parent = self.get("parent")
        fh.write("ALL_COMMONRULES += {0}\n"
                 "{0}_parent := {1}\n"
                 "{0}_INIT_FUNC += $$(eval $$(call CommonProductRules,{0},{2},{3}))\n".
                 format(safepath, parent, path, xclass))
        return
