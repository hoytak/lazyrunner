"""
Manages the lookup tables for the module 
"""

import logging
import inspect
import re
from os.path import samefile

from .. import parameters

_pmodule_run_queue = None
_pmodule_run_set = None
_pmodule_lookup = None

def resetAndInitialize():
    global _pmodule_lookup
    global _pmodule_run_queue
    global _pmodule_run_set
    
    _pmodule_lookup = {}
    _pmodule_run_queue = []
    _pmodule_run_set = set()

def addToRunQueue(module_name):
    global _pmodule_run_queue
    global _pmodule_run_set

    if type(module_name) is not str:
        raise TypeError("Type of module in run queue must be str (not '%s')" % str(type(m)))
            
    n = module_name.lower()

    if n not in _pmodule_run_set:
        
        _pmodule_run_queue.append(n)
        _pmodule_run_set.add(n)
    
def getCurrentRunQueue():
    global _pmodule_run_queue
    
    return [s for s in _pmodule_run_queue]

class PModulePreset(object):
    
    def __init__(self, name):
        self.name = name

    def __call__(self, p):
        addToRunQueue(self.name)
        
# a decorator
def pmodule(c):
    global _pmodule_lookup    
    
    name = c._name = c.__name__.lower()
    
    assert type(name) is str

    ret = _pmodule_lookup.setdefault(name, c)
    
    if not ret is c:
        if (inspect.getsourcefile(ret) == inspect.getsourcefile(c)
            or inspect.getfile(ret) == inspect.getfile(c)):
        
            return c         
        
        raise NameError("Processing Module '%s' doubly defined in files %s and %s." 
                        % (name, inspect.getfile(ret), inspect.getfile(c)))

        
    c.log = logging.getLogger(c._name)

    parameters.processPModule(c)

    parameters.registerPreset("r." + name, PModulePreset(name),
                              description = "Runs processing module '%s'." % c.__name__)
    
    logging.getLogger("Manager").debug("Processing module '%s' registered." % c.__name__)
        
    c._is_pmodule = True
    
    return c

def getPModuleClass(name):
    global _pmodule_lookup
    
    try:
        return _pmodule_lookup[name]
    except KeyError:
        raise NameError("Module '%s' not found." % name)

def isPModule(name):
    global _pmodule_lookup
    return name in _pmodule_lookup


def finalize():
    pass