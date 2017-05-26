# -*- coding: utf-8 -*-


import json
from functools import wraps
from abc import ABCMeta

from six import string_types, add_metaclass
import requests
import numpy as np


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


class CatmaidClient(object):
    """
    Python object handling authentication, request pooling etc. for requests made to a CATMAID server.
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
    def from_json(cls, path, with_project_id=True):
        """
        Return a CatmaidClient instance with credentials matching those in a JSON file. Should have the property
        `base_url` as a minimum.

        If HTTP authentication is required, should have the properties `auth_name` and `auth_pass`.

        If you intend to use an authorized CATMAID account (required for some endpoints), should have the property
        `token`.

        Can optionally include the property `project_id`.

        Parameters
        ----------
        path : str
            Path to the JSON credentials file
        with_project_id : bool
            Whether to look for the `project_id` field (it can be set later on the returned CatmaidClient instance)

        Returns
        -------
        CatmaidClient
            Instance of the API, authenticated with
        """
        with open(path) as f:
            credentials = json.load(f)
        return cls(
            credentials['base_url'],
            credentials.get('token'),
            credentials.get('auth_name'),
            credentials.get('auth_pass'),
            credentials.get('project_id') if with_project_id else None
        )

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
        if response.headers['content-type'] == 'application/json' and not raw:
            return response.json()
        else:
            return response.text


@add_metaclass(ABCMeta)
class CatmaidClientApplication(object):
    def __init__(self, catmaid_client):
        self._catmaid = catmaid_client

    @property
    def project_id(self):
        return self._catmaid.project_id

    @wraps(CatmaidClient.get)
    def get(self, *args, **kwargs):
        return self._catmaid.get(*args, **kwargs)

    @wraps(CatmaidClient.post)
    def post(self, *args, **kwargs):
        return self._catmaid.post(*args, **kwargs)

    @wraps(CatmaidClient.fetch)
    def fetch(self, *args, **kwargs):
        return self._catmaid.fetch(*args, **kwargs)


class CoordinateTransformer(object):
    def __init__(self, resolution=None, translation=None):
        """
        Helper class for transforming between stack and project coordinates.

        Parameters
        ----------
        resolution : dict
            x, y and z resolution of the stack
        translation : dict
            x, y and z the location of the stack's origin (0, 0, 0) in project space
        """
        if resolution is None:
            resolution = dict()
        if translation is None:
            translation = dict()

        self.resolution = {dim: resolution.get(dim, 1) for dim in 'xyz'}
        self.translation = {dim: translation.get(dim, 0) for dim in 'xyz'}

        self._resolution_arrays = dict()
        self._translation_arrays = dict()

    @classmethod
    def from_catmaid(cls, catmaid_client, stack_id):
        """
        Return a CoordinateTransformer for a particular CATMAID stack.

        Parameters
        ----------
        catmaid_client : CatmaidClient
            Authenticated instance of CatmaidClient
        stack_id : int

        Returns
        -------
        CoordinateTransformer
        """
        stack_info = catmaid_client.get((catmaid_client.project_id, 'stack', stack_id, 'info'))
        return cls(stack_info['resolution'], stack_info['translation'])

    def _get_resolution_array(self, dims):
        if dims not in self._resolution_arrays:
            self._resolution_arrays[dims] = np.array([self.resolution[dim] for dim in dims])
        return self._resolution_arrays[dims]

    def _get_translation_array(self, dims):
        if dims not in self._resolution_arrays:
            self._translation_arrays[dims] = np.array([self.translation[dim] for dim in dims])
        return self._translation_arrays[dims]

    def project_to_stack_coord(self, dim, project_coord):
        return (project_coord - self.translation[dim]) / self.resolution[dim]

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
        return {dim: self.project_to_stack_coord(dim, proj_coord) for dim, proj_coord in project_coords.items()}

    def project_to_stack_array(self, arr, dims='xyz'):
        """
        Take an array of points in project space and transform them into stack space.

        Parameters
        ----------
        arr : array-like
            M by N array containing M coordinates in project / real space in N dimensions
        dims : str
            Order of dimensions in columns, default 'xyz'

        Returns
        -------
        np.ndarray
            M by N array containing M coordinates in stack / voxel space in N dimensions
        """
        arr = np.array(arr)
        resolution_arr = self._get_resolution_array(dims)
        translation_arr = self._get_translation_array(dims)

        return (arr - translation_arr) / resolution_arr

    def stack_to_project_coord(self, dim, stack_coord):
        return stack_coord * self.resolution[dim] + self.translation[dim]

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
        return {dim: self.stack_to_project_coord(dim, stack_coord) for dim, stack_coord in stack_coords.items()}

    def stack_to_project_array(self, arr, dims='xyz'):
        """
        Take an array of points in stack space and transform them into project space.

        Parameters
        ----------
        arr : array-like
            M by N array containing M coordinates in stack / voxel space in N dimensions
        dims : array-like or str
            Order of dimensions in columns, default (x, y, z)

        Returns
        -------
        np.ndarray
            M by N array containing M coordinates in project / real space in N dimensions
        """
        arr = np.array(arr)
        resolution_arr = self._get_resolution_array(dims)
        translation_arr = self._get_translation_array(dims)

        return arr * resolution_arr + translation_arr
