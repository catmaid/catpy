from __future__ import unicode_literals
from six import string_types

try:
    from functools import lru_cache
except ImportError:
    from backports.functools_lru_cache import lru_cache

from catpy.applications.base import CatmaidClientApplication


def name_to_id(fn):

    def wrapper(instance, id_or_name, *args, **kwargs):
        if isinstance(id_or_name, int):
            return id_or_name
        elif isinstance(id_or_name, string_types):
            return fn(instance, id_or_name, *args, **kwargs)
        else:
            raise TypeError("Argument was neither integer ID nor string name")

    return wrapper


class NameResolverException(ValueError):
    pass


class NoMatchingNamesException(NameResolverException):
    pass


class MultipleMatchingNamesException(NameResolverException):
    pass


class NameResolver(CatmaidClientApplication):
    """Catmaid client application which looks up integer database IDs for string names for various objects.

    For convenience, lookup methods short-circuit if given an int (i.e. you can transparently use either
    the ID or the name of an object).

    HTTP responses are cached where possible, so there may be a performance benefit to sharing NameResolver instances.
    Furthermore, subsequent lookups of IDs of the same object type (e.g. stack, user)
    should be much faster than the first.

    Lookup methods ensure that one object matches the given name/title for the given project,
    raising a NoMatchingNamesException if there are zero matches,
    and a MultipleMatchingNamesException if there are more than one,
    both of which subclass NameResolverException, which subclasses ValueError.
    """

    def _ensure_one(self, match_set, name, obj):
        if len(match_set) == 0:
            raise NoMatchingNamesException(
                "Zero {} objects found with name {} in project {}".format(
                    obj, repr(name), self.project_id
                )
            )
        elif len(match_set) == 1:
            return match_set.pop()
        else:
            raise MultipleMatchingNamesException(
                "Multiple {} objects ({}) found with name {} in project {}".format(
                    obj,
                    ", ".join(str(i) for i in sorted(match_set)),
                    name,
                    self.project_id,
                )
            )

    @lru_cache(1)
    def _get_stacks(self):
        return self.get((self.project_id, "stacks"))

    @name_to_id
    def get_stack_id(self, title):
        """Get the ID of the stack with the given title.

        Parameters
        ----------
        title : str or int
            Stack title

        Returns
        -------
        int
        """
        matching_ids = set()
        for stack in self._get_stacks():
            if stack["title"] == title:
                matching_ids.add(stack["id"])

        return self._ensure_one(matching_ids, title, "stack")

    @lru_cache(1)
    def _get_user_list(self):
        return self.get("user-list")

    @name_to_id
    def get_user_id(self, name):
        """Get the ID of the user with the given login or full name

        Parameters
        ----------
        name : str or int

        Returns
        -------
        int
        """
        matching_ids = set()
        for user in self._get_user_list():
            if name in [user["login"], user["full_name"]]:
                matching_ids.add(user["id"])

        return self._ensure_one(matching_ids, name, "user")
