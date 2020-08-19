from __future__ import absolute_import

from collections import defaultdict

from ..enums import ConnectorRelation
from .base import CatmaidClientApplication


class RelationIdentifier(CatmaidClientApplication):
    """Class to convert connector relation IDs to ConnectorRelation enums and back.

    The mappings are cached on the class, and so do not need to be re-fetched for new instances.

    The mappings are retrieved on a per-project basis.
    """

    id_to_relation = defaultdict(dict)
    relation_to_id = defaultdict(dict)

    def _check_pid(self):
        if self.project_id is None:
            raise RuntimeError(
                "No project ID defined; cannot get relation name-id mappings"
            )
        else:
            return self.project_id

    def _fetch_mappings(self, project_id):
        return self.get((project_id, "connectors", "types"))

    def populate_mappings(self, project_id):
        """Populate the id-relation mappings cache for the given project"""
        if isinstance(self, type):
            raise ValueError("Cannot populate relation ID mappings as a class method")

        project_id = int(project_id)

        id_to_rel = dict()
        rel_to_id = dict()
        types_response = self._fetch_mappings(project_id)
        for obj in types_response:
            rel = ConnectorRelation[obj["relation"]]
            rel_id = obj["relation_id"]

            id_to_rel[rel_id] = rel
            rel_to_id[rel] = rel_id

        type(self).id_to_relation[project_id] = id_to_rel
        type(self).relation_to_id[project_id] = rel_to_id

    def _get_dict(self, is_relation, project_id):
        project_id = int(project_id or self._check_pid())
        d = (self.id_to_relation, self.relation_to_id)[is_relation]
        if project_id not in d:
            self.populate_mappings(project_id)
        return d[project_id]

    def from_id(self, relation_id, project_id=None):
        """
        Return the ConnectorRelation for the given relation ID.
        If ``project_id`` is given and you know this project's mappings are already populated
        (possibly via a different instance),
        this can be used as a class method.

        Parameters
        ----------
        relation_id
        project_id

        Returns
        -------
        ConnectorRelation
        """
        if relation_id == -1:
            return ConnectorRelation.other
        return self._get_dict(False, project_id)[relation_id]

    def to_id(self, relation, project_id=None):
        """
        Return the integer ID for the given ConnectorRelation.
        If ``project_id`` is given and you know this project's mappings are already populated,
        (possibly via a different instance
        this can be used as a class method.

        Parameters
        ----------
        relation
        project_id

        Returns
        -------
        int
        """
        if relation == ConnectorRelation.other:
            return -1
        return self._get_dict(True, project_id)[relation]
