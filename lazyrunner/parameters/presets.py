"""
The central place for handling parameters.
"""

from treedict import TreeDict
from collections import namedtuple
import sys, textwrap
import re
import warnings
import os, struct
import inspect
from os.path import commonprefix
from common import cleanedPreset, checkNameValidity, combineNames
from parameters import getDefaultTree, modifyPModuleBranchDefault, modifyGlobalDefaultTree
import random
from copy import copy

################################################################################
# Global variables that hold the lookup tables

__preset_staging = None
__preset_staging_visited = None
__preset_lookup = None
__preset_description_lookup = None
__preset_tree = None
__preset_unique_prefix = 'PRESET_' + ('%06x' % random.randrange(256**3)) + "_"

################################################################################
# Stuff for keeping track of the parameter tree

def defaults():
    """
    The primary way for setting the default parameters in a tree.

    """
    global __preset_staging
    
    t = TreeDict('Default_Parameter_Tree', __defaultpresettree__ = True)
    __preset_staging[id(t)] = t
    return t

################################################################################
# Functions for pulling out the presets from a PModule

def processPModule(pm):

    global __default_tree
    global __preset_staging
    global __preset_staging_visited
    global __preset_unique_prefix

    already_processed = set()

    def _process_pmodule(pm, name):

        # Do it first so that higher level things are overridden by upper level ones
        for base in pm.__bases__:
            _process_pmodule(base, name)
        
        attr_dict = dict(inspect.getmembers(pm))
    
        for k, t in attr_dict.iteritems():
            
            if type(t) is TreeDict:
                if id(t) in __preset_staging and not id(t) in already_processed:
                    if t.get("__defaultpresettree__", False):
                        modifyPModuleBranchDefault(name, t)
                        __preset_staging_visited.add(id(t))
                    else:
                        pw = copy(__preset_staging[id(t)])
                        pw._prependPModuleContext(name)
                        __preset_staging[id(pw)] = pw
                        __preset_staging_visited.add(id(t))
                    
                    already_processed.add(id(t))

            elif (hasattr(t, "__name__") 
                  and t.__name__.startswith(__preset_unique_prefix)
                  and not t.__name__ in already_processed):
                                            
                p = copy(__preset_staging[t.__name__])
                p._prependPModuleContext(name)
                __preset_staging[id(p)] = p
                __preset_staging_visited.add(t.__name__)
                
                already_processed.add(t.__name__)
                
    _process_pmodule(pm, pm._name)
    
                
    
############################################################
# A container for holding the preset

class _PresetWrapper:

    def __init__(self, name, branch, action, description, apply):
        self.name = name
        self.branch = branch
        self.action = action
        self.description = description
        self.apply = apply

    def __call__(self, ptree, list_args = [], kw_args = {}):

        assert type(list_args) is list
        assert type(kw_args) is dict

        if self.apply:
            for ap in self.apply:
                if type(ap) is dict:
                    for k, v in ap.iteritems():
                        ptree[k] = v
                        
                elif type(ap) is str:
                    applyPreset(ap, ptree)
                    
                elif callable(ap):
                    args, varargs, keywords, defaults = getargspec(ap)
                    
                    if len(args) == 1:
                        ap(ptree)
                    else:
                        raise TypeError("Functions in apply list can only take one argument.")
                else:
                    raise TypeError("Incorrect type in apply list.")

        if self.branch is not None:
            ptree = ptree.makeBranch(self.branch, False)
            if type(ptree) is not TreeDict:
                raise TypeError("Requested branch '%' for preset '%s' not a branch."
                                % (self.branch, self.name))
            
        if type(self.action) is TreeDict:
            if kw_args or list_args:
                raise ValueError("Cannot pass arguments to a preset defined as a Tree.")
            
            ptree.update(self.action)
            
        else:
            self.action(ptree, *list_args, **kw_args)

    def _prependPModuleContext(self, n):
        self.name = combineNames(n, self.name)
        self.branch = combineNames(n, self.branch)


################################################################################
# Registering and looking up available presets

def __presetTreeName(n):
    if type(n) is str:
        return n.lower() + ".__preset__"
    elif type(n) is tuple:
        assert type(n[0]) is str
        return n[0].lower() + ".__preset__"
    else:
        raise TypeError

def __cleanPresetTreeName(n):
    return n.replace('.__preset__', "")

def resetAndInitPresets():
    global __preset_staging
    global __preset_staging_visited
    global __preset_lookup
    global __preset_description_lookup
    global __preset_tree

    __preset_staging = {}
    __preset_staging_visited = set()
    __preset_lookup = {}
    __preset_description_lookup = TreeDict('preset_descriptions')
    __preset_tree = None

def registerPreset(name, preset, branch = None, description = None,
                   apply = [], ignore_context = False):
    """
    Manually register a preset `preset` with name `name`.  The type of
    `preset` determines how it is applied when requested -- if a
    TreeDict, it is applied as an update to the parameter tree; if it
    is a function or other callable, applying the preset is done by
    calling the function with the parameter tree as the sole argument.

    If description is not None, it gives the description for the
    preset as appears in help contexts or by calling ``Z -l``.
    Otherwise, if preset is a function, the docstring is used as the
    description.  If preset is a TreeDict instance, as returned by
    presetTree, the attribute ``__description__`` may be set to the description.

    If `ignore_context` is True, a list of additional applications may
    be passed as well.  This follows the same format as described in
    :ref:`group`, with the two exceptions that it must be a list, even
    if it's only a list of a single item, and that TreeDict instances
    are not allowed.  These are applied before the preset is
    called/applied.

    Note that this function is normally not needed, as using the
    standard functions, :ref:`preset` and :ref:`presetTree`, do this
    automatically.
    """

    global __preset_staging
    global __preset_unique_prefix

    checkNameValidity(name)
    checkNameValidity(branch)

    if not ignore_context:
        ctx    = getCurrentContext()
        name   = combineNames(ctx.prefix, name)
        branch = combineNames(ctx.branch, branch)
        apply = ctx.apply

    # Get the description
    if description is None:
        if type(preset) is TreeDict:
            d = preset.get("__description__", "")
        else:
            d = preset.__doc__
    else:
        d = description

    if d is None:
        d = ""

    description = re.sub(r"\s+", " ", d)

    # Checks to make sure it's gonna work later on
    if type(preset) is not TreeDict:
        
        if not callable(preset):
            raise TypeError("Preset '%s' must be TreeDict or callable with parameter tree." % name)
        
        preset.__name__ = __preset_unique_prefix + name + str(id(preset))
        
        __preset_staging[preset.__name__] = _PresetWrapper(
            name, branch, preset, description, apply)
        
    else:
        __preset_staging[id(preset)] = _PresetWrapper(
            name, branch, preset, description, apply)


def finalizePresetLookup():

    lookup = {}
    
    for k in __preset_staging_visited:
        del __preset_staging[k]

    for pw in __preset_staging.itervalues():

        if type(pw) is TreeDict:
            del pw["__defaultpresettree__"]
            modifyGlobalDefaultTree(pw)
            continue

        preset_tree_name = __presetTreeName(pw.name)

        ret = lookup.setdefault(preset_tree_name, pw)

        if ret is not pw:
            if ret.action is not pw.action:
                warnings.warn( ("Possible duplicate preset name '%s'; \n "
                                "  original in module '%s'; ignoring "
                                "duplicate from module %s.")
                               % (pw.name, inspect.getmodule(ret.action), inspect.getmodule(pw.action))
                               )

    # Give everything over to the main preset thing
    assert __preset_lookup == {}
    __preset_lookup.update(lookup)


def registerPrefixDescription(prefix, description, ignore_context = False):
    """
    Registers `description` as a help tag for preset prefix `prefix`.
    When the preset list is requested with `Z -l`, presets with
    `prefix` are listed as a separate group described by `description`.
    For Example::
    
    
    """

    global __preset_description_lookup

    checkNameValidity(prefix)

    if not ignore_context:
        prefix = combineNames(getCurrentContext().prefix, prefix)

    if prefix is None:
        raise ValueError("Either prefix must be given or "
                         "this must be called within a group context.")

    __preset_description_lookup[prefix.lower() + ".__description__"] = \
         re.sub(r"\s+", " ", description)
    
    
def preset(prefix=None, branch = None, apply = None):
    """
    A decorator that registers a function as a preset.  The function
    it decorates must accept take the parameter tree it's modifying as
    its sole parameter.

    `preset` may be used with or without arguments.  If used with
    arguments, it can take any combination of three arguments.

    `prefix` prepends a tag to the preset name, separated by a period.
    These are added in addition to those given by the current group
    context, if present. For example::

        @preset(prefix = 'pr')
        def box(p):
            # ....

    defines a preset callable as ``pr.box``.

    `branch` specifies the operating branch of the preset.  If given,
    the parameter tree passed to the function will be this branch of
    the current tree.  For example::

        @preset(branch = 'data')
        def box(b):
            # b is the data branch of the parameter tree
        
    `apply` allows an alternative way to modify the parameter tree
    before it is passed to this function.  The format is the same as
    that for the `apply` parameter of :ref:`group`.  The typical use
    case would be to apply other presets before this one -- for
    example, if 'data_setup' is another preset::

        @preset(apply = 'data_setup')
        def box(p):
            # ...

    applies ``data_setup`` prior to calling `box`.

    Within a ``with group(...):`` construct (see :ref:`group`), prefix
    tags and branches are appended to those specified by the with
    statement(s).

    Example 1::
    
        # Registers a preset with name 'box' that sets leaf
        # 'dataset.style' to 'a box' in the main parameter tree.

        @preset
        def box(p):
            p.datset.style = 'a box'
           
    Example 2::

        # Same as example 1, except that the prefix is called 'data.box'.

        @preset('data', branch = 'dataset')
        def box(b):
            # Now `b` is the 'dataset' branch of the central parameter tree
            b.style = 'a box'

    Example 3 -- within a group::

        # Same as example 2
        with group(prefix = 'data', branch = 'dataset'):
            @preset
            def box(b):
                b.style = 'a box'

    """

    if type(prefix) is str or prefix is None:
        return PresetContext(prefix, branch, apply = apply)

    else:
        f = cleanedPreset(prefix)
        registerPreset(f.__name__, f, ignore_context = False)

        return f

def presetTree(name, branch = None, description = None):
    """
    Returns a TreeDict instance registered as a preset with the name
    `name`.  This TreeDict instance (modified after being returned
    from this function) will be applied as an update to the central
    paramter tree when preset `name` is requested.  If branch is not
    None, it is applied to that branch.  `description`, if given, adds
    a description to the preset, displayed when presets are listed.

    Example 1::

        p = presetTree('box', 'dataset')
        p.preset = 'box'
        p.dimensions = (3,3,2)

    In the above example, when preset `box` is applied, it changes
    ``p.dataset.datatype`` to ``'box'`` and ``p.dataset.dimensions``
    to ``(3,3,2)`` (where ``p`` represents the central parameter
    tree).
    
    """

    checkNameValidity(name)
    checkNameValidity(branch)

    pt = TreeDict("preset")

    registerPreset(name, pt, branch, description, ignore_context = False)

    return pt
    
################################################################################
# Describing/listing the different presets.

def allPresets():
    """
    Returns a list of all the currently registered presets.
    """

    return [__cleanPresetTreeName(k) for k in __preset_lookup.iterkeys()]

################################################################################
# Applying the preset

class BadPreset(Exception): pass

def applyPreset(*args, **kwargs):
    """
    Applys one or more presets to a given parameter tree.  The
    arguments to `applyPreset` must be exactly one TreeDict instance
    to be modified and one or more strings specifying presets to be
    applied.  This function accepts arguments in any order, but the
    presets are applied in the order in which they are specified. 

    Note that the presets must be specified using their full names, as
    the ``with`` statements generally apply only to declarations.

    Example 1::

      # Define a preset that simply calls two other presets.
      @preset
      def my_problem(p):
          applyPreset('box', p)
          applyPreset('solver1', p)

    Examples::

        # This is identical to Example 1
      @preset
      def my_problem(p):
          applyPreset(p, 'box', 'solver1')
    
    """

    global __preset_lookup
    global __preset_description_lookup
    
    preset_names = [n for n in args if type(n) is str]
    ptree_list = [t for t in args if type(t) is TreeDict]

    if len(ptree_list) != 1:
        raise TypeError("Exactly one TreeDict instance must be passed to applyPreset().")
    elif len(preset_names) == 0:
        return
    elif len(preset_names) + len(ptree_list) != len(args):
        raise TypeError("Arguments to applyPreset() must be preset names and one TreeDict instance.")
       
    ptree = ptree_list[0]

    # assume that it may be passed a branch of the parameter tree
    ptree = ptree.rootNode()
    ptree.attach(recursive = True)

    for n in preset_names:
    
        try:
            preset = __preset_lookup[__presetTreeName(n)]
        except KeyError:
            msgs = validatePresets(preset_names)
            raise BadPreset('\n'.join( (("\n Preset '%s' not found; did you mean:\n " % pname)
                                        + ('\n'.join(msg)) ))
                            for (pname, msg) in msgs)
            
        preset(ptree)
                
    return True

################################################################################
# Preset Context -- the mechanism behind the with group() statements

_preset_context_stack = []

class PresetContext(object):

    register_preset_function = None

    # When initializing a context, it is always parameters of interest 
    def __init__(self, prefix = None, branch = None, description = None, apply = None):

        global _preset_context_stack

        if prefix is not None:
            prefix = prefix.lower()
            
        if branch is not None:
            branch = branch.lower()
        
        checkNameValidity(prefix)
        checkNameValidity(branch)

        if _preset_context_stack:
            context = _preset_context_stack[-1]

            self.prefix = combineNames(context.prefix, prefix)
            self.branch = combineNames(context.branch, branch)
            self.apply  = [l for l in context.apply]
            
        else:
            self.prefix = prefix
            self.branch = branch
            self.apply = []

        # Update the apply
        if apply is not None:
            def addToCurrentStack(ap):

                if type(ap) is dict or type(ap) is TreeDict:
                    d = {}
                    for k, v in ap.iteritems():
                        checkNameValidity(k)
                        d[combineNames(self.branch, k)] = v
                        
                    self.apply.append(d)
                    
                elif type(ap) is str:
                    self.apply.append(ap)

                elif type(ap) is list or type(ap) is tuple:
                    for v in ap:
                        addToCurrentStack(v)
                        
                else:
                    raise TypeError("Argument types to apply() must be dict, TreeDict, "
                                    "a preset name (string), or a list/tuple of these.")
                
            addToCurrentStack(apply)

        if self.prefix is not None and description is not None:
            registerPrefixDescription(self.prefix, description, ignore_context = True)

    # Called when used as a decorator; registers the function
    def __call__(self, f):
        name = f.__name__
        registerPreset(combineNames(self.prefix, name), f, branch = self.branch,
                       apply = self.apply, ignore_context = True)

        return cleanedPreset(f)

    # The functionality for a with statement
    def __enter__(self):
        global _preset_context_stack

        _preset_context_stack.append(self)
        return self

    def __exit__(self, type, value, traceback):
        global _preset_context_stack

        assert _preset_context_stack[-1] is self
        _preset_context_stack.pop()

_preset_context_stack.append(PresetContext(None, None, None))

def getCurrentContext():
    return _preset_context_stack[-1]

def ensureValidPModuleContext(pm):
    if len(_preset_context_stack) > 1:
        raise Exception("PModule '%s' cannot be defined within a prefix group." % pm.name())

################################################################################
# Now, for the with statements, we can use the following:

def group(prefix = None, branch = None, description = None, apply = None):
    """
    Enables organization of presets through the use of a with
    statement; by itself, this function does nothing.  Typical use
    is::

        with group(prefix = 'g1', branch = 'b1', description='my group'):
            # preset definitions ...

    This prepends the prefix ``g1`` to all presets defined within that
    block, and sets all of them to operate on branch 'b1'.
    Descriptions then show up when listing prefixes.

    The parameter `prefix`, when given, prepends `prefix`, plus a
    period, to the names of all presets given within the ``with
    group()`` statement.  For example::

        with group('g1'):
            presetTree('set_a').a = 1

    defines a preset named ``g1.set_a`` that sets ``p.a = 1``.

    The parameter `branch`, when given, sets the branch of the current
    local tree to `branch`.  All presets within this group then
    operate on this branch.  For example::

        with group(branch = 'mymodule'):
            presetTree('set_a').a = 1

    defines a preset named ``set_a`` that sets ``p.mymodule.a = 1``.

    If group is not None and `description` is given, the given
    description string is added to the help display of the
    command-line preset list.  This is equivalent to calling
    :ref:`registerPrefixDescription` on the same group.

    Presets within a ``with group()`` statement may be defined using
    either :ref:`prefix` or :ref:`presetTree`.  Thus the following
    examples are all equivalent, defining a preset named ``g1.set_a``
    that sets ``p.mymodule.a = 1``::

        # Version 1
        presetTree('g1.set_a').mymodule.a = 1

        # Version 2
        @prefix(group = 'g1', branch = 'mymodule')
        def set_a(p):
            p.a = 1

        # Version 3
        with group('g1', 'mymodule'):
            presetTree('set_a').a = 1

        # Version 4
        with group('g1'):

            @prefix
            def set_a(p):
                p.mymodule.a = 1
    
    Furthermore, with statements may be nested.  Again, the following
    are equivalent, each defining a preset named ``g1.subgroup.set_a``
    that sets ``g1.mymodule.data.a = 1``::

        # Version 1
        with group(prefix = 'g1.subgroup', branch = 'mymodule.data'):
            presetTree('set_a').a = 1

        # Version 2
        with group('g1', 'mymodule'):
            with group('subgroup', 'data'): 
                presetTree('set_a').a = 1

        # Version 3
        with group('g1'):
            with group(branch = 'mymodule'):
                with group('subgroup'):
                    with group(branch = 'data'):
                        presetTree('set_a').a = 1

    Finally, presets within a group can have common parameters set
    through options passed to `apply`.  `apply` can accept a
    dictionary, a TreeDict instance, the name of another preset, or a
    list of any combination of these items.  When any preset within
    this group is applied, the parameter tree is first updated with
    the values given by `apply`.  If a dictionary or TreeDict instance
    is given, the parameter tree is updated with all the (key, value)
    pairs.

    If the name of another preset is given, then it is applied; in
    this case, the operating branch of this preset is respected.

    If a list of any of these items is given, then each is applied in
    order. For example, the following examples all create a preset
    named ``set_x`` that sets ``p.data.x = 1``, ``p.data.b.x = 2``,
    and ``p.data.b.y = 3``::

        # Version 1 -- dictionary
        with group(branch = 'data', apply = {'b.x' : 2, 'b.y' : 3} ):

            @preset
            def set_x(p):
                p.x = 1


        # Version 2 -- TreeDict instance
        t = TreeDict()
        t.b.x = 2
        t.b.y = 2

        with group(branch = 'data', apply = t):
            presetTree('set_x').x = 1

        # Version 3 -- other preset

        @preset(branch = 'data.b')
        def setup_data_b(p):
            p.x = 2
            p.y = 3
        
        with group(branch = 'data', apply = 'setup_data_b'):
            
            @preset
            def set_x(p):
                p.x = 1
            
        # Version 4 -- separated with statements
        with group(branch = 'data'):
            with group(apply = {'b.x' : 2, 'b.y' : 3} ):
                presetTree('set_x').x = 1

        # Version 5 -- using a list 
        with group(branch = 'data', apply = [{'b.x' : 2}, {'b.y' : 3}] ):
            presetTree('set_x').x = 1

    """
    
    return PresetContext(prefix, branch, description, apply)


################################################################################
# A few internal utility functions 

def _getTerminalSize():
    """
    returns (lines:int, cols:int)
    """

    def ioctl_GWINSZ(fd):
        import fcntl, termios
        return struct.unpack("hh", fcntl.ioctl(fd, termios.TIOCGWINSZ, "1234"))
    # try stdin, stdout, stderr
    for fd in (0, 1, 2):
        try:
            return ioctl_GWINSZ(fd)
        except:
            pass
    # try os.ctermid()
    try:
        fd = os.open(os.ctermid(), os.O_RDONLY)
        try:
            return ioctl_GWINSZ(fd)
        finally:
            os.close(fd)
    except:
        pass
    
    # try `stty size`
    try:
        return tuple(int(x) for x in os.popen("stty size", "r").read().split())
    except:
        pass
    # try environment variables
    try:
        return tuple(int(os.getenv(var)) for var in ("LINES", "COLUMNS"))
    except:
        pass
    # i give up. return default.
    return (25, 80)


def getPresetHelpList(preset_list = None, width = None):

    global __preset_lookup
    global __preset_description_lookup

    if width is None:
        width = _getTerminalSize()[1]

        if width == 0:
            width = 120
            
        if width < 10:
            width = 10

    max_name_width = 25 #max(int(width / 3), 30)

    def printBlock(print_list, item_list, prefix="", start_width = None):

        if not item_list:
            return

        if start_width is None:
            start_width = min(max(len(n) for n, d in item_list) + 2 + len(prefix), max_name_width)
        else:
            start_width += 2

        for n, d in item_list:
            d = d.strip()
            n = n.strip()

            if not n and not d:
                continue
            
            if len(n) > start_width - len(prefix):
                print_list.append( prefix + n)
                initial = " "*(start_width + 2)
            else:
                initial = prefix + n + " "*(start_width - len(n))

            if d:

                print_list += textwrap.wrap(
                    d, width,
                    initial_indent = initial,
                    subsequent_indent = " "*(start_width))
                
            else:
                print_list.append(initial)
        
    # Once we have everything, run through it all
    class Group:
        def __init__(self, name, description):
            self.name = name.strip()
            self.description = description.strip()
            self.items = {}

        def add(self, name, description):
            name = name.strip()
            if not name:
                return
            
            self.items[name] = description

        def printGroup(self, print_list, width):

            if not self.items:
                return
            
            if self.name:
                print self.name + ": " + self.description
                printBlock(print_list, sorted(self.items.iteritems()), "  ", width)
            else:
                printBlock(print_list, sorted(self.items.iteritems()), "", width+2)

    class GroupOrganizer:

        def __init__(self):

            self.name_map = {}
            self.group_map = {}

        def addGroup(self, name, description):
            name = name.strip()
            description = description.strip()
            self.group_map[name] = description

        def addPreset(self, name, description):
            name = name.strip()
            description = description.strip()
            if name:
                self.name_map[name] = description

        def printGroups(self, print_list):

            if not self.name_map:
                return
            
            def _getGroupName(group_map, name):

                group = ''

                if name in group_map:
                    return name

                # Get whether it's a part of a group
                cur_pos = 0

                while True:
                    cur_pos = name.find('.', cur_pos+1)

                    if cur_pos == -1:
                        break

                    if name[:cur_pos] in group_map:
                        group = name[:cur_pos]

                return group

            # put all the groups together
            groups = dict( (n, Group(n, d) ) for n, d in self.group_map.iteritems())
            groups[''] = Group('', '')
            
            # put all the presets into groups
            for n, d in self.name_map.iteritems():
                g = _getGroupName(groups, n)
                if g == n:
                    groups[g].add(n, "(As preset) " + d)
                else:
                    groups[g].add(n, d)

            print_width = max(len(n) for n in self.name_map.iterkeys())

            # give them back
            for k, g in sorted(groups.iteritems()):
                g.printGroup(print_list, print_width)


    ##################################################
    # This is to deal with the special case of presets also being names
    pl_alt = TreeDict()
    pl_alt.update( (__cleanPresetTreeName(k), v)
                   for k,v in sorted(__preset_lookup.iteritems(), reverse=True) )

    __preset_description_lookup.attach(recursive = True)

    print_list = []

    org = GroupOrganizer()

    if preset_list is None:

        # Have to sanitize the description tree
        for k in pl_alt.iterkeys(recursive = True, branch_mode = 'only'):
            query_key = k + ".__description__"
            d = __preset_description_lookup.get(query_key, None)
            org.addGroup(k, d if d else "")

        for n in sorted(pl_alt.iterkeys(recursive = True, branch_mode = 'all')):

            k = __presetTreeName(n)

            if k in __preset_lookup:
                org.addPreset(n, __preset_lookup[k].description)

        org.printGroups(print_list)

    else:
        printBlock(print_list, [(n, __preset_lookup[__presetTreeName(n)].description) for n in preset_list])

    return print_list


class PCall(object):
    
    def __init__(self, preset_name, *args, **kwargs):
        
        if type(preset_name) is not str and preset_name is not None:
            raise TypeError("Preset name must be a string.")        
            
        self._preset_name_ = preset_name
        self._preset_args_ = list(args)
        self._preset_kwargs_ = kwargs
        
    def __call__(self, *args, **kwargs):
        self._preset_args_ = list(args)
        self._preset_kwargs_ = kwargs
        return self
        
    def __getattr__(self, attr):
        
        # Prevent the pickler from getting very confused
        if attr.startswith("__") and attr.endswith("__"):
            raise AttributeError
        
        if attr == "clear":
            # Clears all modifications of the preset tree and restores it to its original.
            return PClearTree(self._preset_name_)

        return PCall(combineNames(self._preset_name_, attr))
        
    def __treedict_hash__(self):
        p = getParameterTree([self], TreeDict())
        return p.hash()
            
        
        
        
class PDeltaTree(object):
    
    def __init__(self, tree):
        self.tree = tree.copy()
        self.tree.attach(recursive = True)

    def __call__(self, p_tree):
        p_tree.update(self.tree)
        
class PClearTree(object):
    def __init__(self, name):
        self.name = name
        self._preset_name_ = name + ".clear"
        
    def __call__(self, parameters=None, list_args=None, kw_args=None):
        if parameters is None:
            return self
        
        parameters[self.name].clear()
        parameters[self.name].update(getDefaultTree()[self.name])


def updatePresetCompletionCache(filename):
    """
    Saves a list of the current presets to a temporary file.  This is
    to speed up tab completion for preset names.

    """

    f = open(filename, 'w')
    f.write(" ".join(allPresets()))
    f.close()
    
################################################################################
# Now methods for gracefully handling errors

def getPresetCorrectionMessage(preset, n_close = 5, width = 80):
    global __preset_tree

    if __preset_tree is None:
        __preset_tree = TreeDict.fromdict(__preset_lookup)
                                          
    preset = preset.lower()

    startwith_list = [__cleanPresetTreeName(k)
                      for k in __preset_tree.iterkeys() if k.startswith(preset)]

    closest = [__cleanPresetTreeName(nc)
               for nc in __preset_tree.getClosestKey(__presetTreeName(preset), n_close)]

    for k in (set(closest) & set(startwith_list)):
        closest.pop(closest.index(k))

    return getPresetHelpList(startwith_list + closest, width = width)


def validatePresets(*presets):
    """
    Returns list of tuples (bad preset, message if bad).
    """

    def translate(n):
        if type(n) is str:
            pass
        elif type(n) is tuple:
            n = n[0]
        elif isinstance(n, PCall):
            n = n._preset_name_
        else:
            raise TypeError("Preset type not recognized for '%s'." % n)
        
        if type(n) is not str:
            raise TypeError("Preset type not recognized for '%s'." % n)
        
        return n
        
    
    presets = [translate(n) for n in presets]

    return [(n, getPresetCorrectionMessage(n))
            for n in presets
            if __presetTreeName(n) not in __preset_lookup]


PresetInfo = namedtuple('PresetInfo', 
                        ['name', 'preset', 'list_args', 'kw_args'])

def parsePreset(preset):
    
    if type(preset) is str:
            
        if ":" in preset:
            args = [s.strip() for s in preset.split(":")]
            
            name = args[0].lower()
            preset_wrapper = __preset_lookup[__presetTreeName(name)]
            list_args = []
            kw_args = {}
            
            for s in args[1:]:            
                if "=" in s:
    
                    index = s.find("=")
                    name = s[:index].strip()
                    
                    # Check the name
                    name_check = name.replace("_", "")
                    
                    if not (name_check[0].isalpha() and name_check.isalnum()):
                        raise NameError("Argument '%s' not a valid name." % name)
                    
                    kw_args[name] = s[index + 1 :].strip()
                    
                else:
    
                    if kw_args:
                        raise ValueError("Keyword arguments in '%s' must be specified after positional arguments." % pi.name)
                    
                    list_args.append(s)
                    
            def convertType(s):
                try:
                    s = float(s)
                except ValueError:
                    return s

                si = int(s)
                if si == s:
                    return si
                else:
                    return s
                
            list_args = [convertType(s) for s in list_args]
            kw_args = dict( (k, convertType(v)) for k, v in kw_args.iteritems())
            
        else:
            name = preset.lower()
            preset_wrapper = __preset_lookup[__presetTreeName(name)]
            list_args = []
            kw_args = {}
            
    elif isinstance(preset, PCall):
        name = preset._preset_name_.lower()
        preset_wrapper = __preset_lookup[__presetTreeName(name)]        
        list_args = preset._preset_args_
        kw_args = preset._preset_kwargs_
    
    elif isinstance(preset, PClearTree):
        name = preset._preset_name_.lower()
        preset_wrapper = preset     
        list_args = []
        kw_args = {}

    elif type(preset) is TreeDict:
        name = None
        preset_wrapper = PDeltaTree(preset)
        list_args = []
        kw_args = {}
            
    elif isinstance(preset, PresetInfo):
        return preset
                
    else:
        def raiseException():
            raise TypeError("Preset must be either string or (name, list_args[, arg_dict]) tuple.")

        if type(preset) is tuple:
            
            if len(preset) == 2:
                name, list_args = preset
                kw_args = {}
            elif len(preset) == 3:
                name, list_args, kw_args = preset
            else:
                raiseException()
            
            if not (type(list_args) is list and type(kw_args) is dict):
                raiseException()
                
        else:
            if type(preset) is not str:
                raiseException()
            
            name, list_args, kw_args = preset, [], {}
        
        name = name.lower()
        preset_wrapper = __preset_lookup[__presetTreeName(name)]
        
    return PresetInfo(
        name = name,
        preset = preset_wrapper,
        list_args = list_args,
        kw_args = kw_args)

def getParameterTree(presets, parameters = None):
    """
    Returns the parameter tree 
    """
    
    try:
        preset_list = [parsePreset(n) for n in presets]
    except KeyError:
        msgs = validatePresets(*presets)
        raise BadPreset('\n'.join( (("\n Preset '%s' not found; did you mean:\n " % pname)
                                    + ('\n'.join(msg)) )
                        for (pname, msg) in msgs))
    
    if parameters is None:
        parameters = getDefaultTree()
    else:
        assert type(parameters) is TreeDict
    
    for pt in preset_list:
        pt.preset(parameters, pt.list_args, pt.kw_args)
        
    parameters.attach(recursive = True)
    parameters.freeze()

    return parameters
            
def parsePresetStrings(ps_list):
    """
    Parses parameter tree arguments 
    """

    return [parsePreset(ps) for ps in ps_list]


