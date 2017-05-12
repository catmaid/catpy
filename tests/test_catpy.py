#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_client
----------------------------------

Tests for `catpy.client` module.
"""


from catpy import client


def test_make_url():
    """Tests for catpy.client.make_url
    """
    url = client.make_url('foo/', '/bar')
    assert url == 'foo/bar', 'Duplicate slashes should be removed'
