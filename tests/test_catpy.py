#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_client
----------------------------------

Tests for `catpy.client` module.
"""
from __future__ import absolute_import

import catpy.client
import catpy.util
from catpy import client


def test_make_url_double_slash():
    """Tests for catpy.client.make_url
    """
    url = catpy.client.make_url("foo/", "/bar")
    assert url == "foo/bar", "Duplicate slashes should be removed"


def test_make_url_no_slash():
    """Tests for catpy.client.make_url
    """
    url = catpy.client.make_url("foo", "bar")
    assert url == "foo/bar", "Elements should be joined with a slash"


def test_make_url_trailing_slash_unchanged():
    """Tests for catpy.client.make_url
    """
    url1 = catpy.client.make_url("foo", "bar")
    assert url1 == "foo/bar", "Should not add trailing slash"
    url2 = catpy.client.make_url("foo", "bar/")
    assert url2 == "foo/bar/", "Should not remove trailing slash"
