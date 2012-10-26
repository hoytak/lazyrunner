from treedict import TreeDict
import re
from inspect import ismethod

################################################################################
# A few quick functions for validation

__name_validator = re.compile(r"\A([a-zA-Z_]\w*)(\.[a-zA-Z_]\w*)*\Z")

def checkNameValidity(n):
    global __name_validator

    if n is not None:
        if type(n) is not str:
            raise TypeError("Name/prefix/branch must be string.")
        elif __name_validator.match(n) is None:
            raise NameError("'%s' not a valid preset tag/name." % n)

def cleanedPreset(f):
    return staticmethod(f) if ismethod(f) else f

def combineNames(k1, k2):
    if k1 is None:
        return k2
    elif k2 is None:
        return k1
    else:
        return "%s.%s" % (k1, k2)
