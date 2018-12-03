# -*- coding: utf-8 -*-

from __future__ import division, unicode_literals, absolute_import

import json
import webbrowser
from abc import ABCMeta, abstractmethod
from warnings import warn

from six import string_types, add_metaclass
from enum import IntEnum, Enum
import requests
import numpy as np


class ConnectorRelationType(Enum):
    SYNAPTIC = "Synaptic"
    GAP_JUNCTION = "Gap junction"
    ABUTTING = "Abutting"
    ATTACHMENT = "Attachment"
    SPATIAL = "Spatial"
    OTHER = ""

    @classmethod
    def from_relation(cls, relation):
        return {
            ConnectorRelation.presynaptic_to: cls.SYNAPTIC,
            ConnectorRelation.postsynaptic_to: cls.SYNAPTIC,
            ConnectorRelation.gapjunction_with: cls.GAP_JUNCTION,
            ConnectorRelation.abutting: cls.ABUTTING,
            ConnectorRelation.attached_to: cls.ATTACHMENT,
            ConnectorRelation.close_to: cls.SPATIAL,
            ConnectorRelation.other: cls.OTHER
        }[relation]


class ConnectorRelation(Enum):
    """Enum describing the link between a treenode and connector, i.e. the treenode is ____ to the connector.

    The enum's ``name`` is CATMAID's concept of "relation name":
    what is returned in the ``relation`` field of the <pid>/connectors/types/ response.

    The enum's ``value`` is the ``name`` field of the <pid>/connectors/types/ response.

    The mappings from relation name to relation ID are project-specific and must be fetched from CATMAID.
    """
    other = ""
    presynaptic_to = "Presynaptic"
    postsynaptic_to = "Postsynaptic"
    gapjunction_with = "Gap junction"
    abutting = "Abutting"
    attached_to = "Attachment"
    close_to = "Close to"

    @property
    def type(self):
        return ConnectorRelationType.from_relation(self)

    @property
    def is_synaptic(self):
        return self.type == ConnectorRelationType.SYNAPTIC

    def __str__(self):
        return self.value


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
    def from_value(cls, value, default='xy'):
        """Convert an int, str or StackOrientation into a StackOrientation.
        A NoneType ``value`` will use the default orientation."""
        if value is None:
            value = default

        if isinstance(value, string_types):
            return cls.from_str(value)
        elif isinstance(value, int):
            return cls(value)
        else:
            raise TypeError("Cannot create a StackOrientation from {}".format(type(value).__name__))

    def __iter__(self):
        return iter(str(self))

    def __getitem__(self, item):
        return str(self)[item]

    def __contains__(self, item):
        return item in str(self)


def make_url(base_url, *args):
    """
    Given any number of URL components, join them as if they were a path regardless of trailing and prepending slashes

    Examples
    --------

    >>> make_url('google.com', 'mail')
    'google.com/mail'

    >>> make_url('google.com/', '/mail')
    'google.com/mail'
    """
    for arg in args:
        arg_str = str(arg)
        joiner = '' if base_url.endswith('/') else '/'
        relative = arg_str[1:] if arg_str.startswith('/') else arg_str
        base_url = requests.compat.urljoin(base_url + joiner, relative)

    return base_url


class WrappedCatmaidException(Exception):
    exception_keys = frozenset(('traceback', 'error', 'type'))
    spacer = '    '

    def __init__(self, message, response):
        """
        Exception wrapping a django error which results in a JSON response being returned containing information
        about that error.

        Parameters
        ----------
        response : requests.Response
            Response containing JSON-formatted error from Django
        """
        super(WrappedCatmaidException, self).__init__(message)
        self.msg = message
        data = response.json()
        self.traceback = data['traceback']
        self.type = data['type']
        self.error = data['error']

    def __str__(self):
        return '\n'.join([
                    super(WrappedCatmaidException, self).__str__(),
                    self.spacer + 'Response contained traceback (most recent call last):'
                ] + [
                    self.spacer + line for line in self.traceback.split('\n')
                ] + [
                    '{}{}: {}'.format(self.spacer, self.type, self.error)
                ]
            )

    @classmethod
    def raise_on_error(cls, response):
        if response.headers.get('content-type') == 'application/json':
            data = response.json()
            if isinstance(data, dict) and cls.exception_keys.issubset(data):
                raise cls('Received error response from {}'.format(response.url), response)


@add_metaclass(ABCMeta)
class AbstractCatmaidClient(object):
    """
    Abstract parent class for CatmaidClient and CatmaidClientApplications.

    Users should not subclass this; it is provided purely as a convenience for type checking.
    """

    def get(self, relative_url, params=None, raw=False, **kwargs):
        """
        Get data from a running instance of CATMAID.

        Parameters
        ----------
        relative_url : str or tuple of str
            URL to send the request to, relative to the base_url. If a tuple is passed, its elements will be joined
            with '/'.
        params: dict or str, optional
            JSON-like key/value data to be included in the get URL (defaults to empty)
        raw: bool, optional
            Whether to return the response as a string regardless of its content-type (by default, JSON responses will
            be parsed)
        kwargs
            Extra keyword arguments to pass to `requests.Session.get()`

        Returns
        -------
        dict or str
            Data returned from CATMAID: type depends on the 'raw' parameter.
        """
        return self.fetch(relative_url, method='GET', data=params, raw=raw, **kwargs)

    def post(self, relative_url, data=None, raw=False, **kwargs):
        """
        Post data to a running instance of CATMAID.

        Parameters
        ----------
        relative_url : str or tuple of str
            URL to send the request to, relative to the base_url. If a tuple is passed, its elements will be joined
            with '/'.
        data: dict or str, optional
            JSON-like key/value data to be included in the request as a payload (defaults to empty)
        raw: bool, optional
            Whether to return the response as a string regardless of its content-type (by default, JSON responses will
            be parsed)
        kwargs
            Extra keyword arguments to pass to `requests.Session.post()`

        Returns
        -------
        dict or str
            Data returned from CATMAID: type depends on the 'raw' parameter.
        """
        return self.fetch(relative_url, method='POST', data=data, raw=raw, **kwargs)

    @abstractmethod
    def fetch(self, relative_url, method='GET', data=None, raw=False, **kwargs):
        pass


class CatmaidClient(AbstractCatmaidClient):
    """
    Python object handling authentication, request pooling etc. for requests made to a CATMAID server.

    Users creating their own interface should not subclass this, but instead subclass CatmaidClientApplication, which
    wraps a CatmaidClient object. This composition approach eases testing and sharing CatmaidClient instances among
    different interfaces.
    """

    def __init__(self, base_url, token=None, auth_name=None, auth_pass=None, project_id=None):
        """
        Instantiate CatmaidClient object for handling requests to a CATMAID server.

        Parameters
        ----------
        base_url : str
            URL at which CATMAID server is running
        token : str
            API token as assigned by CATMAID server
        auth_name : str
            HTTP auth username
        auth_pass : str
            HTTP auth password
        project_id : int
            (Optional)
        """
        self.base_url = base_url

        self._session = requests.Session()
        if auth_name is not None and auth_pass is not None:
            self.set_http_auth(auth_name, auth_pass)
        if token is not None:
            self.set_api_token(token)

        self.project_id = project_id

    def set_http_auth(self, username, password):
        """
        Set HTTP authorization for CatmaidClient in place.

        Parameters
        ----------
        username : str
            HTTP authorization username
        password : str
            HTTP authorization password

        Returns
        -------
        CatmaidClient
            Reference to the same, now-authenticated CatmaidClient instance
        """
        self._session.auth = (username, password)
        return self

    def set_api_token(self, token):
        """
        Set CatmaidClient to use the given API token in place.

        Parameters
        ----------
        token : str
            API token associated with your CATMAID account

        Returns
        -------
        CatmaidClient
            Reference to the same, now-authenticated CatmaidClient instance
        """
        self._session.headers['X-Authorization'] = 'Token ' + token
        return self

    def _make_request_url(self, arg):
        """
        Create an absolute request URL for the CATMAID server.

        Parameters
        ----------
        arg : str or tuple of str
            Relative URL (to the base_url). If a tuple is passed, its elements will be joined with '/'.

        Returns
        -------
        str
        """
        if isinstance(arg, string_types):
            return make_url(self.base_url, arg)
        else:
            return make_url(self.base_url, *arg)

    @classmethod
    def from_json(cls, credentials):
        """
        Return a CatmaidClient instance with credentials matching those in a JSON file. Should have the property
        `base_url` as a minimum.

        If HTTP authentication is required, should have the properties `auth_name` and `auth_pass`.

        If you intend to use an authorized CATMAID account (required for some endpoints), should have the property
        `token`.

        Can optionally include the property `project_id`.

        Parameters
        ----------
        credentials : str or dict
            Path to the JSON credentials file, or a dict representing the object

        Returns
        -------
        CatmaidClient
            Instance of the API, authenticated with the encoded credentials
        """
        if not isinstance(credentials, dict):
            with open(str(credentials)) as f:
                credentials = json.load(f)

        return cls(
            credentials['base_url'],
            credentials.get('token'),
            credentials.get('auth_name'),
            credentials.get('auth_pass'),
            credentials.get('project_id')
        )

    def fetch(self, relative_url, method='GET', data=None, raw=False, **kwargs):
        """
        Interact with the CATMAID server in a manner very similar to the javascript CATMAID.fetch API.

        Parameters
        ----------
        relative_url : str or tuple of str
            URL to send the request to, relative to the base_url. If a tuple is passed, its elements will be joined
            with '/'.
        method: {'GET', 'POST'}, optional
            HTTP method to use (the default is 'GET')
        data: dict or str, optional
            JSON-like key/value data to be included in the request as a payload (defaults to empty)
        raw: bool, optional
            Whether to return the response as a string regardless of its content-type (by default, JSON responses will
            be parsed)
        kwargs
            Extra keyword arguments to pass to `requests.Session.get/post()`, depending on `method`

        Returns
        -------
        dict or list or str
            Data returned from CATMAID. JSON responses will be parsed unless `raw` is `True`; all other responses
            will be returned as strings.
        """
        url = self._make_request_url(relative_url)
        data = data or dict()
        if method.upper() == 'GET':
            response = self._session.get(url, params=data, **kwargs)
        elif method.upper() == 'POST':
            response = self._session.post(url, data=data, **kwargs)
        else:
            raise ValueError('Unknown HTTP method {}'.format(repr(method)))

        response.raise_for_status()
        WrappedCatmaidException.raise_on_error(response)
        if response.headers['content-type'] == 'application/json' and not raw:
            return response.json()
        else:
            return response.text


class CoordinateTransformer(object):
    def __init__(self, resolution=None, translation=None, orientation=StackOrientation.XY, scale_z=False):
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

        self.resolution = {dim: resolution.get(dim, 1) for dim in 'zyx'}
        self.translation = {dim: translation.get(dim, 0) for dim in 'zyx'}
        self.scale_z = scale_z

        self.orientation = StackOrientation.from_value(orientation)
        self.depth_dim = [dim for dim in 'zyx' if dim not in self.orientation][0]

        # mapping of project dimension to stack dimension, based on orientation
        self._s2p = {
            'x': self.orientation[0],
            'y': self.orientation[1],
            'z': self.depth_dim
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
        stack_info = catmaid_client.get((catmaid_client.project_id, 'stack', stack_id, 'info'))
        return cls(stack_info['resolution'], stack_info['translation'], stack_info['orientation'])

    def project_to_stack_coord(self, proj_dim, project_coord):
        return self._p2s[proj_dim], (project_coord - self.translation[proj_dim]) / self.resolution[proj_dim]

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

    def project_to_stack_array(self, arr, dims='xyz'):
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
        return self._s2p[stack_dim], stack_coord * self.resolution[proj_dim] + self.translation[proj_dim]

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

    def stack_to_project_array(self, arr, dims='xyz'):
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
        if dim == 'z' and not self.scale_z:
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

    def stack_to_scaled_array(self, arr, tgt_zoom, src_zoom=0, dims='xyz'):
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
            xy_idxs = tuple(idx for idx, dim in enumerate(dims) if dim in 'xy')
            out[:, xy_idxs] = out[:, xy_idxs] / scale_diff
            return out

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        attributes = ('resolution', 'translation', 'scale_z')
        return all(getattr(self, name) == getattr(other, name) for name in attributes)


def get_typed(d, key, constructor=None, default=None):
    """
    like dict.get, but if the response/default is not None, pass it to the given constructor.

    Parameters
    ----------
    d : dict
    key : hashable
    constructor : callable
    default

    Returns
    -------

    """
    response = d.get(key, default)
    if constructor is None or response is None:
        return response
    else:
        return constructor(response)


class CatmaidUrl(object):
    tracing_tool_name = 'tracingtool'

    def __init__(
        self, base_url, project_id, stack_group_id=None, stack_id=None, scale=0, x=None, y=None, z=None,
        tool=None, active_skeleton_id=None, active_node_id=None
    ):
        self.base_url = base_url

        self.project_id = project_id

        self.default_scale = scale

        self.stack_group = None
        self.stack_group_scale = None
        self.stacks = []
        self.set_stack_group(stack_group_id, scale)
        if stack_id is not None:
            self.add_stack(stack_id, scale)

        self.x = x
        self.y = y
        self.z = z

        self.tool = tool
        self.active_skeleton_id = active_skeleton_id
        self.active_node_id = active_node_id

    @classmethod
    def from_catmaid(
        cls, catmaid_client, stack_group_id=None, stack_id=None, scale=0, x=None, y=None, z=None,
        tool=None, active_skeleton_id=None, active_node_id=None
    ):
        """
        Instantiate CatmaidUrl based on a CATMAID interface instance.

        Parameters
        ----------
        catmaid_client : CatmaidClient or catpy.applications.base.CatmaidClientApplication
        stack_group_id : int
        stack_id : int
        scale : float
        x : float
            x coordinate in project (real) space
        y : float
            y coordinate in project (real) space
        z : float
            z coordinate in project (real) space
        tool : str
        active_skeleton_id : int
        active_node_id : int

        Returns
        -------
        CatmaidUrl
        """
        return cls(catmaid_client.base_url, catmaid_client.project_id, stack_group_id, stack_id, scale, x, y, z,
                   tool, active_skeleton_id, active_node_id)

    @classmethod
    def from_url(cls, url):
        """
        Instantiate CatmaidUrl based on a URL pulled from a running CATMAID instance.

        Parameters
        ----------
        url : str

        Returns
        -------
        CatmaidUrl
        """
        base_url, args = url.split('/?')
        d = dict(item.split('=') for item in args.split('&'))

        kwargs = dict(
            project_id=get_typed(d, 'pid', int), scale=None,
            x=get_typed(d, 'xp', float), y=get_typed(d, 'yp', float), z=get_typed(d, 'zp', float),
            tool=d.get('tool'),
            active_skeleton_id=get_typed(d, 'active_skeleton_id', int),
            active_node_id=get_typed(d, 'active_node_id', int)
        )

        obj = cls(base_url, **kwargs)
        obj.set_stack_group(stack_group_id=int(d.get('sg')), scale=float(d.get('sgs')))

        stacks = dict()
        scales = dict()
        for key, value in d.items():
            if key.startswith('sid'):
                try:
                    stacks[int(key[3:])] = int(value)
                except ValueError:
                    pass
            elif key.startswith('s'):
                try:
                    scales[int(key[1:])] = int(value)
                except ValueError:
                    pass

        for idx, sid in sorted(stacks.items(), key=lambda x: (x[1], x[0])):
            obj.add_stack(sid, scales.get(idx))

        if obj.default_scale is None:
            obj.default_scale = 0

        return obj

    def add_stack(self, stack_id, scale=None):
        """
        Parameters
        ----------
        stack_id : int
        scale : float

        Returns
        -------
        CatmaidUrl
            A reference to itself, for chaining
        """
        # todo? fetch stack ID from stack name
        self.stacks.append((stack_id, scale))
        if self.default_scale is None:
            self.default_scale = scale
        return self

    def set_stack_group(self, stack_group_id, scale=None):
        """
        Parameters
        ----------
        stack_group_id : int
        scale : float

        Returns
        -------
        CatmaidUrl
            A reference to itself, for chaining
        """
        # todo? fetch stacks from stack group
        self.stack_group = stack_group_id
        self.stack_group_scale = scale
        if self.default_scale is None:
            self.default_scale = scale
        return self

    def _terminate_base_url(self):
        url = self.base_url
        if url.endswith('/'):
            url += '?'
        if not url.endswith('/?'):
            url += '/?'

        return url

    def __str__(self):
        elements = ['pid={}'.format(self.project_id)]

        coords = ['{}p={}'.format(dim, float(getattr(self, dim))) for dim in 'xyz' if getattr(self, dim) is not None]
        if len(coords) == 3:
            elements.extend(coords)
        elif coords:
            warn('Only {} of 3 coordinates found, ignoring'.format(len(coords)))

        if self.tool:
            elements.append('tool=' + self.tool)
            if self.tool == 'tracingtool':
                elements.append('active_node_id={}'.format(self.active_node_id))
                elements.append('active_skeleton_id={}'.format(self.active_skeleton_id))

        if self.stack_group is not None:
            elements.append('sg={}'.format(self.stack_group))
            elements.append(
                'sgs={}'.format(
                    float(self.stack_group_scale) if self.stack_group_scale is not None else float(self.default_scale)
                )
            )

        if not self.stacks:
            warn('No stacks added found, URL may be invalid')
        for idx, (stack_id, scale) in enumerate(self.stacks):
            elements.append('sid{}={}'.format(idx, stack_id))
            elements.append('s{}={}'.format(idx, float(scale) if scale is not None else float(self.default_scale)))

        return self._terminate_base_url() + '&'.join(elements)

    def open(self):
        webbrowser.open(str(self), new=2)
