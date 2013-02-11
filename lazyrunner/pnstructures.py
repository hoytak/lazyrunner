from treedict import TreeDict
from parameters import applyPreset
from collections import defaultdict
from os.path import join, abspath, exists, split
from os import makedirs
import hashlib, base64, weakref, sys, gc, logging
from itertools import chain
from collections import namedtuple
from pmodule import isPModule, getPModuleClass
from diskio import saveResults, loadResults


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

    __slots__ = ["reference_count", "cache"]

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

    def __init__(self, opttree):
        self.log = logging.getLogger("RunCTRL")

        # This is for node filtering, i.e. eliminating duplicates
        self.pnode_lookup = weakref.WeakValueDictionary()

        self.non_persistant_pointer_lookup = weakref.WeakValueDictionary()
        self.non_persistant_deleter = _PNodeNonPersistentDeleter(self)

        # This is for local cache lootup
        self.cache_lookup = defaultdict(PNodeModuleCache)

        self.cache_directory = opttree.cache_directory
        self.disk_read_enabled = opttree.disk_read_enabled
        self.disk_write_enabled = opttree.disk_write_enabled
        
        self.opttree = opttree


    def getResults(self, parameters, names):

        if type(names) is str:
            single = True
            names = [names]
        else:
            single = False

        def getPN(n):
            if type(n) is not str:
                raise TypeError("Module name not a string.")
            
            pn = PNode(self, parameters, n, 'results')
            pn.initialize()
            
            pn = self.registerPNode(pn)
            pn.increaseParameterReference()
            pn.increaseResultReference()

            return pn
        
        pn_list = [getPN(n) for n in names]
        
        assert len(set(id(pn) for pn in pn_list)) == len(set(names))

        ret_list = [pn.pullUpToResults().result for pn in pn_list]
        
        if single:
            assert len(ret_list) == 1
            return ret_list[0]
        else:
            return ret_list
    
        
    def registerPNode(self, pn):

        # see if it's a duplicate
        key = (pn.name, pn.key)

        if key in self.pnode_lookup:
            pnf = self.pnode_lookup[key]
            if not pn.is_only_parameter_dependency:
                pnf.is_only_parameter_dependency = False
            pn_ret = pnf
            
        else:
            self.pnode_lookup[key] = pn_ret = pn

        pn_ret.buildReferences()
            
        return pn_ret

    def deregisterPNode(self, pn):
        key = (pn.name, pn.key)

        assert self.pnode_lookup[key] is pn

        del self.pnode_lookup[key]
        

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
        self._loadFromDisk(container)

        return container

    
    def _loadFromDisk(self, container):

        if not container.isDiskWritable():
            return

        if self.disk_read_enabled:
            filename = abspath(join(self.cache_directory, container.getFilename()))

            self.log.debug("Trying to load %s from %s" % (container.getKeyAsString(), filename))

            if exists(filename):
                error_loading = False
                
                try:
                    pt = loadResults(self.opttree, filename)
                except Exception, e:
                    self.log.error("Exception Raised while loading %s: \n%s"
                                   % (filename, str(e)))
                    error_loading = True
                    
                if not error_loading:

                    self.log.debug("--> Object successfully loaded.")
                    container.setObject(pt)
                    return
                else:
                    pass # go to the disk write enabled part
                
            else:
                self.log.debug("--> File does not exist.")

        if self.disk_write_enabled and container.isDiskWritable():
            container.setObjectSaveHook(self._saveToDisk)

    def _saveToDisk(self, container):

        assert self.disk_write_enabled and container.isDiskWritable()

        filename = join(self.cache_directory, container.getFilename())
        obj = container.getObject()

        self.log.debug("Saving object  %s to   %s." % (container.getKeyAsString(), filename))

        try:
            saveResults(self.opttree, filename, obj)
            assert exists(filename)
            
        except Exception, e:
            
            self.log.error("Exception raised attempting to save object to cache: \n%s" % str(e))

            try:
                remove(filename)
            except Exception:
                pass

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

_PulledResult     = namedtuple('PulledResult',     ['parameters', 'result'])
_PulledModule     = namedtuple('PulledModule',     ['parameters', 'result', 'module'])

class PNode(object):

    def __init__(self, common, parameters, name, p_type):

        # print ">>>>>>>>>>>>>>>>>>>> INIT: %s <<<<<<<<<<<<<<<<<<<<" % name

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
            
            self.parameters[name] = pt = p_class._preprocessParameters(self.parameters)
            pt.attach(recursive = True)
            pt.freeze()
            self.parameter_key = self.parameters.hash(name)

            h = hashlib.md5()
            h.update(str(p_class._getVersion()))
            h.update(self.parameter_key)
            
            self.local_key = base64.b64encode(h.digest(), "az")[:8]

            self.results_reported = False
            self.full_key = self.parameters.hash()

            # Reference counting isn't used in the parameter classes
            self.parameter_reference_count = 0
            self.result_reference_count = 0
            self.module_reference_count = 0
            self.module_access_reference_count = 0
            self.dependent_modules_pulled = False
            self.children_have_reference = False
            
        else:
            self.parameter_key = self.parameters.hash(name)
            self.parameter_reference_count = 0

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

                        # delay the creation until we know we need it
                        h = self.full_key if parameters is self.parameters else parameters.hash()
                        rs[(s, h)] = (s if first_order else name_override, parameters, s, p_type)

                elif t is list or t is tuple or t is set:
                    for se in s:
                        add(se, parameters, first_order, name_override)

                elif getattr(s, "__parameter_container__", False):
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

        # print "init-3: %s-%s has ref count %d" % (self.name, self.key, sys.getrefcount(self))
                        
        # Now go through and push the dependencies down
        self.result_dependencies.update(self.module_dependencies)
        self.parameter_dependencies.update(self.result_dependencies)

        # And go through and instantiate all of the remaining ones
        for k, t in self.parameter_dependencies.items():
            pn = PNode(self.common, *t[1:])
            self.parameter_dependencies[k] = v = (t[0], pn)

            if k in self.result_dependencies:
                self.result_dependencies[k] = v

                if k in self.module_dependencies:
                   self.module_dependencies[k] = v 

        # Go through and instantiate all the children
        for n, pn in self.result_dependencies.itervalues():
            pn.initialize()

        # Now go through and eliminate duplicates
        for k, (n, pn) in self.result_dependencies.items():
            pnf = self.common.registerPNode(pn)

            if pnf is not pn:
                self.result_dependencies[k] = (n, pnf)
                self.parameter_dependencies[k] = (n, pnf)

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

        # Load the parameter tree
        self.dependency_parameter_tree = TreeDict()

        for (n, th), (ln, pn) in sorted(self.parameter_dependencies.iteritems()):
            if ln is not None:
                self.dependency_parameter_tree[ln] = pn.pullParameterPreReferenceCount()

        self.dependency_parameter_tree[self.name] = self.parameters[self.name]

        self.is_disk_writable = self.p_class._allowsCaching(self.dependency_parameter_tree)
        self.is_result_disk_writable = (False if not self.is_disk_writable else
                                        self.p_class._allowsResultCaching(self.dependency_parameter_tree))

    def buildReferences(self):

        if not self.is_only_parameter_dependency and not self.children_have_reference:

            ########################################
            # Do reference counting with all the children
            for k, (n, pn) in self.parameter_dependencies.items():
                pn.increaseParameterReference()

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

            for k, (n, pn) in self.parameter_dependencies.items():
                pn.decreaseParameterReference()

            self.children_have_reference = False

    ##################################################
    # Instantiating things

    def _instantiate(self, need_module):

        if not hasattr(self, "results_container"):

            # Attempt to load the results from cache
            self.results_container = self.common.loadContainer(
                PNodeModuleCacheContainer(
                    pn_name = self.name,
                    name = "__results__",
                    local_key = self.local_key,
                    dependency_key = self.dependency_key,
                    is_disk_writable = self.is_result_disk_writable),
                no_local_caching = True)

            have_loaded_results = self.results_container.objectIsLoaded()

            # we're done if the results are loaded and that's all we need    
            if have_loaded_results:

                self._reportResults(self.results_container.getObject())

                if self.module_reference_count == 0:
                    assert not need_module
                    self.dropUnneededReferences()
                    return
                
                if not need_module:
                    return
        else:
            have_loaded_results = self.results_container.objectIsLoaded()

        # Okay, not done yet

        ########################################
        # This pulls all the dependency parts
        # Create the dependency parts
        self.child_pull_dict = {}
        global _Null

        modules = TreeDict()
        results = TreeDict()
        params = TreeDict()

        for k, (load_name, pn) in self.module_dependencies.iteritems():
            self.child_pull_dict[k] = p,r,m = pn.pullUpToModule()
            
            if load_name is not None:
                params[load_name], results[load_name], modules[load_name] = p,r,m
                               
        modules.freeze()

        for k, (load_name, pn) in self.result_dependencies.iteritems():
            if k in self.child_pull_dict:
                if load_name is not None:
                    params[load_name], results[load_name] = self.child_pull_dict[k][:2]
            else:
                p, r = pn.pullUpToResults()
                self.child_pull_dict[k] = (p, r, _Null)
                
                if load_name is not None:
                    params[load_name], results[load_name] = p, r
                
        results.freeze()
        
        # parameters are easy
        for k, (load_name, pn) in self.parameter_dependencies.iteritems():
            if k in self.child_pull_dict:
                if load_name is not None:
                    params[load_name] = self.child_pull_dict[k][0]
            else:
                p = pn.pullParameters()
                self.child_pull_dict[k] = (p, _Null, _Null)
                
                if load_name is not None:
                    params[load_name] = p
                
        params[self.name] = self.parameters[self.name]
        params.freeze()

        # Now we've pulled all we need!
        self.children_have_reference = False

        self.increaseModuleAccessCount()
        
        # Now instantiate the module
        self.module = self.p_class(self, params, results, modules)

        if not have_loaded_results:
            r = self.module.run()

            if type(r) is TreeDict:
                r.freeze()
                
            self.results_container.setObject(r)

            self._reportResults(r)

        else:
            r = self.results_container.getObject()

        self.module._setResults(r)

        self.dependent_modules_pulled = True

        self.decreaseModuleAccessCount()
            
    ##################################################
    # Interfacing stuff

    def _checkModuleDeletionAllowances(self):

        mac_zero = (self.module_access_reference_count == 0)
        mrc_zero = (self.module_reference_count == 0)
        rrc_zero = (self.result_reference_count == 0)

        if mrc_zero and mac_zero and self.dependent_modules_pulled:

            # Get rid of everything but the results
            self.module._destroy()
            del self.module

            # propegate all the dependencies
            for k, (load_name, pn) in self.module_dependencies.iteritems():
                pn.decreaseModuleAccessCount()

            if hasattr(self, "additional_module_nodes_accessed"):
                for pn in self.additional_module_nodes_accessed:
                    pn.decreaseModuleAccessCount()

                del self.additional_module_nodes_accessed

            # This is gauranteed to exist if all the code is right
            del self.child_pull_dict

            self.dependent_modules_pulled = False

    def _checkDeletability(self):
        if not self.is_only_parameter_dependency:
            assert self.module_reference_count <= self.parameter_reference_count
            assert self.result_reference_count <= self.parameter_reference_count

        if self.parameter_reference_count == 0 and (
            self.is_only_parameter_dependency or self.module_access_reference_count == 0):

            # Clean out the heavy parts in light of everything
            if not self.is_only_parameter_dependency:
                self.common.deregisterPNode(self)
                
                self.module_dependencies.clear()
                self.result_dependencies.clear()
                self.parameter_dependencies.clear()

    def increaseParameterReference(self):
        if not self.is_only_parameter_dependency:
            assert self.module_reference_count <= self.parameter_reference_count
            assert self.result_reference_count <= self.parameter_reference_count
            
        assert type(self.parameters) is TreeDict
        
        self.parameter_reference_count += 1

    def decreaseParameterReference(self):

        assert self.parameter_reference_count >= 1
        self.parameter_reference_count -= 1

        if not self.is_only_parameter_dependency:
            assert self.module_reference_count <= self.parameter_reference_count
            assert self.result_reference_count <= self.parameter_reference_count

        if self.parameter_reference_count == 0:
            self._checkDeletability()
            
    def increaseResultReference(self):
        self.result_reference_count += 1

    def decreaseResultReference(self):
        assert self.result_reference_count >= 1
        
        self.result_reference_count -= 1

        assert self.module_reference_count <= self.result_reference_count

        if self.result_reference_count == 0:
            try:
                del self.results_container
            except AttributeError:
                pass
                
            self.dropUnneededReferences()

    def increaseModuleAccessCount(self):
        self.module_access_reference_count += 1
        self.common.increaseCachingReference(self)

    def decreaseModuleAccessCount(self):
        assert self.module_access_reference_count >= 1

        self.module_access_reference_count -= 1
        self.common.decreaseCachingReference(self)        
        
        if self.module_access_reference_count == 0:
            self._checkModuleDeletionAllowances()
            self._checkDeletability()
        
    def increaseModuleReference(self):
        self.module_reference_count += 1
        self.common.increaseCachingReference(self)

    def decreaseModuleReference(self):
        assert self.module_reference_count >= 1
        
        self.module_reference_count -= 1
        self.common.decreaseCachingReference(self)

        if self.module_reference_count == 0:
            self._checkModuleDeletionAllowances()

    def pullParameterPreReferenceCount(self):
        return self.parameters[self.name]
            
    def pullParameters(self):
        assert self.parameter_reference_count >= 1
        
        p = self.parameters[self.name]

        self.decreaseParameterReference()

        return p

    def pullUpToResults(self):
        
        assert self.result_reference_count >= 1

        if not hasattr(self, "results_container"):
            self._instantiate(False)
            
        r = self.results_container.getObject()

        ret = _PulledResult(self.parameters[self.name], r)

        rc = self.results_container
        
        self.decreaseResultReference()
        self.decreaseParameterReference()

        return ret

    def pullUpToModule(self):

        # print "Pulling module for module %s." % self.name
        assert self.module_reference_count >= 0

        if not hasattr(self, "module") or not hasattr(self, "results_container"):
            self._instantiate(True)

        r = self.results_container.getObject()

        self._reportResults(r)
        
        ret = _PulledModule(self.parameters[self.name], r, self.module)

        self.increaseModuleAccessCount()
        
        self.decreaseModuleReference()
        self.decreaseResultReference()
        self.decreaseParameterReference()

        return ret

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
            
        elif getattr(r, "__parameter_container__", False):
            name = r.name
            ptree = r._getParameters(self.parameters)
            key = ptree.hash()
            
        else:
            raise TypeError("Requested %s must be specified as a string or "
                            "a parameter container class like 'Delta'.")

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
            elif r_type == "parameters":
                return params
            else:
                assert False
            
        if r_type == "results":
            return self.common.getResults(ptree, name)
        
        elif r_type == "module":

            pn = PNode(self.common, ptree, name, 'module')
            pn.initialize()
            pn = self.common.registerPNode(pn)
            
            pn.increaseParameterReference()
            pn.increaseResultReference()
            pn.increaseModuleReference()

            if hasattr(self, "additional_module_nodes_accessed"):
                self.additional_module_nodes_accessed.append(pn)
            else:
                self.additional_module_nodes_accessed = [pn]

            return pn.pullUpToModule().module

        elif r_type == "parameters":
            pn = PNode(self.common, ptree, name, 'parameters')
            pn.initialize()
            pn = self.common.registerPNode(pn)
            
            pn.increaseParameterReference()
            
            return pn.pullParameters()
        
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
                from robust_inspect import getcallargs

                try:
                    getcallargs(rrf, parameters, p, r)
                except TypeError:
                    raiseTypeError()

                # Well, that wasn't the issue, so it's something internal; re-raise
                raise

        self.results_reported = True
