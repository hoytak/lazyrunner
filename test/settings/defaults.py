
"""
The default settings file used to run the lazyrunner framework.
"""

from treedict import TreeDict

p = TreeDict("parameters")

# The parameters are determined by the module name

p.run_queue = ['params']

p.test_type = 'basic'
