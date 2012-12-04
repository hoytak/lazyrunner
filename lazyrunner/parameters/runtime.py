from presets import getParameterTree

################################################################################

class Direct(object):

    __parameter_container__ = True

    def __init__(self, name):
        self.name = name.lower()

    def _getParameters(self, raw_parameters):
        return raw_parameters

    def _getLoadName(self):
        return self.name
    
class Delta(object):
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
 
    __parameter_container__ = True
 
    def __init__(self, p_name, local_delta = None, delta = None, apply_preset = None, name = None):

        self.name = p_name.lower().strip()
        self.local_delta = local_delta
        self.delta = delta
        
        if apply_preset is None:
            self.apply_preset = None
        elif type(apply_preset) is str:
            self.apply_preset = [apply_preset]
        elif type(apply_preset) is list or type(apply_preset) is tuple:
            self.apply_preset = list(apply_preset)
        else:
            raise TypeError("apply_preset must be either string, list, or tuple (not %s)"
                            % str(type(apply_preset)))
        
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
            pt = getParameterTree(self.apply_preset, pt)

        return pt

    def _getLoadName(self):
        return self.load_name
