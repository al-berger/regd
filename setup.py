# -*- coding: utf-8 -*-
"""
    regd.py
    ~~~~~~~~~~~
    
    Secure registry and data cache.
    
    :copyright: (c) 2015 by Albert Berger.
    :license: GPL, see LICENSE for more details.
"""
from distutils.core import setup
from regd import defs

classifiers = [
    'Development Status :: 4 - Beta',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'Intended Audience :: System Administrators',
    'Intended Audience :: Information Technology',
    'License :: OSI Approved :: GPL License',
    'Operating System :: POSIX',
    'Operating System :: Unix',
    'Programming Language :: Python :: 3.4',
    'Programming Language :: Python :: 3.5',
    'Topic :: Security :: Cryptography',
    'Topic :: Utilities',
]

setup(
    name                = 'regd',
    version             = defs.__version__,
    description         = defs.__description__,
    long_description    = open('README.md').read().strip(),
    author              = defs.__author__,
    author_email        = defs.__author_email__,
    url                 = defs.__homepage__,
    license             = defs.__license__,
    packages            = ['regd', 'regd.testing'],
    #package_data		= {'tests': ['data/test.conf']},
    scripts             = ['data/regd'],
    classifiers         = classifiers,
    keywords            = "registry settings configuration manager daemon cache"
)
