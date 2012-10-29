"""
The central place for handling parameters.
"""

import sys, textwrap
import re
import warnings
import os, struct
import inspect
from os.path import commonprefix
import common

from treedict import TreeDict

################################################################################
# Stuff for keeping track of the parameter tree

__default_tree = None
__default_tree_finalized = False
__pmodule_branch_tree = None

def resetAndInitGlobalParameterTree():
    global __default_tree
    global __default_tree_finalized
    global __pmodule_branch_tree
        
    __pmodule_branch_tree = TreeDict()
    __pmodule_branch_tree.freeze(values_only = True)  # disable value clobbering

    __default_tree = TreeDict("defaults")
    __default_tree["__defaultpresettree__"] = True
    __default_tree.freeze(values_only = True)

    __default_tree_finalized = False

    
def modifyPModuleBranchDefault(branch, t):
    global __pmodule_branch_tree
    
    assert __pmodule_branch_tree is not None
    
    t = t.copy()
    t.attach(recursive = True)
    
    __pmodule_branch_tree.makeBranch(branch).update(t)
        

def finalizeDefaultTree():
    
    global __default_tree

    __default_tree = __default_tree.copy()
    __default_tree.update(__pmodule_branch_tree)
    __default_tree.attach(recursive = True)
    __default_tree.freeze()
    __default_tree_finalized = True
    
    __default_tree.freeze()
    
def globalDefaultTree():
    global __default_tree
    
    assert __default_tree is not None
    		
    return __default_tree

def getDefaultTree():
    
    global __default_tree
    
    return __default_tree.copy()