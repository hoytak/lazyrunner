"""
Manages the lookup tables for the module 
"""

import logging
import inspect

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

        if c.__module__ != _module_lookup[name].__module__:
            raise NameError("Module '%s' doubly defined (%s, %s)."
                            % (name, c.__module__, _module_lookup[name].__module__))
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
