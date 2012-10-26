"""
A class that manages a batch of sessions.  
"""

import time, logging, sys
from diskio import *
from os import makedirs, remove
from os.path import join, expanduser, exists, split, abspath, normpath
from treedict import TreeDict
from pnstructures import PNodeCommon, PNode

import parameters
import pmodule
import loading

def _setupOptTree(opttree):
    default_opttree = TreeDict()
        
    default_opttree.debug_mode = False
    default_opttree.project_directory = '.'
    default_opttree.debug_mode = False
    default_opttree.verbose = False
    default_opttree.no_cache = False
    default_opttree.force = False
    default_opttree.cache_read_only = False
    default_opttree.cache_directory = None
    default_opttree.no_compile = False
    default_opttree.config_module = 'conf'
    default_opttree.settings_module = 'settings.defaults'

    if not type(opttree) is TreeDict:
        raise TypeError("LazyRunner class must be initialized with a TreeDict of options.")

    opttree = opttree.copy()
        
    opttree.update(default_opttree, overwrite_existing = False)

    opttree.project_directory = normpath(abspath(expanduser(opttree.project_directory)))

    return opttree

def clean(opttree):
    opttree = _setupOptTree(opttree)
    config = loading.loadConfigInformation(opttree)

    loading.cleanAll(opttree, config)
        
class RunManager(object):
    """
    A class providing an API for interfacing directly with a
    lazyrunner project.  
    """

    def __init__(self, opttree):
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
        config_module = 'conf',
        settings_module = 'settings.defaults'
        
        """

            
        sys.path.append(opttree.project_directory)

        self.opttree = opttree
        self.config = loading.loadConfigInformation(opttree)

        ################################################################################
        # Now set up all the logger options

        self.log = logging.getLogger("Manager")
        
        if  normpath(abspath(expanduser(os.getcwd()))) != opttree.project_directory:
            self.log.info("Using '%s' as project directory." % opttree.project_directory)

            # Configure the cache directory
            if opttree.cache_directory is None:
                cache_directory = config.cache_directory
                
            else:
                cache_directory = opttree.cache_directory
                
            cache_read_only = opttree.cache_read_only
        
            if opttree.no_cache:
                cache_directory = None
    
            # set up the result cache
            if cache_directory is not None:
                
                self.log.info("Using cache directory '%s'" % cache_directory)
    
                self.cache_directory = expanduser(cache_directory)
                self.disk_read_enabled = True
                self.disk_write_enabled = not cache_read_only
            else:
                self.disk_read_enabled = False
                self.disk_write_enabled = False
                self.log.info("Not using disk cache.")
            
        ################################################################################
        # Init all the module lookup stuff
        
        pmodule.resetAndInitialize()
        parameters.resetAndInitialize()
        
        loading.resetAndInitModules(self.opttree, self.config)
                
        parameters.finalize()
        pmodule.finalize()
    
    ########################################################################################
    # General Control Functions
    
    def run(self, presets):
        
        ptree = parameters.getParameterTree(*presets)
        final_modules = pmodule.getCurrentRunQueue()
    
        return self.getResults(ptree, final_modules)
    
    def getResults(self, ptree, modules):
                
        common = PNodeCommon(self.opttree)
        
        results = common.getResults(ptree, modules)
        
        return dict(zip(results, modules)) 
    
    def getPresetHelp(self, width = None):
        return '\n'.join(parameters.getPresetHelpList(width = width))
    
    def updatePresetCompletionCache(self, preset_name_cache_file):
        parameters.presets.updatePresetCompletionCache(preset_name_cache_file)
            
     