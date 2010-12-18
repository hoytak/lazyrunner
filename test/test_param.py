
from lazyrunner import pmodule, PModule
from treedict import TreeDict
import sys

@pmodule
class Params(PModule):

    # The current version of the pmodule.  The caching facilities
    # assume results are different between different versions.
    version = 0.01

    # Include dependencies here; alternatively, these may be given as
    # class methods, optionally accepting the parameter tree, to
    # provide parameter-dependent dependency checking
    
    parameter_dependencies = ['test_type']
    result_dependencies    = []
    module_dependencies    = []

    # If true, the results are never saved or loaded from the cache.
    disable_result_caching = False

    def setup(self):
        # Setup the Pmodule.  Called whenever the module is created.
        
        pass

    def run(self):
        # Run the module and return a TreeDict instance holding the
        # results.  Note that this function is not necessarily called
        # if the results can be loaded from cache

        print self.parameters.keys()

        if self.parameters.test_type == 'basic':

            if self.p.a != 2:
                print "ERROR: p.params.a == %d" % self.p.a
                sys.exit(1)
            else:
                print "SUCCESS: p.params.a == 2"
                
        elif self.parameters.test_type == 'double':
            
            if self.p.a != 2 or self.p.b.a != 3:
                print "ERROR: p.params.a == %d, p.params.a.b == %d" % (self.p.a, self.p.b.a)
                sys.exit(1)
            else:
                print "SUCCESS"
        else:
            assert False
            
    @classmethod
    def reportResult(cls, parameters, p, r):
        # Report on results, even if they are loaded from
        # cache. `parameters` is the full parameter tree as specified
        # by all parameter dependencies, `p` is the local parameter
        # tree branch for this module, and `r` is the result of run(),
        # possibly loaded from cache.

        pass

