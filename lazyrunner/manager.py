"""
A class that manages a batch of sessions.  
"""

import time, logging, sys
from diskio import *
import os, os.path as osp
from pmodulelookup import *
from treedict import TreeDict

        
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
            self.use_disk_cache = True
            self.disk_cache_read_only = mp.cache_read_only
        else:
            self.use_disk_cache = False
            self.log.info("Not using disk cache.")

        # Set up the lookups 
        self.local_cache = {}
        self.current_modules = {}
	self.current_bare_modules = {}
	self.reported_results = set()
	self.debug_logged_dependencies = set()
        self.parameter_branch_hash_cache = {}

        self.common_objects = {}
	
    ##################################################
    # Interface functions to the outside

    def getResults(self, parameters, name = None):
        """
        The main method for getting results from the outside.  If
        these results are already present, then they are returned as is.
        """

        # make sure that all the flags are removed from the parameter
        # tree; things should be reprocessed here.

        if name is None or type(name) in [list, tuple, set]:
            if name is None:
                
                name = parameters.get("run_queue", [])

                if type(name) is str:
                    name = [name]
                
            pt = parameters.copy()
            r = TreeDict("results")
            
            for n in (nn.lower() for nn in name):
                if n not in r:
		    r[n] = self._getResults(pt, n)

            r.freeze()

            return r
        elif type(name) is str:
            return self._getResults(parameters.copy(), name.lower())

        else:
            raise TypeError("'%s' not a valid type for name parameter." % str(type(name)))

    def _getResults(self, parameters, name, key = None, module_instance = None):

        assert type(name) is str
        name = name.lower()

        # Get the hash of this module
        if key is None:
            key = self._getModuleKey(parameters, name)

        if self.inCache(key, "results"):
            r = self.loadFromCache(key, "results")
	    self.__reportResults(parameters, name, key, r)
	    
        else:
            self.log.debug("Getting results for %s" % name)
            
            if module_instance is None:
                module_instance, r = self._getModule(parameters, name, key=key, calling_from_getresults = True)
	    else:
                self.log.info("Running %s" % name)
		r = module_instance.run()

            if r is None:
                r = TreeDict()
		r.freeze()
	    else:
		r.freeze()
		self.__reportResults(parameters, name, key, r)
		
	    self.saveToCache(key, "results", r)
            
        return r

    def getModule(self, parameters, name):
        """
        Returns a given module of that type.  
        """

        return self._getModule(parameters.copy(), name.lower())

    def _getModule(self, parameters, name, key = None, calling_from_getresults = False):

        # Only save one module of each to keep the memory use down

        if key is None:
            key = self._getModuleKey(parameters, name)

        if name in self.current_modules:
            cur_key, cur_m = self.current_modules[name]

            if cur_key == key:
                return cur_m

        self.log.debug("Instantiating module %s" % name)
        m = getPModuleClass(name)(self, key, parameters, True)

        assert m._name == name, "m._name <- %s != %s -> name" % (m._name, name)
        
        self.current_modules[name] = (key, m)

        r = self._getResults(parameters, name, key, module_instance = m)

	# If we're calling from getResults, return r along with m
	if calling_from_getresults:
	    return m, r
	else:
	    return m

    def _getModuleKey(self, parameters, name):

        def getHashDependencySet(n):
            
            pmc = getPModuleClass(n)
            pdep_set = pmc._getDependencySet(parameters, "parameter")

            for d in (pmc._getDependencySet(parameters, "result")
                      | pmc._getDependencySet(parameters, "module") ):
                
                if d != n:
                    pdep_set |= getHashDependencySet(d)

	    pdep_set_string = ', '.join(sorted(pdep_set))

	    if ("parameter", n, pdep_set_string) not in self.debug_logged_dependencies:
		self.log.debug("Parameter dependencies for %s are %s" % (n, pdep_set_string))
		self.debug_logged_dependencies.add( ("parameter", n, pdep_set_string) )

            return pdep_set
        
        d_set = sorted(getHashDependencySet(name))

        dep_td = TreeDict()

	d_set_str = ', '.join(d_set)

	if ("hash", name, d_set_str) not in self.debug_logged_dependencies:
	    self.log.debug("Hash Dependency set for %s is %s" % (name, d_set_str))
	    self.debug_logged_dependencies.add( ("hash", name, d_set_str) )

        # Set the dependency hash
        dep_hashes = TreeDict()
        
        for d in d_set:
            if d != name:
                dep_td[d] = self.getPreprocessedBranch(parameters, d)

        dep_hash = dep_td.hash()
        
        # Now set the local hash
        local_branch, local_hash = self.getPreprocessedBranch(parameters, name, return_hash = True)

        # if type(local_branch) is TreeDict:
        #     print "\n+++++++++++++ %s ++++++++++++++++" % name
        #     print local_branch.makeReport()
        #     print "+++++++++++++++++++++++++++++"
                    
        return (name, local_hash, dep_hash)

    def __reportResults(self, parameters, name, key, r):
	
	if (name, key) in self.reported_results:
	    return

	self.log.debug("Reporting results for module %s, key = %s" % (name, key))

        p = self.getPreprocessedBranch(parameters, name)

	getPModuleClass(name).reportResults(parameters, p, r)

	self.reported_results.add( (name, key) )


    ##################################################
    # Cache file stuff

    def __resultCachingEnabled(self, name):

        cls = getPModuleClass(name)
        
        if hasattr(cls, 'disable_result_caching') and getattr(cls, 'disable_result_caching'):
            return False
        else:
            return True

    def inCache(self, key, obj_name, local_key_override=None, dependency_key_override=None):
        """
        Returns true if the given object is present in the cache and
        False otherwise.  
        """

        key = self.__processKey(key, local_key_override, dependency_key_override)

        in_cache = False

        if (key, obj_name) in self.local_cache:
            in_cache = True
        elif (not self.use_disk_cache 
            or (obj_name == "results" and not self.__resultCachingEnabled(key[0]))):
              
            in_cache = False
        else:
            in_cache = osp.exists(self.cacheFile(key, obj_name))

        if in_cache:
            self.log.debug("'%s' with key '%s' in cache." % (obj_name, str(key)))
        else:
            self.log.debug("'%s' with key '%s' NOT in cache." % (obj_name, str(key)))

        return in_cache

    def loadFromCache(self, key, obj_name, local_key_override=None, dependency_key_override=None):
        """
        Loads the results from local cache; returns None if they are
        not present.
        """

        key = self.__processKey(key, local_key_override, dependency_key_override)

        self.log.debug("Loading '%s' from cache with key '%s'" % (obj_name, str(key)))

        try:
            return self.local_cache[(key, obj_name)]
        except KeyError:
            pass

        pt = loadResults(self.cacheFile(key, obj_name))

        assert type(pt) is TreeDict

        if pt.treeName() == "ValueWrapper" and pt.size() == 1 and "value" in pt:
            return pt.value
        else:
            return pt
            
    def saveToCache(self, key, obj_name, obj, local_key_override=None, dependency_key_override=None):
        """
        Saves a given object to cache.
        """


        key = self.__processKey(key, local_key_override, dependency_key_override)

        self.log.debug("Saving '%s' to cache with key '%s'" % (obj_name, str(key)))

        self.local_cache[(key, obj_name)] = obj

        if (not self.use_disk_cache
            or self.disk_cache_read_only
            or (obj_name == "results" and not self.__resultCachingEnabled(key[0]))):
            
            return

        filename = self.cacheFile(key, obj_name)

        if type(obj) is not TreeDict:
            pt = TreeDict("ValueWrapper")
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

    ##################################################
    # Cache database stuff

    def dbTable(self, key, table_name, *params):
        """
        Returns an sqlalchemy table that the object can 
        """

        # Load the metadata
        
        try:
            metadata = self.local_cache[(key, "db", "metadata")]
        except KeyError:
            
            # See if the engine is already present
            
            try:
                engine = self.local_cache[(key, "db", "engine")]
            except KeyError:
                dbfile = self.cacheFile(key, "database")
                self.local_cache[(key, "db", "engine")] = engine
                                       
            # Open the database
            metadata = MetaData()
            metadata.bind = engine

        return Table(table_name, metadata, *params)

    def dbSession(self, key):
        """
        Returns an active session object for the database
        """
        
        assert False
        
    ##################################################
    # Cache control stuff

    def __processKey(self, key, local_key_override, dependency_key_override):

        assert type(key) is tuple
        assert len(key) == 3
        assert type(key[0]) is str
        assert type(key[1]) is str
        assert type(key[2]) is str
        
        if local_key_override is None and dependency_key_override is None:
            return key

        return (key[0],
                key[1] if local_key_override is None else local_key_override,
                key[2] if dependency_key_override is None else dependency_key_override)
            
            
    def cacheFile(self, key, obj_name, suffix=".cache"):
        assert self.cache_directory is not None

        directory = osp.join(self.cache_directory, key[0], obj_name)
        
        # Make sure it exists
        if not osp.exists(directory):
            os.makedirs(directory)

        return osp.join(directory, "-".join(key[1:]) + suffix)

    def getPreprocessedBranch(self, parameters, name, return_hash = False):
        """
        Runs the parameters in a particular branch through the
        preprocessor and then freezes the tree / returns the
        associated hash.
        """

        if name not in parameters:
            parameters.makeBranch(name)

        try:
            br_hash = self.parameter_branch_hash_cache[(id(parameters), name)] 

        except KeyError:

            if isPModule(name):
                cls = getPModuleClass(name)
                cls.preprocessParameters(parameters[name])
                parameters[name]["__pmodule_version__"] = cls._getVersion()
                
            parameters.freeze(name)
            br_hash = self.parameter_branch_hash_cache[(id(parameters), name)] = parameters.hash(name)

        if return_hash:
            return parameters[name], br_hash
        else:
            return parameters[name]

    def inCommonObjectCache(self, name, key):

        try:
            return key in self.common_objects[name]
        except KeyError:
            return False
    
    def getCommonObject(self, name, key):

        assert self.inCommonObjectCache(name, key)
        
        return self.common_objects[name][key][1]

    def saveToCommonObjectCache(self, name, key, obj, persistent):

        name_cd = self.common_objects.setdefault(name, {})

        # Clear out non-persistent objects

        for key, (is_persistent, obj) in name_cd.items():
            if not is_persistent:
                del name_cd[key]
            
        name_cd[key] = (persistent, obj)


class DBWrapper(object):
    """
    A thin wrapper around an sqlalchemy database.
    """
    
    def __init__(self, dbfile):

        # Open the database
        self.engine   = create_engine('sqlite:///' + dbfile)
        self.metadata = MetaData()
        self.metadata.bind = self.engine
        
    def table(self, name, *columns, **kwargs):
        """
        Returns a reference to the table named `name`.  
        """
        t = Table(name, self.metadata, *columns, **kwargs)
        t.create(self.engine, checkfirst=True)
        
        return t
