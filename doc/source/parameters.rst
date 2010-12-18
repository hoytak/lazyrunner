
.. currentmodule:: lazyrunner

Parameters and Presets
======================

A central parameter tree governs the behavior of all the processing
modules.  This centralized parameter system is kept sane by employing
a hierarchical structure as enabled by TreeDict_.  Within this system,
Presets -- each a collection of changes to the default values of the
parameter tree -- allows program options to be specified on the
command line.  

The Central Parameter Tree
--------------------------

.. highlight:: python

The default central parameter tree is given in the file
``settings/defaults.py``.  In this file, a TreeDict_ instance with the
name `p` is created, and default values for all the parameters are
given.  For example, if we have we have two processing modules,
`Loader` and `Benchmark`, ``default.py`` might look like this::

    from treedict import TreeDict as TD

    p = TD("Parameters")

    p.run_queue = "Benchmark"

    p.loader.source_dir = "data/or-library"
    p.loader.source_file = "bqp50"

    p.benchmark.algorithm = "ITS"
    
In this example, ``p.loader`` and ``p.benchmark`` specify branches of
the central tree corresponding to the associated processing modules.
These branches are always a lower case version of the processing
module name.

Run Queue
~~~~~~~~~

One particular branch is noteworthy as it gives the default processing
module to run.  ``p.run_queue`` specifies either a single processing
module or a list of processing modules whose results to always
request.  If the :ref:`Z` script is run with no arguments, results
from the modules in ``p.run_queue`` are requested.  The default is to
leave it empty.

Presets
-------

Presets encode and organize modifications to the central parameter
tree. These modifications can be functions modifying the parameter
tree, TreeDict_ instances applied as updates, or references to other
presets.  They are always applied before any processing module is run.

Typically, presets are specified on the command line; for example::

  Z dataset1 r.solver1

would apply two presets, ``dataset1`` and ``r.solver1`` to the central
parameter tree.  Presumably, ``dataset1`` would the set the dataset to
be processed, and ``r.solver1`` would set the processing module in
``p.run_queue`` to ``r.solver1``.  All processing modules are
automatically available as ``r.<name>``, which adds that module to the
run queue.  Custom presets are declared using a handful of functions
described below.

Preset Declaration
~~~~~~~~~~~~~~~~~~

Presets can be specified in two basic ways.  The first is by defining
a function taking a parameter tree and modifying it.  A function is
declared to be a preset through the use of the :ref:`preset`
decorator, described below.  The second way is by defining an "update
tree", a parameter tree that is applied to the parameter tree as an
update.  The :ref:`presetTree` function allows this to happen.

.. autofunction:: preset

.. autofunction:: presetTree

Preset Organization
~~~~~~~~~~~~~~~~~~~

Presets are easily organized through groups, which use Python's
``with`` statement to allow preset organization.

.. autofunction:: group

Preset Utility Functions
~~~~~~~~~~~~~~~~~~~~~~~~

The following utility functions can be called from within a preset
function to either apply another preset (:ref:`applyPreset`) or add
one or more new modules to the run queue (:ref:`addToRunQueue`).

.. autofunction:: applyPreset

.. autofunction:: addToRunQueue


Low-level Functions
~~~~~~~~~~~~~~~~~~~

The following functions are used internally but are made available if
they are needed.

.. autofunction:: registerPreset

.. autofunction:: allPresets



.. _treedict: http://www.stat.washington.edu/~hoytak/code/treedict/index.html
