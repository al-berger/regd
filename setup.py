# -*- coding: utf-8 -*-
"""
    regd.py
    ~~~~~~~~~~~
    
    Secure registry and data cache.
    
    :copyright: (c) 2015 by Albert Berger.
    :license: GPL, see LICENSE for more details.
"""
from setuptools import setup, find_packages
import regd

classifiers = [
    'Development Status :: 4 - Beta',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'Intended Audience :: System Administrators',
    'Intended Audience :: Information Technology',
    'License :: OSI Approved :: GPL License',
    'Operating System :: MacOS',
    'Operating System :: POSIX',
    'Operating System :: Unix',
    'Programming Language :: Python :: 3.4',
    'Topic :: Security :: Cryptography',
    'Topic :: Utilities',
]

setup(
    name                = 'regd.py',
    version             = regd.__version__,
    description         = regd.__description__,
    long_description    = open('README.md').read().strip(),
    author              = regd.__author__,
    author_email        = regd.__author_email__,
    url                 = regd.__homepage__,
    license             = regd.__license__,
    platform            = 'Linux',
    packages            = find_packages(exclude=['test']),
    entry_points="""
        [console_scripts]
        regd=regd.regd:main
    """,
    install_requires    = [],
    classifiers         = classifiers,
    keywords            = "registry settings configuration manager daemon cache"
)
