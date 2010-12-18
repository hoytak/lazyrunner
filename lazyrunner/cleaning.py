import os, shutil
from os.path import exists, join, relpath

def silent_remove(opttree, config, f, is_dir = False):

    if exists(f):
        try:
            if opttree.verbose_mode:
                print "Removing '%s'." % f

            if is_dir:
                shutil.rmtree(f)
            else:
                os.remove(f)

        except OSError, ose:
            print "WARNING: attemted removal of '%s' failed: \n   %s" % (relpath(f), str(ose))
    elif opttree.verbose_mode:
        print "No file '%s' to remove, skipping." % f
        
def clean_cmake_project(opttree, config, cmake_project_branch):

    d = cmake_project_branch.directory
    lib_file = cmake_project_branch.library_file

    silent_remove(opttree, config, join(d, "Makefile"))
    silent_remove(opttree, config, join(d, "CMakeCache.txt"))
    silent_remove(opttree, config, join(d, "cmake_install.cmake"))
    silent_remove(opttree, config, join(d, "CMakeFiles"), True)
    silent_remove(opttree, config, join(d, lib_file))
    
def clean_cython_file(opttree, config, f):
    assert f.endswith(".pyx")

    if config.cython.use_cpp:
        cf = f[:-4] + ".cpp"
    else:
        cf = f[:-4] + ".c"

    silent_remove(opttree, config, cf)
    silent_remove(opttree, config, f[:-4] + ".so")

def clean_pyc_files(opttree, config, base_dir):
    for dirpath, dirnames, filenames in os.walk(base_dir):
        for fn in filenames:
            if fn.endswith(".pyc"):
                silent_remove(opttree, config, join(base_dir, dirpath, fn))
                
    
def cleanAll(opttree, config, base_dir):

    print "Cleaning generated cython files."
    
    for f in config.cython_files:
        clean_cython_file(opttree, config, f)

    print "Cleaning cached cmake files."

    for b in config.cmake.iterbranches():
        clean_cmake_project(opttree, config, b)
        
    print "Cleaning old python .pyc files."

    clean_pyc_files(opttree, config, base_dir)
