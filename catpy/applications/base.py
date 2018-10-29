from abc import ABCMeta
from functools import wraps

from six import add_metaclass

from catpy.client import CatmaidClient, AbstractCatmaidClient


@add_metaclass(ABCMeta)
class CatmaidClientApplication(AbstractCatmaidClient):
    """
    An application which uses the CATMAID interface. Users should subclass this when creating their own applications.
    """

    def __init__(self, catmaid_client):
        """

        Parameters
        ----------
        catmaid_client : CatmaidClient
        """
        self._catmaid = catmaid_client

    @property
    def base_url(self):
        return self._catmaid.base_url

    @property
    def project_id(self):
        return self._catmaid.project_id

    @wraps(CatmaidClient.fetch)
    def fetch(self, *args, **kwargs):
        return self._catmaid.fetch(*args, **kwargs)

    @classmethod
    def from_json(cls, credentials, *args, **kwargs):
        """
        Return a CatmaidClientApplication instance whose underlying CatmaidClient object is instantiated from the JSON
        file as per its own from_json method.

        Parameters
        ----------
        path : str
            Path to the JSON credentials file
        args, kwargs
            Arguments passed to constructor of concrete subclass

        Returns
        -------
        CatmaidClient
            Instance of the API, authenticated with
        """
        return cls(CatmaidClient.from_json(credentials), *args, **kwargs)
