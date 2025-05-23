from os import environ
from re import compile


class ExtraBuildRule:

    def __init__(self, buildrules):
        self.buildrules = buildrules
        buildrules.symlinkPythonDirectory(1)
        buildrules.autoGenerateClassesH(1)
        # $self->addPluginSupport(plugin-type,plugin-flag,plugin-refresh-cmd,dir-regexp-for-default-plugins,
        #   plugin-store-variable,plugin-cache-file,plugin-name-exp,no-copy-shared-lib)
        buildrules.addPluginSupport("edm", "EDM_PLUGIN", "edmPluginRefresh", r'\/plugins$', "SCRAMSTORENAME_LIB",
                                    ".edmplugincache", '$name="${name}.edmplugin"', "yes")
        buildrules.addPluginSupport("rivet", "RIVET_PLUGIN", "RivetPluginRefresh", r'\/plugins$', "SCRAMSTORENAME_LIB",
                                    ".rivetcache", '$name="Rivet${name}.$(SHAREDSUFFIX)"', "yes")
        buildrules.addPluginSupport("dd4hep", "DD4HEP_PLUGIN", "DD4HepPluginRefresh", r'\/nplugins$',
                                    "SCRAMSTORENAME_LIB", ".dd4hepcache", '$name="lib${name}.components"', "yes")
        buildrules.setProjectDefaultPluginType("edm")
        buildrules.addSymLinks("src/LCG include/LCG 1 .")

    def isPublic(self, klass):
        return klass in ["LIBRARY", "BIGPRODUCT"]

    def Project(self):
        common = self.buildrules
        fh = common.filehandle()
        fh.write("CFIPYTHON_PACKAGE_FILES:=$(SCRAM_SOURCEDIR)/FWCore/ParameterSet/templates/modules.py\n")
        fh.write("COND_SERIALIZATION:=$(SCRAM_SOURCEDIR)/CondFormats/Serialization/python"
                 "/condformats_serialization_generate.py\n")
        fh.write("ALL_EXTRA_PRODUCT_RULES+=LCG\n")
        if "_mic_" in environ["SCRAM_ARCH"]:
            fh.write("EDM_WRITE_CONFIG:=true\n"
                     "EDM_CHECK_CLASS_VERSION:=true\n"
                     "EDM_CHECK_CLASS_TRANSIENTS=true\n")
        else:
            fh.write(
                "EDM_WRITE_CONFIG:=edmWriteConfigs\n"
                "EDM_CHECK_CLASS_VERSION:=$(SCRAM_SOURCEDIR)/FWCore/Reflection/scripts/edmCheckClassVersion\n"
                "EDM_CHECK_CLASS_TRANSIENTS=$(SCRAM_SOURCEDIR)/FWCore/Utilities/scripts/edmCheckClassTransients\n"
            )
            if "ASAN" in environ["SCRAM_PROJECTVERSION"]:
                fh.write("EDM_TOOLS_PREFIX:=LD_PRELOAD=$(GCC_CXXCOMPILER_BASE)/lib64/libasan.so\n")
            if "UBSAN" in environ["SCRAM_PROJECTVERSION"]:
                fh.write("EDM_TOOLS_PREFIX:=LD_PRELOAD=$(GCC_CXXCOMPILER_BASE)/lib64/libubsan.so\n")
            if "TSAN" in environ["SCRAM_PROJECTVERSION"]:
                fh.write("EDM_TOOLS_PREFIX:=LD_PRELOAD=$(GCC_CXXCOMPILER_BASE)/lib64/libtsan.so\n")

        fh.write("COMPILE_PYTHON_SCRIPTS:=yes\n"
                 "self_EX_FLAGS_CPPDEFINES+=-DCMSSW_GIT_HASH='\"$(CMSSW_GIT_HASH)\"' "
                 "-DPROJECT_NAME='\"$(SCRAM_PROJECTNAME)\"' -DPROJECT_VERSION='\"$(SCRAM_PROJECTVERSION)\"'\n"
                 "ifeq ($(strip $(RELEASETOP)$(IS_PATCH)),yes)\n"
                 "CMSSW_SEARCH_PATH:=${CMSSW_SEARCH_PATH}:$($(SCRAM_PROJECTNAME)_BASE_FULL_RELEASE)"
                 "/$(SCRAM_SOURCEDIR)\n"
                 "endif\n")

        ######################################################################
        # Dependencies: run ignominy analysis for release documentation
        fh.write(".PHONY: dependencies\n"
                 "dependencies:\n"
                 "\t@cd $(LOCALTOP); \\\n"
                 "\tmkdir -p $(LOCALTOP)/doc/deps/$(SCRAM_ARCH); \\\n"
                 "\tcd $(LOCALTOP)/doc/deps/$(SCRAM_ARCH); \\\n"
                 "\tignominy -f -i -A -g all $(LOCALTOP)\n")

        ######################################################################
        # Documentation targets. Note- must be lower case otherwise conflict with rules
        # for dirs which have the same name:
        fh.write(".PHONY: userguide referencemanual doc doxygen\n"
                 "doc: referencemanual\n"
                 "\t@echo \"Documentation/release notes built for $(SCRAM_PROJECTNAME) v$(SCRAM_PROJECTVERSION)\"\n"
                 "userguide:\n"
                 "\t@if [ -f $(LOCALTOP)/src/Documentation/UserGuide/scripts/makedoc ]; then \\\n"
                 "\t  doctop=$(LOCALTOP); \\\n"
                 "\telse \\\n"
                 "\t  doctop=$(RELEASETOP); \\\n"
                 "\tfi; \\\n"
                 "\tcd $$doctop/src; \\\n"
                 "\tDocumentation/UserGuide/scripts/makedoc $(LOCALTOP)/src $(LOCALTOP)/doc/UserGuide "
                 "$(RELEASETOP)/src\n"
                 "referencemanual:\n"
                 "\t@cd $(LOCALTOP)/src/Documentation/ReferenceManualScripts/config; \\\n"
                 "\tsed -e 's|@PROJ_NAME@|$(SCRAM_PROJECTNAME)|g' \\\n"
                 "\t-e 's|@PROJ_VERS@|$(SCRAM_PROJECTVERSION)|g' \\\n"
                 "\t-e 's|@CMSSW_BASE@|$(LOCALTOP)|g' \\\n"
                 "\t-e 's|@INC_PATH@|$(LOCALTOP)/src|g' \\\n"
                 "\tdoxyfile.conf.in > doxyfile.conf; \\\n"
                 "\tcd $(LOCALTOP); \\\n"
                 "\tls -d src/*/*/doc/*.doc | sed 's|(.*).doc|mv \"&\" \"\\1.dox\"|' | /bin/sh; \\\n"
                 "\tif [ `expr substr $(SCRAM_PROJECTVERSION) 1 1` = \"2\" ]; then \\\n"
                 "\t  ./config/fixdocs.sh $(SCRAM_PROJECTNAME)\"_\"$(SCRAM_PROJECTVERSION); \\\n"
                 "\telse \\\n"
                 "\t  ./config/fixdocs.sh $(SCRAM_PROJECTVERSION); \\\n"
                 "\tfi; \\\n"
                 "\tls -d src/*/*/doc/*.doy |  sed 's/(.*).doy/sed \"s|@PROJ_VERS@|$(SCRAM_PROJECTVERSION)|g\" \"&\" > "
                 "\"\\1.doc\"/' | /bin/sh; \\\n"
                 "\trm -rf src/*/*/doc/*.doy; \\\n"
                 "\tcd $(LOCALTOP)/src/Documentation/ReferenceManualScripts/config; \\\n"
                 "\tdoxygen doxyfile.conf; \\\n"
                 "\tcd $(LOCALTOP); \\\n"
                 "\tls -d src/*/*/doc/*.dox | sed 's|(.*).dox|mv \"&\" \"\\1.doc\"|' | /bin/sh;\n"
                 "doxygen:\n"
                 "\t@rm -rf $(LOCALTOP)/$(WORKINGDIR)/doxygen &&\\\n"
                 "\tmkdir -p $(LOCALTOP)/$(WORKINGDIR)/doxygen &&\\\n"
                 "\tscriptdir=$(LOCALTOP)/$(SCRAM_SOURCEDIR)/Documentation/ReferenceManualScripts/doxygen/utils &&\\\n"
                 "\t[ -d $$scriptdir ] || scriptdir=$(RELEASETOP)/$(SCRAM_SOURCEDIR)/Documentation"
                 "/ReferenceManualScripts"
                 "/doxygen/utils &&\\\n"
                 "\tcd $$scriptdir/doxygen &&\\\n"
                 "\tcp -t $(LOCALTOP)/$(WORKINGDIR)/doxygen cfgfile footer.html header.html doxygen.css "
                 "DoxygenLayout.xml doxygen ../../script_launcher.sh &&\\\n"
                 "\tcd $(LOCALTOP)/$(WORKINGDIR)/doxygen &&\\\n"
                 "\tchmod +rwx doxygen script_launcher.sh &&\\\n"
                 "\tsed -e 's|@CMSSW_BASE@|$(LOCALTOP)|g' cfgfile > cfgfile.conf &&\\\n"
                 "\t./doxygen cfgfile.conf &&\\\n"
                 "\t./script_launcher.sh $(SCRAM_PROJECTVERSION) $$scriptdir $(LOCALTOP) &&\\\n"
                 "\techo \"Reference Manual is generated.\"\n"
                 ".PHONY: gindices\n"
                 "gindices:\n"
                 "\t@cd $(LOCALTOP); \\\n"
                 "\trm -rf  .glimpse_*; mkdir .glimpse_full; \\\n"
                 "\tfind $(LOCALTOP)/src $(LOCALTOP)/cfipython/$(SCRAM_ARCH) -follow -mindepth 3 -type f | "
                 "grep -v '.pyc$$' | sed 's|^./||' | glimpseindex -F -H .glimpse_full; \\\n"
                 "\tchmod 0644 .glimpse_full/.glimpse_*; \\\n"
                 "\tmv .glimpse_full/.glimpse_filenames .; \\\n"
                 "\tfor  x in `ls -A1 .glimpse_full` ; do \\\n"
                 "\t  ln -s .glimpse_full/$$x $$x; \\\n"
                 "\tdone; \\\n"
                 "\tcp .glimpse_filenames .glimpse_full/.glimpse_filenames; \\\n"
                 "\tsed -i -e \"s|$(LOCALTOP)/||\" .glimpse_filenames\n"
                 ".PHONY: productmap\n"
                 "productmap:\n"
                 "\t@cd $(LOCALTOP); \\\n"
                 "\tmkdir -p src; rm -f src/ReleaseProducts.list; "
                 "echo \">> Generating Product Map in src/ReleaseProducts.list.\";\\\n"
                 "\t(RelProducts.pl $(LOCALTOP) > $(LOCALTOP)/src/ReleaseProducts.list || exit 0)\n"
                 ".PHONY: depscheck\n"
                 "depscheck:\n"
                 "\t@ReleaseDepsChecks.pl --detail\n")

    def Extra_template(self):
        common = common = self.buildrules
        skip = common.core.get_flag_value("SKIP_FILES", True)
        if skip == "*" or skip == "%":
            return True
        common.plugin_template()
        common.pushstash()
        common.dict_template()
        common.popstash()
        return True
