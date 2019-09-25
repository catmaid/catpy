from enum import IntEnum

import numpy as np


class StackOrientation(IntEnum):
    """Can be iterated over or indexed like the lower-case string representation of the orientation"""

    XY = 0
    XZ = 1
    ZY = 2

    def __str__(self):
        return self.name.lower()

    @classmethod
    def from_str(cls, s):
        return {o.name: o for o in StackOrientation}[s.upper()]

    @classmethod
    def from_value(cls, value, default="xy"):
        """Convert an int, str or StackOrientation into a StackOrientation.
        A NoneType ``value`` will use the default orientation."""
        if value is None:
            value = default

        if isinstance(value, str):
            return cls.from_str(value)
        elif isinstance(value, int):
            return cls(value)
        else:
            raise TypeError(
                "Cannot create a StackOrientation from {}".format(type(value).__name__)
            )

    def __iter__(self):
        return iter(str(self))

    def __getitem__(self, item):
        return str(self)[item]

    def __contains__(self, item):
        return item in str(self)


class CoordinateTransformer(object):
    def __init__(
        self,
        resolution=None,
        translation=None,
        orientation=StackOrientation.XY,
        scale_z=False,
    ):
        """
        Helper class for transforming between stack and project coordinates.

        Wherever dimensions are required, they must be in lower case ('x', 'y', 'z').

        Parameters
        ----------
        resolution : dict
            x, y and z resolution of the stack, in project units (e.g. nm) per voxel side (i.e. pixel)
        translation : dict
            x, y and z the location of the stack's origin (0, 0, 0) in project space
        orientation : StackOrientation or int or str or None
            Orientation of the stack in relation to the project. Options:
                StackOrientation
                int corresponding to StackOrientation
                'xy', 'xz', or 'zy'
                None (reverts to default 'xy')
            Default StackOrientation.XY
        scale_z : bool
            Whether or not to scale z coordinates when using stack_to_scaled* methods. Default False is recommended, but
            True may be useful for isotropic stacks.
        """
        if resolution is None:
            resolution = dict()
        if translation is None:
            translation = dict()

        self.resolution = {dim: resolution.get(dim, 1) for dim in "zyx"}
        self.translation = {dim: translation.get(dim, 0) for dim in "zyx"}
        self.scale_z = scale_z

        self.orientation = StackOrientation.from_value(orientation)
        self.depth_dim = [dim for dim in "zyx" if dim not in self.orientation][0]

        # mapping of project dimension to stack dimension, based on orientation
        self._s2p = {
            "x": self.orientation[0],
            "y": self.orientation[1],
            "z": self.depth_dim,
        }
        # mapping of stack dimension to project dimension, based on orientation
        self._p2s = {value: key for key, value in self._s2p.items()}

    @classmethod
    def from_catmaid(cls, catmaid_client, stack_id):
        """
        Return a CoordinateTransformer for a particular CATMAID stack.

        Parameters
        ----------
        catmaid_client : AbstractCatmaidClient
            Object capable of interfacing with Catmaid
        stack_id : int

        Returns
        -------
        CoordinateTransformer
        """
        stack_info = catmaid_client.get(
            (catmaid_client.project_id, "stack", stack_id, "info")
        )
        return cls(
            stack_info["resolution"],
            stack_info["translation"],
            stack_info["orientation"],
        )

    def project_to_stack_coord(self, proj_dim, project_coord):
        return (
            self._p2s[proj_dim],
            (project_coord - self.translation[proj_dim]) / self.resolution[proj_dim],
        )

    def project_to_stack(self, project_coords):
        """
        Take a point in project space and transform it into stack space.

        Parameters
        ----------
        project_coords : dict
            x, y, and/or z coordinates in project / real space

        Returns
        -------
        dict
            coordinates transformed into stack / voxel space
        """
        return dict(
            self.project_to_stack_coord(proj_dim, proj_coord)
            for proj_dim, proj_coord in project_coords.items()
        )

    def project_to_stack_array(self, arr, dims="xyz"):
        """
        Take an array of points in project space and transform them into stack space.

        Currently, this is a convenience method only; it does not yet utilise array operations.

        Parameters
        ----------
        arr : array-like
            M by 3 array containing M coordinates in project / real space in 3 dimensions
        dims : str
            Order of dimensions in columns, default 'xyz'

        Returns
        -------
        np.ndarray
            M by 3 array containing M coordinates in stack / voxel space in 3 dimensions
        """
        # todo: use array ops
        return self._transform_arr(arr, dims, self.project_to_stack)

    def stack_to_project_coord(self, stack_dim, stack_coord):
        proj_dim = self._s2p[stack_dim]
        return (
            self._s2p[stack_dim],
            stack_coord * self.resolution[proj_dim] + self.translation[proj_dim],
        )

    def stack_to_project(self, stack_coords):
        """
        Take a point in stack space and transform it into project space.

        Parameters
        ----------
        stack_coords : dict
            x, y, and/or z coordinates in stack / voxel space

        Returns
        -------
        dict
            coordinates transformed into project / real space
        """
        return dict(
            self.stack_to_project_coord(stack_dim, stack_coord)
            for stack_dim, stack_coord in stack_coords.items()
        )

    def stack_to_project_array(self, arr, dims="xyz"):
        """
        Take an array of points in stack space and transform them into project space.

        Currently, this is a convenience method only; it does not yet utilise array operations.

        Parameters
        ----------
        arr : array-like
            M by N array containing M coordinates in stack / voxel space in N dimensions
        dims : array-like or str
            Order of dimensions in columns, default 'xyz'

        Returns
        -------
        np.ndarray
            M by N array containing M coordinates in project / real space in N dimensions
        """
        # todo: use array ops
        return self._transform_arr(arr, dims, self.stack_to_project)

    def _transform_arr(self, arr, dims, fn):
        output = []
        for row in arr:
            row_d = dict(zip(dims, row))
            transformed = fn(row_d)
            output.append([transformed[dim] for dim in dims])

        return np.asarray(output)

    def stack_to_scaled_coord(self, dim, stack_coord, tgt_zoom, src_zoom=0):
        """
        Convert a stack coordinate in a single dimension into a pixel coordinate at the given zoom level.

        Whether z coordinates are scaled is controlled by the `scale_z` constructor argument/ instance variable.

        Parameters
        ----------
        dim : {'x', 'y', 'z'}
            Which dimension to act in
        stack_coord : float
        tgt_zoom : float
            Desired zoom level out of the output coordinate
        src_zoom : float
            Zoom level of the given coordinate (default 0)

        Returns
        -------
        float
        """
        if dim == "z" and not self.scale_z:
            return stack_coord
        scale_diff = np.exp2(tgt_zoom - src_zoom)
        return stack_coord / scale_diff

    def stack_to_scaled(self, stack_coords, tgt_zoom, src_zoom=0):
        """
        Convert a point in stack space into a point in stack space at a different zoom level.

        Whether z coordinates are scaled is controlled by the `scale_z` constructor argument/ instance variable.

        Parameters
        ----------
        stack_coords : dict
            x, y, and/or z coordinates in stack / voxel space
        tgt_zoom : float
            Desired zoom level out of the output coordinates
        src_zoom : float
            Zoom level of the given coordinates (default 0)

        Returns
        -------
        dict
            Rescaled coordinates
        """
        return {
            dim: self.stack_to_scaled_coord(dim, proj_coord, tgt_zoom, src_zoom)
            for dim, proj_coord in stack_coords.items()
        }

    def stack_to_scaled_array(self, arr, tgt_zoom, src_zoom=0, dims="xyz"):
        """
        Take an array of points in stack space into scale them to a different zoom level.

        Whether z coordinates are scaled is controlled by the `scale_z` constructor argument/ instance variable.

        Parameters
        ----------
        arr : np.ndarray
            M by N array containing M coordinates in stack / voxel space in N dimensions
        tgt_zoom : float
            Desired zoom level out of the output coordinates
        src_zoom : float
            Zoom level of the given coordinates (default 0)
        dims : str
            Order of dimensions in columns, default (x, y, z)

        Returns
        -------
        np.ndarray
        """
        scale_diff = np.exp2(tgt_zoom - src_zoom)
        out = np.array(arr)

        if self.scale_z:
            return out / scale_diff
        else:
            xy_idxs = tuple(idx for idx, dim in enumerate(dims) if dim in "xy")
            out[:, xy_idxs] = out[:, xy_idxs] / scale_diff
            return out

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        attributes = ("resolution", "translation", "scale_z")
        return all(getattr(self, name) == getattr(other, name) for name in attributes)
