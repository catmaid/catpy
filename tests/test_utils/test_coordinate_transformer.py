from __future__ import division, unicode_literals

from itertools import permutations
from random import Random

import numpy as np
import pytest

try:
    from unittest import mock
except ImportError:
    import mock

from catpy.client import CoordinateTransformer


COUNT = 20
SEED = 1

DIMS = 'xyz'
DIRECTIONS = 'stack_to_project', 'project_to_stack'


@pytest.fixture
def default_res():
    return {
        'x': 1.0,
        'y': 2.0,
        'z': 3.0
    }


@pytest.fixture
def default_trans():
    return {
        'x': 10.0,
        'y': 20.0,
        'z': 30.0
    }


@pytest.fixture
def coordinate_generator():
    """Return a generator which returns `count` randomly-generated coordinates in the range [-1000, 1000], in a mixture
    of floats and ints"""
    def wrapped(count=COUNT, seed=SEED):
        twister = Random(seed)

        def rand(is_int=False):
            n = (twister.random() - 0.5) * 1000
            return n if not is_int else int(n)

        for _ in range(count):
            is_int = twister.random() > 0.5
            yield {dim: rand(is_int) for dim in DIMS}

    return wrapped


@pytest.fixture
def catmaid_mock(default_res, default_trans):
    catmaid = mock.Mock()
    stack_info = {
        'resolution': default_res,
        'translation': default_trans
    }
    catmaid.configure_mock(**{'get.return_value': stack_info})
    return catmaid


@pytest.fixture
def default_obj(default_res, default_trans):
    return CoordinateTransformer(default_res, default_trans)


@pytest.mark.parametrize('res_fixture', [default_res, lambda: None])
@pytest.mark.parametrize('trans_fixture', [default_trans, lambda: None])
def test_instantiate(res_fixture, trans_fixture):
    assert CoordinateTransformer(res_fixture(), trans_fixture())


def test_from_catmaid(default_obj, catmaid_mock):
    assert CoordinateTransformer.from_catmaid(catmaid_mock, None) == default_obj


@pytest.mark.parametrize('dim', DIMS)
def test_project_to_stack_coord(dim, default_obj, default_res, default_trans):
    project_coord = 10

    expected_response = (project_coord - default_trans[dim]) / default_res[dim]
    response = default_obj.project_to_stack_coord(dim, project_coord)

    assert response == expected_response


@pytest.mark.parametrize('dim', DIMS)
def test_stack_to_project_coord(dim, default_obj, default_res, default_trans):
    stack_coord = 10

    expected_response = (stack_coord * default_res[dim]) + default_trans[dim]
    response = default_obj.stack_to_project_coord(dim, stack_coord)

    assert response == expected_response


@pytest.mark.parametrize('direction', DIRECTIONS)
def test_stack_to_project_and_project_to_stack(coordinate_generator, default_obj, direction):
    for coords in coordinate_generator():
        expected_response = {
            dim: getattr(default_obj, direction + '_coord')(dim, coord) for dim, coord in coords.items()
        }
        actual_response = getattr(default_obj, direction)(coords)

        assert expected_response == actual_response


def get_expected_array_response(coordinate_transformer, direction, coords_list, dims=DIMS):
    """

    Parameters
    ----------
    coordinate_transformer : CoordinateTransformer
    direction : str
        'project_to_stack' or 'stack_to_project'
    coords_list : list of dict
        dicts are of form {'x': number, 'y': number, 'z': number}
    dims : iterable
        dimension order, default 'xyz'

    Returns
    -------
    np.array
    """
    output = []
    for coords in coords_list:
        transformed = getattr(coordinate_transformer, direction)(coords)
        output.append([transformed[dim] for dim in dims])

    return np.array(output)


@pytest.mark.parametrize('dims', permutations('xyz'))
@pytest.mark.parametrize('direction', DIRECTIONS)
def test_arrays(coordinate_generator, default_obj, direction, dims):
    coords_list = list(coordinate_generator())
    coords_array = np.array([[coords[dim] for dim in dims] for coords in coords_list])

    expected_response = get_expected_array_response(default_obj, direction, coords_list, dims)
    actual_response = getattr(default_obj, direction + '_array')(coords_array, dims=dims)

    assert np.allclose(actual_response, expected_response)
