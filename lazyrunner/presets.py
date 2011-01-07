"""
The control base for the preset parameter definitions.
"""

from treedict import TreeDict
import sys, textwrap
import re
import warnings

################################################################################
# A few quick functions

name_validator = re.compile(r"\A([a-zA-Z_]\w*)(\.[a-zA-Z_]\w*)*\Z")

def checkNameValidity(n):
    global name_validator

    if n is not None:
        if type(n) is not str:
            raise TypeError("Name/prefix/branch must be string.")
        elif name_validator.match(n) is None:
            raise NameError("'%s' not a valid preset tag/name." % n)

################################################################################
# Global variables that hold the lookup tables

_preset_lookup = TreeDict('presets')
_preset_description_lookup = TreeDict('preset_descriptions')
_preset_keyset = set()

################################################################################
# The current context is largely used by with statements to ensure
# that the current context supports it

_preset_context_stack = []

class _PresetContext(object):

    # When initializing a context, it is always parameters of interest 
    def __init__(self, prefix = None, branch = None, description = None, apply = None):

        global _preset_context_stack
        global _combine

        if prefix is not None:
            prefix = prefix.lower()
            
        if branch is not None:
            branch = branch.lower()
        
        checkNameValidity(prefix)
        checkNameValidity(branch)

        if _preset_context_stack:
            context = _preset_context_stack[-1]

            self.prefix = _combine(context.prefix, prefix)
            self.branch = _combine(context.branch, branch)
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
                        d[_combine(self.branch, k)] = v
                        
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
        registerPreset(_combine(self.prefix, name), f, branch = self.branch,
                       apply = self.apply, ignore_context = True)

    # The functionality for a with statement
    def __enter__(self):
        global _preset_context_stack

        _preset_context_stack.append(self)
        return self

    def __exit__(self, type, value, traceback):
        global _preset_context_stack

        assert _preset_context_stack[-1] is self
        _preset_context_stack.pop()

_preset_context_stack.append(_PresetContext(None, None, None))

class BadPreset(Exception): pass

################################################################################
# Registering and looking up available presets

def __presetTreeName(n):
    return n.lower() + ".__preset__"

def __cleanPresetTreeName(n):
    return n.replace('.__preset__', "")

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

    global _preset_context_stack

    checkNameValidity(name)
    checkNameValidity(branch)

    if not ignore_context:
        context = _preset_context_stack[-1]
        name   = _combine(context.prefix, name)
        branch = _combine(context.branch, branch)
        apply = context.apply

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
    if type(preset) is not TreeDict and not callable(preset):
        raise TypeError("Preset '%s' must be callable" % name)

    # See if it's multiply defined; issue a warning if so
    preset_tree_name = __presetTreeName(name)
    
    if preset_tree_name in _preset_keyset:
        pw = _preset_lookup[preset_tree_name]

        if pw.action != preset:
            warnings.warn("Possible duplicate preset '%s'; ignoring second." % name)
            
    else:
        # Register it
        _preset_lookup[preset_tree_name] = _PresetWrapper(name, branch, preset, description, apply)
        _preset_keyset.add(name.lower())

def registerPrefixDescription(prefix, description, ignore_context = False):
    """
    Registers `description` as a help tag for preset prefix `prefix`.
    When the preset list is requested with `Z -l`, presets with
    `prefix` are listed as a separate group described by `description`.
    For Example::
    
    
    """

    global _preset_lookup
    global _preset_context_stack
    global _preset_description_lookup

    checkNameValidity(prefix)

    if not ignore_context:
        context = _preset_context_stack[-1]
        prefix = _combine(context.prefix, prefix)

    if prefix is None:
        raise ValueError("Either prefix must be given or "
                         "this must be called within a group context.")

    _preset_description_lookup[prefix.lower() + ".__description__"] = \
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
        return _PresetContext(prefix, branch, apply = apply)

    else:
        f = prefix
        registerPreset(f.__name__, f, ignore_context = False)

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

    return [__cleanPresetTreeName(k) for k in _preset_lookup.keys()]

################################################################################
# Applying the preset

def applyPreset(*args):
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

    global _preset_lookup
    global _preset_context_stack
    global _preset_description_lookup
    
    preset_names = [n for n in args if type(n) is str]
    ptree_list = [t for t in args if type(t) is TreeDict]

    if len(ptree_list) != 1:
        raise TypeError("Exactly one TreeDict instance must be passed to applyPreset().")
    elif len(preset_names) == 0:
        return
    elif len(preset_names) + len(ptree_list) != len(args):
        raise TypeError("Arguments to applyPreset() must be preset names and one TreeDict instance.")
       
    ptree = ptree_list[0]

    for n in preset_names:
    
        n = n.lower()

        if n not in _preset_keyset:
        
            startwith_list = [__cleanPresetTreeName(k)
                for k in _preset_lookup.iterkeys() if k.startswith(n)]

            closest = [__cleanPresetTreeName(nc)
                       for nc in _preset_lookup.getClosestKey(__presetTreeName(n), 5)]

            for k in (set(closest) & set(startwith_list)):
                closest.pop(closest.index(k))

            print_list = startwith_list + closest

            if print_list:
                print "\nPreset '%s' not found; do you mean one of these?\n" % n

                printPresetHelpList(print_list)

                print ""

            raise BadPreset("Bad preset value.")
            
        _preset_lookup[__presetTreeName(n)](ptree)

    return True

    
############################################################
# Now some preset containers for operating on portions of the tree

class _PresetWrapper:

    def __init__(self, name, branch, action, description, apply):
        self.name = name
        self.branch = branch
        self.action = action
        self.description = description
        self.apply = apply

    def __call__(self, ptree):

        if self.apply:
            for ap in self.apply:
                if type(ap) is dict:
                    for k, v in ap.iteritems():
                        ptree[k] = v
                        
                elif type(ap) is str:
                    applyPreset(ap, ptree)
                    
                else:
                    raise TypeError("Incorrect type in apply list.")

        if self.branch is not None:
            ptree = ptree[self.branch]
            if type(ptree) is not TreeDict:
                raise TypeError("Requested branch '%' for preset '%s' not a branch."
                                % (self.branch, self.name))
            
        if type(self.action) is TreeDict:
            ptree.update(self.action)
            
        else:
            self.action(ptree)

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
    
    return _PresetContext(prefix, branch, description, apply)
    

################################################################################
# A few helper functions that affect the parameter tree; used by
# internal presets and external calls
        
def addToRunQueue(p, *modules):
    """
    Adds one or more modules to the queue of modules to be run in the
    parameter tree `p`.  These are run in the order added, starting
    with those (possibly) given in the default settings file.
    """

    p.setdefault('run_queue', [])
    
    for m in modules:
        if type(m) is not str:
            raise TypeError("Type of module in run queue must be str (not '%s')" % str(type(m)))
            
        p.run_queue.append(m.lower())

################################################################################
# A few internal utility functions 

def _combine(k1, k2):
    if k1 is None:
        return k2
    elif k2 is None:
        return k1
    else:
        return k1 + "." + k2

def printPresetHelpList(n_list = None):

    global _preset_lookup
    global _preset_description_lookup

    # This is to deal with the special case of presets also being names
    pl_alt = TreeDict()
    pl_alt.update( (__cleanPresetTreeName(k), v)
                   for k,v in sorted(_preset_lookup.iteritems(), reverse=True) )

    _preset_description_lookup.attach(recursive = True)

    def printBlock(block):
        fwidth = max(max(len(n) for n, d in block) + 2, 20)

        # Check this
        tw = textwrap.TextWrapper(width=80, subsequent_indent = " "*fwidth)

        for n, d in block:
            assert type(d) is str
            print n + " "*(fwidth - len(n)) + '\n'.join(tw.wrap(d))

    if n_list is None:

        # Have to sanitize the description tree
        headers = {}

        for k in pl_alt.iterkeys(recursive = True, branch_mode = 'only'):

            query_key = k + ".__description__"
            
            d = _preset_description_lookup.get(query_key, None)

            if d is not None:
                assert type(d) is str
                headers[k] = k + ":  " + d

            else:
                headers[k] = k + ": "

        # Now go through and get a breakup of the different groups
        current_prefix = None
        groups = []
        singles = []

        for n, v in sorted(pl_alt.iteritems(recursive = True, branch_mode = 'all')):

            if n in headers:
                assert type(v) is TreeDict
                current_prefix = n

                kq = __presetTreeName(n)

                if kq in _preset_lookup:
                    assert isinstance(_preset_lookup[kq], _PresetWrapper)
                                      
                    groups.append( (headers[n], [(' < applied >', _preset_lookup[kq].description) ]) )
                else:
                    groups.append( (headers[n], []) )

            else:
                assert isinstance(v, _PresetWrapper)

                if '.' not in n:
                    singles.append( (n, v.description) )

                else:
                    if not n.startswith(current_prefix):
                        n_base = n[:n.rfind('.')]
                        assert current_prefix.startswith(n_base)
                        current_prefix = n_base
                        
                    groups[-1][1].append((" " + n[len(current_prefix):], v.description))

        # Now we're ready to print it all
        for head, block in groups:
            print head
            printBlock(block)
            print ""

        if singles:
            printBlock(singles)
    else:
        printBlock([(n, _preset_lookup[__presetTreeName(n)].description) for n in n_list])
