from exceptions import ConfigError
from config_processing import loadConfigInformation
from utils import loadModule
from runner_setup import setup
from os.path import split, join
from presets import applyPreset, BadPreset
import logging
from treedict import TreeDict
import sys

def setupManagerOptions(base_dir, opttree, config):
    mp = TreeDict()
    mp.cache_directory = config.cache_directory
    mp.cache_read_only = opttree.cache_read_only

    if opttree.no_cache:
        mp.cache_directory = None

    return mp

def getParameterTree(base_dir, opttree, config):
    # Maybe make this different 

    try:
        defaults_module = loadModule(base_dir, opttree.settings_module)
    except ImportError:
        raise ConfigError("Error loading settings file '%s'"
                          % (opttree.settings_module.replace(".", "/") + ".py"))

    if not hasattr(defaults_module, "p"):
        raise ConfigError("Parameter tree 'p' in default parameter file not found.")

    p = defaults_module.p

    # Go through and sanitize a few things
    p.setdefault("run_queue", [])

    if type(p.run_queue) is str:
        p.run_queue = [p.run_queue]

    if type(p.run_queue) is not list:
        raise ConfigError("Type of `p.run_queue` must be a list of modules to run.")
    
    for m in p.run_queue:
        if type(m) is not str:
            raise ConfigError("Module type '%s' not understood (should be string)" % str(m))

    # Convert to lower case.
    p.run_queue = [m.lower() for m in p.run_queue]

    # Apply the presets
    applyPreset(p, *opttree.presets)
    
    return p

config = None

def loadBase(base_dir, opttree):

    global config

    if config is not None:
        return

    try:
            
        # First get the config information
        config = loadConfigInformation(base_dir, opttree)

        # Now make sure everything is set up
        setup(base_dir, opttree, config)

        # Now import everything; these will just create registrations in
        # the presets and modules list which we can then run. 
        for m in config.modules_to_import:
            if opttree.verbose_mode:
                print "Loading module '%s' in directory '%s'" % (m, base_dir)
                
            loadModule(base_dir, m)

    except ConfigError, ce:
        
        print "\nAborting due to error in configuration:"
        print str(ce), "\n"
        sys.exit(1)
    

def run(base_dir, opttree):

    # set the logging level
    logging.basicConfig(level= (logging.DEBUG if opttree.debug_mode else logging.INFO), 
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s', 
                        datefmt='%H:%M:%S')


    try:
        loadBase(base_dir, opttree)

        # set up manager option tree.
        mp = setupManagerOptions(base_dir, opttree, config)

        # Create the manager, give it a list of presets to run, and off we go!
        from manager import Manager
        m = Manager(mp)

        # Load in the base parameters
        parameters = getParameterTree(base_dir, opttree, config)

        # Now time for business
        m.getResults(parameters)
    except ConfigError, ce:
        
        print "\nAborting due to error in configuration:"
        print str(ce), "\n"
        sys.exit(1)
        
    except BadPreset:
        sys.exit()
        
    
