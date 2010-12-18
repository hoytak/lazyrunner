"""
This module defines a central way to control and manage actions.
"""

import inspect, sys
from treedict import TreeDict

class ActionError(Exception): pass

class Action:

    def __init__(self, action_func):
        self.action_func = f = action_func
        self.name = f.__name__

        self.args, self.varargs, self.varkw, self.defaults = inspect.getargspec(f)

        self.docstring = f.__doc__.strip()
        
        self.helpstring = (
            "Usage: %s %s %s\n\n%s\n"
            % (sys.argv[0], 
               self.name,
               inspect.formatargspec(self.args, self.varargs, self.varkw, self.defaults),
               self.docstring))

    def __call__(self, arglist):
        # Parses the given argument list; open for improvements

        
        return self.action_func(*arglist)
               


_action_lookup = TreeDict()
                
def action(f):
    a = Action(f)

    _action_lookup[a.name] = a


##################################################
# Running the actions

def runAction(action_name, arglist):
    
    # Process the args
    try:
        a = _action_lookup[action_name]
    except KeyError:
        raise ActionError("Action '%s' not valid; did you mean one of %s?" 
                          % (action_name, ', '.join(_action_lookup.getClosestKey(action_name, 5))))
    
    return a(arglist)

def allActions():
    return _action_lookup.keys()

