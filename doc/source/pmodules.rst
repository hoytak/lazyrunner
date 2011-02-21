
.. _pmodule:

.. currentmodule:: lazyrunner

==================
Processing Modules
==================

A processing module is a class that inherits the base class
:ref:`PModule` and is registered by decorating the class with
``pmodule``.  As such, we'll often refer to a processing module as a
*PModule*.  

The basic components of a PModule are a :ref:`run` method that
produces the results and a list of dependencies to the results of
other modules.  Further functionality is available as well, but let's
consider a basic example::

  from lazyrunner import pmodule, PModule
  from treedict import TreeDict

  @pmodule
  class Standardize(PModule):
      """
      Standardizes the data from the MyData processing module.
      """

      version = 0.01

      result_dependencies = ['mydata']

      def run(self):

          # The results from MyData are requested by
	  # result_dependencies above, so they are available in
	  # self.results.

          X = self.results.mydata.X

	  X -= X.mean()

	  # `self.p.scale_by_stddev` would be specified through
	  # setting `p.standardize.scale_by_stddev` in the central
	  # parameter tree.

	  if self.p.scale_by_stddev:
	      X /= X.std()

	  # Return a TreeDict instance with `X` as a stored value.
	  return TreeDict(X = X)

Parsing this example, we have a class decorated with ``@pmodule`` and
inheriting the base class ``PModule``.  There are two notable class
attributes: :ref:`PModule.version`, which specifies the version number of the
module.  This is for caching purposes; the results are not assumed to
be the same across versions. 

Behavior Configuration
======================

The behavior of a PModule regarding caching, other PModules, and
dependencies for processing is governed by class attributes.  The
above example gives two of these, :ref:`PModule.version` and
:ref:`PModule.result_dependencies`; other attributes are also useful,
as described in this section.

Dependencies
------------

Dependencies are handled via the class attributes
:ref:`PModule.result_dependencies`,
:ref:`PModule.parameter_dependencies`, and
:ref:`PModule.module_dependencies`.  Generally, each of these is a
list of nomes of other modules on which it depends.

.. _result-dependencies:

.. attribute:: PModule.result_dependencies

   A list of PModule names whose results are retrieved before
   :ref:`PModule.setup` or :ref:`PModule.run` is called on this
   module.  When these methods are run, :ref:`self.results` will hold
   all the specified results (e.g. ``self.results.mymodule`` will hold
   the results from the PModule `MyModule` if ``result_dependencies =
   ['mymodule']``.) 

.. attribute:: PModule.module_dependencies

   A list of PModule names that are instanciated before
   :ref:`PModule.setup` or :ref:`PModule.run` is called on this
   module.  When these methods are run, :ref:`self.modules` will hold
   instances of all the specified modules
   (e.g. ``self.modules.mymodule`` will hold an instance of the
   PModule `MyModule` if ``module_dependencies = ['mymodule']``.)
   Module dependencies are mostly useful for retrieving additional
   optional results from a different module.

.. attribute:: PModule.parameter_dependencies

   A list of dependencies on branches of the parameter tree in
   addition to the dependencies implied through
   :ref:`PModule.result_dependencies` and
   :ref:`PModule.module_dependencies`; the caching system considers it
   in loading results.  Unlike these, however, it does not have to
   specify the name of a PModule, but more generally specifies any
   branch or value of the parameter tree.  A possible use case is a
   globally specified random seed.


Parameter-Dependent Dependencies
--------------------------------

Additionally, it's possible to replace any of the above with an
associated classmethod (method decorated by ``@classmethod`` that
accepts as input the parameter tree and returns a list of
dependencies; this allows parameter-dependent specification of
dependencies.  For example, instead of::

  @pmodule
  class Standardize(PModule):

      # ...

      result_dependencies = ['mydata']

one could give::

  @pmodule
  class Standardize(PModule):

      # ...

      @classmethod
      def result_dependencies(cls, p):

          if p.standardize.process_other_data:
	      return ['mydata', 'otherdata']
	  else:
	      return ['mydata']

Note that the full parameter tree is passed as the argument, so local
parameters must be accessed through the respective branch.  This is
motivated by the use case of a single flag governing the processing of
several modules.

Caching
-------

Caching is normally done through hdf5 files in a directory specified
by conf.py; if this directory is None, or --nocache is passed in on
the cammand line, then caching is disabled.  Optionally, the class
attribute :ref:`PModule.disable_result_caching` may be set to True to
disable result caching for a specific module.

.. attribute:: PModule.disable_result_caching

  If set to True, disables result caching for the local PModule.  This
  ensures that :ref:`PModule.run` is called every time the results are
  requested.

Processing Methods
==================

PModule processing is meant to be done by specifying particular
methods that setup or run the module.  

Setup
-----

.. automethod:: PModule.setup

Running
-------

.. automethod:: PModule.run


Reporting
---------

.. automethod:: PModule.reportResults

Preprocessing
-------------

.. automethod:: PModule.preprocessParameters


Available Attributes
====================

When :ref:`PModule.setup` or :ref:`PModule.run` are run by LazyRunner,
several attributes of the instance class are provided to make part of
the processing easier:

.. attribute:: p

  The branch of the central parameter tree is contained in ``self.p``.
  For example, if the parameters are given in ``settings/defaults.py``
  as::

    p.mymodule.x1  = 2
    p.mymodule.a.y = [1,2,3]

  then ``self.p.x1`` would equal 2 and ``self.p.a.y`` would equal
  ``[1,2,3]`` in PModule `MyModule`.
  
  Note: if specified, :ref:`PModule.preprocessParameters` is called to
  (possibly) modify this tree..

.. attribute:: parameters

  A copy of the parameter tree with the parameters of all parameter,
  result, and module dependencies contained as branches.  For example,
  if ``'othermodule'`` was specified as one of the dependencies, then
  the parameters for `othermodule` (run through `othermodule`'s
  preprocessing function) would be available through
  ``self.parameters.othermodule``.

.. attribute:: results

  A TreeDict instance holding, as keys, the result trees of all the
  result dependencies given in :ref:`PModule.result_dependencies`.
  For example, if ``'dataloader'`` was given as a dependency, and the
  PModule `DataLoader` returned a TreeDict instance with key ``X``,
  this would be available here through ``self.results.dataloader.X``.

.. attribute:: module

  A TreeDict instance containing, as keys, instances of all the
  modules listed in :ref:`PModules.module_dependencies`.  For example,
  if ``'othermodule'`` was given as a module dependencies, then
  ``self.modules.othermodule`` would reference an instance of that
  module.  The :ref:`PModule.setup` method of this module would have
  been run, but :ref:`PModule.run` may or may not have been.  

.. attribute:: log

  A class attribute that references a logger_ setup for this class.
  For example::
  
    self.log.info("Now analyzing X") 

  would send "Now analyzing X" to a specified logging device, by
  default the standard output, at `info
  <http://docs.python.org/library/logging.html#logging.info>`_
  importance level.  Other levels are 
  `debug <http://docs.python.org/library/logging.html#logging.debug>`_, 
  `warning <http://docs.python.org/library/logging.html#logging.warning>`_, 
  `error <http://docs.python.org/library/logging.html#logging.error>`_, and
  `critical <http://docs.python.org/library/logging.html#logging.critical>`_.
  
  TODO: make this specifiable in conf.py

.. attribute:: local_results

  Once a processing module is intialized, other methods of the class
  can access the results given by :ref:`run`.  This attribute is set
  only after :ref:`setup` and possibly :ref:`run` are called.  If the
  pmodule results can be loaded from cache, then the attribute is
  still set, even thought :ref:`run` may not have been called.

.. attribute:: manager

  The attribute ``self.manager`` references the :ref:`central managing
  module <manager>`; however, this is not usually needed as most
  relevant functionality is provided through methods inherited from
  the PModule_ base class.

Inherited Methods 
=====================

These API functions are intended to add functionality to the
processing modules.

Specific Cache Methods
----------------------

These cache methods allow for finer-grained use of the cache.

.. automethod:: PModule.inCache

.. automethod:: PModule.loadFromCache

.. automethod:: PModule.saveToCache

.. automethod:: PModule.itemHash

Interfacing with other PModules
-------------------------------

.. automethod:: PModule.getSpecificResults

.. automethod:: PModule.getSpecificModule

.. automethod:: PModule.getCommonObject

.. automethod:: PModule.key

.. _logger: http://docs.python.org/library/logging.html
