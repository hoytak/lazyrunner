
from lazyrunner import preset, applyPreset, group, presetTree

from treedict import TreeDict as TD

# A preset is just a function taking one argument, a parameter tree,
# and returning a modified form of the tree.  Presets may be applied
# as dependencies using applyPreset(p).


with group(prefix='pr'):

    @preset
    def t01(p):
        p.params.a = 2

    pt1 = presetTree('t02')
    pt1.params.a = 2

    presetTree('t03').params.a = 2

    presetTree('t04', branch='params').a = 2
    
with group(prefix = 'pr', branch = 'params'):

    @preset
    def t10(p):
        p.a = 2
        
    pt2 = presetTree('t11')
    pt2.a = 2

    presetTree('t12').a = 2

    
@preset(prefix='pr')
def t20(p):
    p.params.a = 2

@preset(prefix='pr', branch = 'params')
def t21(p):
    p.a = 2

pt3 = presetTree('pr.t22', branch = 'params')
pt3.a = 2

with group(prefix = 'pr'):
    with group(branch = 'params'):

        @preset
        def t30(p):
            p.a = 2

        pt3 = presetTree('t31')
        pt3.a = 2

        presetTree('t32').a = 2
    
########################################
# Tests of the apply sequence

presetTree('test2').test_type = 'double'

p = presetTree('pr.t40')
p.params.a = 2
p.params.b.a = 3

with group(apply = {'params.a': 2}):
    presetTree('pr.t41').params.b.a = 3
    presetTree('pr.t42', branch = 'params').b.a = 3
    
with group('pr', 'params'):
    with group(apply = TD(a = 2)):
        presetTree('t50').b.a = 3

with group('pr', 'params', apply = TD(a = 2)):
    presetTree('t51').b.a = 3

presetTree('apply_test').params.a = 2

with group('pr', 'params', apply = 'apply_test'):
    presetTree('t52').b.a = 3

with group(branch = 'params', apply = ['apply_test', {}]):
    presetTree('pr.t53').b.a = 3

with group(branch = 'params', apply = [['apply_test'], {}]):
    presetTree('pr.t54').b.a = 3

with group(branch = 'params', apply = [TD(a = 3), TD(a = 2)]):
    presetTree('pr.t55').b.a = 3

with group('pr', 'params'):
    with group(apply = TD(a = 2)):
        presetTree('t56').b.a = 3

with group('pr', 'params'):
    @preset(apply = 'apply_test')
    def t57(p):
        p.b.a = 3

with group('pr'):
    @preset(apply = 'apply_test')
    def t58(p):
        p.params.b.a = 3
        




