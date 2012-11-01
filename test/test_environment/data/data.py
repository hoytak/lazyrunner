from lazyrunner import pmodule, PModule, preset, presetTree, defaults, globalDefaultTree
from treedict import TreeDict

p = globalDefaultTree()

p.data_defaults.a = 1
p.data_defaults.b = 2


@preset
def change_default_a(p):
    p.data_defaults.a = 10


@pmodule
class Data(PModule):

    # Use this to set up the local branch of the preset tree.  Calling
    # defaults() requests the local branch of the 

    p = defaults()
    p.x = 1

    @preset
    def set_X_2(p):
        p.x = 2
        
    @preset
    def set_X(p, x_value = 3):
        p.x = x_value
    

    # The current version of the pmodule.  The caching facilities
    # assume results are different between different versions.
    version = 0.01

    # Include dependencies here; alternatively, these may be given as
    # class methods, optionally accepting the parameter tree, to
    # provide parameter-dependent dependency checking.  See
    # documentation for more info.
    
    parameter_dependencies = ['data_defaults']
    result_dependencies    = []
    module_dependencies    = []

    # If true, the results are never saved or loaded from the cache.
    # Switch to True once the module is tested. 
    disable_result_caching = True

    def setup(self):
        # Setup the Pmodule.  Called whenever the module is created.
        
        pass

    def run(self):
        # Run the module and return a TreeDict instance holding the
        # results.  Note that this function is not necessarily called
        # if the results can be loaded from cache

        self.log.info("The value of X is %d." % self.p.x)

        return TreeDict(x = self.p.x, 
                        a = self.parameters.data_defaults.a, 
                        b = self.parameters.data_defaults.b
                        )
        
    @classmethod
    def reportResult(cls, parameters, p, r):
        # Report on results, even if they are loaded from
        # cache. `parameters` is the full parameter tree as specified
        # by all parameter dependencies, `p` is the local parameter
        # tree branch for this module, and `r` is the result of run(),
        # possibly loaded from cache.

        self.log.info("The reported value of X is %d. " % r.x)
