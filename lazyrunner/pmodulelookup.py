"""
Manages the lookup tables for the module 
"""

import logging
import inspect
import re
from os.path import samefile

from presets import registerPreset, addToRunQueue

_module_lookup = {}

class PModulePreset(object):
    
    def __init__(self, name):
        self.name = name

    def __call__(self, p):
        addToRunQueue(p, self.name)
        
# a decorator
def pmodule(c):
    name = c._name = c.__name__.lower()

    assert type(name) is str
    
    if name in _module_lookup:
        m = _module_lookup[name]

        cf = inspect.getfile(c)
        mf = inspect.getfile(m)

        if c is not m and cf != mf and not samefile(cf, mf):

            # It's still possible that one file is the compiled
            # version of the other file.

            if not samefile(cf.replace('.pyc', '.py'), mf.replace('.pyc', '.py')):
                raise NameError("Module '%s' doubly defined (%s, %s)." % (name, cf, mf))
        else:
            return
        
    c.log = logging.getLogger(c._name)

    _module_lookup[name] = c

    registerPreset("r." + name, PModulePreset(name),
                   description = "Runs processing module '%s'." % c.__name__)
    
    return c

def getPModuleClass(name):

    try:
        return _module_lookup[name]
    except KeyError:
        raise NameError("Module '%s' not found." % name)

def isPModule(name):
    return name in _module_lookup
