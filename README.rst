catpy - Python client for the CATMAID API
=========================================


.. image:: https://img.shields.io/pypi/v/catpy.svg
        :target: https://pypi.python.org/pypi/catpy
        :alt: PyPI Package Version

.. image:: https://img.shields.io/travis/catmaid/catpy.svg
        :target: https://travis-ci.org/catmaid/catpy
        :alt: Continuous Integration Status

.. image:: https://readthedocs.org/projects/catpy/badge/?version=latest
        :target: https://catpy.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://img.shields.io/badge/License-MIT-blue.svg
        :target: https://opensource.org/licenses/MIT
        :alt: License: MIT


Python client for the `CATMAID <https://catmaid.org>`_ API, plus some helpful tools for working with the data.

Versioning
----------

``catpy`` stopped using semantic versioning after 0.3.0, and now uses [calendar versioning](https://calver.org), using the scheme `YYYY.0M.0D` , with an optional incrementing field in rare cases where more than one release is necessary in a day.
The `next_version.py` script produces the next version.

CATMAID also uses calendar versioning.
However, development does not always happen in parallel so a new CATMAID release does not imply a new catpy release and vice versa.

The core CATMAID API supported by catpy does not change frequently.
If a new release of either breaks their coupling, please raise an issue.

