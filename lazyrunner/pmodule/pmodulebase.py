from copy import deepcopy, copy
import logging
from treedict import TreeDict
import re
from axisproxy import AxisProxy
    
class PModule:
    """
    The base class for a processing module.
    """

    @classmethod
    def name(cls):
        """
        A convenience function; returns the name of the class.
        """
        
        return cls._name

    @classmethod
    def preprocessParameters(cls, local_parameters):
        """
        Optionally, return a preprocessd version of the parameters with
        unneeded options removed.  This allows for a hash to be
        calculated that just works with relevant parameters.

        meant to be overwritten.
        """
        return local_parameters

    @classmethod
    def _preprocessParameters(cls, parameters):

        pb = parameters[cls._name]

        for t in [[], [pb], [pb,parameters.copy(freeze=True)]]:
            try:
                p = cls.preprocessParameters(*t)
                break
            except TypeError, te:

                if "preprocessParameters" in str(te):
                    continue
                else:
                    raise

        return p if p is not None else parameters[cls._name]

    @classmethod
    def _getDependencies(cls, parameters):
        
        def getDep(dep_type):

            # Get the precise dependencies 
            dep_attr = dep_type + '_dependencies'

            def process_dependency(dl):
                def wrong_type(s):
                    raise TypeError("'%s' dependency type '%s' for module '%s' not understood"
                                    % (dep_type, str(type(s)), cls._name))
                
                def clean(s):
                    if type(s) is str:
                        return s.strip().lower()
                    elif not getattr(s, "__parameter_container__", False):
                        wrong_type(s)
                    return s
                    
                if type(dl) is str or getattr(dl, "__parameter_container__", False):
                    s = [dl]
                elif type(dl) in [list, tuple, set]:
                    s = list(dl)
                elif dl is None:
                    s = []
                else:
                    wrong_type(dl)
                    
                s = [clean(se) for se in s]

                return [se for se in s if se != ""]

            if hasattr(cls, dep_attr):
                dependency_function = getattr(cls, dep_attr)

                if type(dependency_function) in [list, tuple, set, str]:
                    return process_dependency(dependency_function)

                null_ = "_null_"

                deps = null_
                
                pb = parameters[cls._name]
                
                for t in [[], [pb], [pb,parameters]]:
                    try:
                        deps = dependency_function(*t)
                        break
                    except TypeError, te:

                        if dep_attr in str(te):
                            continue
                        else:
                            raise

                if deps is null_:
                    raise TypeError(("%s() for %s must be a string, list, tuple, set or "
                                     "take either no parameters, the local parameter "
                                     "tree, or the local and global parameter trees.")
                                    % (dep_attr, cls._name))

                
                return process_dependency(deps)   

            else:
                return []

        mod_dep = getDep("module")
        res_dep = getDep("result")
        par_dep = getDep("parameter")

        return (mod_dep, res_dep, par_dep)
        

    @classmethod
    def _getVersion(cls):
        """
        Returns a number indicating the version of the pmodule for
        caching purposes.
        """
        
        if hasattr(cls, "version"):
            return cls.version
        else:
            return None

    @classmethod
    def _getLogger(cls):
        """
        Returns the logger associated with the given manager.  Note
        that this is available to subclasses as `self.log` or class
        methods as `cls.log` (the log attribute is given to the module
        by the pmodule decorator)
        """
        
        return logging.getLogger(cls._name)

    @classmethod
    def __getBinaryAttr(self, attr, parameters):
        
        x = getattr(self, attr)

        if x in [True, False]:
            return x
        else:
            pb = parameters[self._name]

            for t in [[], [pb], [pb, parameters]]:
                try:
                    ret = x(*t)
                    break
                except TypeError, te:

                    if attr in str(te):
                        continue
                    else:
                        raise

            if ret not in [True, False]:
                raise TypeError("'%s' must evaluate to or "
                                "return True or False." % attr)
            return ret        

    @classmethod
    def _allowsResultCaching(self, parameters):
        if not self._allowsCaching(parameters):
            return False

        if hasattr(self, "disable_results_caching"):
            return not self.__getBinaryAttr("disable_results_caching", parameters)
        elif hasattr(self, "disable_result_caching"):
            return not self.__getBinaryAttr("disable_result_caching", parameters)
        else:
            return True
            
    @classmethod
    def _allowsCaching(self, parameters):
        if hasattr(self, "disable_caching"):
            return not self.__getBinaryAttr("disable_caching", parameters)
        else:
            return True

    def _setResults(self, r):
        self.local_results = r

    def _destroy(self):

        # makes the the GC easier

        del self.local_results
        del self.modules
        del self.results
        del self.parameters
        del self.p
        self.__container_map.clear()

        self.log.debug("Module %s destroyed." % self._name)

        self._pnode = None
        
    ############################################################
    # Now the initializing and running functions
    def __init__(self, pnode, parameters, results, modules):

        name = self._name
        
        self._pnode = pnode

        self.log.info('Initializing Module %s.' % self._name)

        self.parameters = parameters
        self.p = parameters[self._name]
        self.results = results
        self.modules = modules

        self.__container_map = {}

        # Now, call the per-class setup method
        self.setup()

        self.log.debug("Module %s set up." % self._name)

    # The setup function; in case it's not needed
    def setup(self):
        """
        `setup()` is called whenever the processing module is
        initialized, regardless of whether the results are requested
        or not.  It is the proper place to put all code that sets up
        the module and is needed to be accessed from other modules

        Any return value is discarded.

        Note that :ref:`run` is called only if matching results are
        not in the cache.
        """
        
        pass

    @classmethod
    def reportResults(cls, parameters, p, r):
        """
        Called after results are either loaded from cache or produced
        by :ref:`run` to allow for reporting information about the
        results to the log.  Since this method is a class method, it
        cannot depend on :ref:`setup` or :ref:`run`.

        `parameters` is the full parameter tree, `p` is the branch of
        the parameter tree specific to this module, and `r` is the
        result tree produced by a previous call to `run` or loaded
        from cache.

        Note that results should normally be reported using the class
        attribute `cls.log`.
        """
        
	cls.log.debug("Null Result Reporting function for %s." % cls._name)
        
        pass
        
    def run(self):
        """
        The primary method to produce results.  It may return either
        None (no results produced) or a TreeDict instance with the
        results stored in it.  This TreeDict instance is saved to the
        cache if caching is enabled.

        If the class attribute `disable_results_caching` is set to
        True, or the return result is None, then the results are never
        saved to cache and this method is always called when results
        from the module are requested.  Otherwise, they are loaded
        from cache if possible.
        """
        
        pass

    ############################################################
    # Hash stuff

    def itemHash(self, *items):
	"""
	Returns a hash of arbitrary items.  This is intended to be
	used for fine-grained control of dependencies on parameters;
	the resulting value can passed to :ref:`inCache`,
	:ref:`loadFromCache`, and :ref:`saveToCache`.  For example::

          key = self.itemHash(self.p.x1, self.p.x2)

          if self.inCache(key):
              return self.loadFromCache(key)
          else:
              # process, create obj

              self.saveToCache(key, obj)

        Note that most of this functionality is provided by specifying
        `items` as a tuple to the key argument of :ref:inCache,
        :ref:loadFromCache, or :ref:saveToCache.
        
	"""

	t = TreeDict()

	for n, it in enumerate(items):
	    t["b%d" % n] = it

	return t.hash()

    def _cacheAction(self, action,
                     obj_name, key,
                     ignore_module,
                     ignore_local,
                     ignore_dependencies,
                     is_disk_writable,
                     is_persistent,
                     creation_function = None,
                     obj = None):

        if key is not None:
            key = TreeDict(key = key).hash()

        d_key = (obj_name, key, ignore_module, ignore_local,
                 ignore_dependencies, is_persistent)

        try:
            container = self.__container_map[d_key]
        except KeyError:
            container = self.__container_map[d_key] = self._pnode.getCacheContainer(
                obj_name, key, ignore_module, ignore_local,
                ignore_dependencies, is_disk_writable, is_persistent)

        if not is_disk_writable:
            container.disableDiskWriting()

        if action == "query":
            return container.objectIsLoaded()
        elif action == "load":
            if not container.objectIsLoaded():
                if creation_function is None:
                    raise RuntimeError(
                        "creation_function must be supplied if the "
                        "object is not available in the cache.")
                
                container.setObject(creation_function())
                
            return container.getObject()
        
        elif action == "save":
            container.setObject(obj)

        elif action == "key":
            return container.getKeyAsString()
        
        else:
            assert False

    def inCache(self, obj_name, key = None,
                ignore_module = False,
                ignore_local = False,
                disk_writable = True,
                ignore_dependencies = False):
        """
        Returns True if an object with key `obj_name` can be loaded
        from cache and False otherwise.

        If `key` is not None, a hash is taken of all the values in
        `key` and appended to `obj_name` to specify the name of the
        object.  This is an easy and robust way of specifying
        dependencies on parameters.  It can be almost any python
        object (the TreeDict hash() function is used to generate the
        hash).
        
        If `ignore_module` is True, then the specific module is
        ignored when caching the object.  This can be used for sharing
        objects between modules (when the existing dependency system
        is inadequate).

        If `ignore_local` is True, then the local branch of the
        central parameter tree is ignored in calculating the
        dependencies. This allows for fine-grained control over which
        local parameters the object depends on.  For example, perhaps
        an object only depends on the local parameters `x` and `y` and
        results from another module.  The proper way to query such an
        object would be::

          self.inCache(\"myobj\", ignore_local = True, key = (self.p.x, self.p.y))

        If `ignore_dependencies` is True, then the parameters (and
        PModule versions) of all specified dependencies are ignored
        when generating the key for the queried object.  For example,
        if an object only depends on the values of the local parameter
        branch and is independent of the results of dependent modules,
        then it can be stored and loaded from cache more frequently by
        specifying ``ignore_dependencies=True``).
     
        """

        return self._cacheAction("query", obj_name, key, ignore_module,
                                 ignore_local, ignore_dependencies, True, True)
                                        
    def loadFromCache(self, obj_name, key = None,
                      ignore_module = False,
                      ignore_local = False,
                      ignore_dependencies = False,
                      disk_writable = True,
                      persistent = True,
                      creation_function = None):
        """
        Loads the specific object from the cache if available.  If it
        is not available, a RuntimeError is raised.

        If `key` is not None, a hash is taken of all the values in
        `key` and appended to `obj_name` to specify the name of the
        object.  This is an easy and robust way of specifying
        dependencies on parameters.  It can be almost any python
        object (the TreeDict hash() function is used to generate the
        hash).

        If `ignore_module` is True, then the specific module is
        ignored when caching the object.  This can be used for sharing
        objects between modules (when the existing dependency system
        is inadequate).

        If `ignore_local` is True, then the local branch of the
        central parameter tree is ignored in calculating the
        dependencies. This allows for fine-grained control over which
        local parameters the object depends on.  For example, perhaps
        an object only depends on the local parameters `x` and `y` and
        results from another module.  The proper way to load such an
        object would be::

          self.loadFromCache(\"myobj\", ignore_local = True,
                             key = (self.p.x, self.p.y))

        If `ignore_dependencies` is True, then the parameters (and
        PModule versions) of all specified dependencies are ignored
        when generating the key for the requested object.  For
        example, if an object only depends on the values of the local
        parameter branch and is independent of the results of
        dependent modules, then it can be stored and loaded from cache
        more frequently by specifying ``ignore_dependencies=True``).
        If `persistent` is False, then only one objects with the
        given name ever held in the in-memory cache at a single time.
        If `ignore_module` is True, this holds across modules,
        otherwise, it holds only within this module.

        If `disk_writable` is False, then only the internal memory
        cache is used; the object is never written to disk.

        If `creation_function` is not None, and the object is not in
        cache, ``creation_function()`` is called to create an instance
        of the object, which is then stored in cache and returned.
        For example, in the following code, the function ``create()``
        is called only if `listobj` is not in the cache::

          def run(self):

              # ...

              def create_listobj():
                  return [None]*self.p.list_length

              L = self.loadFromCache(\"listobj\", creation_function = create_listobj)
              
        """

        return self._cacheAction("load", obj_name, key, ignore_module,
            ignore_local, ignore_dependencies, disk_writable,
            persistent, creation_function = creation_function)
        
    def saveToCache(self, obj_name, obj,
                    key = None,
                    ignore_module = False,
                    ignore_local = False,
                    ignore_dependencies = False,
                    persistent = True,
                    disk_writable = True):
        """
        Caches the specific object `obj` in the local cache.

        If `key` is not None, a hash is taken of all the values in
        `key` and appended to `obj_name` to specify the name of the
        object.  This is an easy and robust way of specifying
        dependencies on parameters.  It can be almost any python
        object (the TreeDict hash() function is used to generate the
        hash).

        If `ignore_module` is True, then the specific module is
        ignored when caching the object.  This can be used for sharing
        objects between modules (when the existing dependency system
        is inadequate).

        If `ignore_local` is True, then the local branch of the
        central parameter tree is ignored in calculating the
        dependencies. This allows for fine-grained control over which
        local parameters the object depends on.  For example, perhaps
        an object only depends on the local parameters `x` and `y` and
        results from another module.  The proper way to save such an
        object to the cache would be::

          self.saveToCache(\"myobj\", ignore_local = True,
                           key = (self.p.x, self.p.y))

        If `ignore_dependencies` is True, then the parameters (and
        PModule versions) of all specified dependencies are ignored
        when generating the key for the requested object.  For
        example, if an object only depends on the values of the local
        parameter branch and is independent of the results of
        dependent modules, then it can be saved and loaded from cache
        more frequently by specifying ``ignore_dependencies=True``).

        If `persistent` is False, then only one objects with the
        given name ever held in the in-memory cache at a single time.
        If `ignore_module` is True, this holds across modules,
        otherwise, it holds only within this module.

        If `disk_writable` is False, then only the internal memory
        cache is used; the object is never written to disk.
        """

        return self._cacheAction(
            "save", obj_name, key, ignore_module, ignore_local,
            ignore_dependencies, disk_writable, persistent, obj=obj)

    def key(self, obj_name = None,
            key = None,
            ignore_module = False,
            ignore_local = False,
            ignore_dependencies = False):
        """
        Returns a unique string representing the state of the current
        processing module or a certain object.  This string is a
        deterministic hash of the parameters, possibly including
        dependencies, for the processing module.  

        """

        return self._cacheAction("key", "__null__" if obj_name is None else obj_name,
                                 key, ignore_module, ignore_local,
                                 ignore_dependencies, True, True)
        
    def getParameters(self, n):
        """
        Returns the parameter tree specified
        """

        return self._pnode.getSpecific("parameters", n)

    def getResults(self, r):
        """
        Returns the results from r 
        """

        return self._pnode.getSpecific("results", r)

    def getModule(self, m):
        """

        """

        return self._pnode.getSpecific("module", m)

    
