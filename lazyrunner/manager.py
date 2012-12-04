"""
A class that manages a batch of sessions.  
"""

import time, logging, sys
from os import makedirs, remove
from os.path import join, expanduser, exists, split, abspath, normpath
from treedict import TreeDict
from pnstructures import PNodeCommon, PNode

import parameters as parameter_module
import pmodule
import loading
import configuration


################################################################################

def __initLoggingSystem(custom_opttree):
            
    # get one filled in with the defaults
    opttree = configuration.setupOptionTree(custom_opttree, None, False)
    
    # Set up the logging stuff
    logging.basicConfig(
        format = opttree.logging.format,
        datefmt = opttree.logging.datefmt,
        level = logging.DEBUG if opttree.verbose else logging.INFO
    )
    
    logging.captureWarnings(True)

def clean(custom_opttree = None, **kwargs):
    
    if custom_opttree is None:
        custom_opttree = TreeDict()
        
    custom_opttree.update(TreeDict.fromdict(kwargs))
    
    __initLoggingSystem(custom_opttree)

    log = logging.getLogger("Configuration")
    opttree = configuration.setupOptionTree(custom_opttree, log, False)

    loading.cleanAll(opttree)
        

################################################################################        

__manager = None        
        
def initialize(custom_opttree = None, **kwargs):
    global __manager
    
    if __manager is not None:
        raise RuntimeError("Initialize has already been called!  Call reset first to reinitialize.")

    # fill in the custom opt_tree here with default options.
    if custom_opttree is None:
        custom_opttree = TreeDict()

    custom_opttree.update(TreeDict.fromdict(kwargs)) 
    
    __initLoggingSystem(custom_opttree)
    
    # set up the manager    
    __manager = _RunManager(custom_opttree)

    
def manager():
    global __manager

    if __manager is None:
        raise RuntimeError("Initialize must be called before manager is available.")
    
    return __manager

def reset():
    global __manager
    __manager = None
    
class _RunManager(object):
    """
    A class providing an API for interfacing directly with a
    lazyrunner project.  
    """

    def __init__(self, custom_opttree):
        """
        Initializes a lazyrunner environment.  The environment options
        are identical to those on the command line.
                 
        project_directory = '.',
        debug_mode = False, 
        verbose = False,
        no_cache = False, 
        force = False,
        cache_read_only = False, 
        cache_directory = None,
        no_compile = False, 
        config_module = 'conf'
        
        """

        self.log = logging.getLogger("Manager")
            
        ################################################################################
        # Init all the module lookup stuff
        opttree = configuration.setupOptionTree(custom_opttree, self.log, False)
        
        loading.resetAndInitModuleLoading(opttree)

        opttree = configuration.setupOptionTree(custom_opttree, self.log, True)
        self.opttree = opttree

        pmodule.resetAndInitialize()
        parameter_module.resetAndInitialize()
        
        loading.resetAndInitModules(self.opttree)
                
        parameter_module.finalize()
        pmodule.finalize()
        
    ########################################################################################
    # General Control Functions
    
    def getResults(self, modules = None, presets = [], parameters = None):
                
        common = PNodeCommon(self.opttree)
        
        ptree = parameter_module.getParameterTree(presets, parameters = parameters)
        
        if modules is None:
            modules = pmodule.getCurrentRunQueue()
        
        if type(modules) is str:        
            modules = [modules]
        
        results = common.getResults(ptree, modules)
        
        return dict(zip(modules, results)) 
    
    def getPresetHelp(self, width = None):
        return '\n'.join(parameters_module.getPresetHelpList(width = width))
    
    def updatePresetCompletionCache(self, preset_name_cache_file):
        parameter_module.presets.updatePresetCompletionCache(preset_name_cache_file)
            
    
def run(modules, presets = [], project_directory = '.', options = None):
    """
    Convenience function for running things directly. `options`, if given,
    should be a TreeDict of configuration options.
    """
    if options is None:
        options = TreeDict()
    else:
        if type(options) is not TreeDict:
            raise TypeError("options parameter needs to be a TreeDict.")
        
    options.project_directory = project_directory
     
    m = RunManager(options)
    
    return m.getResults(modules, presets)