# -*- coding: utf-8 -*-

from warnings import warn
from copy import deepcopy

import networkx as nx
from networkx.readwrite import json_graph

from catpy.applications.base import CatmaidClientApplication
from catpy.client import ConnectorRelation


NX_VERSION_INFO = tuple(int(i) for i in nx.__version__.split('.'))


err_msg = (
    "Tried to treat the edge's source/target fields as indices into the list of nodes, but failed. "
    "See issue #26 [1]. "
    "Has CATMAID upgraded to networkx 2.x? [2]\n\n"
    "[1]: https://github.com/catmaid/catpy/issues/26\n"
    "[2]: https://github.com/catmaid/CATMAID/blob/master/django/requirements.txt"
)


def convert_nodelink_data(jso):
    """NetworkX serialises graphs differently in v1.x and v2.x.

    This converts v1-style data (as emitted by CATMAID) to v2-style data.

    See issue #26 https://github.com/catmaid/catpy/issues/26

    Parameters
    ----------
    jso : dict

    Returns
    -------
    dict
    """
    if NX_VERSION_INFO < (2, 0):
        warn(
            "You are converting networkx v1-style JSON (emitted by CATMAID) to v2-style JSON,"
            " but you are using networkx v1"
        )

    out = deepcopy(jso)
    for edge in out["links"]:
        for label in ["source", "target"]:
            try:
                edge[label] = out["nodes"][edge[label]]["id"]
            except (KeyError, IndexError):
                raise RuntimeError(err_msg)
    return out


class ExportWidget(CatmaidClientApplication):

    def get_swc(self, skeleton_id, linearize_ids=False):
        """
        Get a single skeleton in SWC format.

        Parameters
        ----------
        skeleton_id : int or str
        linearize_ids : bool

        Returns
        -------
        str
        """
        return self.get(
            (self.project_id, "skeleton", skeleton_id, "swc"),
            {"linearize_ids": "true" if linearize_ids else "false"},
        )

    def get_connector_archive(self, *args, **kwargs):
        """Not implemented: requires an async job"""
        raise NotImplementedError("Requires an async job")

    def get_treenode_archive(self, *args, **kwargs):
        """Not implemented: requires an async job"""
        raise NotImplementedError("Requires an async job")

    def get_networkx_dict(self, *skeleton_ids):
        """
        Get the data for a networkx graph of the given skeletons in node-link format.

        In networkx 1.x, as used by CATMAID and therefore returned by this method,
        "source" and "target" in the dicts in "links" refer to nodes by their indices in the "nodes" array.

        See ``convert_nodelink_data`` function to convert into networkx 2.x-compatible format.

        https://networkx.readthedocs.io/en/networkx-1.11/reference/generated/networkx.readwrite.json_graph.node_link_data.html

        Parameters
        ----------
        skeleton_ids : array-like of (int or str)

        Returns
        -------
        dict
        """
        return self.post(
            (self.project_id, "graphexport", "json"),
            data={"skeleton_list": list(skeleton_ids)},
        )

    def get_networkx(self, *skeleton_ids):
        """
        Get a networkx MultiDiGraph of the given skeletons.

        Parameters
        ----------
        skeleton_ids : array-like of (int or str)

        Returns
        -------
        networkx.MultiDiGraph
        """
        data = self.get_networkx_dict(*skeleton_ids)
        if NX_VERSION_INFO >= (2, 0):
            data = convert_nodelink_data(data)
        return json_graph.node_link_graph(data, directed=True)

    def get_neuroml(self, skeleton_ids, skeleton_inputs=tuple()):
        """
        Get NeuroML v1.8.1 (level 3, NetworkML) for the given skeletons, possibly with their input synapses
        constrained to another set of skeletons.

        N.B. If len(skeleton_ids) > 1, skeleton_inputs will be ignored and only synapses within the first skeleton
         set will be used in the model.

        Parameters
        ----------
        skeleton_ids : array-like
            Skeletons whose NeuroML to return
        skeleton_inputs : array-like, optional
            If specified, only input synapses from these skeletons will be added to the NeuroML

        Returns
        -------
        str
            NeuroML output string
        """

        data = {"skids": list(skeleton_ids)}

        if skeleton_inputs:
            if len(skeleton_ids) > 1:
                warn(
                    "More than one skeleton ID was selected: ignoring skeleton input constraints"
                )
            else:
                data["inputs"] = list(skeleton_inputs)

        return self.post((self.project_id, "neuroml", "neuroml_level3_v181"), data=data)

    def get_treenode_and_connector_geometry(self, *skeleton_ids):
        """
        Get the treenode and connector information for the given skeletons. The returned dictionary will be of the form

        {
            "skeletons": {
                skeleton_id1: {
                    "treenodes": {
                        treenode_id1: {
                            "location": [x, y, z],
                            "parent_id": id_of_parent_treenode
                        },
                        treenode_id2: ...
                    },
                    "connectors": {
                        connector_id1: {
                            "location": [x, y, z],
                            "presynaptic_to": [list, of, treenode, ids],
                            "postsynaptic_to": [list, of, treenode, ids]
                        },
                        connector_id2: ...
                    }
                },
                skeleton_id2: ...
            }
        }

        Parameters
        ----------
        skeleton_ids : array-like of (int or str)

        Returns
        -------
        dict
        """

        skeletons = dict()
        warnings = set()

        for skeleton_id in skeleton_ids:

            data = self.get(
                "{}/{}/1/0/compact-skeleton".format(self.project_id, skeleton_id)
            )

            skeleton = {"treenodes": dict(), "connectors": dict()}

            for treenode in data[0]:
                skeleton["treenodes"][int(treenode[0])] = {
                    "location": treenode[3:6],
                    "parent_id": None if treenode[1] is None else int(treenode[1]),
                }

            for connector in data[1]:
                try:
                    relation = ConnectorRelation(connector[2])
                except ValueError as e:
                    msg = str(e)
                    if " is not a valid " in msg:
                        warnings.add(str(e))
                        continue
                    else:
                        raise e

                if not relation.is_synaptic:
                    continue

                conn_id = int(connector[1])
                if conn_id not in skeleton["connectors"]:
                    skeleton["connectors"][conn_id] = {
                        str(r): [] for r in ConnectorRelation if r.is_synaptic
                    }

                skeleton["connectors"][conn_id]["location"] = connector[3:6]
                relation_name = str(relation)
                skeleton["connectors"][conn_id][relation_name].append(connector[0])

            skeletons[int(skeleton_id)] = skeleton

        warn(
            "Skeleton representations contained some unknown treenode->connector relation IDs:\n\t"
            "\n\t".join(sorted(warnings))
        )

        return {"skeletons": skeletons}
