"""
Provides interface functions to the outside world.
"""

import runner_setup
from treedict import TreeDict
from runner_setup import setup
from running import loadBase
from os.path import abspath, normpath, join
import sys, os

class LazyRunner:
    """
    A class providing an API for interfacing directly with a
    lazyrunner project.  It provides the same functionality as the
    command line, with a few additional methods for querying and
    testing.
    """

    def __init__(self, project_directory = '.',
                 debug = False, verbose = False,
                 no_cache = False, force = False,
                 cache_read_only = False, cache_directory = None,
                 no_compile = False, config_module = 'conf',
                 settings_module = 'settings.defaults'):
        """
        Initializes a lazyrunner environment.  The environment options
        are identical to those on the command line.
        """

        self.opttree = TreeDict()
        
        self.opttree.debug_mode      = debug
        self.opttree.verbose_mode    = verbose
        self.opttree.no_cache        = no_cache
        self.opttree.force           = force
        self.opttree.cache_read_only = cache_read_only
        self.opttree.cache_directory = cache_directory
        self.opttree.no_compile      = no_compile
        self.opttree.config_module_name = config_module
        self.opttree.settings_module = settings_module

        self.opttree.freeze()

        base_dir = normpath(abspath(join(os.getcwd(), project_directory)))

        if project_directory != '.':
            print "Using directory %s" % base_dir
            
        sys.path.append(base_dir)

        loadBase(base_dir, self.opttree)


    

    
