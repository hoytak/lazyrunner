from lazyrunner import RunManager
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
        
        runner = RunManager(opttree)
        results = runner.getResults(modules = [module], presets = preset_list)
        t = results[module]
        
        for k, v in test_tree.iteritems():
            assert t[k] == v, ("%s: t[%s] != %s" % (module, k, repr(v)))
            
    
    opttree = TreeDict()
    opttree.project_directory = project_directory
    
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
        
if __name__ == '__main__':
    unittest.main()