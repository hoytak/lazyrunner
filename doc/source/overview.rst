Overview 
=======================

LazyRunner is best thought of as a collection of processing modules
with a central parameter tree governing all input and configuration
parameters.  These processing modules are strung together by either
specifying dependencies or explicitly requesting results.  The former
is the more typical usage, but the latter allows more flexibility
(such as requesting results with parameters that differ from the
central tree).

Modular Structure
------------------

The computations are meant to be done through a sequence of modular
units called *processing modules.* A `processing module <Pmodule>`_ is
a module that takes as input a set of parameters and/or result trees
from other modules and produces a set of results based on that input.
For example, one module could load a dataset, storing the loaded data
and associated metadata in a TreeDict instance, returning that as the
result.  Another module could process that data, returning some
analysis; and a third module could print out that analysis in a pretty
way (e.g. a Latex table).

Processing modules have significant flexibility, see :ref:`pmodule` for more
information.

Caching
-------

The power of this setup comes partly from the caching ability.
Results from modules are, by default, cached; thus expensive
operations need to only be run once.  All parameters and dependencies
are automatically handled and considered in the caching.

Continuing the above example, suppose one wanted to benchmark an
algorithm run on a particular dataset and print out the result in a
Latex table; however, running the algorithm is time-consuming.  In a
naive setup, one would run each of them sequentially, with the
algorithm results being printed as a Latex table when it finished.
Now suppose the desired format of the result table changes. The user
is left with two undesirable options -- either manually edit the
table, which could be quite tedious, or rerun the algorithm, which
could be time-consuming. In the LazyRunner setup, however, the results
of running the algorithm would be quickly loaded from the cache.

Command Line & Requests
-----------------------

.. highlight:: bash

The LazyRunner framework is meant to be run from the command line
using concise and clear commands.  The main program script is
conveniently named `Z`.  The results of processing modules are
`requested` by specifying the associated module names on the command
line.  For example::

  $ Z analyzer

Would specify that the results from PModule `Analyzer` (case doesn't
matter here) should be obtained, either by loading them from cache or
calling :ref:`PModule.run`.  Note that either way, the results are
reported through the :ref:`PModule.reportResults` processing module
method.

In addition, this script makes it easy to create new modules or create
a new project altogether; run::

  $ Z --init

in an empty directory to create a new project, and run::

  $ Z -m running.Analyzer

to create a new processing module called `Analyzer`, contained in the
file ``running/analyzer.py``.  This file is added to the list of files
loaded by the script (through ``conf.py``), and ``running/analyzer.py``
contains an empty template file that's ready to be modified.

Centralized Parameters
----------------------

The parameters for the entire program are contained in a central
treedict_ data structure. This is done to enforce an organization on
the program.  Each processing module in the program has its own branch
in this central tree with the same name (in lower case) as the
processing module.  By default, this tree is specified in
``settings/defaults.py``.  TreeDict_, developed alongside LazyRunner,
simplifies the process of centrally organizing parameters.

For more advanced functionality, functions called :ref:`presets` can
modify this structure and be specfied by the command line.

Requests
--------

Requests are simply requests for the results of processing modules
based on a specified (usually the default) parameter tree.  Requests
are loaded either from cache or through the corresponding :ref:`run`
method.  

For the user requesting a result is the same action as asking for a
report of it; whenever a results is created or loaded, the the
:ref:`PModule.reportResults` processing module method logs any aspects
of it to the user.  

.. _treedict: http://www.stat.washington.edu/~hoytak/code/treedict/index.html
