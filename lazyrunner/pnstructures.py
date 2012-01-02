from treedict import TreeDict
from presets import applyPreset
from collections import defaultdict
from os.path import join
from pmodulelookup import *
import hashlib, base64, weakref, sys, gc
from itertools import chain

results_weak_lookup = weakref.WeakValueDictionary()
tn_counter = 0

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
    results or module requested.  `local_delta` is a TreeDict instanc   e
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

        self.name = p_name.lower().strip()
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
                 is_disk_writable = True,
                 is_persistent = True):

        self.__pn_name = pn_name
        self.__name = name
        self.__specific_key = specific_key
        self.__local_key = local_key
        self.__dependency_key = dependency_key
        self.__is_disk_writable = is_disk_writable
        self.__is_non_persistent = not is_persistent
        self.__obj = None
        self.__obj_is_loaded = False
        self.__disk_save_hook = None
        self.__non_persistent_hook = None

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

    def isNonPersistent(self):
        return self.__is_non_persistent

    def getNonPersistentKey(self):
        assert self.__is_non_persistent
        return (self.__pn_name, self.__name)

    def setObject(self, obj):
        assert not self.__obj_is_loaded
        self.__obj_is_loaded = True
        self.__obj = obj

        if self.__disk_save_hook is not None:
            self.__disk_save_hook(self)
            self.__disk_save_hook = None

        if self.__non_persistent_hook is not None:
            self.__non_persistent_hook(self)
            self.__non_persistent_hook = None

    def isLocallyEqual(self, pnc):
        return self.__name == pnc.__name and self.__specific_key == pnc.__specific_key

    def setObjectSaveHook(self, hook):
        self.__disk_save_hook = hook

    def setNonPersistentObjectSaveHook(self, hook):
        assert self.__is_non_persistent
        self.__non_persistent_hook = hook
    
    def getObject(self):
        assert self.__obj_is_loaded
        return self.__obj

    def objectIsLoaded(self):
        return self.__obj_is_loaded

    def disableDiskWriting(self):
        self.__is_disk_writable = False
        self.__disk_save_hook = None
         
    def isDiskWritable(self):
        return self.__is_disk_writable

    def objRefCount(self):
        return sys.getrefcount(self.__obj)

class PNodeModuleCache(object):

    def __init__(self):
        self.reference_count = 0
        self.cache = {}

class _PNodeNonPersistentDeleter(object):
    
    def __init__(self, common):
        self.common = common
        
    def __call__(self, container):
        np_key = container.getNonPersistentKey()

        try:
            old_container = self.common.non_persistant_pointer_lookup[np_key]
        except KeyError:
            old_container = None

        if old_container is not None:
            try:
                del self.common.cache_lookup[old_container.getCacheKey()].cache[old_container.getObjectKey()]
            except KeyError:
                pass

        self.common.non_persistant_pointer_lookup[np_key] = container
              

# This class holds the runtime environment for the pnodes
class PNodeCommon(object):

    def __init__(self, manager):
        self.manager = manager

        # This is for node filtering, i.e. eliminating duplicates
        self.pnode_lookup = weakref.WeakValueDictionary()

        self.non_persistant_pointer_lookup = weakref.WeakValueDictionary()
        self.non_persistant_deleter = _PNodeNonPersistentDeleter(self)

        # This is for cache lootup
        self.cache_lookup = defaultdict(PNodeModuleCache)
        

    def getResults(self, parameters, names):

        def getPN(n):
            if type(n) is not str:
                raise TypeError("Module name not a string.")
            
            pn = PNode(self, parameters, n, 'results')
            pn.initialize()
            pn = self.registerPNode(pn)
            pn.increaseResultReference()
            return pn
        
        if type(names) is str:
            r = getPN(names).pullUpToResults()[-1]
        elif type(names) in [list, tuple]:
            r = [getPN(n).pullUpToResults()[-1] for n in names]
        else:
            raise TypeError("Names must be a string or list/tuple of strings.")

        from guppy import hpy
        h=hpy()
        hp = h.heap()

        print "#"*80
        
        print hp

        print "#"*40

        print hp.bytype[0].byvia
        print hp.bytype[0].byvia.more

        print "#"*40
        print "hp.bytype[0].byrcs"

        print hp.bytype[0].byrcs
        print hp.bytype[0].byrcs.more

        print "#"*40
        print "hp.bytype[0].byrcs[0].bysize"

        print hp.bytype[0].byrcs[0].bysize
        print hp.bytype[0].byrcs[0].bysize[0].byrcs

        print "#"*40
        print "hp.bytype[0].byclodo"
 
        print hp.bytype[0].byclodo
        print hp.bytype[0].byclodo.more

        print "#"*40

        print h.heapu()

        print "*"*80
        print "Number of items in cache = ", sum([len(cache.cache) for cache in self.cache_lookup.itervalues()])
        print "Number of PNodes in existance =", len(self.pnode_lookup)

        return r
        
    def registerPNode(self, pn):

        # see if it's a duplicate
        key = (pn.name, pn.key)

        if key in self.pnode_lookup:
            
            pnf = self.pnode_lookup[key]
            if not pn.is_only_parameter_dependency:
                pnf.is_only_parameter_dependency = False
            pn = pnf
            
        else:
            self.pnode_lookup[key] = pn
            
        pn.buildReferences()
            
        return pn

    def _getCache(self, pn, use_local, use_dependencies, should_exist):
        
        key = (pn.name if pn is not None else None,
               pn.local_key if use_local else None,
               pn.dependency_key if use_dependencies else None)

        if should_exist:
            assert key in self.cache_lookup

        return key, self.cache_lookup[key]

    def increaseCachingReference(self, pn):

        # print ("increasing reference, name = %s, key = %s, local_key = %s, dep_key = %s"
        #        % (pn.name, pn.key, pn.local_key, pn.dependency_key))

        for t in [(None, False, False),
                  (pn, True, False),
                  (pn, False, True),
                  (pn, False, False),
                  (pn, True, True)]:

            key, cache = self._getCache(*(t + (False,)))
            cache.reference_count += 1

    def decreaseCachingReference(self, pn):

        # print ("decreasing reference,  name = %s, key = %s, local_key = %s, dep_key = %s"
        #        % (pn.name, pn.key, pn.local_key, pn.dependency_key))

        for t in [(None, False, False),
                  (pn, True, False),
                  (pn, False, True),
                  (pn, False, False),
                  (pn, True, True)]:
            
            key, cache = self._getCache(*(t + (True,)))
            cache.reference_count -= 1

            assert cache.reference_count >= 0

            # Clear the cache if it's no longer needed
            if cache.reference_count == 0:
                # if len(cache.cache) != 0:
                #     print "Clearing cache %s. objects in the cache are:" % str(key)

                #     for v in cache.cache.itervalues():
                #         print "%s: ref_count = %d" % (v.getObjectKey(), v.objRefCount())
                
                del self.cache_lookup[key]

    def loadContainer(self, container, no_local_caching = False):

        assert not container.objectIsLoaded()

        if not no_local_caching:
            cache = self.cache_lookup[container.getCacheKey()]
            c = cache.cache

            obj_key = container.getObjectKey()

            if obj_key in c:
                return c[obj_key]
            else:
                c[obj_key] = container

            if container.isNonPersistent():
                container.setNonPersistentObjectSaveHook(self.non_persistant_deleter)

        # now see if it can be loaded from disk
        self.manager._loadFromDisk(container)

        return container

    def _debug_referencesDone(self):
        import gc
        gc.collect()

        print "**************** running check*****************"

        for pn in self.pnode_lookup.values():
            if pn.result_reference_count != 0 or pn.module_reference_count != 0 or pn.module_access_reference_count != 0:
                
                print (("Nonzero references, (%d, %d, %d), name = %s, key = %s, "
                        "local_key = %s, dep_key = %s")
                       % (pn.result_reference_count, pn.module_reference_count, pn.module_access_reference_count,
                          pn.name, pn.key,
                          pn.local_key, pn.dependency_key))

            for t in [(None, False, False),
                      (pn, True, False),
                      (pn, False, True),
                      (pn, False, False),
                      (pn, True, True)]:

                key, cache = self._getCache(*(t + (False,)))

                if cache.reference_count != 0:

                    print (("Nonzero (%d) cache reference, name = %s, key = %s, "
                            "local_key = %s, dep_key = %s")
                           % (cache.reference_count,
                              "null" if t[0] is None else pn.name,
                              pn.key,
                              "null" if not t[1] else pn.local_key,
                              "null" if not t[2] else pn.dependency_key))

            if hasattr(pn, "module") and pn.module is not None:

                print (("Non-None module, (%d, %d, %d), name = %s, key = %s, "
                        "local_key = %s, dep_key = %s")
                       % (pn.result_reference_count, pn.module_reference_count, pn.module_access_reference_count,
                          pn.name, pn.key,
                          pn.local_key, pn.dependency_key))

            if hasattr(pn, "results_container") and pn.results_container is not None:

                print (("Non-None results, (%d, %d, %d), name = %s, key = %s, "
                        "local_key = %s, dep_key = %s")
                       % (pn.result_reference_count, pn.module_reference_count, pn.module_access_reference_count,
                          pn.name, pn.key,
                          pn.local_key, pn.dependency_key))
                
            if hasattr(pn, "child_pull_dict"):

                print (("Child pull dict bad!!!, (%d, %d, %d), name = %s, key = %s, "
                        "local_key = %s, dep_key = %s")
                       % (pn.result_reference_count, pn.module_reference_count, pn.module_access_reference_count,
                          pn.name, pn.key,
                          pn.local_key, pn.dependency_key))

_Null = "null"

class PNode(object):

    def __init__(self, common, parameters, name, p_type):

        self.common = common
        self.parameters = parameters.copy()
        self.parameters.attach(recursive = True)
        self.name = name

        self.is_pmodule = isPModule(name)

        if p_type in ["module", "results"]:

            if not self.is_pmodule:
                raise ValueError("%s is not a recognized processing module." % name)
        else:
            if p_type != "parameters":
                raise ValueError( ("p_type must be either 'module', 'results', "
                                   "or 'parameters' (not '%s').") % p_type)

        # Parameters don't hold references to other objects
        self.is_only_parameter_dependency = (p_type == "parameters") 

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

            self.parameter_key = self.parameters.hash(name)

            h = hashlib.md5()
            h.update(str(p_class._getVersion()))
            h.update(self.parameter_key)
            
            self.local_key = base64.b64encode(h.digest(), "az")[:8]

            self.is_disk_writable = p_class._allowsCaching(self.parameters)
            self.module = None
            self.results_container = None
            self.results_reported = False
            self.full_key = self.parameters.hash()

            # Reference counting isn't used in the parameter classes
            self.result_reference_count = 0
            self.module_reference_count = 0
            self.module_access_reference_count = 0
            self.dependent_modules_pulled = False
            self.children_have_reference = False
            self.additional_module_nodes_accessed = []
            
        else:
            self.parameter_key = self.parameters.hash(name)

    ########################################
    # Setup

    def initialize(self):
        # This extra step is needed as the child pnodes must be
        # consolidated into the right levels first

        assert self.is_pmodule

        def _processDependencySet(p_type, dl):

            rs = {}

            def add(s, parameters, first_order, name_override):

                t = type(s)

                if t is str:
                    if s != self.name:

                        pn = PNode(self.common, parameters, s, p_type)

                        h = self.full_key if parameters is self.parameters else parameters.hash()

                        rs[(s, h)] = (pn.name if first_order else name_override, pn)

                elif t is list or t is tuple or t is set:
                    for se in s:
                        add(se, parameters, first_order, name_override)

                elif isinstance(s, _PNSpecBase):
                    add(s.name, s._getParameters(parameters), False, s._getLoadName())
                else:
                    raise TypeError("Dependency type not recognized.")

            add(dl, self.parameters, True, None)

            return rs

        # Initializes the results above the dependencies

        # get the verbatim children specifications and lists of
        # dependencies
        m_dep, r_dep, p_dep = self.p_class._getDependencies(self.parameters)

        # these are (name, hash) : pnode dicts
        self.module_dependencies = _processDependencySet("module", m_dep)
        self.result_dependencies = _processDependencySet("results", r_dep)
        self.parameter_dependencies = _processDependencySet("parameters", p_dep)

        # Now go through and push the dependencies down
        self.result_dependencies.update(self.module_dependencies)
        self.parameter_dependencies.update(self.result_dependencies)

        # Go through and instantiate all the children
        for n, pn in self.result_dependencies.itervalues():
            pn.initialize()

        # Now go through and eliminate duplicates
        for k, (n, pn) in self.result_dependencies.items():
            pnf = self.common.registerPNode(pn)

            if pnf is not pn:
                self.result_dependencies[k] = (n, pnf)

                if k in self.module_dependencies:
                    self.module_dependencies[k] = (n, pnf)

        ########################################
        # don't need to propegate parameter dependencies to children,
        # computing the hash as well
        h = hashlib.md5()

        for (n, th), (ln, pn) in sorted(self.parameter_dependencies.iteritems()):
            h.update(n)
            h.update(pn.parameter_key)
        
        for (n, th), (ln, pn) in sorted(self.result_dependencies.iteritems()):
            h.update(n)
            h.update(pn.key)

        self.dependency_key = base64.b64encode(h.digest(), "az")[:8]

        h.update(self.local_key)
        
        self.key = base64.b64encode(h.digest(), "az")[:8]

    def buildReferences(self):

        if not self.is_only_parameter_dependency and not self.children_have_reference:

            ########################################
            # Do reference counting with all the children
            for k, (n, pn) in self.result_dependencies.items():
                pn.increaseResultReference()

            for k, (n, pn) in self.module_dependencies.items():
                pn.increaseModuleReference()

            self.children_have_reference = True

    def dropUnneededReferences(self):

        if self.children_have_reference:

            ########################################
            # Do reference counting with all the children

            for k, (n, pn) in self.module_dependencies.items():
                pn.decreaseModuleReference()

            for k, (n, pn) in self.result_dependencies.items():
                pn.decreaseResultReference()

            self.children_have_reference = False

    ##################################################
    # Instantiating things

    def _instantiate(self, need_module):

        if self.results_container is None:

            # Attempt to load the results from cache
            self.results_container = self.common.loadContainer(
                PNodeModuleCacheContainer(
                    pn_name = self.name,
                    name = "__results__",
                    local_key = self.local_key,
                    dependency_key = self.dependency_key,
                    is_disk_writable = (
                        self.is_disk_writable
                        and self.p_class._allowsResultCaching(self.parameters))),
                no_local_caching = True)

            have_loaded_results = self.results_container.objectIsLoaded()

            # we're done if the results are loaded and that's all we need    
            if have_loaded_results:
                if self.module_reference_count == 0:
                    assert not need_module
                    self.dropUnneededReferences()
                    return
                
                if not need_module:
                    return

        # Okay, not done yet

        ########################################
        # This pulls all the dependency parts
        # Create the dependency parts
        pull_dict = {}
        global _Null

        modules = TreeDict()
        results = TreeDict()
        params = TreeDict()

        for k, (load_name, pn) in self.module_dependencies.iteritems():
            pull_dict[k] = p,r,m = pn.pullUpToModule()
            
            if load_name is not None:
                params[load_name], results[load_name], modules[load_name] = p,r,m
                               
        modules.freeze()

        for k, (load_name, pn) in self.result_dependencies.iteritems():
            if k in pull_dict:
                if load_name is not None:
                    params[load_name], results[load_name] = pull_dict[k][:2]
            else:
                p, r = pn.pullUpToResults()
                pull_dict[k] = (p, r, _Null)
                
                if load_name is not None:
                    params[load_name], results[load_name] = p, r
                
        results.freeze()
        
        # parameters are easy
        for k, (load_name, pn) in self.parameter_dependencies.iteritems():
            if k in pull_dict:
                if load_name is not None:
                    params[load_name] = pull_dict[k][0]
            else:
                p = pn.pullParameters()
                pull_dict[k] = (p, _Null, _Null)
                
                if load_name is not None:
                    params[load_name] = p
                
        params[self.name] = self.parameters[self.name]
        params.freeze()

        # Now we've pulled all we need!
        self.children_have_reference = False

        # Now instantiate the module
        m = self.p_class(self, params, results, modules)

        if not have_loaded_results:
            self.child_pull_dict = pull_dict
            r = m.run()
            del self.child_pull_dict
                
            if type(r) is TreeDict:
                r.freeze()
                
            self.results_container.setObject(r)
        else:
            r = self.results_container.getObject()

        m._setResults(r)

        if self.module_reference_count >= 1:
            self.module = m
            self.child_pull_dict = pull_dict
            self.dependent_modules_pulled = True
            
        else:
            
            # We're done with the module, so we need to say so
            for k, (load_name, pn) in self.module_dependencies.iteritems():
                pn.decreaseModuleAccessCount()
            
    ##################################################
    # Interfacing stuff

    def _checkModuleDeletionAllowances(self):

        mac_zero = (self.module_access_reference_count == 0)
        mrc_zero = (self.module_reference_count == 0)
        rrc_zero = (self.result_reference_count == 0)

        if mrc_zero:
            # Get rid of everything but the results
            self.module = None
        
        if mrc_zero and mac_zero and self.dependent_modules_pulled:

            # propegate all the dependencies
            for k, (load_name, pn) in self.module_dependencies.iteritems():
                pn.decreaseModuleAccessCount()

            for pn in self.additional_module_nodes_accessed:
                pn.decreaseModuleAccessCount()

            # This is gauranteed to exist if all the code is right
            del self.child_pull_dict

            self.dependent_modules_pulled = False
            gc.collect()

    def increaseModuleAccessCount(self):
        self.module_access_reference_count += 1
        self.common.increaseCachingReference(self)

    def decreaseModuleAccessCount(self):
        assert self.module_access_reference_count >= 1

        self.module_access_reference_count -= 1
        self.common.decreaseCachingReference(self)
        
        if self.module_access_reference_count == 0:
            self._checkModuleDeletionAllowances()
        
    def increaseModuleReference(self):
        self.module_reference_count += 1
        self.common.increaseCachingReference(self)

    def decreaseModuleReference(self):
        assert self.module_reference_count >= 1
        
        self.module_reference_count -= 1
        self.common.decreaseCachingReference(self)

        if self.module_reference_count == 0:
            self._checkModuleDeletionAllowances()
            
    def increaseResultReference(self):
        self.result_reference_count += 1

    def decreaseResultReference(self):
        assert self.result_reference_count >= 1

        # print ("PNode DEC Ref Count, %s, name = %s, key = %s, local_key = %s, dep_key = %s"
        #        % (self.p_type, self.name, self.key, self.local_key, self.dependency_key))
        
        self.result_reference_count -= 1

        assert self.module_reference_count <= self.result_reference_count

        if self.result_reference_count == 0:
            self.results_container = None
            self.dropUnneededReferences()
            gc.collect()
        
    def pullParameters(self):
        return self.parameters[self.name]

    def pullUpToResults(self):
        
        # print "Pulling results for module %s." % self.name

        assert self.result_reference_count >= 1

        if self.results_container is None:
            self._instantiate(False)
            
        r = self.results_container.getObject()

        self._reportResults(r)

        ret = (self.parameters[self.name], r)

        rc = self.results_container

        # print "#"*30
        # print "result %d returning with earlier ref = %d" % (id(r), sys.getrefcount(r))
        # print "container rc = %d" % (sys.getrefcount(rc))
        
        self.decreaseResultReference()

        # print "result %d returned with new_ref = %d" % (id(r), sys.getrefcount(r))
        # print "container rc = %d" % sys.getrefcount(rc)
        # print "new res count = %d" % self.result_reference_count

        return ret

    def pullUpToModule(self):

        # print "Pulling module for module %s." % self.name
        assert self.module_reference_count >= 0

        if self.module is None:
            self._instantiate(True)

        r = self.results_container.getObject()

        self._reportResults(r)
        
        ret = (self.parameters[self.name], r, self.module)

        self.increaseModuleAccessCount()
        
        self.decreaseModuleReference()
        self.decreaseResultReference()

        return ret

    def doneWithModule(self):
        self.decreaseModuleAccessCount()

    ################################################################################
    # Loading cache stuff

    def getCacheContainer(self, obj_name, key, ignore_module, ignore_local,
                          ignore_dependencies, is_disk_writable, is_persistent):

        container = PNodeModuleCacheContainer(
            pn_name = None if ignore_module else self.name,
            name = obj_name,
            local_key = None if ignore_local else self.local_key,
            dependency_key = None if ignore_dependencies else self.dependency_key,
            specific_key = key,
            is_disk_writable = is_disk_writable and self.is_disk_writable,
            is_persistent = is_persistent)
            
        return self.common.loadContainer(container)

    def _resolveRequestInfo(self, r):

        # first get the key
        if type(r) is str:
            name = r
            ptree = self.parameters
            key = self.full_key
            
        elif isinstance(r, _PNSpecBase):
            name = r.name
            ptree = r._getParameters(self.parameters)
            key = ptree.hash()
            
        else:
            raise TypeError("Requested %s must be specified as a string or "
                            "as an instance of a _PNSpecBase class like 'Delta'.")

        return name, ptree, key
        
    def getSpecific(self, r_type, r):

        name, ptree, key = self._resolveRequestInfo(r)

        lookup_key = (name, key)

        if lookup_key in self.child_pull_dict:
            params, results, module = self.child_pull_dict[lookup_key]

            global _Null

            if r_type == "results" and results is not _Null:
                return results
            elif r_type == "module" and module is not _Null:
                return module
            
        # # should return before now if everything is good
        # self.p_class.log.warning( ("%s requested (%s) without being specified as "
        #                            "a %s dependency; possible source of cache corruption "
        #                            "if the module result depends on this without "
        #                            "specification in the local parameter branch.")
        #                           % (r_type, name, r_type) )

        if r_type == "results":

            if isinstance(r, _PNSpecBase):
                common = PNodeCommon(self.common.manager)
                r = common.getResults(ptree, name)
                common._debug_referencesDone()
                gc.collect()
                assert sys.getrefcount(r) == 2, sys.getrefcount(r)
                return r
            else:
                return self.common.getResults(ptree, name)
        
        elif r_type == "module":

            pn = PNode(self.common, ptree, name, 'module')
            pn.initialize()
            pn = self.common.registerPNode(pn)
            pn.increaseResultReference()
            pn.increaseModuleReference()

            self.additional_module_nodes_accessed.append(pn)

            return pn.pullUpToModule()[-1]

        else:
            assert False
               
    ##################################################
    # Result Reporting stuff
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
                from inspect import getcallargs

                try:
                    getcallargs(rrf, parameters, p, r)
                except TypeError:
                    raiseTypeError()

                # Well, that wasn't the issue, so it's something internal; re-raise
                raise

        self.results_reported = True
