from os.path import join, split, exists, abspath
from os import makedirs

################################################################################
# writing files

def writeFiles(fl, force_writing = True):

    # First see if any of these files exist already.  If so, raise an
    # exception and break.
    fl = [(abspath(filename), content) for filename, content in fl]

    files = [filename for filename, content in fl]

    existing_files = [exists(fn) for fn in files]
    
    if any(existing_files):

        file_list_str = ",\n".join(fn for e, fn in zip(existing_files, files) if e)

        if force_writing:
            print "Overwriting the following files:"
            print file_list_str
        else:
            err_str = ("Error: the following files would be overwritten:\n")
            raise IOError(err_str + file_list_str)

    # Make sure all the directories exist
    for fn, content in fl:
        d = split(fn)[0]
        if not exists(d):
            makedirs(d)

    # Now proceed to write out the files; abort on an error
    file_info = [ (open(fn, 'w'), content) for fn, content in fl]
    
    for f, content in file_info:
        f.write(content)
        f.close()


################################################################################
# initial creation

defaults_file_template = \
"""
\"\"\"
The default settings file used to run the lazyrunner framework.
\"\"\"

from treedict import TreeDict

p = TreeDict(\"parameters\")

# The parameters are determined by the module name for e.g. for
# MyModule, use p.mymodule.x to set the parameters for module
# 'mymodule'.

"""

init_file_template = \
"""
import %(defaults_module_name)s
import %(presets_module_name)s
"""

presets_file_template = \
"""
from lazyrunner import preset, applyPreset

# A preset is just a function taking one argument, a parameter tree,
# and returning a modified form of the tree.  Presets may be applied
# as dependencies using applyPreset(p).

"""

config_file_template = \
"""
from treedict import TreeDict
config = TreeDict(\"configuration\")

################################################################################
# Project Source Directories
################################################################################

# A list of files and/or directories to import to define the project.
# These can be directories containing a '__init__.py' file.  These
# files may be .pyx files, in which case they will be compiled as
# cython files or .py files, in which case they will be treated as
# python files.
#
# Note: you may also specify auto_import = True below, which
# recursively imports files in the local directory.  Furthermore,
# modules created using the '-m' command line are automatically
# appended to this list in the AutoStart section below.
#

config.import_list      = ['settings']

# If this is true, automatically add all the subdirectories having an
# __init__ file and all the local files (except conf.py) with a .py or
# .pyx extension (default True) to the import list.

config.auto_import  = True

# Debug mode turns on debug options in compiling code and prints
# diagnostic info during the configuration.
config.debug_mode              = False

# The location for the cache.  If None, cache is disabled.
config.cache_directory         = None

################################################################################
# CYTHON
#
# General options for compiling cython generated files
################################################################################

# language (C if False else C++)
config.cython.use_cpp                 = False

# Arguments passed to the c compiler when compiling cython-generated files.
config.cython.compiler_args           = []

# Arguments passed to the linker when linking cython-generated files.
config.cython.link_args               = []

# Libraries for all the files to import; these may be strings, giving
# specific library names, or branches to library specifications in
# other parts of this config tree (e.g. \"gsl\", config.cmake.mycmakeproj).

config.cython.libraries               = []

# More options for the compiler and linkers
config.cython.extra_library_dirs      = []
config.cython.extra_include_dirs      = []


# Whether numpy is needed (defaults to True); if True, the numpy
# headers and libraries are included in the compilation.

config.cython.numpy_needed            = True

####################

# Library includes specific to modules; the following is a dict
# filled with keys of the form <cython module> : <list of libraries>; e.g.
# \"subdir.cython_module\" : [\"gsl\", config.cmake.mycmakeproj].  

config.cython.library_map = {}

################################################################################
# CMAKE SUBPROJECTS
################################################################################

# CMake Subproject producing a library.  I find CMake to be a better
# way to handle some projects (python's distutils has some limitations
# that cmake doesn't). Example:

# config.cmake.lib_1.directory    = \"path/from/base\"
# config.cmake.lib_1.library_name = \"lib_name\"  # defaults to branch name


# Use this option to control how many parallel processes are used
# during compilation of CMake projects (default = 1).

# config.cmake_parallel_compiling_processes = 1


################################################################################
# Automatic config information for new modules; do not edit anything
# below this line unless you are very adventurous.

#@AutoStart
config.setdefault(\"import_list\", [])

"""

def createInitial(base_dir, opttree):

    # Okay, go for it
    d = {}

    settings_dir = d["settings_dir"] = \
                   join(base_dir, opttree.get("settings_dir", "settings"))

    defaults_module_name = d["defaults_module_name"] = \
                   opttree.get("defaults_module_name", "defaults").replace(".py", "")

    presets_module_name = d["presets_module_name"] = \
                   opttree.get("presets_module_name", "presets").replace(".py", "")

    config_module_name = d["config_module_name"] = \
                   opttree.get("config_module_name", "conf").replace(".py", "")
    
    # Process a few of these
    defaults_file = join(settings_dir, defaults_module_name + ".py")
    init_file     = join(settings_dir, "__init__.py")
    presets_file  = join(settings_dir, presets_module_name + ".py")
    config_file   = join(base_dir,     config_module_name + ".py")

    fl = [
        (config_file,   config_file_template % d),
        (defaults_file, defaults_file_template % d),
        (init_file,     init_file_template % d),
        (presets_file,  presets_file_template % d)]

    writeFiles(fl, force_writing = opttree.force)

################################################################################
# Creating a module

module_template_file = \
"""
from lazyrunner import pmodule, PModule
from treedict import TreeDict

@pmodule
class %(module_name)s(PModule):

    # The current version of the pmodule.  The caching facilities
    # assume results are different between different versions.
    version = 0.01

    # Include dependencies here; alternatively, these may be given as
    # class methods, optionally accepting the parameter tree, to
    # provide parameter-dependent dependency checking
    
    parameter_dependencies = []
    result_dependencies    = []
    module_dependencies    = []

    # If true, the results are never saved or loaded from the cache.
    disable_result_caching = False

    def setup(self):
        # Setup the Pmodule.  Called whenever the module is created.
        
        pass

    def run(self):
        # Run the module and return a TreeDict instance holding the
        # results.  Note that this function is not necessarily called
        # if the results can be loaded from cache

        # Available attributes:
        #   self.p           The local parameter tree, given by
        #                    p.%(module_name)s in the central parameter tree.
        #   self.parameters  A tree giving parameters in branches, one for
        #                    each entry in any dependency above.
        #   self.results     A tree giving results in branches, one for
        #                    each entry in result_dependencies above.
        #   self.modules     A tree referencing module instances as given
        #                    in module_dependencies above.

        pass

    @classmethod
    def reportResult(cls, parameters, p, r):
        # Report on results, even if they are loaded from
        # cache. `parameters` is the full parameter tree as specified
        # by all parameter dependencies, `p` is the local parameter
        # tree branch for this module, and `r` is the result of run(),
        # possibly loaded from cache.

        pass
"""

def createNewModule(base_dir, opttree, module):

    d = {}

    module_names = module.split('.')
    module_name = d["module_name"]  = module_names[-1]
    directories  = module_names[:-1]

    module_file = join(base_dir, *(directories + [module_name.lower() + ".py"]))

    print "Writing a new module '%s' to file '%s'" % (module_name, module_file)

    writeFiles([(module_file, module_template_file % d)],
               force_writing = opttree.force)

