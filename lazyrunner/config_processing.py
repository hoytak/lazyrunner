"""
Process the config file.
"""
from exceptions import ConfigError
from utils import loadModule, checkType, checkValue
from os.path import exists, join, split, abspath, isdir, normpath, relpath
from itertools import chain
import os, re
from treedict import TreeDict

is_boolean = set([True, False])

# Create a few regular expressions to extract information
config_extract_module_file_load = \
    re.compile(r"config\.additional_source_files\.append\([\"'](?P<sourcefile>[\w\./]+)[\"']\)")

def configFilename(base_dir, opttree):
    config_module_name = opttree.config_module_name
    return join(base_dir, config_module_name + ".py")

def parseConfigAutoSection(base_dir, opttree):

    config_filename = configFilename(base_dir, opttree)
    config_f = open(config_filename)

    config_list = [(i, l) for i, l in
                   ((i, ll.strip()) for (i, ll) in enumerate(config_f))
                   if l != ""]

    # Find config.start
    idx = len(config_list) - 1
    
    while True:
        
        if config_list[idx][1] == "#@AutoStart":
            idx_start = idx
            break
    
        if idx == 0:
            raise ConfigError("Automatic section of config file not valid "
                              "('#@AutoStart' line not found)")
        idx -= 1

    t = TreeDict()
    t.autoload.source_files = []
    t.autoload.deletion_queue = []

    for i, l in config_list[idx_start+1:]:
        if l.startswith("config.import_list.append"):
            m = config_extract_module_file_load.match(l)
            if m is None:
                raise ConfigError("Parse Error in line %d of %s" % (i+1, config_filename))

            source_file = join(base_dir, m.group("sourcefile"))

            if exists(source_file):
                t.autoload.source_files.append(source_file)
            else:
                raise ConfigError(
                    "Source file '%s' does not exist.\n" % source_file 
                    + ("Remove or comment out line %d from '%s' to disable this warning."
                       % (i+1, config_filename)))
                
        elif l == "config.setdefault(\"import_list\", [])":
            pass
        elif l.startswith("#"):
            pass
        else:
            print "WARNING: Line %d ('%s') may be invalid." % (i+1, l)

    config_f.close()
    
    return t


def addSourceFileToAutoLoad(base_dir, opttree, sourcefile):

    config_f = open(configFilename(base_dir, opttree), 'a')

    config_f.seek(0, os.SEEK_END)

    f.writeline('config.additional_source_files.append("%s")\n' % sourcefile)

    f.close()

config_info = None

def loadConfigInformation(base_dir, opttree):
    " Both loads and validates the config file."

    global config_info

    if config_info is not None:
        return config_info
    
    # First, parse the automatic part of the configuration file to
    # make sure everything holds together there

    config_module_name = opttree.config_module_name
    config_filename = configFilename(base_dir, opttree)
    
    try:
        cm = loadModule(base_dir, config_module_name)
    except ImportError:
        raise ConfigError("Error loading '%s.py'; not in an initialized directory?"
                          %  config_module_name)

    # Run a bunch of checks on the config file
    auto_t = parseConfigAutoSection(base_dir, opttree)

    cp = cm.config

    def set_and_check_value(n, default_value, possible_values):
        cp.setdefault(n, default_value)
        checkValue(cp[n], possible_values, "config.%s" % n)
        
    def set_and_check_type(n, default_value, required_types):
        cp.setdefault(n, default_value)
        checkType(cp[n], required_types, "config.%s" % n)

    def normdir(d):
        d = normpath(relpath(base_dir, d))
        if d.endswith('/'):
            return d[:-1]
        else:
            return d

    set_and_check_value("debug_mode", False, is_boolean)
    set_and_check_type("import_list", [], list)
    set_and_check_value("add_all_with_init_file", True, is_boolean)

    # First, get a list of all the source files and source directories
    # to be included in

    modules_to_import = set()
    cython_files = set()

    for m in cp.import_list:
        if exists(m):
            if m.endswith(".py"):
                modules_to_import.add(abspath(m[:-3]))
            elif m.endswith(".pyx"):
                cython_files.add(abspath(m))
                modules_to_import.add(abspath(m[:-4]))
            elif isdir(m):
                modules_to_import.add(abspath(normpath(m)))
            else:
                raise ConfigError("Import file/module type of '%s' not supported." % m)

        elif exists(m + ".pyx"):
            cython_files.add(abspath(m + ".pyx"))
            modules_to_import.add(abspath(m))

            if exists(m + ".py"):
                raise ConfigError("Both .py and .pyx files exist for module '%s'." % m)

        elif exists(m + ".py"):
            modules_to_import.add(abspath(m))
            
        else:
            raise ConfigError("Import file/module '%s' does not exist." % m)
        

    # Recursively go through and add in directories with an __init__.py file
    if cp.add_all_with_init_file:

        for dirpath, dirnames, filenames in os.walk(base_dir, topdown=True,followlinks=True):
            new_dirs = [dn for dn in dirnames if exists(join(dirpath, dn, '__init__.py'))]
            dirnames[:] = new_dirs

            new_source_dirs = [abspath(join(dirpath, dn)) for dn in dirnames]
            
            modules_to_import.update(new_source_dirs)

            # Add in all the cython files present in this directory
            cython_files.update(abspath(join(dirpath, fn)) for fn in filenames
                                if fn.endswith('.pyx'))

    modules_to_import.discard(abspath(config_filename))

    # Now add everything
    cp.modules_to_import = tuple(modules_to_import)
    cp.cython_files      = tuple(cython_files)

    set_and_check_value("cython.use_cpp", False, is_boolean)
    set_and_check_type("cython.compiler_args", [], list)
    set_and_check_type("cython.link_args", [], list)
    set_and_check_type("cython.extra_library_dirs", [], list)
    set_and_check_type("cython.extra_include_dirs", [], list)
    set_and_check_type("cython.libraries",   [], list)
    set_and_check_value("cython.numpy_needed", True, is_boolean)
    set_and_check_type("cython.library_map", {}, dict)

    for k, v in cp.cython.library_map.items():
        if k.endswith(".pyx"):
            del cp.cython.library_map[k]
            k = k[:-4]

            if k in cp.cython.library_map:
                raise ConfigError("Both '%s' and '%s' in cython.library_map" % (k, k +".pyx"))
            
            cp.cython.library_map[k] = v

    # Now process the cmake directory options
    
    cp.makeBranch("cmake")

    # Move all the items in the cmake_list over into cmake item branches

    for k, b in cp.cmake.iteritems(recursive=False, branch_mode = "all"):

        if type(b) is not TreeDict:
            raise ConfigError("Cmake project '%s' needs to be specified with a " % k
                              + "cmake.<name>.directory structure;\n (e.g. cmake.%s.directory = '%s')" %(k,b))
        
        if "directory" not in b:
            raise ConfigError("'directory' parameter for cmake project '%s' not specified."
                             % ("cmake." + k))

        b.directory = d = abspath(normpath(b.directory))

        if not exists(d):
            raise ConfigError("Directory '%s' for cmake project '%s' does not exist." % (d,k))
        
        if not isdir(d):
            raise ConfigError("'%s' for cmake project '%s' not a directory." % (d,k))

        if not exists(join(d, "CMakeLists.txt")):
            raise ConfigError("'CMakeLists.txt' absent from directory '%s' for cmake project '%s'."
                              %(d,k))

        set_and_check_type("cmake.%s.library_name" % k, k, str)
        set_and_check_type("cmake.%s.library_file" % k,  join(d, "lib%s.so" % cp.cmake[k].library_name), str)

    cp.update(auto_t)

    cp.attach(recursive=True)
    cp.freeze()

    if opttree.verbose_mode:
        print "++++++++++++++++++++++++++++++++++++++++"
        print ("Module files/directories to import: \n%s\n"
               % ",\n".join(sorted('  ./' + relpath(d) for d in cp.modules_to_import)))
        print ("CMake library projects to compile and load: \n%s\n"
               % ",\n".join(sorted('  ./' + relpath(b.directory) for b in cp.cmake.iterbranches())))
        print ("Cython files to compile and load: \n%s\n"
               % ",\n".join('  ./' + relpath(d) for d in sorted(cp.cython_files)))

    config_info = cp
    return cp
