#!/usr/bin/env python
# -*- coding: utf-8 -*-
import runpy
from setuptools import setup
import os

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, "README.rst")) as readme_file:
    readme = readme_file.read()

with open(os.path.join(here, "HISTORY.rst")) as history_file:
    history = history_file.read()

version_dict = runpy.run_path(os.path.join(here, "catpy", "version.py"))

author_dict = runpy.run_path(os.path.join(here, "catpy", "author.py"))

requirements = ["networkx>=2.0", "numpy>=1.12", "Pillow>=5.0", "requests>=2.14", "requests-futures>=0.9"]

setup_requirements = ["pytest-runner>=2.11"]

test_requirements = ["pytest>=3"]

setup(
    name="catpy",
    version=version_dict["__version__"],
    description="Python client for the CATMAID API",
    long_description=readme + "\n\n" + history,
    author=author_dict["__author__"],
    author_email=author_dict["__email__"],
    url="https://github.com/catmaid/catpy",
    packages=["catpy", "catpy.applications"],
    include_package_data=True,
    install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    keywords="catpy catmaid neuron",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
    ],
    requires_python=">=3.6",
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
)
