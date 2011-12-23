from treedict import TreeDict
from presets import applyPresets

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

class PNodeModuleCache(object):

    def __init__(self):

        self.access_count = 1
        self.cache = {}
        



# This class holds the runtime environment for the pnodes
class PNodeCommon(object):

    def __init__(self, manager):
        self.manager = manager


        # holds weak refs to all the common module caches

        # This assumes that 
        self.module_common = {}

        # Holds common objects
        self.common_objects = {}

        # This is for node filtering, i.e. eliminating duplicates
        self.pnode_lookup = {}
        
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

    def decreaseReference(self, pn):

        m_cache = self.module_common[pn.name]

        m_cache.access_count -= 1

        if m_cache.access_count == 0:
            del self.module_common[pn.name]

    def saveToModuleCache    
    
    

class PNode(object):

    def __init__(self, common, parameters, name, p_type):

        self.common = common
        self.parameters = self.parameters.copy()
        self.name = name
        self.p_type = p_type

        ##################################################
        # Get the preprocessed parameters

        if name not in self.parameters:
            self.parameters.makeBranch(name)

        if isPModule(name):

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

            self.local_hash = base64.b64encode(h.digest(), "az")[:8]
            
        else:
            self.local_hash = self.parameters.hash(name)

        self.reference_count = 1
        self.results = None
        self.module = None
        self.child_pull_dict = {}

        self.cache_dep_all = {}
        self.cache_dep_local = self.common.getCache(self, True, False)
        self.cache_dep_dep_dependencies = self.common.getCache(self, False, True)
        self.cache_dep_module = self.common.getCache(self, False, False)


    def instantiateChildren(self):

        # get the verbatim children specifications and lists of
        # dependencies
        m_dep, r_dep, p_dep = manager.getDependencies(self.parameters, name)

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

        h.update(self.local_hash)
        
        self.key = base64.b64encode(h.digest(), "az")[:8]

        return self.key

    def _processDependencySet(self, p_type, dl):

        rs = {}

        def add(s, parameters, first_order, name_override):

            t = type(s)

            if t is str:
                pn = PNode(self.manager, parameters, s, p_type)

                n = name_override if name_override is not None else pn.name
                rs[(s, pn.local_hash)] = (n if first_order else None, pn)
                
            elif t is list or t is tuple or t is set:
                for se in s:
                    add(se, parameters, first_order, name_override)

            elif isinstance(s, _PNSpecBase):
                add(s.name, s._getParameters(parameters), False, s._getLoadName())
                
            else:
                raise TypeError("Dependency type not recognized.")

        add(dl, self.parameters, True, None)

        return ret

    def _loadModule(self, attempt_to_load_results = True):

        assert self.module is None

        if attempt_to_load_results:
            have_results = self._loadResults(False)

        m_class = getPModuleClass(self.name)

        # Create the dependency trees
        self.child_pull_dict = {}

        modules = TreeDict()
        for k, (load_name, pn) in self.module_dependencies.iteritems():
            params[load_name], results[load_name], modules[load_name] = \
                               self.child_pull_dict[k] = pn.pullUpToModule()

        results = TreeDict()
        for k, (load_name, pn) in self.result_dependencies.iteritems():
            if k in self.child_pull_dict:
                params[load_name], results[load_name], junk = self.child_pull_dict[k]
            else:
                params[load_name], results[load_name] = p, r = pn.pullUpToResults()
                self.child_pull_dict[k] = (p, r, None)
                
        # parameters are easy
        params = TreeDict()
        for k, (load_name, pn) in self.parameter_dependencies.iteritems():
            if k in self.child_pull_dict:
                params[load_name] = self.child_pull_dict[k][0]
            else:
                params[load_name] = p = pn.pullParameters()
                self.child_pull_dict[k] = (p, None, None)


        # Now instantiate the module
        self.module = m = m_class(self, params, results, modules)

        if self.results is None:
            self.results = m.run()
            self.manager.saveToCache(vvv)
                          
    def _loadResults(self, calling_from_loadmodule = False):

        assert self.results is None

        is_loaded, self.results = self.manager.loadResultsFromCache(self.name, self.key)

        if not is_loaded:

            if calling_from_loadmodule:
                return False
            else:
                self.loadModule(attempt_to_load_results = False)
        else:
            if not calling_from_loadmodule:
                self._doReferencePull()
                
            
        assert self.results is not None

        return True
        

    ##################################################
    # Interfacing stuff

    def _decreaseReferenceCount(self):
        assert self.reference_count >= 1

        self.reference_count -= 1

        # Don't need these any more
        if self.reference_count == 0:
            self.results = None
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

        if self.results is None:
            self.results = self._loadResults()

        ret = (self.parameters[self.name], self.results)

        self._decreaseReferenceCount()

        return ret

    def pullUpToModule(self):

        assert self.p_type == "module"

        if self.module is None:
            self._loadModule()

        ret = (self.parameters[self.name], self.results, self.module)

        self._decreaseReferenceCount()

        return ret

        
