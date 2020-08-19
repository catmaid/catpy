"""Module which collects exceptions defined elsewhere, for convenient access"""
import textwrap

import requests


class NameResolverException(ValueError):
    pass


class NoMatchingNamesException(NameResolverException):
    pass


class MultipleMatchingNamesException(NameResolverException):
    pass


__all__ = ["WrappedCatmaidException"]


class WrappedCatmaidException(requests.HTTPError):
    spacer = "    "

    def __init__(self, response, error_data=None):
        """
        Exception wrapping a django error which results in a JSON response being returned containing information
        about that error.

        Parameters
        ----------
        response : requests.Response
            Response containing JSON-formatted error from Django
        """
        super(WrappedCatmaidException, self).__init__(
            "Received HTTP{} from {}".format(response.status_code, response.url),
            response=response,
        )
        if error_data is None:
            error_data = response.json()

        self.error = error_data["error"]
        self.detail = error_data["detail"]
        self.type = error_data["type"]

        self.meta = error_data.get("meta")
        self.info = error_data.get("info")
        self.traceback = error_data.get("traceback")

    def format_detail(self, indent=""):
        return textwrap.indent("Response contained:\n" + self.detail.rstrip(), indent)

    def __str__(self):
        return (
            super(WrappedCatmaidException, self).__str__()
            + "\n"
            + self.format_detail(self.spacer)
        )

    @classmethod
    def raise_for_status(cls, response):
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            if response.headers.get("content-type") == "application/json":
                try:
                    wrapped = cls(response)
                    raise wrapped from e
                except KeyError:
                    pass
            raise e
