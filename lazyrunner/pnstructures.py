from treedict import TreeDict
from presets import applyPresets

class _PNSpecBase(object):
    pass

class Direct(_PNSpecBase):

    def __init__(self, name):
        self.name = name.lower()

    def _getParameters(self, raw_parameters):
        return raw_parameters


class Delta(_PNSpecBase):

    def __init__(self, name, local_delta = None, delta = None, apply_preset = None):

        self.name = name.lower()
        self.local_delta = local_delta
        self.delta = delta
        self.apply_preset = apply_preset

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
        
class PNChild(object):

    def 


class PNode(object):

    def __init__(self, manager, parameters, name, p_type):
        
        self.manager = manager
        self.parameters = parameters.copy()
        self.name = name
        self.p_type = p_type

        # NOTE: the p_dict is a locally used single-depth tree of all
        # the branches as TreeDicts as values.  Should be copied on each pass down

        # Get the local parameter tree stuff
        self.parameters[name], self.local_hash = \
                               manager.getPreprocessedBranch(self.parameters, name, True)

        self.reference_count = 1
        self.value = None

    def instanciateChildren(self):

        # get the verbatim children specifications and lists of
        # dependencies
        m_dep, r_dep, p_dep = manager.getDependencies(self.parameters, name)

        # these are (name, hash) : pnode dicts
        module_dependencies = self._processDependencySet("module", m_dep)
        result_dependencies = self._processDependencySet("result", r_dep)
        parameter_dependencies = self._processDependencySet("parameter", p_dep)
 
        # Now go through and push the dependencies down
        result_dependencies.update(module_dependencies)
        parameter_dependencies.update(result_dependencies)

        # don't need to propegate parameter dependencies to children,
        # computing the hash as well
        h = hashlib.md5()
        for n, tn in sorted(parameter_dependencies.iterkeys()):
            h.update(tn)
        
        for rp, pn in sorted(result_dependencies.iteritems()):
            h.update(pn.instanciateChildren())

        self.key = self.name + "-" + base64.b64encode(h.digest(), "az")[:8]

        return self.key

    def _processDependencySet(self, p_type, dl):

        rs = {}

        def add(s, parameters):

            t = type(s)

            if t is str:
                pn = PNode(self.manager, parameters, s, p_type)
                rs[(s, pn.local_hash)] = pn
                return
                
            else if t is list or t is tuple or t is set:
                for se in s:
                    add(se, parameters)

            else if isinstance(s, _PNSpecBase):
                add(s.name, s._getParameters(parameters))
                
            raise TypeError("Dependency type not recognized.")

        add(dl, self.parameters)

        return rs

    def pull(self):

        if self
