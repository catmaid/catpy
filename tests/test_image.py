from itertools import cycle, chain

import pytest
import numpy as np
import requests
from PIL import Image
from io import BytesIO
from concurrent.futures import Future
from requests import HTTPError

try:
    import mock
except ImportError:
    from unittest import mock

from catpy.image import (
    TileIndex, StackMirror, TileSourceType, TileCache,
    format_urls, is_valid_format_url, response_to_array,
    as_future, fill_tiled_cuboid, dict_subtract, Stack, ImageFetcher, ROIMode, ProjectStack, ThreadedImageFetcher,
    DummyResponse)

IMAGE_BASE = 'http://not-catmaid.org/'
TILE_SOURCE_TYPE = TileSourceType.FILE_BASED
FORMAT_URL = format_urls[TILE_SOURCE_TYPE]

IMAGE_MODES = [
    'L',  # 8-bit uint greyscale pixels
    'RGB',  # 3x8-bit
    'RGBa',  # 3x8-bit with premultiplied alpha
    'RGBA',  # 4x8-bit (transparency mask)
    'CMYK',  # 4x8-bit
]


@pytest.fixture()
def row_maker():
    """Generate a list of numbers from 1 to 254 inclusive, wrapping around"""
    def maker(length, start=1):
        if not 0 < start < 255:
            raise ValueError('Start must be between 0 and 254 inclusive')
        it = chain(range(start, 255), cycle(range(1, 255)))
        out = []
        while len(out) < length:
            out.append(next(it))

        return out

    return maker


@pytest.fixture
def gradient_h(row_maker):
    return np.array([row_maker(254)] * 128, dtype=np.uint8)


@pytest.fixture
def vol_maker(row_maker):
    def maker(shape, x_offset=0):
        while x_offset >= 254:
            x_offset -= 254
        return np.array([[row_maker(shape[2], x_offset + 1)] * shape[1]] * shape[0], dtype=np.uint8)
    return maker


@pytest.mark.parametrize('x_offset,shape,expected_final', [
    (0, (1, 1, 1), 1),
    (1, (1, 1, 1), 2),
    (0, (10, 10, 10), 10),
    (0, (1, 1, 300), 46),
    (1, (1, 1, 300), 47),
])
def test_vol_maker(vol_maker, x_offset, shape, expected_final):
    volume = vol_maker(shape, x_offset)
    assert volume.shape == shape
    assert volume[0, 0, 0] == x_offset + 1  # does not check large-offset
    assert volume[-1, -1, -1] == expected_final


def make_response_mock(content_arr, mode='L', format='png'):
    response = mock.Mock(spec=requests.Response)
    response.headers = {'Content-Type': 'image/' + format}
    im = Image.fromarray(content_arr)
    converted_im = im.convert(mode)

    buffer = BytesIO()
    converted_im.save(buffer, format)
    buffer.seek(0)
    response.content = buffer.read()

    return response


##########################
# Utility function tests #
##########################

@pytest.mark.parametrize('mode', ['L', 'RGB', 'RGBA'])
def test_response_to_array_png(gradient_h, mode):
    response_mock = make_response_mock(gradient_h, mode, 'png')
    returned_arr = response_to_array(response_mock)

    assert np.allclose(gradient_h, returned_arr)


@pytest.mark.parametrize('mode', ['L', 'RGB'])
def test_response_to_array_jpeg(gradient_h, mode):
    response_mock = make_response_mock(gradient_h, mode, 'jpeg')
    returned_arr = response_to_array(response_mock)

    # jpeg compression means exact matching is not possible
    assert gradient_h.shape == returned_arr.shape
    # assert np.allclose(gradient_h.ptp(), returned_arr.ptp())


@pytest.mark.parametrize('tile_source_type,format_url', format_urls.items())
def test_predefined_format_urls_are_valid(tile_source_type, format_url):
    assert is_valid_format_url(format_url), 'URL for {} is invalid'.format(tile_source_type)


def test_as_future_for_not_future():
    item = 'item'

    not_future_as_future = as_future(item)
    assert isinstance(not_future_as_future, Future)
    assert not_future_as_future.result() == item


def test_as_future_for_future():
    item = 'item'
    future = Future()
    future.set_result(item)

    future_as_future = as_future(future)
    assert isinstance(future_as_future, Future)
    assert future_as_future.result() == item


def test_fill_tiled_cuboid():
    kwargs = {'zoom_level': 1, 'height': 2, 'width': 3}

    min_tile = TileIndex(1, 2, 3, **kwargs)
    max_tile = TileIndex(2, 4, 3, **kwargs)

    results = fill_tiled_cuboid(min_tile, max_tile)

    expected_results = {
        TileIndex(1, 2, 3, **kwargs),
        TileIndex(2, 2, 3, **kwargs),
        TileIndex(1, 3, 3, **kwargs),
        TileIndex(2, 3, 3, **kwargs),
        TileIndex(1, 4, 3, **kwargs),
        TileIndex(2, 4, 3, **kwargs)
    }

    assert results == expected_results


def test_fill_tiled_cuboid_raises():
    min_tile = TileIndex(1, 2, 3, 1, 2, 3)
    max_tile = TileIndex(2, 4, 3, 4, 5, 6)

    with pytest.raises(ValueError):
        fill_tiled_cuboid(min_tile, max_tile)


def test_dict_subtract_mismatched_keys():
    d1 = {'a': 1, 'b': 2}
    d2 = {'a': 5, 'c': 10}

    with pytest.raises(ValueError):
        dict_subtract(d1, d2)


def test_dict_subtract():
    d1 = {'a': 1, 'b': 2}
    d2 = {'a': 5, 'b': 10}

    result = dict_subtract(d1, d2)
    assert result == {'a': -4, 'b': -8}


###################
# TileIndex tests #
###################

def test_tile_index_coords():
    idx = TileIndex(5, 2, 1, None, 10, 20)
    result = idx.coords

    expected_result = {
        'z': 5,
        'y': 20,
        'x': 20
    }

    assert result == expected_result


@pytest.mark.parametrize('name', ['zoom_level', 'height', 'width'])
def test_tile_index_comparable(name):
    kwargs = {'zoom_level': 1, 'height': 10, 'width': 20}
    idx1 = TileIndex(1, 2, 3, **kwargs)
    idx2 = TileIndex(4, 5, 6, **kwargs)

    assert idx1.is_comparable(idx2)

    kwargs[name] = kwargs[name]*2
    idx3 = TileIndex(7, 8, 9, **kwargs)

    assert not idx1.is_comparable(idx3)


def test_tile_index_url_kwargs():
    idx = TileIndex(1, 2, 3, 4, 5, 6)
    d = idx.url_kwargs
    for key in ('depth', 'row', 'col', 'zoom_level'):
        assert key in d


#####################
# StackMirror tests #
#####################

def test_stackmirror_corrects_image_base():
    other_args = (1, 1, 1, 'png')
    mirror_slash = StackMirror(IMAGE_BASE, *other_args)
    mirror_no_slash = StackMirror(IMAGE_BASE[:-1], *other_args)

    assert mirror_slash.image_base == mirror_no_slash.image_base == IMAGE_BASE


def test_stackmirror_corrects_file_extension():
    other_args = (IMAGE_BASE, 1, 1, 1)
    mirror_dot = StackMirror(*other_args, file_extension='.png')
    mirror_no_dot = StackMirror(*other_args, file_extension='png')

    assert mirror_dot.file_extension == mirror_no_dot.file_extension == 'png'


@pytest.mark.parametrize('tile_source_type', list(TileSourceType))
def test_stackmirror_formats_url(tile_source_type):
    mirror = StackMirror(IMAGE_BASE, 256, 256, tile_source_type, 'png')
    tile_idx = TileIndex(0, 0, 0, 0, 256, 256)

    response = mirror.generate_url(tile_idx)
    assert not set('{}').issubset(response)


def test_stackmirror_raises_on_incompatible_tile_index():
    mirror = StackMirror(IMAGE_BASE, 512, 512, TILE_SOURCE_TYPE, 'png')
    tile_idx = TileIndex(0, 0, 0, 0, 256, 256)

    with pytest.raises(ValueError):
        mirror.generate_url(tile_idx)


def test_stackmirror_get_tile_index():
    tile_side = 100
    mirror = StackMirror(IMAGE_BASE, tile_side, tile_side, TILE_SOURCE_TYPE, 'png')
    tile_idx_kwargs = {'zoom_level': 0, 'height': tile_side, 'width': tile_side}

    # trivial case
    coords = {'x': 0, 'y': 0, 'z': 0}
    idx, offset = mirror.get_tile_index(coords)
    assert idx == TileIndex(0, 0, 0, **tile_idx_kwargs)
    assert offset == {'x': 0, 'y': 0, 'z': 0}

    # test offset
    coords = {'x': 50, 'y': 50, 'z': 0}
    idx, offset = mirror.get_tile_index(coords)
    assert idx == TileIndex(0, 0, 0, **tile_idx_kwargs)
    assert offset == {'x': 50, 'y': 50, 'z': 0}

    # test tile idx
    coords = {'x': tile_side, 'y': tile_side, 'z': 1}
    idx, offset = mirror.get_tile_index(coords)
    assert idx == TileIndex(1, 1, 1, **tile_idx_kwargs)
    assert offset == {'x': 0, 'y': 0, 'z': 0}

    # test row/col correctness
    coords = {'x': tile_side, 'y': 0, 'z': 0}
    idx, offset = mirror.get_tile_index(coords)
    assert idx == TileIndex(depth=0, row=0, col=1, **tile_idx_kwargs)
    assert offset == {'x': 0, 'y': 0, 'z': 0}


###############
# Stack tests #
###############

def test_stack_sets_broken_slices_canary():
    stack = Stack(None)

    assert len(stack.broken_slices) == 0
    assert stack.canary_location == {'x': 0, 'y': 0, 'z': 0}


def test_stack_fastest_mirror_calls_get():
    stack = Stack(None)
    stack.mirrors = [StackMirror(IMAGE_BASE, 512, 512, TILE_SOURCE_TYPE, 'png')] * 3

    with mock.patch('requests.get') as mock_get:
        stack.get_fastest_mirror()

    assert mock_get.call_count == 3


def test_stack_fastest_mirror_raises():
    stack = Stack(None)
    stack.mirrors = [StackMirror(IMAGE_BASE, 512, 512, TILE_SOURCE_TYPE, 'png')] * 3

    with pytest.raises(ValueError):
        stack.get_fastest_mirror(timeout=0.01)


@pytest.mark.xfail(reason="Mock timeit doesn't work", raises=ValueError)
def test_stack_fastest_mirror_gets_fastest():
    # todo
    stack = Stack(None)
    stack.mirrors = [
        StackMirror(IMAGE_BASE + '2', 512, 512, TILE_SOURCE_TYPE, 'png'),
        StackMirror(IMAGE_BASE + '1', 512, 512, TILE_SOURCE_TYPE, 'png'),
        StackMirror(IMAGE_BASE + '3', 512, 512, TILE_SOURCE_TYPE, 'png')
    ]

    with mock.patch('timeit.timeit', side_effect=[2, 1, 3]):
        m = stack.get_fastest_mirror()

    assert m == stack.mirrors[1]


###################
# TileCache tests #
###################

def test_tilecache_can_set():
    cache = TileCache(None, None)
    key = 1
    value = 1

    assert len(cache) == 0

    cache[key] = value
    assert len(cache) == 1


def test_tilecache_set_refreshes_old():
    """Ensure that newly-pushed items get appended to the end, even if they already exist in the cache"""
    cache = TileCache(None, None)
    key = 1
    value = 1

    assert len(cache) == 0

    cache[key] = value
    cache[2] = 2
    assert list(cache) == [1, 2]
    cache[1] = 1
    assert list(cache) == [2, 1]


def test_tilecache_can_get():
    cache = TileCache(None, None)
    key = 1
    value = 1

    assert len(cache) == 0

    cache[key] = value
    assert len(cache) == 1

    response = cache[key]
    assert response == value


def test_tilecache_lru():
    cache = TileCache(None, None)
    cache[1] = 1
    cache[2] = 2
    val = cache[1]
    assert val == 1
    assert list(cache) == [2, 1]


def test_tilecache_can_clear():
    cache = TileCache(None, None)
    key = 1
    value = 1

    assert len(cache) == 0

    cache[key] = value
    assert len(cache) == 1

    cache.clear()
    assert len(cache) == 0


def test_tilecache_can_constrain_len():
    cache = TileCache(3, None)

    for key in range(3):
        cache[key] = str(key)
    assert set(cache) == {0, 1, 2}

    cache[3] = '3'
    assert set(cache) == {1, 2, 3}


def test_tilecache_can_constrain_bytes():
    arr = np.ones((10, 10))
    nbytes = arr.nbytes

    cache = TileCache(None, int(nbytes*3.5))

    for key in range(3):
        cache[key] = arr
    assert set(cache) == {0, 1, 2}

    cache[3] = arr
    assert set(cache) == {1, 2, 3}


######################
# ImageFetcher tests #
######################


def test_imagefetcher_can_instantiate():
    ImageFetcher(Stack(None))


def mirror_generator(count=5):
    for idx in range(count):
        yield StackMirror(
            IMAGE_BASE + str(idx), 100 + idx, 200 + idx, TILE_SOURCE_TYPE,
            'png', title='title' + str(idx), position=idx*2
        )


@pytest.fixture
def min_fetcher():
    stack = Stack(None)
    stack.mirrors.extend(mirror_generator())

    return ImageFetcher(stack)


def test_imagefetcher_mirror_fallback_warning(min_fetcher):
    min_fetcher._mirror = None
    with pytest.warns(UserWarning, match='title0'):
        min_fetcher.mirror


def test_imagefetcher_set_mirror_none(min_fetcher):
    min_fetcher.mirror = None

    with pytest.warns(UserWarning, match='title0'):
        min_fetcher.mirror

    assert min_fetcher._mirror is None


def test_imagefetcher_set_mirror_mirror(min_fetcher):
    min_fetcher.mirror = min_fetcher.stack.mirrors[1]
    assert min_fetcher._mirror == min_fetcher.stack.mirrors[1]


def test_imagefetcher_set_mirror_mirror_raises(min_fetcher):
    mirror = min_fetcher.stack.mirrors.pop()
    min_fetcher.stack.mirrors = []
    with pytest.raises(ValueError):
        min_fetcher.mirror = mirror


def test_imagefetcher_set_mirror_int(min_fetcher):
    min_fetcher.mirror = 2
    assert min_fetcher._mirror == min_fetcher.stack.mirrors[1]


def test_imagefetcher_set_mirror_int_as_str(min_fetcher):
    min_fetcher.mirror = '2'
    assert min_fetcher._mirror == min_fetcher.stack.mirrors[1]


def test_imagefetcher_set_mirror_position_warns_no_match(min_fetcher):
    with pytest.warns(UserWarning, match='does not exist'):
        min_fetcher.mirror = 1000
    assert min_fetcher._mirror is None


def test_imagefetcher_set_mirror_position_warns_too_many(min_fetcher):
    min_fetcher.stack.mirrors.append(StackMirror(IMAGE_BASE, 1, 1, TILE_SOURCE_TYPE, 'png', 'title5', 0))
    with pytest.warns(UserWarning, match='ore than one'):
        min_fetcher.mirror = 0
    assert min_fetcher._mirror == min_fetcher.stack.mirrors[0]


def test_imagefetcher_set_mirror_title(min_fetcher):
    min_fetcher.mirror = 'title2'
    assert min_fetcher._mirror == min_fetcher.stack.mirrors[2]


def test_imagefetcher_set_mirror_title_warns_no_match(min_fetcher):
    with pytest.warns(UserWarning, match='does not exist'):
        min_fetcher.mirror = 'not a title'
    assert min_fetcher._mirror is None


def test_imagefetcher_set_mirror_title_warns_too_many(min_fetcher):
    min_fetcher.stack.mirrors.append(StackMirror(IMAGE_BASE, 1, 1, TILE_SOURCE_TYPE, 'png', 'title0', 10))
    with pytest.warns(UserWarning, match='ore than one'):
        min_fetcher.mirror = 'title0'
    assert min_fetcher._mirror == min_fetcher.stack.mirrors[0]


def test_imagefetcher_get_auth_default(min_fetcher):
    min_fetcher.mirror = min_fetcher.stack.mirrors[0]
    assert min_fetcher._session.auth is None


def test_imagefetcher_get_auth_from_mirror(min_fetcher):
    min_fetcher.stack.mirrors[0].auth = ('name', 'pass')
    min_fetcher.mirror = min_fetcher.stack.mirrors[0]
    assert min_fetcher._session.auth == ('name', 'pass')


def test_imagefetcher_get_auth_fallback(min_fetcher):
    min_fetcher.auth = ('name', 'pass')
    min_fetcher.mirror = min_fetcher.stack.mirrors[0]
    assert min_fetcher._session.auth == ('name', 'pass')


def test_imagefetcher_clear_cache(min_fetcher):
    min_fetcher._tile_cache.clear = mock.Mock()
    min_fetcher.clear_cache()
    min_fetcher._tile_cache.clear.assert_called_once()


def test_imagefetcher_map_dimensions(min_fetcher):
    min_fetcher.source_orientation = 'zyx'
    min_fetcher.target_orientation = 'xyz'

    assert min_fetcher._map_dimensions() == (2, 1, 0)


def test_imagefetcher_reorient(min_fetcher):
    min_fetcher.source_orientation = 'zyx'
    min_fetcher.target_orientation = 'xyz'
    min_fetcher._dimension_mappings = min_fetcher._map_dimensions()
    arr = np.ones((3, 4, 5))
    assert min_fetcher._reorient_volume_src_to_tgt(arr).shape == (5, 4, 3)


def test_imagefetcher_reorient_expands(min_fetcher):
    min_fetcher.source_orientation = 'zyx'
    min_fetcher.target_orientation = 'xyz'
    min_fetcher._dimension_mappings = min_fetcher._map_dimensions()
    arr = np.ones((3, 4))
    assert min_fetcher._reorient_volume_src_to_tgt(arr).shape == (4, 3, 1)


def test_imagefetcher_reorient_throws(min_fetcher):
    arr = np.ones((3, 4, 5, 6))

    with pytest.raises(ValueError):
        min_fetcher._reorient_volume_src_to_tgt(arr)


# drc=depth,row,col
@pytest.mark.parametrize('roi,expected_drc,expected_yx_minmax', [
    [[[0, 0, 0], [1, 1, 1]],      [(0, 0, 0)],            ((0, 0), (0, 0))],
    [[[0, 0, 0], [2, 1, 1]],      [(0, 0, 0), (1, 0, 0)], ((0, 0), (0, 0))],
    [[[0, 0, 0], [1, 51, 51]],    [(0, 0, 0)],            ((0, 50), (0, 50))],
    [[[0, 20, 20], [1, 51, 51]],  [(0, 0, 0)],            ((20, 50), (20, 50))],
    [[[0, 20, 20], [1, 151, 51]], [(0, 0, 0), (0, 1, 0)], ((20, 50), (20, 50))],
])
def test_imagefetcher_roi_to_tiles(min_fetcher, roi, expected_drc, expected_yx_minmax):
    tile_side = 100
    zoom_level = 0
    mirror = StackMirror(IMAGE_BASE, tile_side, tile_side, TILE_SOURCE_TYPE, 'png')
    min_fetcher.stack.mirrors = [mirror]
    min_fetcher.mirror = mirror

    (min_y, max_y), (min_x, max_x) = expected_yx_minmax
    expected_bounds = {
        'min': {
            'z': 0,
            'y': min_y,
            'x': min_x,
        },
        'max': {
            'z': 0,
            'y': max_y,
            'x': max_x,
        },
    }

    expected_tiles = {TileIndex(*drc, zoom_level=zoom_level, height=tile_side, width=tile_side) for drc in expected_drc}

    tiles, slicing = min_fetcher._roi_to_tiles(roi, zoom_level)

    assert tiles == expected_tiles
    assert slicing == expected_bounds


@pytest.fixture
def tile_gen(gradient_h):
    def generator():
        while True:
            yield gradient_h.copy()
    return generator()


@pytest.fixture
def tile_response_future_gen(tile_gen):
    """Endlessly generate a Future containing a Response containing gradient_h as a PNG"""
    def generator():
        for arr in tile_gen:
            future = Future()
            future.set_result(DummyResponse(arr))
            yield future

    return generator()


@pytest.fixture(params=[ImageFetcher, ThreadedImageFetcher])
def realistic_fetcher(request, gradient_h, tile_gen, tile_response_future_gen):
    tile_height, tile_width = gradient_h.shape
    stack = ProjectStack(
        dimension={'z': 100, 'y': 200, 'x': 300},
        translation={'z': 10, 'y': 20, 'x': 30},
        resolution={'z': 1, 'y': 2, 'x': 3},
        orientation='xy'
    )
    mirror = StackMirror(IMAGE_BASE, tile_height, tile_width, TILE_SOURCE_TYPE, 'png', 'title', 0)
    stack.mirrors.append(mirror)

    fetcher = request.param(stack, preferred_mirror=0)

    side_effect = tile_gen if request.param == ImageFetcher else tile_response_future_gen
    fetcher._fetch = mock.Mock(side_effect=side_effect)

    return fetcher


@pytest.mark.parametrize('roi_mode,zoom_level,expected', [
    [ROIMode.SCALED, 0,   [[0, 0, 0],       [10, 10, 10]]],
    [ROIMode.STACK, 0,    [[0, 0, 0],       [10, 10, 10]]],
    [ROIMode.STACK, -2,   [[0, 2, 2],       [10, 38, 38]]],
    [ROIMode.STACK, 1,    [[0, 0, 0],       [10, 5, 5]]],
    [ROIMode.PROJECT, 0,  [[-10, -10, -10], [0, -5, -6]]],
    [ROIMode.PROJECT, -2, [[-10, -39, -40], [0, -21, -27]]],
    [ROIMode.PROJECT, 1,  [[-10, -5, -5],   [0, -2, -3]]]
])
def test_imagefetcher_roi_to_scaled(realistic_fetcher, roi_mode, zoom_level, expected):
    input_roi = np.array([[0.5, 0.5, 0.5], [9.5, 9.5, 9.5]])
    result = realistic_fetcher.roi_to_scaled(input_roi, roi_mode, zoom_level)
    assert np.allclose(result, np.array(expected, dtype=int))


def test_imagefetcher_roi_to_scaled_raises(realistic_fetcher):
    with pytest.raises(NotImplementedError):
        realistic_fetcher.roi_to_scaled([[0, 0, 0], [1, 1, 1]], roi_mode=ROIMode.SCALED, zoom_level=0.5)


@pytest.mark.parametrize('roi,expected_fetches', [
    ([[0, 0, 0], [1, 20, 20]], 1),
    ([[0, 0, 0], [2, 20, 20]], 2),
    ([[0, 10, 10], [1, 20, 30]], 1),
    ([[0, 10, 10], [1, 20, 300]], 2),
    ([[0, 0, 0], [1, 20, 300]], 2),
    ([[0, 0, 0], [1, 200, 300]], 4),
    ([[10, 10, 10], [13, 200, 300]], 12),
])
def test_imagefetcher_get(realistic_fetcher, vol_maker, roi, expected_fetches):
    zoom_level = 0
    roi_mode = ROIMode.SCALED

    realistic_fetcher.stack.broken_slices.add(100)

    roi = np.asarray(roi)

    expected = vol_maker(np.diff(roi, axis=0).squeeze(), roi[0, -1])

    output = realistic_fetcher.get(roi, roi_mode, zoom_level)

    assert output.shape == expected.shape
    assert np.allclose(expected, output)
    assert realistic_fetcher._fetch.call_count == expected_fetches


def test_imagefetcher_get_into_array(realistic_fetcher, vol_maker):
    zoom_level = 0
    roi_mode = ROIMode.SCALED
    roi = np.array([[10, 10, 10], [13, 200, 300]])
    shape = np.diff(roi, axis=0).squeeze()
    out = np.empty(shape)
    expected = vol_maker(shape, roi[0, -1])

    out2 = realistic_fetcher.get(roi, roi_mode, zoom_level, out)

    assert out is out2
    assert out2.shape == expected.shape
    assert np.allclose(expected, out2)
    assert realistic_fetcher._fetch.call_count == 12


def test_imagefetcher_get_tile_from_cache(realistic_fetcher, tile_gen):
    cached = next(tile_gen)
    height, width = cached.shape
    tile_index = TileIndex(0, 0, 0, 0, height, width)

    realistic_fetcher._tile_cache[tile_index] = cached
    out = realistic_fetcher.get([[0, 0, 0], [1, height, width]], ROIMode.SCALED, 0)
    realistic_fetcher._fetch.assert_not_called()
    assert np.allclose(out.squeeze(), cached)


def test_imagefetcher_get_tile_from_broken_slice(realistic_fetcher, tile_gen):
    height, width = next(tile_gen).shape
    realistic_fetcher.stack.broken_slices.add(0)
    shape = (1, height, width)
    out = realistic_fetcher.get([[0, 0, 0], shape], ROIMode.SCALED, 0)
    expected = np.zeros(shape)
    assert np.allclose(out, expected)
    realistic_fetcher._fetch.assert_not_called()


def test_imagefetcher_get_tile_from_fetch(min_fetcher):
    idx = TileIndex(0, 0, 0, 0, 100, 100)
    min_fetcher._fetch = mock.Mock()
    min_fetcher._get_tile(idx)
    min_fetcher._fetch.assert_called_with(idx)


def test_imagefetcher_fetch(min_fetcher):
    idx = TileIndex(0, 0, 0, 0, 100, 100)
    min_fetcher._session.get = mock.Mock()
    with mock.patch('catpy.image.response_to_array', mock.Mock()):
        min_fetcher._fetch(idx)
    min_fetcher._session.get.assert_called_once()


@pytest.mark.parametrize('space', list(ROIMode))
def test_imagefetcher_get_wrappers(min_fetcher, space):
    min_fetcher.get = mock.Mock()
    getattr(min_fetcher, 'get_{}_space'.format(space.value))('roi', 'zoom_level')
    min_fetcher.get.assert_called_with('roi', space, 'zoom_level', None)


def test_404_handled_correctly(min_fetcher):
    idx = TileIndex(0, 0, 0, 0, 100, 100)
    min_fetcher._session.get = mock.Mock(side_effect=HTTPError(response=mock.Mock(status_code=404)))
    with mock.patch('catpy.image.response_to_array', mock.Mock()):
        tile = min_fetcher._fetch(idx)
    assert tile.shape == (100, 100)
    assert (tile == 0).sum() == tile.size


@pytest.mark.xfail(reason="404 handling not implemented for threaded fetcher")
def test_404_handled_correctly_threaded(min_fetcher):
    assert False
