import os, shutil
from os.path import exists, join, relpath

def silent_remove(opttree, f, is_dir = False):

    if exists(f):
        try:
            if opttree.verbose:
                print "Removing '%s'." % f

            if is_dir:
                shutil.rmtree(f)
            else:
                os.remove(f)

        except OSError, ose:
            print "WARNING: attemted removal of '%s' failed: \n   %s" % (relpath(f), str(ose))
    elif opttree.verbose:
        print "No file '%s' to remove, skipping." % f
        
def clean_cmake_project(opttree, cmake_project_branch):

    d = cmake_project_branch.directory
    lib_file = cmake_project_branch.library_file

    silent_remove(opttree, join(d, "Makefile"))
    silent_remove(opttree, join(d, "CMakeCache.txt"))
    silent_remove(opttree, join(d, "cmake_install.cmake"))
    silent_remove(opttree, join(d, "CMakeFiles"), True)
    silent_remove(opttree, join(d, lib_file))
    
def clean_cython_file(opttree, f):
    assert f.endswith(".pyx")

    if opttree.cython.use_cpp:
        cf = f[:-4] + ".cpp"
    else:
        cf = f[:-4] + ".c"

    silent_remove(opttree, cf)
    silent_remove(opttree, f[:-4] + ".so")

def clean_pyc_files(opttree):
    for dirpath, dirnames, filenames in os.walk(opttree.project_directory):
        for fn in filenames:
            if fn.endswith(".pyc"):
                silent_remove(opttree, join(opttree.project_directory, dirpath, fn))
                
    
def cleanAll(opttree):

    log = logging.getLogger("CTRL")

    log.info("Cleaning generated cython files.")
    
    for f in opttree.cython_files:
        log.debug("Cython: Cleaning %s." % f) 
        clean_cython_file(opttree, f)

    log.info("Cleaning cached cmake files.")

    for b in opttree.cmake.iterbranches():
        log.debug("CMake: Cleaning %s." % b.directory) 
        clean_cmake_project(opttree, b)
        
    log.info("Cleaning old python .pyc files.")
    clean_pyc_files(opttree)
