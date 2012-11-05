"""
A class that manages a batch of sessions.  
"""

import time, logging, sys
from diskio import *
from os import makedirs, remove
from os.path import join, expanduser, exists, split, abspath, normpath
from treedict import TreeDict
from pnstructures import PNodeCommon, PNode

import parameters as parameter_module
import pmodule
import loading
import configuration


################################################################################

def clean(custom_opttree):
    log = logging.getLogger("Configuration")
    opttree = configuration.setupOptionTree(opttree, log)

    loading.cleanAll(opttree)
        
    
class RunManager(object):
    """
    A class providing an API for interfacing directly with a
    lazyrunner project.  
    """

    def __init__(self, opttree = None):
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
            
        if opttree is None:
            opttree = TreeDict()
            
        ################################################################################
        # Init all the module lookup stuff
        
        loading.resetAndInitModuleLoading(opttree)

        self.log = logging.getLogger("Manager")
        self.opttree = opttree = configuration.setupOptionTree(opttree, self.log)

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