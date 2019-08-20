from __future__ import unicode_literals, absolute_import
from six import string_types
import logging

try:
    from functools import lru_cache
except ImportError:
    from backports.functools_lru_cache import lru_cache

from catpy.applications.base import CatmaidClientApplication


logger = logging.getLogger(__name__)


def name_to_id(fn):

    def wrapper(instance, id_or_name, *args, **kwargs):
        if isinstance(id_or_name, int):
            return id_or_name
        elif isinstance(id_or_name, string_types):
            return fn(instance, id_or_name, *args, **kwargs)
        else:
            raise TypeError("Argument was neither integer ID nor string name")

    return wrapper


def id_to_name(fn):

    def wrapper(instance, id_or_name, *args, **kwargs):
        if isinstance(id_or_name, string_types):
            return id_or_name
        elif isinstance(id_or_name, int):
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


class NameIdMapping:
    def __init__(self, name_id_pairs):
        self.name_to_id = dict()
        self.id_to_name = dict()

        counter = 0
        for name, id_ in name_id_pairs:
            id_ = int(id_)
            self.name_to_id[name] = id_
            self.id_to_name[id_] = name
            counter += 1

        if counter != len(self.name_to_id) or counter != len(self.id_to_name):
            raise ValueError("Non-unique names or IDs; cannot make 2-way mapping")


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
    def _stacks(self):
        logger.debug("Populating _stacks cache")
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
        for stack in self._stacks():
            if stack["title"] == title:
                matching_ids.add(stack["id"])

        return self._ensure_one(matching_ids, title, "stack")

    @lru_cache(1)
    def _user_list(self):
        logger.debug("Populating _user_list cache")
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
        for user in self._user_list():
            if name in [user["login"], user["full_name"]]:
                matching_ids.add(user["id"])

        return self._ensure_one(matching_ids, name, "user")

    def get_neuron_names(self, *skeleton_ids):
        """Get a dict of skeleton IDs to neuron names.

        Parameters
        ----------
        skeleton_ids

        Returns
        -------
        dict of int to str
        """
        # todo: lru cache
        return self.post((self.project_id, "skeleton", "neuronnames"), {"skids": skeleton_ids})

    @id_to_name
    def get_neuron_name(self, skeleton_id):
        """Get the neuron name associated with the given skeleton ID.

        Utilises an LRU cache and can handle being given the name (just returns the name),
        so useful for ensuring that a given argument resolves to a name either way.

        Parameters
        ----------
        skeleton_id

        Returns
        -------
        str
        """
        return self.get((self.project_id, "skeleton", skeleton_id, "neuronname"))["neuronname"]

    @lru_cache(1)
    def _list_annotations(self):
        logger.debug("Populating _list_annotations cache")
        response = self.get((self.project_id, "annotations"))
        return NameIdMapping(
            (obj["name"], obj["id"]) for obj in response["annotations"]
        )

    @name_to_id
    def get_annotation_id(self, annotation_name):
        return self._list_annotations().name_to_id[annotation_name]

    @id_to_name
    def get_annotation_name(self, annotation_id):
        return self._list_annotations().id_to_name[int(annotation_id)]

    def clear_cache(self, *names):
        if not names:
            names = [k for k, v in self.__dict__.items() if hasattr(v, "cache_clear")]

        for name in names:
            getattr(self, name).cache_clear()
