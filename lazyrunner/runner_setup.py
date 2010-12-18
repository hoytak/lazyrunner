from exceptions import ConfigError
from config_processing import loadConfigInformation
from copy import copy
from itertools import chain, product
from os.path import exists, abspath, join, split, relpath
import os
import sys
from glob import glob
from treedict import TreeDict
from cStringIO import StringIO
import re
import ctypes
import shutil
import cleaning

"""
Specifies the setup stuff 
"""

# This list is to keep them from being unloaded and garbage collected.
loaded_ctype_dlls = []

# A setup regular expression for the 

output_line_okay = re.compile(
    r"(^\s*running build_ext\s*$)|(^\s*skipping.+up-to-date\)\s*$)|(^\s*$)")

# Copied from python 2.7's subprocess.py file
from subprocess import Popen, PIPE, STDOUT

# Exception classes used by this module.
class CalledProcessError(Exception):
    """This exception is raised when a process run by check_call() or
    check_output() returns a non-zero exit status.
    The exit status will be stored in the returncode attribute;
    check_output() will also store the output in the output attribute.
    """
    def __init__(self, returncode, cmd, output=None):
        self.returncode = returncode
        self.cmd = cmd
        self.output = output
    def __str__(self):
        return "Command '%s' returned non-zero exit status %d" % (self.cmd, self.returncode)

def check_output(*popenargs, **kwargs):
    r"""Run command with arguments and return its output as a byte string.

    If the exit code was non-zero it raises a CalledProcessError.  The
    CalledProcessError object will have the return code in the returncode
    attribute and output in the output attribute.

    The arguments are the same as for the Popen constructor.  Example:

    >>> check_output(["ls", "-l", "/dev/null"])
    'crw-rw-rw- 1 root root 1, 3 Oct 18  2007 /dev/null\n'

    The stdout argument is not allowed as it is used internally.
    To capture standard error in the result, use stderr=STDOUT.

    >>> check_output(["/bin/sh", "-c",
    ...               "ls -l non_existent_file ; exit 0"],
    ...              stderr=STDOUT)
    'ls: non_existent_file: No such file or directory\n'
    """
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')
    process = Popen(stdout=PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        raise CalledProcessError(retcode, cmd, output=output)
    return output


def readyCMakeProjects(base_dir, opttree, config):
    """
    Compiles CMake Projects. 
    """

    # may switch so it runs in a specified build directory.

    if opttree.verbose_mode:
        print "\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
        print "Compiling cmake projects.\n"
    
    for k, b in config.cmake.iteritems(recursive=False, branch_mode = "only"):
        d = abspath(join(base_dir, b.directory))

        if not exists(d):
            raise ConfigError("CMake subproject '%s' directory does not exist (%s)"
                              % (k, d))

        def run(cmd):

            run_command = \
                "cd '%s' && CMAKE_INCLUDE_PATH=$INCLUDE_PATH CMAKE_LIBRARY_PATH=$LD_LIBRARY_PATH %s" % (d, cmd)

            try:
                check_output([run_command], shell=True, stderr=STDOUT)
            except CalledProcessError, ce:
                raise ConfigError("Error while compiling cmake project '%s' in '%s':\n%s\n%s"
                                  %(k, d, "Error code %d while running '%s':" % (ce.returncode, cmd), ce.output))

        if opttree.verbose_mode:
            print "CMake: '%s' in '%s' " % (k,d)


        first_attempt = True

        while True:

            try:
                if not exists(join(d, "Makefile")):
                    run("cmake ./")
                    
                run("make --jobs -f Makefile")
                    
            except ConfigError, ce:
                    
                if first_attempt:
                    print ("WARNING: Error while compiling cmake project '%s';"
                           " removing cache files and retrying.") % k
                    cleaning.clean_cmake_project(opttree, config, b)
                    first_attempt = False
                    continue

                else:
                    raise ce
                
            break

        if not exists(b.library_file):
            raise ConfigError("Expected shared library apparently not produced by compiliation: \n"
                              + "  Subproject: %s " % k
                              + "  Expected library file: %s" % (relpath(b.library_file)))

        # Dynamically load them here; this means they will be preloaded and the program will work
        loaded_ctype_dlls.append(ctypes.cdll.LoadLibrary(b.library_file))

    if opttree.verbose_mode:
        print "Done compiling and loading cmake library projects."
        print "<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<\n"
        
def runBuildExt(base_dir, opttree, config):
    """
    Sets up and runs the python build_ext setup configuration.
    """

    ct = config.cython

    extra_include_dirs = ct.extra_include_dirs
    extra_library_dirs = ct.extra_library_dirs
    libraries          = ct.libraries
    library_map        = ct.library_map
    compiler_args      = ct.compiler_args
    link_args          = ct.link_args

    quiet = not opttree.verbose_mode
    
    from distutils.core import setup as dist_setup
    from distutils.extension import Extension
    
    if ct.numpy_needed:
	import numpy 
	extra_include_dirs += [numpy.get_include()]

    ######################################################
    # First have to see if we're authorized to use cython files, or if we
    # should instead compile the included files

    # Get all the cython files in the sub directories and in this directory
    cython_files = config.cython_files

    # Set the compiler arguments -- Add in the environment path stuff
    ld_library_path = os.getenv("LD_LIBRARY_PATH")

    if ld_library_path is not None:
	extra_library_dirs += [p.strip() for p in ld_library_path.split(":") if len(p.strip()) > 0]

    include_path = os.getenv("INCLUDE_PATH")
    if include_path is not None:
	extra_include_dirs += [p.strip() for p in include_path.split(":") if len(p.strip()) > 0]

    # The rest is also shared with the setup.py file, in addition to
    # this one, so 

    def strip_empty(l):
        return [e.strip() for e in l if len(e.strip()) != 0]

    def get_include_dirs(m):
        return strip_empty(extra_include_dirs)

    def get_libnode_library(t):
        return t.library_name

    def get_libnode_directory(t):
        return t.directory

    def get_library_dirs(m):
        l = strip_empty(extra_library_dirs)

        if m in library_map:
            for lib in library_map[m]:
                if type(lib) is TreeDict:
                    l.append(get_libnode_directory(lib))

        l = [abspath(ld) for ld in l]
        return l

    def get_libraries(m):
        def process_lib(lib):
            if type(lib) is TreeDict:
                return get_libnode_library(lib)
            else:
                return lib

        liblist = libraries + (library_map[m] if m in library_map else [])
        
        return strip_empty(process_lib(lib) for lib in liblist)

    def get_extra_compile_args(m):
        return strip_empty(compiler_args + (['-g'] if config.debug_mode else ["-DNDEBUG"]))

    def get_extra_link_args(m):
        return strip_empty(link_args + (['-g'] if config.debug_mode else ["-DNDEBUG"]))

    ############################################################
    # Cython extension lists
    ext_modules = []
    
    for f in cython_files:
        # extract the module names 
        rel_f = relpath(f, base_dir)
        assert rel_f.endswith('.pyx')
        modname = rel_f[:-4].replace('/', '.')

        ext_modules.append(Extension(
            modname,
            [f], 
            include_dirs = get_include_dirs(modname),
            library_dirs = get_library_dirs(modname),
            libraries = get_libraries(modname),
            extra_compile_args = get_extra_compile_args(modname),
            extra_link_args = get_extra_link_args(modname),
            language = "c++" if ct.use_cpp else "c",
            ))

    ############################################################
    # Now get all these ready to go

    from Cython.Distutils import build_ext

    cmdclass = {'build_ext' : build_ext}

    old_argv = copy(sys.argv)
    sys.argv = (old_argv[0], "build_ext", "--inplace")

    if not quiet:
        print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> "
        print "Compiling cython extension modules.\n"

        
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    
    try:
        if quiet:
            output = sys.stderr = sys.stdout = StringIO()
        
        dist_setup(
            cmdclass = cmdclass,
            ext_modules = ext_modules)
        
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        if quiet:
            output_string = output.getvalue()

            # Check for output
            if not all(output_line_okay.match(le) is not None for le in output_string.split('\n')):
                if quiet:
                    print "++++++++++++++++++++"
                    print "Compiling cython extension modules.\n"

                print output_string

    if not quiet:
        print "\nCython extension modules successfully compiled."
        print "<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<\n"

    sys.argv = old_argv

def setup(base_dir, opttree, config):
    "The main setup function; calls the rest."

    readyCMakeProjects(base_dir, opttree, config)
    runBuildExt(base_dir, opttree, config)


