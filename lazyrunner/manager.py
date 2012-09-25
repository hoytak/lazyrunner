"""
A class that manages a batch of sessions.  
"""

import time, logging, sys
from diskio import *
from os import makedirs, remove
from os.path import join, expanduser, exists, split, abspath
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

            self.cache_directory = expanduser(mp.cache_directory)
            self.disk_read_enabled = True
            self.disk_write_enabled = not mp.cache_read_only
        else:
            self.disk_read_enabled = False
            self.disk_write_enabled = False
            self.log.info("Not using disk cache.")

    def run(self, parameters, final_modules = None):

        if final_modules is None:
            final_modules = parameters.run_queue

        return self.getResults(parameters, final_modules)
    
    def getResults(self, parameters, names):
        common = PNodeCommon(self)
        r = common.getResults(parameters, names)
        # common._debug_referencesDone()
        return r
    
    def _loadFromDisk(self, container):

        if not container.isDiskWritable():
            return

        if self.disk_read_enabled:
            filename = abspath(join(self.cache_directory, container.getFilename()))

            self.log.debug("Trying to load %s from %s" % (container.getKeyAsString(), filename))

            if exists(filename):
                try:
                    pt = loadResults(filename)
                except Exception, e:
                    self.log.error("Exception Raised while loading %s: \n%s"
                                   % (filename, str(e)))
                    pt = None
                    
                if pt is not None:

                    self.log.debug("--> Object successfully loaded.")
    
                    if (pt.treeName() == "__ValueWrapper__"
                        and pt.size() == 1
                        and "value" in pt):
                    
                        container.setObject(pt.value)
                    else:
                        container.setObject(pt)
                        
                    return
            else:
                self.log.debug("--> File does not exist.")

        if self.disk_write_enabled and container.isDiskWritable():
            container.setObjectSaveHook(self._saveToDisk)

    def _saveToDisk(self, container):

        assert self.disk_write_enabled and container.isDiskWritable()

        filename = join(self.cache_directory, container.getFilename())
        directory = split(filename)[0]
        obj = container.getObject()

        self.log.debug("Saving object  %s to   %s." % (container.getKeyAsString(), filename))

            # Make sure it exists
        if not exists(directory):
            makedirs(directory)

        if type(obj) is not TreeDict:
            pt = TreeDict("__ValueWrapper__", value = obj)
        else:
            pt = obj

        try:
            saveResults(filename, pt)

            assert exists(filename)
            
        except Exception, e:
            self.log.error("Exception raised attempting to save object to cache: \n%s" % str(e))

            try:
                remove(filename)
            except Exception:
                pass
