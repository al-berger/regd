# -*- coding: utf-8 -*-
"""
    safestor.py
    ~~~~~~~~~~~
    
    Secure storage server.
    
    :copyright: (c) 2015 by Albert Berger.
    :license: BSD, see LICENSE for more details.
"""
from setuptools import setup
import safestor

classifiers = [
    'Development Status :: 4 - Beta',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'Intended Audience :: System Administrators',
    'Intended Audience :: Information Technology',
    'License :: OSI Approved :: BSD License',
    'Operating System :: MacOS',
    'Operating System :: POSIX',
    'Operating System :: Unix',
    'Operating System :: Microsoft',
    'Operating System :: OS Independent',
    'Programming Language :: Python :: 3.4',
    'Topic :: Security :: Cryptography',
    'Topic :: Utilities',
]

setup(
    name                = 'safestor.py',
    version             = safestor.__version__,
    description         = safestor.__description__,
    long_description    = open('README.md').read().strip(),
    author              = safestor.__author__,
    author_email        = safestor.__author_email__,
    url                 = safestor.__homepage__,
    license             = safestor.__license__,
    py_modules          = ['safestor'],
    scripts             = ['safestor.py'],
    install_requires    = [],
    classifiers         = classifiers
)
