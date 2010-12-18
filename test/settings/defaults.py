
"""
The default settings file used to run the lazyrunner framework.
"""

from treedict import TreeDict

p = TreeDict("parameters")

# The parameters are determined by the module name for e.g. for
# MyModule, use p.mymodule.x to set the parameters for module
# 'mymodule'.

p.run_queue = ['params']

p.test_type = 'basic'

p.params.a = 1
