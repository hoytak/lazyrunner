#!/usr/bin/env python
from glob import glob
from os.path import split, join
from itertools import chain, product

source_directory_list = ['lazyrunner']
version = "0.01v3"
description="LazyRunner: Module based scientific experiment framework with lazy evaluation."
author = "Hoyt Koepke"
author_email="hoytak@gmail.com"
name = 'lazyrunner'
scripts = ['Z']
url = "http://www.stat.washington.edu/~hoytak/code/lazyrunner/"
download_url = "http://pypi.python.org/packages/source/l/lazyrunner/lazyrunner-0.01v3.tar.gz"
long_description = \
"""
LazyRunner is a framework for organized scientific computing. It aims
to make it easy to write properly designed programs as quickly as
hacked-together scripts while providing useful features (such as
caching of results) that often take a fair bit of effort and planning
to implement in most scientific projects.

The development of LazyRunner grew out of my frustration at the length
of time often required to write good, reusable scientific code. It
seems there are often two options -- either throw together some scripts
that work but are hard to reuse, or spend a reasonable amount of time
on writing boilerplate code. This library was motivated by realizing
that most of the boilerplate required to organize scientific code can
be abstracted into a common framework. LazyRunner's workflow -- a
modular structure with centralized and hierarchical parameter
organization -- works well for most scientific projects (I use it for
all of my coding). In addition, the caching features provide a huge
speedup for practical computation with minimal additional coding.
"""

classifiers = [
    'Development Status :: 3 - Alpha',
    'Environment :: Console',
    'Intended Audience :: Science/Research',
    'License :: OSI Approved :: BSD License',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Topic :: Scientific/Engineering'
    ]

install_requires = ['treedict']

if __name__ == '__main__':

    # Collect all the python modules
    def get_python_modules(f):
	d, m = split(f[:f.rfind('.')])
	return m if len(d) == 0 else d + "." + m

    exclude_files = set(["setup.py"])
    python_files = set(chain(* (list(glob(join(d, "*.py"))
                                     for d in source_directory_list) + [glob("*.py")])))
    python_files -= exclude_files

    python_modules = [get_python_modules(f) for f in python_files]

    print "Relevant Python Files Found: \n%s\n+++++++++++++++++++++" % ", ".join(sorted(python_files))
    # Now set everything up
    from distutils.core import setup

    setup(
        version = version,
        description = description,
        author = author, 
        author_email = author_email,
        name = name,
        py_modules = python_modules,
        scripts = scripts,
        classifiers = classifiers,
        url = url,
        download_url = download_url,
        install_requires=install_requires)

