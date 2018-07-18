import json
from functools import wraps
from xml.etree import ElementTree
from warnings import warn

import numpy as np

from catpy.client import CatmaidClientApplication, CatmaidException

import six

try:
    from os import PathLike
except ImportError:
    PathLike = six.string_types

MESHIO_MSG = "meshio is not available. For reading/writing files containing CATMAID volumes, `pip install meshio`"

try:
    import meshio
except ImportError:
    meshio = None
    warn(MESHIO_MSG)


def chunk(iterable, length, fn=None):
    if not fn:
        fn = lambda x: x

    items = []
    it = iter(iterable)
    while True:
        try:
            items.append(fn(next(it)))
        except StopIteration:
            if items:
                raise ValueError("Iterable did not have a multiple of {} items ({} spare)".format(length, len(items)))
            else:
                return
        else:
            if len(items) == length:
                yield tuple(items)
                items = []


def x3d_to_points(s):
    indexed_triangle_set = ElementTree.fromstring(s)
    assert indexed_triangle_set.tag == "IndexedTriangleSet"
    assert len(indexed_triangle_set) == 1

    coordinate = indexed_triangle_set[0]
    assert coordinate.tag == "Coordinate"
    assert len(coordinate) == 0
    points_str = coordinate.attrib["point"]
    
    for item in chunk(points_str.split(' '), 3, float):
        yield item


def points_to_triangles(points):
    return list(chunk(points, 3))


def points_to_indexed(points):
    coords_d = dict()

    coords_ref = []
    tri_indices = []

    for tri in chunk(points, 3):
        tri_indices.append([])
        for coord in tri:
            point_idx = coords_d.get(coord)

            if point_idx is None:
                point_idx = len(coords_ref)
                coords_d[coord] = point_idx
                coords_ref.append(coord)

            tri_indices[-1].append(point_idx)

    return coords_ref, tri_indices


def requires_meshio(fn):
    @wraps(fn)
    def decorated(*args, **kwargs):
        if not meshio:
            raise ImportError(MESHIO_MSG)
        return fn(*args, **kwargs)
    return decorated


@requires_meshio
def _as_meshio(points, triangles):
    return meshio.Mesh(np.asarray(points), {"triangles": np.asarray(triangles)})


@requires_meshio
def read_file(path, file_format=None):
    mesh = meshio.read(path, file_format)
    return mesh.points, mesh.cells["triangles"]


def as_list(arraylike):
    try:
        return arraylike.tolist()
    except AttributeError:
        return arraylike


class VolumeClient(CatmaidClientApplication):
    def fetch_volume(self, volume_id, indexed=True):
        """
        Retrieve a mesh from CATMAID, returning it in one of two formats.

        Parameters
        ----------
        volume_id : int
        indexed : bool
            Whether to return triangles as a (points, vertices) pair, or as a single list of triangles.

        Returns
        -------
        tuple of (np.ndarray, np.ndarray) or list of list of list
            If ``indexed`` is True (default), return a tuple of two np.ndarrays.
            The first is Nx3, where there are N vertices in the mesh,
            and contains the 3D location of each vertex in XYZ project space.
            The second is Mx3, where there are M triangles,
            and each row contains the three vertices of a triangle as indices along axis 0 of the vertex array.

            If ``indexed`` is False, return an Nx3x3 np.ndarray whose first axis enumerates triangles,
            whose second axis enumerates points describing the triangle,
            and whose third axis enumerates coordinate values describing the point.
        """
        x3d = self.get((self.project_id, "volumes", volume_id))['mesh']
        triangle_vertices = x3d_to_points(x3d)
        if indexed:
            vertices, triangles = points_to_indexed(triangle_vertices)
            return np.asarray(vertices), np.asarray(triangles)
        else:
            return np.asarray(points_to_triangles(triangle_vertices))

    @requires_meshio
    def save_volume(self, volume_id, out, out_format=None):
        mesh = _as_meshio(*self.fetch_volume(volume_id))
        meshio.write(out, mesh, file_format=out_format)

    def upload_volume(self, vertices, triangles, title, comment=None):
        geom = [as_list(vertices), as_list(triangles)]
        geom_str = json.dumps(geom)
        data = {"title": title, "mesh": geom_str, "type": "trimesh"}

        if comment is not None:
            data["comment"] = comment
        result = self.post((self.project_id, "volumes", "add"), data)

        if result["success"]:
            return result["volume_id"]
        else:
            raise CatmaidException("Failed to upload volume {} to CATMAID".format(title))

    def upload_volume_from_file(self, path, title, comment=None, file_format=None):
        vertices, triangles = read_file(path, file_format)
        return self.upload_volume(vertices, triangles, title, comment)

    def update_volume(self, volume_id, type_=None, title=None, comment=None):
        data = dict()
        if type_ is not None:
            data["type"] = type_
        if title is not None:
            data["title"] = title
        if comment is not None:
            data["comment"] = comment

        result = self.post((self.project_id, "volumes", volume_id), data)
        if result["success"]:
            return result["volume_id"]
        else:
            raise CatmaidException("Failed to update volume {} in CATMAID".format(volume_id))
