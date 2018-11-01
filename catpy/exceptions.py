"""Module which collects exceptions defined elsewhere, for convenient access"""
from catpy.client import WrappedCatmaidException  # noqa
from catpy.applications.nameresolver import (  # noqa
    NameResolverException,
    NoMatchingNamesException,
    MultipleMatchingNamesException,
)
