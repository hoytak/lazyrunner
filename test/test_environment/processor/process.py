from lazyrunner import pmodule, PModule, preset, presetTree, defaults, globalDefaultTree
from treedict import TreeDict

p = globalDefaultTree()

p.process_defaults.add_to_a = 0

@preset
def add_to_a(p, a = 1):
    p.process_defaults.add_to_a = a


@pmodule
class Process(PModule):

    p = defaults()
    p.add_to_x = 0

    @preset
    def addToX(p, y = 1):
        p.add_to_x = y

    
    result_dependencies = "data"
    parameter_dependencies = "process_defaults"
    
    def run(self):
        if self.p.return_value == 'x':
            return self.results.data.x + self.p.add_to_x
        elif self.p.return_value == 'a':
            return self.results.data.a + self.process_defaults.add_to_a
        elif self.p.return_value == 'b':
            return self.results.data.b
        else: 
            assert False
    