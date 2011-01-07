from copy import deepcopy, copy
import logging
from treedict import TreeDict
from pmodulelookup import getPModuleClass, isPModule
import re

_key_processing_re = re.compile('[0-9a-zA-Z_]+')
    
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
    def _getDependencySet(cls, parameters, dep_type):
        
        assert dep_type in ["result", "module", "parameter"]

        # Get the dependency set that this one builds on
        if dep_type == "parameter":
            dep_set = cls._getDependencySet(parameters, "result") | set([cls._name])
        elif dep_type == "result":
            dep_set = cls._getDependencySet(parameters, "module")
        else:
            dep_set = set()

        # Get the precise dependencies 
        dep_attr = dep_type + '_dependencies'

        def process_dependency(dl):
            if type(dl) is str:
                s = set([dl])
            elif type(dl) in [list, tuple, set]:
                s = set(dl)
            elif dl is None:
                s = set()
            else:
                raise TypeError("'%s' dependency type '%s' for module '%s' not understood"
                                % (dep_type, str(type(dl)), cls._name))

            return set(n.strip() for n in s if len(n.strip()) != 0)

        if hasattr(cls, dep_attr):
            dependency_function = getattr(cls, dep_attr)

            if type(dependency_function) in [list, tuple, set, str]:
                dep_set |= process_dependency(dependency_function)
            else:
                try:
                    dep_set |= process_dependency(dependency_function())
                except TypeError:
                    dep_set |= process_dependency(dependency_function(parameters))

        return dep_set

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
        
    ############################################################
    # Now the initializing and running functions
    def __init__(self, manager, key, parameters, setup_module):

        name = self._name
        
        self.manager = manager

        # Set the name of the local class
        self.__key = key

        self.log = self._getLogger()
	
	if setup_module:
	    self.log.info('Initializing Module %s.' % self._name)

        self.parameters = TreeDict()
        self.raw_parameters = parameters

        name = self._name

        self.p = self.manager.getPreprocessedBranch(parameters, name)
        self.parameters[name] = self.p

        for p_branch in self._getDependencySet(parameters, 'parameter'):
            self.parameters[p_branch] = self.manager.getPreprocessedBranch(parameters, p_branch)

        self.parameters.freeze()

        if setup_module:
            # self.results contains the results of all the modules
            # requested as dependencies.

            self.results = TreeDict('results')
        
            for r in self._getDependencySet(parameters, 'result'):
                self.results[r] = self.manager._getResults(parameters, r)

            self.results.freeze()

            # Instantiate dependent modules
            self.modules = TreeDict('modules')

            for m in self._getDependencySet(parameters, 'module'):
                self.modules[m] = self.manager._getModule(parameters, m)

            self.modules.freeze()

            # Now, call the per-class setup method
            self.setup()

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

    def __processKey(self, obj_name, key):

        if type(obj_name) is not str:
            raise TypeError("`obj_name` must be a string.")

        if key is not None:
            if type(key) is str and _key_processing_re(key) is not None:
                return obj_name + key
            else:
                return obj_name + TreeDict(key = key).hash()
        else:
            return obj_name

    def inCache(self, obj_name, key = None, ignore_local = False, ignore_dependencies = False):
        """
        Returns True if an object with key `obj_name` can be loaded
        from cache and False otherwise.

        If `key` is not None, a hash is taken of all the values in
        `key` and appended to `obj_name` to specify the name of the
        object.  This is an easy and robust way of specifying
        dependencies on parameters.  It can be almost any python
        object (the TreeDict hash() function is used to generate the
        hash).

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

        name = self.__processKey(obj_name, key)
        local_key_override = ("IGN" if ignore_local else None)
        dependency_key_override = ("IGN" if ignore_dependencies else None)
        
        return self.manager.inCache(self.__key, name, local_key_override, dependency_key_override)
                                    
    def loadFromCache(self, obj_name, key = None, ignore_local = False,
                      ignore_dependencies = False, create_function = None):
        """
        Loads the specific object from the cache if available.  If it
        is not available, a RuntimeError is raised.

        If `key` is not None, a hash is taken of all the values in
        `key` and appended to `obj_name` to specify the name of the
        object.  This is an easy and robust way of specifying
        dependencies on parameters.  It can be almost any python
        object (the TreeDict hash() function is used to generate the
        hash).

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

        If `create_function` is not None, and the object is not in
        cache, ``create_function()`` is called to create an instance
        of the object, which is then stored in cache and returned.
        For example, in the following code, the function ``create()``
        is called only if `listobj` is not in the cache::

          def run(self):

              # ...

              def create_listobj():
                  return [None]*self.p.list_length

              L = self.loadFromCache(\"listobj\", create_function = create_listobj)
        
        """

        name = self.__processKey(obj_name, key)
        
        self.log.debug("Trying to load %s from cache." % name)
        
        local_key_override = ("IGN" if ignore_local else None)
        dependency_key_override = ("IGN" if ignore_dependencies else None)

        if (create_function is not None
            and not self.manager.inCache(self.__key, name,
                local_key_override, dependency_key_override)):

            self.log.debug("%s not in cache; creating." % name)

            obj = create_function()
            self.manager.saveToCache(self.__key, name, obj,
                                     local_key_override, dependency_key_override)
            return obj
        
        return self.manager.loadFromCache(self.__key, obj_name,
            local_key_override, dependency_key_override)
        
        

    def saveToCache(self, obj_name, obj, key = None, ignore_local = False, ignore_dependencies = False):
        """
        Caches the specific object `obj` in the local cache.

        If `key` is not None, a hash is taken of all the values in
        `key` and appended to `obj_name` to specify the name of the
        object.  This is an easy and robust way of specifying
        dependencies on parameters.  It can be almost any python
        object (the TreeDict hash() function is used to generate the
        hash).

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
        """


        
        if type(obj_name) is not str:
            raise TypeError("`obj_name` must be a string.")

        if key is not None:
            obj_name += "-" + TreeDict(key = key).hash()

        self.log.debug("Saving object '%s' to cache" % obj_name)

        self.manager.saveToCache(self.__key, obj_name, obj,
                                 local_key_override = ("IGN" if ignore_local else None),
                                 dependency_key_override = ("IGN" if ignore_dependencies else None))
                                 

    def getSpecificResults(self, name, name_p = None, full_ptree = None):
        """
        Returns the results from p-module `name`, with the parameters
        local to `name` being given (possibly in part) by `name_p`.

        For example, if `p.mypmodule.a = 1` was given in the default
        parameter settings, specifying `mypmodule` in the result
        dependencies would cause `self.results.mypmodule` to hold the
        results from mypmodule run with `a = 1`.  However, suppose the
        results from mypmodule with `a = 2` were required.  Then calling::

          self.getSpecificResults('mypmodule', TreeDict(a = 2) )

        would return those results.  

        By default, all the parameters present in the default
        parameter tree but not present in the given one are imported
        from the default.  Thus it is only necessary to specify
        modified parameters.

        If additional parts of the `ptree` need to be changed from the
        default, they can be specified using `full_p`.  This has the
        same behavior as `name_p`, except that modifications are
        specified from the root of the parameter tree rather than the
        branch associated with `name`.
        """
        
        # First make a copy of the full parameter tree.

        pt = self.raw_parameters.copy()

        if full_ptree is not None:
            pt.update(full_ptree)

        name = name.lower()

        if name_p is not None:
            pt.makeBranch(name)
            pt[name].update(name_p)

        return self.manager.getResults(pt, name)

    def getCommonObject(self, name, key = None, creation_function = None,
                        obj = None, persistent = True):
        """
        Returns a common object, such as a processing object/class,
        that can be shared between parts of the program.  This object
        is not cached to disk, but can be shared in common between
        parts of the program.  An example could be an external solver
        that is setup the same across problem instances, but run in
        different ways across several methods.

        Note that the key here does not depend on any aspect of the
        parameter tree except possibly through the user specified
        `key`.  If `key` is None, it is taken to be the local key of
        the processing module (see :ref:`key`).

        If `creation_function` is given, it is called to create the
        object if it is not found in the common lookup table.
        Alternately, if `object` is given, then this object is
        inserted into the common lookups if it is not already present.

        If `persistent` is False (default True), then the object is
        deleted once another object with the same name is requested.
        """

        if key is None:
            key = self.key()

        if self.manager.inCommonObjectCache(name, key):
            return self.manager.getCommonObject(name, key)
        
        else:
            if creation_function is not None:
                obj = creation_function()
            
            self.manager.saveToCommonObjectCache(name, key, obj, persistent)

            return obj

    def key(self, ignore_local=False, ignore_dependencies=False):
        """
        Returns a unique string representing the state of the current
        processing module.  This string is a deterministic hash of the
        parameters, possibly including dependencies, for the
        processing module.  It's intended to be used for obtaining a
        key for use in methods such as :ref:`getCommonObject`.

        `ignore_dependencies` and `ignore_local` are handled in ways
        identical to the caching functions.
        """

        local_key_override = ("IGN" if ignore_local else None)
        dependency_key_override = ("IGN" if ignore_dependencies else None)

        return self.manager._getKeyAsString(
            self.__key, local_key_override, dependency_key_override)
