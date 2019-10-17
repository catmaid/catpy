# -*- coding: utf-8 -*-

from __future__ import division, unicode_literals, absolute_import

import logging
from io import BytesIO
from collections import OrderedDict

from requests import HTTPError
import itertools
from warnings import warn

from concurrent.futures import Future, as_completed

from PIL import Image
import numpy as np
import requests
from requests_futures.sessions import FuturesSession

from catpy.spatial import StackOrientation, CoordinateTransformer
from catpy.stacks import StackMirror, ProjectStack, TileIndex
from catpy.util import StrEnum
from catpy.compat import tqdm

logger = logging.getLogger()


DEFAULT_CACHE_ITEMS = 10
DEFAULT_CACHE_BYTES = None
THREADS = 10

SUPPORTED_CONTENT_TYPES = {"image/png", "image/jpeg"}


class Orientation3D(StrEnum):
    NUMPY = "zyx"
    C = "zyx"
    ZYX = "zyx"
    VIGRA = "xyz"
    FORTRAN = "xyz"
    XYZ = "xyz"


DEFAULT_3D_ORIENTATION = Orientation3D.NUMPY


class BrokenSliceHandling(StrEnum):
    FILL = "fill"
    # ABOVE = 'above'
    # BELOW = 'below'
    # CLOSEST = 'closest'
    # INTERPOLATE = 'interpolate'


DEFAULT_BROKEN_SLICE_HANDLING = BrokenSliceHandling.FILL


class ROIMode(StrEnum):
    STACK = "stack"
    SCALED = "scaled"
    PROJECT = "project"


DEFAULT_ROI_MODE = ROIMode.STACK


def response_to_array(response, pil_kwargs=None):
    response.raise_for_status()
    content_type = response.headers["Content-Type"]

    if content_type in SUPPORTED_CONTENT_TYPES:
        buffer = BytesIO(
            response.content
        )  # opening directly from raw response doesn't work for JPEGs
        raw_img = Image.open(buffer)
        pil_kwargs = dict(pil_kwargs) if pil_kwargs else dict()
        pil_kwargs["mode"] = pil_kwargs.get("mode", "L")
        grey_img = raw_img.convert(**pil_kwargs)
        return np.array(grey_img)
    else:
        raise NotImplementedError(
            "Image fetching is only implemented for greyscale PNG and JPEG, not {}".format(
                content_type.upper().split("/")[1]
            )
        )


def response_to_array_callback(session, response):
    response.array = response_to_array(response)


def as_future(item):
    if isinstance(item, Future):
        return item
    f = Future()
    f.set_result(item)
    return f


def fill_tiled_cuboid(min_tile_idx, max_tile_idx):
    if not min_tile_idx.is_comparable(max_tile_idx):
        raise ValueError("Tile indices are not comparable (different zoom or size)")

    iters = [
        range(getattr(min_tile_idx, name), getattr(max_tile_idx, name) + 1)
        for name in ("depth", "row", "col")
    ]
    return {
        TileIndex(
            depth,
            row,
            col,
            min_tile_idx.zoom_level,
            min_tile_idx.height,
            min_tile_idx.width,
        )
        for depth, row, col in itertools.product(*iters)
    }


def dict_subtract(d1, d2):
    if set(d1) != set(d2):
        raise ValueError("Dicts have different keys")

    out = dict()
    for key in d1.keys():
        out[key] = d1[key] - d2[key]
    return out


def is_valid_format_url(format_url):
    """
    Ensure that the given URL has the required format keys for use as a format URL.

    Parameters
    ----------
    format_url : str

    Returns
    -------
    bool
    """
    components = [
        "image_base",
        "{depth}",
        "{zoom_level}",
        "{row}",
        "{col}",
        "file_extension",
    ]
    return all("{" + component + "}" in format_url for component in components)


class TileCache(object):
    def __init__(self, max_items=DEFAULT_CACHE_ITEMS, max_bytes=DEFAULT_CACHE_BYTES):
        super(TileCache, self).__init__()
        self.max_bytes = max_bytes
        self.max_items = max_items
        self._dict = OrderedDict()

    @property
    def current_bytes(self):
        """
        Current total size, in bytes, of the cache's values

        Returns
        -------
        int
        """
        if self.max_bytes is None:
            return -1

        return sum(value.nbytes for value in self._dict.values())

    def __setitem__(self, key, value):
        """
        Append value to cache under the given key. If this causes the cache to break the size constraints, remove the
        oldest items until it is valid again.

        Parameters
        ----------
        key : TileIndex
        value : np.ndarray
        """
        if key in self._dict:
            del self._dict[key]
        self._dict[key] = value
        self._constrain_size()

    def __getitem__(self, key):
        value = self._dict.pop(key)
        self._dict[key] = value
        return value

    def clear(self):
        self._dict.clear()

    def __contains__(self, item):
        return item in self._dict

    def __len__(self):
        return len(self._dict)

    def __iter__(self):
        return iter(self._dict)

    def _constrain_size(self):
        if self.max_items is not None:
            while len(self) > self.max_items:
                self._dict.popitem(False)

        if self.max_bytes is not None:
            total_bytes = self.current_bytes
            while total_bytes > self.max_bytes:
                key, value = self._dict.popitem(False)
                total_bytes -= value.nbytes


class ImageFetcher(object):
    def __init__(
        self,
        stack,
        output_orientation=DEFAULT_3D_ORIENTATION,
        preferred_mirror=None,
        timeout=1,
        cache_items=DEFAULT_CACHE_ITEMS,
        cache_bytes=DEFAULT_CACHE_BYTES,
        broken_slice_handling=DEFAULT_BROKEN_SLICE_HANDLING,
        cval=0,
        auth=None,
    ):
        """

        Parameters
        ----------
        stack : catpy.stacks.Stack
        output_orientation : str or Orientation3D
            default Orientation3D.ZYX
        preferred_mirror : int or str or StackMirror, optional
            default None
        timeout : float, optional
            default 1
        cache_items : int, optional
            default 10
        cache_bytes : int, optional
            default None
        broken_slice_handling : str or BrokenSliceHandling
            default BrokenSliceHandling.FILL
        cval : int, optional
            default 0
        auth : (str, str), optional
            Tuple of (username, password) for basic HTTP authentication, to be used if the selected mirror has no
            defined ``auth``. Default None
        """
        self.stack = stack
        self.depth_dimension = "z"
        self.source_orientation = self.depth_dimension + "yx"

        self.broken_slice_handling = BrokenSliceHandling(broken_slice_handling)

        if self.broken_slice_handling == BrokenSliceHandling.FILL:
            self.cval = cval
        else:
            self.cval = None

        self.target_orientation = str(output_orientation)

        self._dimension_mappings = self._map_dimensions()

        self.timeout = timeout

        self.coord_trans = CoordinateTransformer(
            *[
                getattr(self.stack, name, None)
                for name in ("resolution", "translation", "orientation")
            ]
        )

        self._tile_cache = TileCache(cache_items, cache_bytes)

        self._session = requests.Session()
        self._auth = auth

        self._mirror = None
        self.mirror = preferred_mirror

    @property
    def auth(self):
        return self._auth

    @auth.setter
    def auth(self, name_pass):
        self._auth = name_pass
        if self._mirror and not self._mirror.auth:
            self._session.auth = name_pass

    @property
    def mirror(self):
        if not self._mirror:
            warn(
                "No mirror set: falling back to {}, which may not be accessible."
                "You might want to run set_fastest_mirror.".format(
                    self.stack.mirrors[0].title
                )
            )
            m = self.stack.mirrors[0]
            self._session.auth = m.auth or self.auth
            return m
        return self._mirror

    @mirror.setter
    def mirror(self, preferred_mirror):
        """
        Set mirror by its string name, its position attribute, or the object itself

        Parameters
        ----------
        preferred_mirror : str or int or catpy.stacks.StackMirror
        """
        if preferred_mirror is None:
            self._mirror = None

        elif isinstance(preferred_mirror, StackMirror):

            if preferred_mirror not in self.stack.mirrors:
                raise ValueError("Selected mirror is not in stack's mirrors")
            self._mirror = preferred_mirror

        else:

            try:

                pos = int(preferred_mirror)
                matching_mirrors = [m for m in self.stack.mirrors if m.position == pos]

                if not matching_mirrors:
                    warn(
                        "Preferred mirror position {} does not exist, choose from {}".format(
                            pos, ", ".join(str(m.position) for m in self.stack.mirrors)
                        )
                    )
                    return
                elif len(matching_mirrors) > 1:
                    warn(
                        "More than one mirror found for position {}, picking {}".format(
                            pos, matching_mirrors[0].title
                        )
                    )
                self._mirror = matching_mirrors[0]

            except (ValueError, TypeError):

                if isinstance(preferred_mirror, str):
                    matching_mirrors = [
                        m for m in self.stack.mirrors if m.title == preferred_mirror
                    ]
                    if not matching_mirrors:
                        warn(
                            "Preferred mirror called {} does not exist, choose from {}".format(
                                preferred_mirror,
                                ", ".join(m.title for m in self.stack.mirrors),
                            )
                        )
                        return
                    elif len(matching_mirrors) > 1:
                        warn(
                            "More than one mirror found for title {}, picking first".format(
                                preferred_mirror
                            )
                        )
                    self._mirror = matching_mirrors[0]

        if self._mirror is not None and self._mirror.auth:
            self._session.auth = self._mirror.auth
        else:
            self._session.auth = self.auth

    def clear_cache(self):
        self._tile_cache.clear()

    def _map_dimensions(self):
        """
        Find the indices of the target dimensions in the source dimension order

        Returns
        -------
        tuple of int

        Examples
        --------
        >>> self.source_orientation = 'xyz'
        >>> self.target_orientation = 'yzx'
        >>> self._map_dimensions()
        (1, 2, 0)
        """
        mapping = {dim: idx for idx, dim in enumerate(self.source_orientation)}
        return tuple(mapping[dim] for dim in self.target_orientation)

    def _reorient_volume_src_to_tgt(self, volume):
        arr = np.asarray(volume)
        if len(arr.shape) == 2:
            arr = np.expand_dims(arr, 0)
        if len(arr.shape) != 3:
            raise ValueError("Unknown dimension of volume: should be 2D or 3D")
        return np.moveaxis(arr, (0, 1, 2), self._dimension_mappings)

    def _make_empty_tile(self, width, height=None):
        height = height or width
        tile = np.empty((height, width), dtype=np.uint8)
        tile.fill(self.cval)
        return tile

    def _get_tile(self, tile_index):
        """
        Get the tile from the cache, handle broken slices, or fetch.

        Parameters
        ----------
        tile_index : TileIndex

        Returns
        -------
        Future
        """
        try:
            return self._tile_cache[tile_index]
        except KeyError:
            pass

        if tile_index.depth in self.stack.broken_slices:
            if (
                self.broken_slice_handling == BrokenSliceHandling.FILL
                and self.cval is not None
            ):
                return self._make_empty_tile(tile_index.width, tile_index.height)
            else:
                raise NotImplementedError(
                    "'fill' with a non-None cval is the only implemented broken slice handling mode"
                )

        return self._fetch(tile_index)

    def _roi_to_tiles(self, roi_src, zoom_level):
        """

        Parameters
        ----------
        roi_src : array-like
            2 x 3 array where the rows are the half-closed interval of which pixels to select in the given dimension
            and at the given zoom level, and the columns are the 3 dimensions in the source orientation
        zoom_level : int
            Zoom level at which roi is scaled and which images will be fetched

        Returns
        -------
        set of TileIndex
            Set of tile indices to fetch
        dict of {str to dict of {str to int}}
            {'min': {}, 'max': {}} with values {'x': int, 'y': int, 'z': int}
            Pixel offsets of the minimum maximum pixels from the shallow-top-left corner of the tile which they are on
        """
        closed_roi = np.array(roi_src)
        closed_roi[1, :] -= 1
        min_pixel = dict(zip(self.source_orientation, closed_roi[0, :]))
        max_pixel = dict(zip(self.source_orientation, closed_roi[1, :]))

        min_tile, min_offset = self.mirror.get_tile_index(min_pixel, zoom_level)
        max_tile, max_offset = self.mirror.get_tile_index(max_pixel, zoom_level)

        tile_indices = fill_tiled_cuboid(min_tile, max_tile)
        src_inner_slicing = {"min": min_offset, "max": max_offset}

        return tile_indices, src_inner_slicing

    def _insert_tile_into_arr(
        self, tile_index, src_tile, min_tile, max_tile, src_inner_slicing, out
    ):
        min_col = tile_index.col == min_tile.col
        max_col = tile_index.col == max_tile.col

        min_row = tile_index.row == min_tile.row
        max_row = tile_index.row == max_tile.row

        tile_slicing_dict = {
            "z": slice(None),
            "y": slice(
                src_inner_slicing["min"]["y"] if min_row else None,
                src_inner_slicing["max"]["y"] + 1 if max_row else None,
            ),
            "x": slice(
                src_inner_slicing["min"]["x"] if min_col else None,
                src_inner_slicing["max"]["x"] + 1 if max_col else None,
            ),
        }

        tile_slicing = tuple(
            tile_slicing_dict[dim] for dim in self.source_orientation if dim in "xy"
        )

        tgt_tile = self._reorient_volume_src_to_tgt(src_tile[tile_slicing])

        untrimmed_topleft = dict_subtract(tile_index.coords, min_tile.coords)
        # location of the top left of the tile in out
        topleft_dict = {
            "z": untrimmed_topleft["z"],  # we don't trim in Z
            "y": 0
            if min_row
            else untrimmed_topleft["y"] - src_inner_slicing["min"]["y"],
            "x": 0
            if min_col
            else untrimmed_topleft["x"] - src_inner_slicing["min"]["x"],
        }
        topleft = tuple(topleft_dict[dim] for dim in self.target_orientation)

        arr_slice = tuple(slice(tl, tl + s) for tl, s in zip(topleft, tgt_tile.shape))
        out[arr_slice] = tgt_tile

    def _iter_tiles(self, tile_indices):
        for tile_idx in tile_indices:
            yield self._get_tile(tile_idx), tile_idx

    def _assemble_tiles(self, tile_indices, src_inner_slicing, out):
        """

        Parameters
        ----------
        tile_indices : list of TileIndex
            tiles to be got, reoriented, and compiled.
        src_inner_slicing : dict of str to {dict of str to int}
            {'min': {}, 'max': {}} with values {'x': int, 'y': int, 'z': int}
        out : array-like
            target-spaced, into which the tiles will be written

        Returns
        -------
        np.ndarray
        """
        min_tile = min(tile_indices, key=lambda idx: (idx.depth, idx.row, idx.col))
        max_tile = max(tile_indices, key=lambda idx: (idx.depth, idx.row, idx.col))

        tqdm_kwargs = {
            "total": len(tile_indices),
            "ncols": 80,
            "unit": "tiles",
            "desc": "Downloading tiles",
        }
        for src_tile, tile_index in tqdm(self._iter_tiles(tile_indices), **tqdm_kwargs):
            self._tile_cache[tile_index] = src_tile
            self._insert_tile_into_arr(
                tile_index, src_tile, min_tile, max_tile, src_inner_slicing, out
            )

        return out

    def _fetch(self, tile_index):
        """

        Parameters
        ----------
        tile_index : TileIndex

        Returns
        -------
        Future of np.ndarray in source orientation
        """
        url = self.mirror.generate_url(tile_index)
        try:
            return response_to_array(self._session.get(url, timeout=self.timeout))
        except HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(
                    "Tile not found at %s (error 404), returning blank tile", url
                )
                return self._make_empty_tile(tile_index.width, tile_index.height)
            else:
                raise

    def _reorient_roi_tgt_to_src(self, roi_tgt):
        return roi_tgt[:, self._dimension_mappings]

    def roi_to_scaled(self, roi, roi_mode, zoom_level):
        """
        Convert ROI into scaled stack space, keeping in the target dimension order.

        Parameters
        ----------
        roi : np.ndarray
            ROI as 2x3 array containing half-closed bounds in the target dimension order
        roi_mode : ROIMode or str
            Whether the ROI is in "project", "stack", or "scaled" stack coordinates
        zoom_level : float
            The desired zoom level of the returned data

        Returns
        -------
        np.ndarray
            ROI as 2x3 array containing half-closed bounds in scaled stack space in the target dimension order
        """
        roi_mode = ROIMode(roi_mode)
        roi_tgt = np.asarray(roi)

        if zoom_level != int(zoom_level):
            raise NotImplementedError("Non-integer zoom level is not supported")

        if roi_mode == ROIMode.PROJECT:
            if not isinstance(self.stack, ProjectStack):
                raise ValueError(
                    "ImageFetcher's stack is not related to a project, cannot use ROIMode.PROJECT"
                )
            if self.stack.orientation != StackOrientation.XY:
                warn(
                    "Stack orientation differs from project: returned array's orientation will reflect"
                    "stack orientation, not project orientation"
                )
            roi_tgt = self.coord_trans.project_to_stack_array(
                roi_tgt, dims=self.target_orientation
            )
            roi_mode = ROIMode.STACK

        if roi_mode == ROIMode.STACK:
            roi_tgt = self.coord_trans.stack_to_scaled_array(
                roi_tgt, zoom_level, dims=self.target_orientation
            )
            roi_mode = ROIMode.SCALED

        if roi_mode == ROIMode.SCALED:
            roi_tgt = np.array(
                [np.floor(roi_tgt[0, :]), np.ceil(roi_tgt[1, :])], dtype=int
            )
        else:
            raise ValueError(
                "Mismatch between roi_mode and roi"
            )  # shouldn't be possible

        return roi_tgt

    def get(self, roi, roi_mode=ROIMode.STACK, zoom_level=0, out=None):
        """
        Fetch image data in the ROI in the dimension order of the target orientation.

        ROI modes:
            ROIMode.PROJECT ('project'):
                - `roi` is given in project space
                - `zoom_level` specifies the zoom level of returned data
                - Returned array may overflow desired ROI by < 1 scaled pixel per side
                - Data will be reoriented from stack space/orientation into the `target_orientation` without
                  going via project space: as such, for stacks with orientation other than 'xy', the output
                  data will not be in the same orientation as the project-spaced query.
            ROIMode.STACK ('stack'):
                - Default option
                - `roi` is given in unscaled stack space (i.e. pixels at zoom level 0)
                - `zoom_level` specifies the desired zoom level of returned data
                - Returned array may overflow desired ROI by < 1 scaled pixel per side
                - Equivalent to ROIMode.SCALED if `zoom_level` == 0
            ROIMode.SCALED ('scaled'):
                - `roi` is given in scaled stack space at the given zoom level.
                - `zoom_level` specifies the zoom level of ROI and returned data
                - Returned array treats `roi` as a half-closed interval: i.e. it should have shape np.diff(roi, axis=0)

        Parameters
        ----------
        roi : array-like
            2 x 3 array where the columns are the 3 dimensions in the target orientation, and the rows are the upper
             and lower bounds of the ROI.
        roi_mode : ROIMode or str
            Default ROIMode.STACK
        zoom_level : int
        out : array-like or None
            Anything with array-like __setitem__ handling (e.g. np.ndarray, np.memmap, h5py.File, z5py.File), to which
            the results will be written. Must have the same shape in as the ROI does in scaled pixels. If None
            (default), will create a new np.ndarray.

        Returns
        -------
        array-like
        """
        roi_tgt = self.roi_to_scaled(roi, roi_mode, zoom_level)
        roi_src = self._reorient_roi_tgt_to_src(roi_tgt)
        tile_indices, inner_slicing_src = self._roi_to_tiles(roi_src, zoom_level)

        if out is None:
            out = np.zeros(np.diff(roi_tgt, axis=0).squeeze(), dtype=np.uint8)

        return self._assemble_tiles(tile_indices, inner_slicing_src, out)

    def get_project_space(self, roi, zoom_level=0, out=None):
        """
        Equivalent to `get` method with roi_mode=ROIMode.PROJECT
        """
        return self.get(roi, ROIMode.PROJECT, zoom_level, out)

    def get_stack_space(self, roi, zoom_level=0, out=None):
        """
        Equivalent to `get` method with roi_mode=ROIMode.STACK
        """
        return self.get(roi, ROIMode.STACK, zoom_level, out)

    def get_scaled_space(self, roi, zoom_level=0, out=None):
        """
        Equivalent to `get` method with roi_mode=ROIMode.SCALED
        """
        return self.get(roi, ROIMode.SCALED, zoom_level, out)

    def set_fastest_mirror(self, reps=1, normalise_by_tile_size=True):
        """
        Set the ImageFetcher to use the fastest accessible mirror.

        Parameters
        ----------
        reps : int
            How many times to fetch the canary tile, for robustness
        normalise_by_tile_size : bool
            Whether to normalise the fetch time by the tile size used by this mirror (to get per-pixel response time)
        """
        self.mirror = self.stack.get_fastest_mirror(
            self.timeout, reps, normalise_by_tile_size
        )

    @classmethod
    def from_stack_info(cls, stack_info, *args, **kwargs):
        """

        Parameters
        ----------
        stack_info : dict
        args, kwargs
            See __init__ for arguments beyond stack

        Returns
        -------
        ImageFetcher
        """
        return cls(ProjectStack.from_stack_info(stack_info), *args, **kwargs)

    @classmethod
    def from_catmaid(cls, catmaid, stack_id, *args, **kwargs):
        """

        Parameters
        ----------
        catmaid : catpy.AbstractCatmaidClient
        stack_id : int
        args, kwargs
            See __init__ for arguments beyond stack

        Returns
        -------
        ImageFetcher
        """
        stack_info = catmaid.get((catmaid.project_id, "stack", stack_id, "info"))
        return cls.from_stack_info(stack_info, *args, **kwargs)


class DummyResponse(object):
    def __init__(self, array):
        self.array = array


def as_future_response(array):
    return as_future(DummyResponse(array))


class ThreadedImageFetcher(ImageFetcher):
    def __init__(
        self,
        stack,
        output_orientation=DEFAULT_3D_ORIENTATION,
        preferred_mirror=None,
        timeout=1,
        cache_items=DEFAULT_CACHE_ITEMS,
        cache_bytes=DEFAULT_CACHE_BYTES,
        broken_slice_handling=DEFAULT_BROKEN_SLICE_HANDLING,
        cval=0,
        auth=None,
        threads=THREADS,
    ):
        """
        Note: for small numbers of tiles on fast internet connection, ImageFetcher may be faster

        Parameters
        ----------
        stack : catpy.stacks.Stack
        output_orientation : str or Orientation3D
            default Orientation3D.ZYX
        preferred_mirror : int or str or StackMirror or None
            default None
        timeout : float
            default 1
        cache_items : int or None
            default 10
        cache_bytes : int or None
            default None
        broken_slice_handling : str or BrokenSliceHandling
            default BrokenSliceHandling.FILL
        cval : int
            default 0
        threads : int
            default 10
        """
        super(ThreadedImageFetcher, self).__init__(
            stack,
            output_orientation,
            preferred_mirror,
            timeout,
            cache_items,
            cache_bytes,
            broken_slice_handling,
            cval,
            auth,
        )
        self._session = FuturesSession(session=self._session, max_workers=threads)

    def _get_tile(self, tile_index):
        """
        Get the tile from the cache, handle broken slices, or fetch.

        Parameters
        ----------
        tile_index : TileIndex

        Returns
        -------
        Future
        """
        try:
            return as_future_response(self._tile_cache[tile_index])
        except KeyError:
            pass

        if tile_index.depth in self.stack.broken_slices:
            if (
                self.broken_slice_handling == BrokenSliceHandling.FILL
                and self.cval is not None
            ):
                tile = np.empty((tile_index.width, tile_index.height))
                tile.fill(self.cval)
                return as_future_response(tile)
            else:
                raise NotImplementedError(
                    "'fill' with a non-None cval is the only implemented broken slice handling mode"
                )

        return self._fetch(tile_index)

    def _iter_tiles(self, tile_indices):
        logger.info("Queuing requests, may take a few seconds...")
        fetched_tiles = {
            self._get_tile(tile_index): tile_index for tile_index in tile_indices
        }
        for tile_future in as_completed(fetched_tiles):
            yield tile_future.result().array, fetched_tiles[tile_future]

    def _fetch(self, tile_index):
        """

        Parameters
        ----------
        tile_index : TileIndex

        Returns
        -------
        Future of np.ndarray in source orientation
        """
        url = self.mirror.generate_url(tile_index)
        return self._session.get(
            url, timeout=self.timeout, background_callback=response_to_array_callback
        )
