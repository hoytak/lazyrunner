"""
A class that manages a batch of sessions.  
"""

import time, logging, sys
from diskio import *
import os, os.path as osp
from treedict import TreeDict
from pnstructures import PNodeCommon, PNode
        
class Manager(object):
    """
    The command and control center for coordinating the sessions.
    
    The main aspect of this is caching, which is implemented by
    storing the elements of the cache in files named the hash of their
    parameters.
    """

    def __init__(self, manager_params):

        self.manager_params = mp = manager_params

        self.log = logging.getLogger("Manager")

        # set up the result cache
        if "cache_directory" in mp and mp.cache_directory is not None:
            
            self.log.info("Using cache directory '%s'" % mp.cache_directory)

            self.cache_directory = osp.expanduser(mp.cache_directory)
            self.disk_read_enabled = True
            self.disk_write_enabled = not mp.cache_read_only
        else:
            self.disk_read_enabled = False
            self.disk_write_enabled = False
            self.log.info("Not using disk cache.")

    def run(self, parameters, final_modules = None):

        common = PNodeCommon(self)

        if final_modules is None:
            final_modules = parameters.run_queue

        for name in final_modules:
            self._get(parameters, name, "results", common)

        common._debug_referencesDone()
    
    def getResults(self, parameters, name):

        return self._get(parameters, name, "results")

    def getModule(self, parameters, name):

        return self._get(parameters, name, "module")


    ##################################################
    # Interactions with the PNode structures

    def _get(self, parameters, name, p_type, common = None):

        if common is None:
            check = True
            common = PNodeCommon(self)
        else:
            check = False

        pnode = PNode(common, parameters, name, p_type)
        pnode.initialize()
        
        if p_type == "module":
            ret = pnode.pullUpToModule()[-1]
        elif p_type == "results":
            ret = pnode.pullUpToResults()[-1]
        else:
            assert False

        if check:
            common._debug_referencesDone()

        return ret

    def _loadFromCache(self, container):

        if self.disk_read_enabled:
            filename = join(self.cache_directory, container.getFilename())
         
            if exists(filename):
                try:
                    pt = loadResults(filename)
                except Exception, e:
                    self.log.error("Exception Raised while loading %s: \n%s"
                                   % (filename, str(e)))
                    pt = None
                    
                if pt is not None:

                    if (pt.treeName() == "__ValueWrapper__"
                        and pt.size() == 1
                        and "value" in pt):
                    
                        container.setObject(pt.value)
                    else:
                        container.setObject(pt)
                        
                    return

        if self.disk_write_enabled:
            container.setObjectSaveHook(self._saveToCache)


    def _saveToCache(self, container):
            
        if self.disk_write_enabled:

            filename = join(self.cache_directory, container.getFilename())
            directory = split(filename)[0]

                # Make sure it exists
            if not osp.exists(directory):
                os.makedirs(directory)

            if type(obj) is not TreeDict:
                pt = TreeDict("__ValueWrapper__")
                pt.value = obj
            else:
                pt = obj

            try:
                saveResults(filename, pt)
            except Exception, e:
                self.log.error("Exception raised attempting to save object to cache: \n%s" % str(e))

                try:
                    os.remove(filename)
                except Exception:
                    pass

