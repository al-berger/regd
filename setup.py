# -*- coding: utf-8 -*-
"""
    regd.py
    ~~~~~~~~~~~
    
    Secure registry and data cache.
    
    :copyright: (c) 2015 by Albert Berger.
    :license: GPL, see LICENSE for more details.
"""
from distutils import setup
import regd

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
    'Topic :: Security :: Cryptography',
    'Topic :: Utilities',
]

setup(
    name                = 'regd',
    version             = regd.__version__,
    description         = regd.__description__,
    long_description    = open('README.md').read().strip(),
    author              = regd.__author__,
    author_email        = regd.__author_email__,
    url                 = regd.__homepage__,
    license             = regd.__license__,
    platform            = 'Linux',
    packages            = ['regd'],
    scripts             = ['regd.regd'],
    install_requires    = [],
    classifiers         = classifiers,
    keywords            = "registry settings configuration manager daemon cache"
)
