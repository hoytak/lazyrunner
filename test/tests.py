from lazyrunner import manager, initialize, reset, PCall
from treedict import TreeDict
from os.path import exists, join
import shutil
import unittest


if exists('test_environment'):
    project_directory = 'test_environment'
elif exists('test/test_environment'):
    project_directory = 'test/test_environment'
else:
    raise RuntimeError('Bad Initial directory for running tests.')

def runTest(preset_list, module, test_tree):
    
    # Run several different versions; with and without cache 

    def test(opttree):
        reset()
        initialize(opttree)
        runner = manager()
        
        results = runner.getResults(modules = [module], presets = preset_list)
        t = results[module]
        
        if type(test_tree) is TreeDict:
            for k, v in test_tree.iteritems():
                assert t[k] == v, ("%s: t[%s] != %s" % (module, k, repr(v)))
        else:
            assert test_tree == t
            
    
    opttree = TreeDict()
    opttree.project_directory = project_directory
    opttree.debug_mode = True
    opttree.verbose_mode = True
    
    test(opttree)
    
    opttree.cache_directory = join(project_directory, ".cache")
    
    test(opttree)
    test(opttree)
    
    shutil.rmtree(opttree.cache_directory, ignore_errors = True)
    
    
class TestBasic(unittest.TestCase):
    
    
    def test01(self):
        
        test_tree = TreeDict()
        test_tree.x = 1
        test_tree.a = 1
        test_tree.b = 2
        
        runTest([], 'data', test_tree)
        
    def test02(self):
        
        test_tree = TreeDict()
        test_tree.x = 1
        test_tree.a = 10
        test_tree.b = 2
        
        runTest(['change_default_a'], 'data', test_tree)

    def test03(self):
        
        test_tree = TreeDict()
        test_tree.x = 2
        test_tree.a = 1
        test_tree.b = 2
        
        runTest(['data.set_X_2'], 'data', test_tree)

    def test10_paramPassing_0_defaults(self):
        
        test_tree = TreeDict()
        test_tree.x = 2
        
        runTest(['data.set_X'], 'data', test_tree)

    def test10_paramPassing_1(self):
        
        test_tree = TreeDict()
        test_tree.x = 3
        
        runTest(['data.set_X:3'], 'data', test_tree)

    def test10_paramPassing_2(self):
        
        test_tree = TreeDict()
        test_tree.x = 3
        
        runTest(['data.set_X:x=3'], 'data', test_tree)

    def test10_paramPassing_3(self):
        test_tree = TreeDict()
        test_tree.x = 3
        
        runTest([('data.set_X', [3])], 'data', test_tree)

    def test10_paramPassing_4(self):
        test_tree = TreeDict()
        test_tree.x = 3
        
        runTest([('data.set_X', [], {'x' : 3})], 'data', test_tree)

    def test10_paramPassing_5(self):
        
        test_tree = TreeDict()
        test_tree.x = 3
        
        runTest([PCall('data.set_X', 3)], 'data', test_tree)

    def test10_paramPassing_6(self):
        
        test_tree = TreeDict()
        test_tree.x = 3
        
        runTest([PCall('data.set_X', x=3)], 'data', test_tree)
        
    def test21(self):
        runTest(['process.addToX'], 'process', 2)

    def test22(self):
        runTest([('process.addToX', [3])], 'process', 4)

    def test23(self):
        runTest([('process.returnvalue', ['a'])], 'process', 1)
        
        
if __name__ == '__main__':
    unittest.main()