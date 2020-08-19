from enum import IntEnum
from timeit import timeit

import requests

from catpy.compat import tqdm
from catpy.spatial import StackOrientation


class StackMirror(object):
    def __init__(
        self,
        image_base,
        tile_height,
        tile_width,
        tile_source_type,
        file_extension,
        title=None,
        position=0,
        auth=None,
    ):
        """
        Representation of CATMAID stack mirror

        Parameters
        ----------
        image_base : str
        tile_width : int
        tile_height : int
        tile_source_type : int or TileSourceType
        file_extension : str
        title : str
        position : int
        """
        self.auth = auth

        self.image_base = image_base if image_base.endswith("/") else image_base + "/"
        self.tile_height = int(tile_height)
        self.tile_width = int(tile_width)
        self.tile_source_type = TileSourceType(tile_source_type)
        self.file_extension = (
            file_extension[1:] if file_extension.startswith(".") else file_extension
        )
        self.title = str(title)
        self.position = int(position)

        self.format_url = self.tile_source_type.format(**self.__dict__)

    def generate_url(self, tile_index):
        """
        Generate absolute URL to desired image

        Parameters
        ----------
        tile_index : TileIndex

        Returns
        -------
        str
        """
        if (
            tile_index.height != self.tile_height
            and tile_index.width != self.tile_width
        ):
            raise ValueError("Given TileIndex is not compatible with this stack mirror")
        return self.format_url.format(**tile_index.url_kwargs)

    def get_tile_index(self, scaled_coords, zoom_level=0):
        """

        Parameters
        ----------
        scaled_coords : dict
        zoom_level : int

        Returns
        -------
        tuple of (TileIndex, dict)
            Index of tile on which this pixel appears, and its offset from the top left shallow corner of that tile
        """
        tile_idx = TileIndex(
            depth=int(scaled_coords["z"]),
            row=int(scaled_coords["y"] / self.tile_height),
            col=int(scaled_coords["x"] / self.tile_width),
            zoom_level=zoom_level,
            height=self.tile_height,
            width=self.tile_width,
        )

        tile_coords = tile_idx.coords
        offset = {dim: scaled_coords[dim] - tile_coords[dim] for dim in "xyz"}

        return tile_idx, offset

    @classmethod
    def from_dict(cls, d):
        """
        Instantiate StackMirror from one of the items in the 'mirrors' list supplied under
        CATMAID's {project_id}/stack/{stack_id}/info endpoint

        Parameters
        ----------
        d : dict

        Returns
        -------
        StackMirror
        """
        return cls(
            d["image_base"],
            d["tile_height"],
            d["tile_width"],
            d["tile_source_type"],
            d["file_extension"],
            d["title"],
            d["position"],
        )


class Stack(object):
    def __init__(self, dimension, broken_slices=None, canary_location=None):
        """
        Representation of an image stack which could be used by CATMAID.

        Parameters
        ----------
        dimension : dict
            {'x': x, 'y': y, 'z': z}, size of stack in voxels
        broken_slices : iterable of int
            z-slice indices which are missing from stack
        canary_location : dict
            {'x': x, 'y': y, 'z': z}
        """
        self.dimension = dimension
        self.broken_slices = {int(s) for s in broken_slices} if broken_slices else set()
        self.canary_location = canary_location or {"x": 0, "y": 0, "z": 0}
        self.mirrors = []

    def get_fastest_mirror(self, timeout=1, reps=1, normalise_by_tile_size=True):
        """
        Determine the fastest accessible mirror.

        Parameters
        ----------
        timeout : float
            Timeout in seconds for each request to the tile server
        reps : int
            How many times to fetch the canary tile, for robustness
        normalise_by_tile_size : bool
            Whether to normalise the fetch time by the tile size used by this mirror (to get per-pixel response time)

        Returns
        -------
        StackMirror
        """
        response_times = []

        tqdm_kwargs = {"ncols": 80, "unit": "mirrors", "desc": "Checking mirrors"}
        for mirror in tqdm(self.mirrors, **tqdm_kwargs):
            tile_index, _ = mirror.get_tile_index(self.canary_location)
            url = mirror.generate_url(tile_index)

            try:
                response_time = timeit(
                    lambda: requests.get(url, timeout=timeout), number=reps
                )
                if normalise_by_tile_size:
                    response_time /= tile_index.width * tile_index.height
                response_times.append((mirror, response_time))
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                continue

        if not response_times:
            raise ValueError("No reachable mirrors found")

        return min(response_times, key=lambda pair: pair[1])[0]


class ProjectStack(Stack):
    orientation_choices = {0: "xy", 1: "xz", 2: "zy"}

    def __init__(
        self,
        dimension,
        translation,
        resolution,
        orientation,
        broken_slices=None,
        canary_location=None,
    ):
        """
        Representation of an image stack as it pertains to a CATMAID project

        Parameters
        ----------
        dimension : dict
            {'x': x, 'y': y, 'z': z}, size of stack in voxels
        translation : dict
            {'x': x, 'y': y, 'z': z}, origin of stack in project space
        resolution : dict
            {'x': x, 'y': y, 'z': z}, size of stack voxels in project units
        orientation : {'xy', 'xz' 'zy'}
        broken_slices : iterable of int
            z-slice indices which are missing from stack
        canary_location : dict
            {'x': x, 'y': y, 'z': z}
        """
        super(ProjectStack, self).__init__(dimension, broken_slices, canary_location)
        self.translation = translation
        self.resolution = resolution
        self.orientation = StackOrientation.from_value(orientation)

    @classmethod
    def from_stack_info(cls, stack_info):
        """
        Instantiate Stack from the response supplied by CATMAID's {project_id}/stack/{stack_id}/info endpoint

        Parameters
        ----------
        stack_info : dict

        Returns
        -------
        Stack
        """
        stack = cls(
            stack_info["dimension"],
            stack_info["translation"],
            stack_info["resolution"],
            stack_info["orientation"],
            stack_info["broken_slices"],
            stack_info["canary_location"],
        )
        mirrors = [StackMirror.from_dict(d) for d in stack_info["mirrors"]]

        stack.mirrors.extend(sorted(mirrors, key=lambda m: (m.position, m.title)))
        return stack


class TileSourceType(IntEnum):
    """https://catmaid.readthedocs.io/en/stable/tile_sources.html"""

    FILE_BASED = 1
    REQUEST_QUERY = 2
    HDF5 = 3
    FILE_BASED_WITH_ZOOM_DIRS = 4
    DIR_BASED = 5
    DVID_IMAGEBLK = 6
    RENDER_SERVICE = 7
    DVID_IMAGETILE = 8
    FLIXSERVER = 9
    H2N5_TILES = 10

    def format(self, **kwargs):
        try:
            format_url = format_urls[self]
        except KeyError:
            raise ValueError(
                "{} is not supported by TileFetcher, supported types are below:\n\t{}".format(
                    self, "\n\t".join(str(k) for k in sorted(format_urls))
                )
            )
        return format_url.format(**kwargs)


format_urls = {
    TileSourceType.FILE_BASED: "{image_base}{{depth}}/{{row}}_{{col}}_{{zoom_level}}.{file_extension}",
    TileSourceType.FILE_BASED_WITH_ZOOM_DIRS: "{image_base}{{depth}}/{{zoom_level}}/{{row}}_{{col}}.{file_extension}",
    TileSourceType.DIR_BASED: "{image_base}{{zoom_level}}/{{depth}}/{{row}}/{{col}}.{file_extension}",
    TileSourceType.RENDER_SERVICE: "{image_base}largeDataTileSource/{tile_width}/{tile_height}/"
    "{{zoom_level}}/{{depth}}/{{row}}/{{col}}.{file_extension}",
    TileSourceType.FLIXSERVER: "{image_base}{{depth}}/{{row}}_{{col}}_{{zoom_level}}.{file_extension}",
}


class TileIndex(object):
    hash_keys = ("depth", "row", "col", "zoom_level", "height", "width")
    url_keys = ("depth", "row", "col", "zoom_level")
    comparable_keys = ("zoom_level", "height", "width")

    def __init__(self, depth, row, col, zoom_level, height, width):
        """

        Parameters
        ----------
        depth : int
            z-index
        row : int
            y-index
        col : int
            x-index
        zoom_level : int
        height : int
            Scaled pixels
        width : int
            Scaled pixels
        """
        self.depth = depth
        self.row = row
        self.col = col
        self.zoom_level = zoom_level  # todo: not actually necessary?
        self.height = height
        self.width = width

    @property
    def coords(self):
        """
        Calculate the coordinates of the tile's upper left corner, in scaled stack coordinates.

        Returns
        -------
        dict
        """
        return {
            "x": self.width * self.col,
            "y": self.height * self.row,
            "z": self.depth,
        }

    def is_comparable(self, other):
        return all(
            getattr(self, key) == getattr(other, key, None)
            for key in self.comparable_keys
        )

    @property
    def url_kwargs(self):
        return {key: getattr(self, key) for key in self.url_keys}

    def __repr__(self):
        return "TileIndex({})".format(
            ", ".join("{}={}".format(key, getattr(self, key)) for key in self.hash_keys)
        )

    def __hash__(self):
        return hash(tuple(getattr(self, name) for name in self.hash_keys))

    def __eq__(self, other):
        return hash(self) == hash(other)
