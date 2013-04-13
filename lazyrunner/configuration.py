from treedict import TreeDict
from os.path import exists, join, split, abspath, isdir, normpath, relpath, expanduser
import os
import loading
import sys

################################################################################
# Options for handling the config tree

__custom_config_tree = None

def resetAndInitConfig():

    global __custom_config_tree
    __custom_config_tree = TreeDict()
    
def configTree():
    
    global __custom_config_tree
    
    assert __custom_config_tree is not None

    return __custom_config_tree

def finalizeLoadedConfigTree():
    global __custom_config_tree
    
    assert __custom_config_tree is not None
    
    t = __custom_config_tree
    __custom_config_tree = None
    
    return t

class DummyLog(object):
    def info(self, *args, **kwargs): pass
    def debug(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass


################################################################################
# Default global options

is_boolean = set([True, False])

__default_opttree = TreeDict()
    
__default_opttree.logging.format = (str, '%(asctime)s %(name)-12s %(levelname)-8s %(message)s', 
                                    'Format string used for the logging.')
__default_opttree.logging.datefmt = (str, '%H:%M:%S', 
                                    'Format string used for the date in the logging.')
    
__default_opttree.debug_mode = (is_boolean, False, "Enable debug mode in compilation.")
__default_opttree.use_hdf5 = (is_boolean, False, "Use hdf5 for caching instead of simple pickling.")
__default_opttree.cache_compression = (is_boolean, True, "Use bz2 compression on the cache files.")
__default_opttree.project_directory = (str, '.', "The root of the project directory.")
__default_opttree.verbose = (is_boolean, False, "Print more detailed diagnostic and progress messages.")
__default_opttree.no_cache = (is_boolean, False, "Disable the caching system.")
__default_opttree.force = (is_boolean, False, "Overwrite existing files when creating new modules.")
__default_opttree.cache_read_only = (is_boolean, False, "Only load things from cache; never save.")
__default_opttree.no_compile = (is_boolean, False, "Disable compiling things, even if source files are modified.")
__default_opttree.config_file = (str, 'conf', "The configuration file to load options from.")
__default_opttree.cache_directory = ([str, type(None)], None, "The cache directory to use; None disables caching.")
__default_opttree.import_list = (list, [], "List of modules / directories to import in loading project.")
__default_opttree.auto_import = (is_boolean, True, "Automatically import all subdirs with __init__.py files.")
__default_opttree.cython.use_cpp = (is_boolean, False, "Compile cython extensions in C++ mode.")
__default_opttree.minimal_cache_persistence = (is_boolean, False, "Clear out objects from the cache as quickly as possible.")

__default_opttree.cython.compiler_args = (list, [], "Additional arguments to use when compiling cython extensions.")
__default_opttree.cython.link_args = (list, [], "Additional arguments to use when linking cython extensions.")
__default_opttree.cython.extra_include_dirs = (list, [], "Additional include directories to pass to the compiler.")
__default_opttree.cython.extra_library_dirs = (list, [], "Additional library directories to pass to the linker.")
__default_opttree.cython.libraries = (list, [], "Additional libraries use in linking.")
__default_opttree.cython.numpy_needed = (is_boolean, False, "Load numpy libraries when compiling cython extension modules.")
__default_opttree.cython.library_map = (dict, {}, "Load specific librares for specific modules, given as name : list pairs.")
__default_opttree.cython.extra_source_map  = (dict, {}, "")

__default_opttree.freeze()

################################################################################

def checkType(value, required_type, name = None, error_message = None):

    def raiseError():
        if error_message is None:
            assert name is not None
            if type(required_type) in [list, tuple]:
                err = ("Type of '%s' must be one of %s."
                      % (name, ','.join(str(t) for t in required_type)))
            else:
                err = ("Type of '%s' must be %s."
                       % (name, str(required_type)))
        else:
            err = error_message
            
        raise TypeError(err)

    if type(required_type) in [list, tuple]:
        for t in required_type:
            if isinstance(value, t):
                return
            
        raiseError()
        
    else:
        if not isinstance(value, required_type):
            raiseError()
        
def checkValue(value, possible_values, name = None, error_message = None):

    if value not in possible_values:
        if error_message is None:
            assert name is not None
            error_message = ("Value of '%s' must be in %s."
                             % (name, ','.join(sorted(str(v) for v in possible_values))))
            
        raise ValueError(error_message)
    
def set_and_check_value(opttree, n, default_value, possible_values):
    opttree.setdefault(n, default_value)
    checkValue(opttree[n], possible_values, n)
    
def set_and_check_type(opttree, n, default_value, required_types):
    opttree.setdefault(n, default_value)
    checkType(opttree[n], required_types, n)

################################################################################
# Processing functions


def _processCMakeConfig(opttree, log):
        
    # Now process the cmake directory options
    opttree.makeBranch("cmake")

    # Move all the items in the cmake_list over into cmake item branches

    for k, b in opttree.cmake.iteritems(recursive=False, branch_mode = "all"):

        if type(b) is not TreeDict:
            raise ConfigError("Cmake project '%s' needs to be specified with a " % k
                              + "cmake.<name>.directory structure;\n (e.g. cmake.%s.directory = '%s')" %(k,b))
        
        if "directory" not in b:
            raise ConfigError("'directory' parameter for cmake project '%s' not specified."
                             % ("cmake." + k))

        b.directory = d = abspath(normpath(join(opttree.project_directory, b.directory)))

        if not exists(d):
            raise ConfigError("Directory '%s' for cmake project '%s' does not exist." % (d,k))
        
        if not isdir(d):
            raise ConfigError("'%s' for cmake project '%s' not a directory." % (d,k))

        if not exists(join(d, "CMakeLists.txt")):
            raise ConfigError("'CMakeLists.txt' absent from directory '%s' for cmake project '%s'."
                              %(d,k))

        set_and_check_type(opttree, "cmake.%s.library_name" % k, k, str)
        set_and_check_type(opttree, "cmake.%s.library_file" % k,  join(d, "lib%s.so" % opttree.cmake[k].library_name), str)
    
def _processImportList(opttree, log):

    modules_to_import = set()
    cython_files = set()

    def process_import(m):
        mf = join(opttree.project_directory, m)
        mf2 = join(opttree.project_directory, m.replace('.', '/'))

        if mf2.endswith('/pyx'):
            mf2 = mf2[:-4] + ".pyx"
        elif mf2.endswith('/py'):
            mf2 = mf2[:-3] + ".py"
        
        if exists(mf):
            return mf

        elif exists(mf + ".pyx"):
            return mf + ".pyx"

        elif exists(mf + ".py"):
            return mf + ".py"
        
        elif exists(mf):
            return mf

        elif exists(mf + ".pyx"):
            return mf + ".pyx"

        elif exists(mf + ".py"):
            return mf + ".py"

        else:
            raise ConfigError("Import file/module '%s' does not exist." % m)
        
    opttree.import_list = [process_import(m) for m in opttree.import_list]

    for m in opttree.import_list:
        if m.endswith(".py"):
            modules_to_import.add(abspath(m[:-3]))
            
        elif m.endswith(".pyx"):
            cython_files.add(abspath(m))
            modules_to_import.add(abspath(m[:-4]))

            if exists(m[:-1]):
                raise ConfigError("Both .py and .pyx files exist for module '%s'." % m)
            
        elif isdir(m):
            modules_to_import.add(m)
            
        else:
            raise ConfigError("Import file/module type of '%s' not supported." % m)

    # Recursively go through and add in directories with an __init__.py file
    if opttree.auto_import:
        
        # Just import the cython files 
        for dirpath in os.listdir(opttree.project_directory):
            dirpath = join(opttree.project_directory, dirpath)
            
            if isdir(dirpath) and exists(join(dirpath, '__init__.py')):
                modules_to_import.add(dirpath)
        
        # Now, walk the cython modules to get which are going to be imported
        for dirpath, dirnames, filenames in os.walk(opttree.project_directory, topdown=True,followlinks=True):
            dirpath = join(opttree.project_directory, dirpath)

            new_dirs = [dn for dn in dirnames if exists(join(dirpath, dn, '__init__.py'))]
            dirnames[:] = new_dirs

            # Add in all the cython files present in this directory
            cython_files.update(abspath(join(dirpath, fn)) for fn in filenames
                                if fn.endswith('.pyx'))

    # Now add everything
    opttree.modules_to_import = list(modules_to_import)
    opttree.cython_files      = list(cython_files)
    
    # Now finalize the cython imports
    for k, v in opttree.cython.library_map.items():
        if k.endswith(".pyx"):
            del opttree.cython.library_map[k]
            k = k[:-4]

            if k in opttree.cython.library_map:
                raise ConfigError("Both '%s' and '%s' in cython.library_map" % (k, k +".pyx"))
            
            opttree.cython.library_map[k] = v

def setupOptionTree(custom_opttree, log, include_config_file):

    if log is None:
        log = DummyLog()

    if not type(custom_opttree) is TreeDict:
        raise TypeError("LazyRunner class must be initialized with a TreeDict of options.")

    global __default_opttree
        
    # First set up the initial options
    base_opttree = TreeDict()

    for k, (v_type, v, msg) in __default_opttree.iteritems():
        base_opttree[k] = v 

    opttree = base_opttree.copy()
    opttree.update(custom_opttree)
    
    # Get a few base options going so we can load the configuration file
    checkType(opttree.project_directory, str, "project_directory")
    opttree.project_directory = abspath(normpath(expanduser(opttree.project_directory)))

    # Now clean up the remaining issues
    if not include_config_file:
        return opttree

    if abspath(normpath(expanduser(os.getcwd()))) != opttree.project_directory:
        log.info("Using '%s' as project directory." % opttree.project_directory)

    # Load in the config information based on what we have here
    resetAndInitConfig()
    checkType(opttree.config_file, str, "config_file")
    loading.loadModule(join(opttree.project_directory, opttree.config_file))
    config_tree = finalizeLoadedConfigTree()
    
    # Now, just need to reload things so it's all in the proper priority...
    opttree = base_opttree.copy()
    opttree.update(custom_opttree)
    opttree.update(config_tree)

    # Check these options 
    for k, (v_critiria, v, msg) in __default_opttree.iteritems():
        if type(v_critiria) is set:
            checkValue(v, v_critiria, k)
        else:
            checkType(v, v_critiria, k)
    
    # now need to just fill out a few parts of this 
    _processImportList(opttree, log)
        
    # Fill out the cmake stuff
    _processCMakeConfig(opttree, log)
        
    # Now, process everything else...
    if opttree.no_cache:
        opttree.cache_directory = None
    
    if opttree.cache_directory is None:
        opttree.disk_read_enabled = False
        opttree.disk_write_enabled = False

    # set up the result cache
    if opttree.cache_directory is not None:
        
        log.info("Using cache directory '%s'" % opttree.cache_directory)

        opttree.cache_directory = abspath(expanduser(opttree.cache_directory))
        opttree.disk_read_enabled = True
        opttree.disk_write_enabled = not opttree.cache_read_only
    else:
        log.info("Not using disk cache.")

        opttree.disk_read_enabled = False
        opttree.disk_write_enabled = False

    # And we're done with this

    opttree.attach(recursive = True)
    opttree.freeze()
        
    # Add up 
    sys.path.insert(0, opttree.project_directory)
        
    return opttree