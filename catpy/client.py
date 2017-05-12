# -*- coding: utf-8 -*-


import json

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

    def __init__(self, base_url, token, auth_name=None, auth_pass=None, project_id=None):
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

        self.session = requests.Session()
        self.session.auth = self.CatmaidAuthToken(token, auth_name, auth_pass)

        self.project_id = project_id

    class CatmaidAuthToken(requests.auth.HTTPBasicAuth):
        def __init__(self, token, auth_name=None, auth_pass=None):
            self.token = token
            super(CatmaidClient.CatmaidAuthToken, self).__init__(auth_name, auth_pass)

        def __call__(self, r):
            r.headers['X-Authorization'] = 'Token {}'.format(self.token)
            return super(CatmaidClient.CatmaidAuthToken, self).__call__(r)

    def _make_request_url(self, *args):
        return make_url(self.base_url, *args)

    @classmethod
    def from_json(cls, path, with_project_id=True):
        """
        Return a CatmaidClient instance with credentials matching those in a JSON file. Should have the properties:

        base_url, token, auth_name, auth_pass

        And optionally

        project_id

        Parameters
        ----------
        path : str
            Path to the JSON credentials file
        with_project_id : bool
            Whether to look for the `project_id` field (it can be set later on the returned CatmaidClient instance)

        Returns
        -------
        CatmaidClient
            Authenticated instance of the API
        """
        with open(path) as f:
            credentials = json.load(f)
        return cls(
            credentials['base_url'],
            credentials['token'],
            credentials['auth_name'],
            credentials['auth_pass'],
            credentials.get('project_id', None) if with_project_id else None
        )

    def get(self, *relative_url, params=None, raw=False):
        """
        Get data from a running instance of CATMAID.

        Parameters
        ----------
        relative_url
            URL to send the request to, relative to the base_url. *args will be joined with '/'
        params: dict or str, optional
            JSON-like key/value data to be included in the get URL (defaults to empty)
        raw: bool, optional
            Whether to return the response as a string (defaults to returning a dict)

        Returns
        -------
        dict or str
            Data returned from CATMAID: type depends on the 'raw' parameter.
        """
        return self.fetch(*relative_url, method='GET', data=params, raw=raw)

    def post(self, *relative_url, data=None, raw=False):
        """
        Post data to a running instance of CATMAID. 

        Parameters
        ----------
        relative_url
            URL to send the request to, relative to the base_url. *args will be joined with '/'
        data: dict or str, optional
            JSON-like key/value data to be included in the request as a payload (defaults to empty)
        raw: bool, optional
            Whether to return the response as a string (defaults to returning a dict)

        Returns
        -------
        dict or str
            Data returned from CATMAID: type depends on the 'raw' parameter.
        """
        return self.fetch(*relative_url, method='POST', data=data, raw=raw)

    def fetch(self, *relative_url, method='GET', data=None, raw=False):
        """
        Interact with the CATMAID server in a manner very similar to the javascript CATMAID.fetch API.

        Parameters
        ----------
        relative_url
            URL to send the request to, relative to the base_url. *args will be joined with '/'
        method: {'GET', 'POST'}, optional
            HTTP method to use (the default is 'GET')
        data: dict or str, optional
            JSON-like key/value data to be included in the request as a payload (defaults to empty)
        raw: bool, optional
            Whether to return the response as a string (defaults to returning a dict)

        Returns
        -------
        dict or str
            Data returned from CATMAID: type depends on the 'raw' parameter.
        """
        url = self._make_request_url(*relative_url)
        data = data or dict()
        if method.upper() == 'GET':
            response = self.session.get(url, params=data)
        elif method.upper() == 'POST':
            response = self.session.post(url, data=data)
        else:
            raise ValueError('Unknown HTTP method {}'.format(repr(method)))

        return response.json() if not raw else response.text


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
        stack_info = catmaid_client.get(catmaid_client.project_id, 'stack', stack_id, 'info')
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
            x, y, and/or z coordinates in project/ real space

        Returns
        -------
        dict
            coordinates transformed into stack/voxel space
        """
        return {dim: self.project_to_stack_coord(dim, proj_coord) for dim, proj_coord in project_coords.items()}

    def project_to_stack_array(self, arr, dims='xyz'):
        """
        Take an array of points in project space and transform them into stack space.

        Parameters
        ----------
        arr : array-like
            M by N array containing M coordinates in project space in N dimensions
        dims : str
            Order of dimensions in columns, default 'xyz'

        Returns
        -------
        np.ndarray
            M by N array containing M coordinates in stack space in N dimensions
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
            x, y, and/or z coordinates in stack/ voxel space

        Returns
        -------
        dict
            coordinates transformed into project/ real space
        """
        return {dim: self.stack_to_project_coord(dim, stack_coord) for dim, stack_coord in stack_coords.items()}

    def stack_to_project_array(self, arr, dims='xyz'):
        """
        Take an array of points in stack space and transform them into project space.

        Parameters
        ----------
        arr : array-like
            M by N array containing M coordinates in stack space in N dimensions
        dims : array-like or str
            Order of dimensions in columns, default (x, y, z)

        Returns
        -------
        np.ndarray
            M by N array containing M coordinates in project space in N dimensions
        """
        arr = np.array(arr)
        resolution_arr = self._get_resolution_array(dims)
        translation_arr = self._get_translation_array(dims)

        return arr * resolution_arr + translation_arr
