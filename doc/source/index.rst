LazyRunner Introduction
=======================

LazyRunner is a framework for organized scientific computing.  It aims
to make it easy to write properly designed programs as quickly as
hacked-together scripts while providing useful features (such as
caching of results) that often take a fair bit of effort and planning
to implement in most scientific projects.  

Fast project startup:
  Starting up a complete new project is as easy as typing ``Z --init``
  on the command line.

Minimal Learning Curve:
  The program is thoroughly documented.  The command line version of
  the program creates template files for new components of the code.

Intuitive and simple: 
  A modular structure with easily-specified dependencies allow the
  entire programming process to be intuitive.  .

Documentation:
  In-code documentation for the modules easily turns into a reference
  site using Sphinx.

Motivation
----------

The development of LazyRunner grew out of my frustration at the length
of time often required to write good, reusable scientific code.  It
seems there are often two options -- either throw together some
scripts that work but are hard to reuse, or spend a reasonable amount
of time on writing boilerplate code.

Now admittedly, my standards for "good" code are pretty high relative
to much of the scientific coding community (e.g. TreeDict_, my
parameter-handling library, has hundreds of unit tests).  Thus good
coding practices are a must.

This library was motivated by realizing that most of the boilerplate
required to organize scientific code can be abstracted into a common
framework.  LazyRunner's workflow -- a modular structure with
centralized and hierarchical parameter organization -- works well for
most scientific projects.

Acknowledgments
----------------

Development of LazyRunner was supported in part by NGA grant
HM1582-06-1-2035.

.. toctree::
    :hidden:
    :maxdepth: 3

    self
    overview
    pmodules
    parameters
    commandline
    managerapi
    download
    license

.. _cython: http://www.cython.org/
.. _treedict: http://www.stat.washington.edu/~hoytak/code/treedict/index.html

