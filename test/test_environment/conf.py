
from lazyrunner import configTree

config = configTree()

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

config.import_list      = []

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
# other parts of this config tree (e.g. "gsl", config.cmake.mycmakeproj).

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
# "subdir.cython_module" : ["gsl", config.cmake.mycmakeproj].  

config.cython.library_map = {}

################################################################################
# CMAKE SUBPROJECTS
################################################################################

# CMake Subproject producing a library.  I find CMake to be a better
# way to handle some projects (python's distutils has some limitations
# that cmake doesn't). Example:

# config.cmake.lib_1.directory    = "path/from/base"
# config.cmake.lib_1.library_name = "lib_name"  # defaults to branch name


# Use this option to control how many parallel processes are used
# during compilation of CMake projects (default = 1).

# config.cmake_parallel_compiling_processes = 1


################################################################################
# Automatic config information for new modules; do not edit anything
# below this line unless you are very adventurous.

#@AutoStart
config.setdefault("import_list", [])


