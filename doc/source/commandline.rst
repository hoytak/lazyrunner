.. highlight:: bash

.. _Z:

========================
Command Line Usage
========================

LazyRunner is meant to be run from the command line using `Z`, the
main lazyrunner script.  The goal is to make it simple to manage the
program and process flow as possible.

Command line options
====================

The command line options (from running ``Z --help``) are as follows::

  Usage: 
  Z [options] preset1, preset2, ...

  Queued Runner -- module based scientific programming.

  Options:
    -h, --help                                      show this help message and exit

    Run Options:
      -g, --debug                                   Sets the logging level to debug, so all
						    log.debug() messages are printed; turns on
						    compiler debug flags.
      -v, --verbose                                 Turns on more detailed printing of lazyrunner
						    actions and messages.
      -n, --no-compile                              Disable automatic recompiling of extension
						    modules.
      -s <settings module/file>, --settings=<settings module/file>
						    Run a specified settings file instead of
						    'defaults'. (Path from settings/ subdirectory,
						    '.py suffix is optional).

    Cache Options and Commands:
      --nocache                                     Disable use of the disk cache.
      --cache-read-only, --ro                       Make the cache read-only; useful for testing
						    new modules.
      --cache-directory=<directory>                 Use an alternate cache directory instead of
						    the one defined in conf.py.

    Creating / Initializing Options:
      --init                                        Initialize a new project in the current
						    working directory.
      -f, --force                                   Force operation to stop only under fatal
						    errors.
      -m <Module Name>, --new-module=<Module Name>  Write a new processing module template file.
						    The argument is of the form
						    '[dir[.subdir]].module'.  For 'dir.ModName', a
						    template module named 'ModName' is created in
						    'dir/modname.py'.

    Querying and Information Options:
      -l, --list-presets                            List available presets and exit.

    Cleaning / Deletion Options:
      --clean                                       Clean all intermediate compiling files.



Examples
========

The following are a few examples of how it could be used.

Listing Processing Modules/Presets::

    costila:~/workspace/qbpmm_benchmarks$ Z -l

    Available presets:
    orlib            Runs module orlib.
    qubpbenchmark    Runs module qubpbenchmark.

    costila:~/workspace/qbpmm_benchmarks$ 

All modules are automatically assigned a preset which runs the
respective :ref:`PModule.run()` method of the module (+ all needed
dependencies).

