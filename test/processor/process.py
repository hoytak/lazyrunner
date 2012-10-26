from lazyrunner import pmodule, PModule, preset, presetTree, defaults
from treedict import TreeDict

@pmodule
class Process(PModule):

    p = defaults()
    
    result_dependencies = "data"
    
    def run(self):
        
        print "self.results.data.x =", self.results.data.x