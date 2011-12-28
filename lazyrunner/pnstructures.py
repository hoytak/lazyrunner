from treedict import TreeDict
from presets import applyPresets
from collections import defaultdict
from os.path import join
from pmodulelookup import *

class _PNSpecBase(object):
    pass

class Direct(_PNSpecBase):

    def __init__(self, name):
        self.name = name.lower()

    def _getParameters(self, raw_parameters):
        return raw_parameters

    def _getLoadName(self):
        return self.name
    

class Delta(_PNSpecBase):
    """
    Encodes a change to the current parameter tree and some
    results/module coming from that change.

    `Delta` is initialized with 1 required parameter and 4 optional
    parameters.  `p_name` is required and gives the module name of the
    results or module requested.  `local_delta` is a TreeDict instance
    that is applied to the parameter tree branch of the parameter tree
    corresponding to the requested dependency.  All the parameters
    present in the default parameter tree but not present in the given
    one are imported from the default.  Thus it is only necessary to
    specify modified parameters.

    If additional parts beyond the requested result/module branch need
    to be changed from the default, they can be specified using
    `delta`.  This has the same behavior as `local_delta`, except that
    modifications are specified from the root of the parameter tree
    rather than the branch associated with `p_name`.

    Alternatively, presets to be applied to the full parameter
    tree may be passed in using `apply_preset`.  `apply_preset`,
    if given, must be a single preset name or a list of valid
    preset names.  If a list, they are applied in order.

    Finally, if instances of `Delta` are used to specify result or
    module dependency, then `name` can be given to specify how that
    result can be accessed from the `results` or `modules` attribute
    in a processing module.  For example, specifying ``name = "sol_alt"``
    for the result dependencies causes these results to show up in
    ``self.results.sol_alt``.
    """
 
    def __init__(self, p_name, local_delta = None, delta = None, apply_preset = None, name = None):

        self.name = p_name.lower()
        self.local_delta = local_delta
        self.delta = delta
        self.apply_preset = apply_preset
        self.load_name = name

    def _getParameters(self, raw_parameters):

        # First make a copy of the full parameter tree.
        pt = raw_parameters.copy()

        if self.delta is not None:
            pt.update(self.delta, protect_structure=False)

        if self.local_delta is not None:
            pt.makeBranch(self.name)
            pt[self.name].update(self.local_delta, protect_structure=False)

        if self.apply_preset is not None:
            if type(self.apply_preset) is str:
                applyPreset(pt, self.apply_preset)
            elif type(self.apply_preset) is list or type(self.apply_preset) is tuple:
                applyPreset(pt, *self.apply_preset)
            else:
                raise TypeError("apply_preset must be either string, list, or tuple (not %s)"
                                % str(type(self.apply_preset)))
        pt.run_queue = []

        return pt

    def _getLoadName(self):
        return self.load_name


################################################################################
# Stuff to manage the cache

class PNodeModuleCacheContainer(object):

    def __init__(self, pn_name, name, 
                 local_key, dependency_key,
                 specific_key = None,
                 is_disk_writable = True):

        self.__pn_name = pn_name
        self.__name = name
        self.__specific_key = specific_key
        self.__local_key = local_key
        self.__dependency_key = dependency_key
        self.__is_disk_writable = is_disk_writable
        self.__obj = None
        self.__obj_is_loaded = False
        self.__disk_save_hook = None

    def getFilename(self):

        def v(t):
            return str(t) if t is not None else "null"
        
        return join(v(self.__pn_name), v(self.__name),
                    "%s-%s-%s.dat" % (v(self.__local_key), v(self.__dependency_key),
                                      v(self.__specific_key)) )

    def getKeyAsString(self):
        return '-'.join( (str(t) if t is not None else "N")
                         for t in [self.__pn_name, self.__name,
                                   self.__local_key,
                                   self.__dependency_key,
                                   self.__specific_key])
        

    def getCacheKey(self):
        # The specific cache
        return (self.__pn_name, self.__local_key, self.__dependency_key)

    def getObjectKey(self):
        return (self.__name, self.__specific_key)

    def setObject(self, obj):
        assert not self.__obj_is_loaded
        self.__obj_is_loaded = True
        self.__obj = obj

        if self.__disk_save_hook is not None:
            self.__disk_save_hook(self)

    def setObjectSaveHook(self, hook):
        self.__disk_save_hook = hook        
    
    def getObject(self):
        assert self.__obj_is_loaded
        return self.__obj

    def objectIsLoaded(self):
        return self.__obj_is_loaded

    def disableDiskWriting(self):
        self.__is_disk_writable = False
        self.__disk_save_hook = None
         


class PNodeModuleCache(object):

    def __init__(self):
        self.access_count = 0
        self.cache = {}

# This class holds the runtime environment for the pnodes
class PNodeCommon(object):

    def __init__(self, manager):
        self.manager = manager

        # Holds common objects
        self.common_objects = {}

        # This is for node filtering, i.e. eliminating duplicates
        self.pnode_lookup = {}

        # This is for cache lootup
        self.cache_lookup = defaultdict(PNodeModuleCache)
        
    def filterPNode(self, pn):
        
        # also do all the registering
        is_module = ( pn.p_type == "module" )

        try:
            self.module_common[pn.name].access_count += 1
        except KeyError:
            self.module_common[pn.name] = PNodeModuleCache()

        # see if it's a duplicate
        key = (pn.name, pn.key)

        if key in self.pnode_lookup:

            pnf = self.pnode_lookup[key]

            if is_module:

                # upgrade the existing one
                pnf.p_type = "module"
                
            pnf.reference_count += 1
            return pnf
        
        else:
            self.pnode_lookup[key] = pn
            return pn

    def _getCache(self, pn, use_local, use_dependencies):
        
        key = (pn.name if pn is not None else None,
               pn.local_key if use_local else None,
               pn.dependency_hash if use_dependencies else None)

        return self.cache_lookup[key]

    def increaseReference(self, pn):

        for t in [(None, False, False),
                  (pn, True, False),
                  (pn, False, True),
                  (pn, False, False),
                  (pn, True, True)]:

            cache = self._getCache(*t)
            cache.reference_count += 1

    def decreaseReference(self, pn):

        for t in [(None, False, False),
                  (self, True, False),
                  (self, False, True),
                  (self, False, False),
                  (self, True, True)]:
            
            cache = self._getCache(*t)
            cache.reference_count -= 1

            assert cache.reference_count >= 0

            # Clear the cache if it's no longer needed
            if cache.reference_count == 0:
                cache.cache = {}

    def loadContainer(self, container):

        assert not container.objectIsLoaded()

        cache = self.cache_lookup[container.getCacheKey()].cache

        obj_key = container.getObjectKey()

        if obj_key in cache:
            return cache[obj_key]
        else:
            cache[obj_key] = container

        # now see if it can be loaded from disk
        self.manager._loadFromDisk(container)

        return container

    def _debug_referencesDone(self):
        for pn in self.pnode_lookup.itervalues():
            assert pn.reference_count == 0, pn.reference_count

        for t in [(None, False, False),
                  (self, True, False),
                  (self, False, True),
                  (self, False, False),
                  (self, True, True)]:
            
            cache = self._getCache(*t)
            assert cache.reference_count == 0, cache.reference_count


class PNode(object):

    def __init__(self, common, parameters, name, p_type):

        self.common = common
        self.parameters = parameters.copy()
        self.parameters.attach(recursive = True)
        
        self.name = name
        self.p_type = p_type
        self.is_pmodule = isPModule(name)

        if p_type in ["module", "results"]:

            if not self.is_pmodule:
                raise ValueError("%s is not a recognized processing module." % name)
        else:
            if p_type != "parameters":
                raise ValueError("p_type must be either 'module', 'results', or 'parameters'.")

        ##################################################
        # Get the preprocessed parameters

        if name not in self.parameters:
            self.parameters.makeBranch(name)

        if self.is_pmodule:

            p_class = self.p_class = getPModuleClass(self.name)
            
            try:
                p = p_class.preprocessParameters(self.parameters[name])
            except TypeError:
                p = p_class.preprocessParameters(self.parameters[name], self.parameters)
                
            if p is not None:
                self.parameters[name] = p

            h = hashlib.md5()
            h.update(str(p_class._getVersion))
            h.update(self.parameters.hash(name))

            self.local_key = base64.b64encode(h.digest(), "az")[:8]

            self.is_disk_writable = p_type._allowsCaching()
            
        else:
            self.local_key = self.parameters.hash(name)
            self.is_disk_writable = False

        self.full_hash = self.parameters.hash()
        self.reference_count = 1
        self.module = None
        self.results_container = None
        self.results_reported = False
        self.child_pull_dict = {}


    def initialize(self):
        # This extra step is needed as the child pnodes must be
        # consolidated into the right levels first

        if not self.is_pmodule:
            return

        # get the verbatim children specifications and lists of
        # dependencies
        m_dep, r_dep, p_dep = self.p_class._getDependencies(self.parameters)

        # these are (name, hash) : pnode dicts
        self.module_dependencies = self._processDependencySet("module", m_dep)
        self.result_dependencies = self._processDependencySet("result", r_dep)
        self.parameter_dependencies = self._processDependencySet("parameter", p_dep)

        # Now go through and push the dependencies down
        self.result_dependencies.update(self.module_dependencies)
        self.parameter_dependencies.update(self.result_dependencies)

        # Go through and instantiate all the children
        for n, pn in self.result_dependencies.itervalues():
            pn.instantiateChildren()

        # Now go through and eliminate duplicates
        for k, (n, pn) in self.result_dependencies.items():
            pnf = self.common.filterPNode(pn)

            if pnf is not pn:

                self.result_dependencies[k] = (n, pnf)

                if k in self.module_dependencies:
                    self.module_dependencies[k] = (n, pnf)

        # don't need to propegate parameter dependencies to children,
        # computing the hash as well
        h = hashlib.md5()

        for n, th in sorted(self.parameter_dependencies.iterkeys()):
            h.update(n)
            h.update(th)
        
        for (n, th), (ln, pn) in sorted(self.result_dependencies.iteritems()):
            h.update(n)
            h.update(pn.key)

        self.dependency_hash = base64.b64encode(h.digest(), "az")[:8]

        h.update(self.local_key)
        
        self.key = base64.b64encode(h.digest(), "az")[:8]

        return self.key

    def _processDependencySet(self, p_type, dl):

        rs = {}

        def add(s, parameters, first_order, name_override):

            t = type(s)

            if t is str:
                pn = PNode(self.common, parameters, s, p_type)

                n = name_override if name_override is not None else pn.name

                h = self.full_hash if parameters is self.parameters else parameters.hash()
                
                rs[(s, h)] = (n if first_order else None, pn)
                
            elif t is list or t is tuple or t is set:
                for se in s:
                    add(se, parameters, first_order, name_override)

            elif isinstance(s, _PNSpecBase):
                add(s.name, s._getParameters(parameters), False, s._getLoadName())
                
            else:
                raise TypeError("Dependency type not recognized.")

        add(dl, self.parameters, True, None)

        return rs

    def _loadResults(self):
        # returns True on success, otherwise need to go with _instanciateModuleAndResults
        
        if self.results_container is None:
            self.results_container = PNodeModuleCacheContainer(
                pn_name = self.name,
                name = "__results__",
                local_key = self.local_key,
                dependency_key = self.dependency_key,
                is_disk_writable = self.is_disk_writable and self.p_type._allowsResultCaching())

        if not self.results_container.objectIsLoaded():
            self.results_container = self.common.loadContainer(self.results_container)

        return self.results_container.objectIsLoaded()

    def _instanciateModuleAndResults(self):

        if self.module is not None:
            assert self.results_container is not None
            return

        if self.results_container is None:
            have_loaded_results = self._loadResults()
        else:
            have_loaded_results = self.results_container.objectIsLoaded()

        m_class = getPModuleClass(self.name)

        # Create the dependency parts
        self.child_pull_dict = {}

        modules = TreeDict()
        for k, (load_name, pn) in self.module_dependencies.iteritems():
            params[load_name], results[load_name], modules[load_name] = \
                               self.child_pull_dict[k] = pn.pullUpToModule()
        modules.freeze()

        results = TreeDict()
        for k, (load_name, pn) in self.result_dependencies.iteritems():
            if k in self.child_pull_dict:
                params[load_name], results[load_name], junk = self.child_pull_dict[k]
            else:
                params[load_name], results[load_name] = p, r = pn.pullUpToResults()
                self.child_pull_dict[k] = (p, r, None)
        results.freeze()
        
        # parameters are easy
        params = TreeDict()
        for k, (load_name, pn) in self.parameter_dependencies.iteritems():
            if k in self.child_pull_dict:
                params[load_name] = self.child_pull_dict[k][0]
            else:
                params[load_name] = p = pn.pullParameters()
                self.child_pull_dict[k] = (p, None, None)
        params.freeze()

        # Now instantiate the module
        self.module = m = self.p_class(self, params, results, modules)

        if not have_loaded_results:
            r = m.run()
            if type(r) is TreeDict:
                r.freeze()
            self.results_container.setObject(r)

        m._setResults(self.results_container.getObject())
        
    def _reportResults(self, results):

        if not self.results_reported:

            try:
                self.p_class.reportResults(self.parameters, self.parameters[self.name], results)
            except TypeError, te:

                rrf = self.p_class.reportResults

                def raiseTypeError():
                    raise TypeError(("reportResults method in '%s' must be @classmethod "
                                    "and take global parameter tree, local parameter tree, "
                                    "and result tree as arguments.") % name)

                # See if it was due to incompatable signature
                try:
                    from inspect import getcallargs
                except ImportError:
                    if "reportResults" in str(te):
                        raiseTypeError()
                    else:
                        raise te

                try:
                    getcallargs(rrf, parameters, p, r)
                except TypeError:
                    raiseTypeError()

                # Well, that wasn't the issue, so it's something internal; re-raise
                raise

        self.results_reported = True

    ##################################################
    # Interfacing stuff

    def _decreaseReferenceCount(self):
        assert self.reference_count >= 1

        self.reference_count -= 1

        # Don't need these any more
        if self.reference_count == 0:
            self.results_container = None
            self.module = None
            self.common.decreaseReference(self)
            self.child_pull_dict = {}

    def _doReferencePull(self):
        # Needed if we can load the results from cache, as nodes down
        # the tree no longer need the reference
        
        for load_name, pn in self.result_dependencies.itervalues():
            pn._doReferencePull()
            
        self._decreaseReferenceCount()
        
    def pullParameters(self):
        return self.parameters[self.name]

    def pullUpToResults(self):

        assert self.p_type in ["module", "results"]

        if self.results_container is None:
            success = self._loadResults()
            if not success:
                self._instanciateModuleAndResults()

        r = self.results_container.getObject()

        self._reportResults(r)

        ret = (self.parameters[self.name], r)

        self._decreaseReferenceCount()

        return ret

    def pullUpToModule(self):

        assert self.p_type == "module"

        if self.module is None:
            self._instanciateModuleAndResults()

        r = self.results_container.getObject()
        
        self._reportResults(r)

        ret = (self.parameters[self.name], r, self.module)

        self._decreaseReferenceCount()

        return ret

    ################################################################################
    # Loading cache stuff

    def getCacheContainer(self, obj_name, key, ignore_module, ignore_local,
                          ignore_dependencies, is_disk_writable, creation_function):

        container = PNodeModuleCacheContainer(
            pn_name = None if ignore_module else self.pn_name,
            name = obj_name,
            local_key = None if ignore_local else self.local_key,
            dependency_key = None if ignore_dependencies else self.dependency_key,
            specific_key = key,
            is_disk_writable = is_disk_writable and self.is_disk_writable)
            
        return self.common.loadContainer(container)
        
    def getSpecific(self, r_type, r):

        assert r_type in ["results", "module"]

        # first get the key

        if type(r) is str:
            name = r
            ptree = self.parameters
            key = self.full_hash
            
        elif isinstance(r, _PNSpecBase):
            name = r.name
            ptree = r._getParameters(self.parameters)
            key = ptree.hash()
            
        else:
            raise TypeError("Requested %s must be specified as a string or "
                            "as an instance of a _PNSpecBase class like 'Delta'.")

        lookup_key = (name, key)

        if lookup_key in self.child_pull_dict:
            params, results, module = self.child_pull_dict[lookup_key]

            if r_type
            
        # should return before now if everything is good
        self.p_type.log.warning( ("%s requested (%s) without being specified as "
                                  "a dependency; possible source of cache corruption.")
                                 % (r_type, name) )

        if r_type == "results":
            return self.manager.getResults(ptree, name)
        elif r_type == "module":
            return self.manager.getModule(ptree, name)
        else:
            assert False
            
