#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup
import os

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.rst')) as readme_file:
    readme = readme_file.read()

with open(os.path.join(here, 'HISTORY.rst')) as history_file:
    history = history_file.read()

with open(os.path.join(here, 'catpy', 'version.py')) as f:
    exec(f.read())

with open(os.path.join(here, 'catpy', 'author.py')) as f:
    exec(f.read())

requirements = [
    "enum34>=1.1; python_version < '3.4'",
    "futures>=3.2; python_version < '3.3'",
    'networkx>=1.11',
    'numpy>=1.12',
    'Pillow>=5.0',
    'requests>=2.14',
    'requests-futures>=0.9',
    'six>=1.10'
]

# environment variable can force a specific networkx requirement, for testing purposes (see tox.ini)
nx_version = os.environ.get('CATPY_NX')
if nx_version:
    requirements = [
        r if not r.startswith('networkx') else "networkx" + nx_version
        for r in requirements
    ]

setup_requirements = [
    'pytest-runner>=2.11',
]

test_requirements = [
    'pytest>=3',
    "mock>=2; python_version < '3.6'"
]

setup(
    name='catpy',
    version=__version__,
    description="Python client for the CATMAID API",
    long_description=readme + '\n\n' + history,
    author=__author__,
    author_email=__email__,
    url='https://github.com/catmaid/catpy',
    packages=[
        'catpy',
    ],
    package_dir={'catpy':
                 'catpy'},
    include_package_data=True,
    install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    keywords='catpy catmaid neuron',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Scientific/Engineering :: Bio-Informatics',
    ],
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements
)
