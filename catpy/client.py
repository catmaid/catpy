# -*- coding: utf-8 -*-

from __future__ import division, unicode_literals, absolute_import

import json
from abc import abstractmethod, ABC

import requests

from catpy.exceptions import WrappedCatmaidException


class AbstractCatmaidClient(ABC):
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
        return self.fetch(relative_url, method="GET", data=params, raw=raw, **kwargs)

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
        return self.fetch(relative_url, method="POST", data=data, raw=raw, **kwargs)

    @abstractmethod
    def fetch(self, relative_url, method="GET", data=None, raw=False, **kwargs):
        pass


class CatmaidClient(AbstractCatmaidClient):
    """
    Python object handling authentication, request pooling etc. for requests made to a CATMAID server.

    Users creating their own interface should not subclass this, but instead subclass CatmaidClientApplication, which
    wraps a CatmaidClient object. This composition approach eases testing and sharing CatmaidClient instances among
    different interfaces.
    """

    def __init__(
        self, base_url, token=None, auth_name=None, auth_pass=None, project_id=None
    ):
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
        self._session.headers["X-Authorization"] = "Token " + token
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
        if isinstance(arg, str):
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
            credentials["base_url"],
            credentials.get("token"),
            credentials.get("auth_name"),
            credentials.get("auth_pass"),
            credentials.get("project_id"),
        )

    def fetch(self, relative_url, method="GET", data=None, raw=False, **kwargs):
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
        if method.upper() == "GET":
            response = self._session.get(url, params=data, **kwargs)
        elif method.upper() == "POST":
            response = self._session.post(url, data=data, **kwargs)
        else:
            raise ValueError("Unknown HTTP method {}".format(repr(method)))

        WrappedCatmaidException.raise_for_status(response)
        if response.headers["content-type"] == "application/json" and not raw:
            return response.json()
        else:
            return response.text


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
        joiner = "" if base_url.endswith("/") else "/"
        relative = arg_str[1:] if arg_str.startswith("/") else arg_str
        base_url = requests.compat.urljoin(base_url + joiner, relative)

    return base_url
