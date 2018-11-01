from __future__ import division, unicode_literals

from itertools import permutations, product
from random import Random

import numpy as np
import pytest

try:
    from unittest import mock
except ImportError:
    import mock

from catpy.client import CoordinateTransformer, StackOrientation

COUNT = 20
SEED = 1

DIMS = "xyz"
DIRECTIONS = "stack_to_project", "project_to_stack"
EXAMPLE_COORD = 10

ZOOM_LEVELS = (-2, 0, 1)


@pytest.fixture
def default_res():
    return {"x": 1.0, "y": 2.0, "z": 3.0}


@pytest.fixture
def default_trans():
    return {"x": 10.0, "y": 20.0, "z": 30.0}


default_orientation = "XY"


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
        "resolution": default_res,
        "translation": default_trans,
        "orientation": default_orientation,
    }
    catmaid.configure_mock(**{"get.return_value": stack_info})
    return catmaid


@pytest.fixture
def default_coord_transformer(default_res, default_trans):
    return CoordinateTransformer(default_res, default_trans)


@pytest.mark.parametrize("res_fixture", [default_res, lambda: None])
@pytest.mark.parametrize("trans_fixture", [default_trans, lambda: None])
def test_instantiate(res_fixture, trans_fixture):
    assert CoordinateTransformer(res_fixture(), trans_fixture())


def test_from_catmaid(default_coord_transformer, catmaid_mock):
    assert (
        CoordinateTransformer.from_catmaid(catmaid_mock, None)
        == default_coord_transformer
    )


@pytest.mark.parametrize("dim", DIMS)
def test_project_to_stack_coord(
    dim, default_coord_transformer, default_res, default_trans
):
    project_coord = EXAMPLE_COORD

    expected_response = (project_coord - default_trans[dim]) / default_res[dim]
    response = default_coord_transformer.project_to_stack_coord(dim, project_coord)

    assert response[1] == expected_response


@pytest.mark.parametrize("dim", DIMS)
def test_stack_to_project_coord(
    dim, default_coord_transformer, default_res, default_trans
):
    stack_coord = EXAMPLE_COORD

    expected_response = (stack_coord * default_res[dim]) + default_trans[dim]
    response = default_coord_transformer.stack_to_project_coord(dim, stack_coord)

    assert response[1] == expected_response


@pytest.mark.parametrize("direction", DIRECTIONS)
def test_stack_to_project_and_project_to_stack(
    coordinate_generator, default_coord_transformer, direction
):
    for coords in coordinate_generator():
        expected_response = dict(
            getattr(default_coord_transformer, direction + "_coord")(dim, coord)
            for dim, coord in coords.items()
        )
        actual_response = getattr(default_coord_transformer, direction)(coords)

        assert expected_response == actual_response


def get_expected_array_response(
    coordinate_transformer, direction, coords_list, dims=DIMS
):
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


@pytest.mark.parametrize("dims", permutations("xyz"))
@pytest.mark.parametrize("direction", DIRECTIONS)
def test_arrays(coordinate_generator, default_coord_transformer, direction, dims):
    coords_list = list(coordinate_generator())
    coords_array = np.array([[coords[dim] for dim in dims] for coords in coords_list])

    expected_response = get_expected_array_response(
        default_coord_transformer, direction, coords_list, dims
    )
    actual_response = getattr(default_coord_transformer, direction + "_array")(
        coords_array, dims=dims
    )

    assert np.allclose(actual_response, expected_response)


@pytest.mark.parametrize("dim", "xyz")
def test_stack_to_scaled_coord(default_coord_transformer, dim):
    coord = EXAMPLE_COORD
    default_coord_transformer.scale_z = True

    for src_zoom, tgt_zoom in product(ZOOM_LEVELS, repeat=2):
        response = default_coord_transformer.stack_to_scaled_coord(
            dim, coord, tgt_zoom, src_zoom
        )
        if tgt_zoom > src_zoom:
            assert response < coord
        elif tgt_zoom < src_zoom:
            assert response > coord
        else:
            assert response == coord

        assert response == coord / np.exp2(tgt_zoom - src_zoom)


def test_stack_to_scaled_coord_z(default_coord_transformer):
    """Test that no scaling is done in Z by default"""
    coord = EXAMPLE_COORD
    for src_zoom, tgt_zoom in product(ZOOM_LEVELS, repeat=2):
        response = default_coord_transformer.stack_to_scaled_coord(
            "z", coord, tgt_zoom, src_zoom
        )
        assert response == coord


@pytest.mark.parametrize("scale_z", (True, False))
def test_stack_to_scaled(coordinate_generator, default_coord_transformer, scale_z):
    default_coord_transformer.scale_z = scale_z
    for coords in coordinate_generator():
        for src_zoom, tgt_zoom in product(ZOOM_LEVELS, repeat=2):
            expected_response = {
                dim: default_coord_transformer.stack_to_scaled_coord(
                    dim, coord, tgt_zoom, src_zoom
                )
                for dim, coord in coords.items()
            }
            actual_response = default_coord_transformer.stack_to_scaled(
                coords, tgt_zoom, src_zoom
            )

            assert expected_response == actual_response


@pytest.mark.parametrize("scale_z", (True, False))
@pytest.mark.parametrize("dims", permutations("xyz"))
def test_stack_to_scaled_array(
    coordinate_generator, default_coord_transformer, scale_z, dims
):
    coords_list = list(coordinate_generator())
    coords_array = np.array([[coords[dim] for dim in dims] for coords in coords_list])
    default_coord_transformer.scale_z = scale_z

    for src_zoom, tgt_zoom in product(ZOOM_LEVELS, repeat=2):
        output = []
        for coords in coords_list:
            transformed = default_coord_transformer.stack_to_scaled(
                coords, tgt_zoom, src_zoom
            )
            output.append([transformed[dim] for dim in dims])

        expected_response = np.array(output)

        actual_response = default_coord_transformer.stack_to_scaled_array(
            coords_array, tgt_zoom, src_zoom, dims
        )

        assert np.allclose(expected_response, actual_response)


@pytest.mark.parametrize("orientation", ["XY", "xy", 0, StackOrientation.XY, None])
def test_can_validate_orientation_valid(orientation):
    trans = CoordinateTransformer(orientation=orientation)
    assert trans.orientation == "xy"
    assert trans.depth_dim == "z"


@pytest.mark.parametrize(
    "orientation,expected_exception",
    [[3, AttributeError], ["xyz", ValueError], ["xc", ValueError]],
)
def test_can_validate_orientation_invalid(orientation, expected_exception):
    with pytest.raises(expected_exception):
        CoordinateTransformer(orientation=orientation)


@pytest.mark.parametrize(
    "orientation,direction,expected,",
    [
        ["XY", "project_to_stack", {"z": 0, "y": 1, "x": 2}],
        ["XY", "stack_to_project", {"z": 0, "y": 1, "x": 2}],
        ["XZ", "project_to_stack", {"z": 1, "y": 0, "x": 2}],
        ["XZ", "stack_to_project", {"z": 1, "y": 0, "x": 2}],
        ["ZY", "project_to_stack", {"z": 2, "y": 1, "x": 0}],
        ["ZY", "stack_to_project", {"z": 2, "y": 1, "x": 0}],
    ],
)
def test_project_to_stack_orientation_xy(orientation, direction, expected):
    coord_trans = CoordinateTransformer(orientation=orientation)
    result = getattr(coord_trans, direction)({"z": 0, "y": 1, "x": 2})
    assert result == expected
