"""Module which collects exceptions defined elsewhere, for convenient access"""
from __future__ import absolute_import

from catpy.client import WrappedCatmaidException  # noqa
from catpy.applications.nameresolver import (  # noqa
    NameResolverException,
    NoMatchingNamesException,
    MultipleMatchingNamesException,
)
