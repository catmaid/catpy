#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    'numpy>=1.12',
    'requests>=2.14',
    'six>=1.10'
]

setup_requirements = [
    'pytest-runner>=2.11',
]

test_requirements = [
    'pytest>=3',
]

setup(
    name='catpy',
    version='0.1.0',
    description="Python client for the CATMAID API",
    long_description=readme + '\n\n' + history,
    author="Andrew S. Champion",
    author_email='andrew.champion@gmail.com',
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
        'Topic :: Scientific/Engineering :: Bio-Informatics',
    ],
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements
)
