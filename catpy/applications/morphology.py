import logging
from typing import NamedTuple, List, Dict

import numpy as np
import pandas as pd

from .nameresolver import NameResolver
from .base import CatmaidClientApplication
from ..spatial import CoordinateTransformer

logger = logging.getLogger(__name__)


def lol_to_df(data, columns, dtypes=None):
    if not dtypes:
        return pd.DataFrame(data, columns=columns)

    col_data = {s: [] for s in columns}
    for row in data:
        for col, item in zip(columns, row):
            col_data[col].append(item)

    try:
        col_dtype = zip(columns, dtypes)
    except TypeError:
        col_dtype = zip(columns, (dtypes for _ in columns))

    col_data = {col: pd.array(col_data[col], dtype=dtype) for col, dtype in col_dtype}
    df = pd.DataFrame(col_data)
    return df[columns]  # < py36, dict ordering


def interpolate_node_locations(parent_xyz, child_xyz, z_res=1, z_offset=0):
    parent_child = np.array([parent_xyz, child_xyz])
    z_slices = np.round((parent_child[:, 2] - z_offset) / z_res).astype(int)

    n_slices_between = abs(np.diff(z_slices)[0]) - 1

    if n_slices_between < 1:
        return

    parent_child[:, 2] = (z_slices * z_res + z_offset).astype(float)

    new_xyz = zip(
        np.linspace(*parent_child[:, 0], num=n_slices_between + 2),
        np.linspace(*parent_child[:, 1], num=n_slices_between + 2),
        np.linspace(*parent_child[:, 2], num=n_slices_between + 2),
    )
    next(new_xyz)  # discard, it's the parent location
    for _ in range(n_slices_between):
        yield next(new_xyz)
    assert next(new_xyz)


def in_roi(roi_xyz, coords_xyz):
    """Closed interval: use intersection_roi"""
    x, y, z = coords_xyz
    return all(
        [
            roi_xyz[0, 0] <= x <= roi_xyz[1, 0],
            roi_xyz[0, 1] <= y <= roi_xyz[1, 1],
            roi_xyz[0, 2] <= z <= roi_xyz[1, 2],
        ]
    )


class SkeletonCompactDetail(NamedTuple):
    id: int
    treenodes: pd.DataFrame
    connectors: pd.DataFrame
    tags: Dict[int, List[str]]

    @classmethod
    def from_response(cls, skid, response):
        node_data = lol_to_df(
            response[0],
            ["id", "parent", "user", "x", "y", "z", "radius", "confidence"],
            [
                np.uint64,
                pd.UInt64Dtype(),
                np.uint64,
                np.float64,
                np.float64,
                np.float64,
                np.float64,
                np.uint8,
            ],
        )
        conn_data = lol_to_df(
            response[1],
            ["treenode", "connector", "relation", "x", "y", "z"],
            [np.uint64, np.uint64, np.int8, np.float64, np.float64, np.float64],
        )
        return SkeletonCompactDetail(int(skid), node_data, conn_data, response[2])


class MorphologyFetcher(CatmaidClientApplication):
    def __init__(self, catmaid_client, stack_id_or_title=None):
        super(MorphologyFetcher, self).__init__(catmaid_client)
        self.name_resolver = NameResolver(catmaid_client)
        self.stack_id = self._get_stack_id(stack_id_or_title)

    def _get_stack_id(self, stack_id_or_title):
        try:
            return int(stack_id_or_title)
        except TypeError:
            if stack_id_or_title is None:
                return None
            return self.name_resolver.get_stack_id(stack_id_or_title)

    def get_stack_info(self, stack_id=None):
        if stack_id is None:
            if self.stack_id is not None:
                stack_id = self.stack_id
            else:
                raise ValueError("Stack ID/title not given")
        else:
            stack_id = self._get_stack_id(stack_id)
        return self.get((self.project_id, "stack", stack_id, "info"))

    def get_coord_transformer(self, stack_id=None):
        if stack_id is None:
            return CoordinateTransformer()
        else:
            stack_id = self._get_stack_id(stack_id)
            return CoordinateTransformer.from_catmaid(self._catmaid, stack_id)

    def get_compact_skeleton_detail(self, skeleton_id, connectors=False, tags=False):
        logger.debug("Getting compact-detail for skeleton %s", skeleton_id)
        params = dict()
        if connectors:
            params["with_connectors"] = "true"
        if tags:
            params["with_tags"] = "true"
        response = self.get(
            (self.project_id, "skeletons", skeleton_id, "compact-detail"), params=params
        )
        return SkeletonCompactDetail.from_response(int(skeleton_id), response)

    def get_compact_skeletons_detail(self, skeleton_ids, connectors=False, tags=False):
        logger.debug("Getting compact-detail for %s skeletons", len(skeleton_ids))
        params = {"skeleton_ids": list(skeleton_ids)}
        if connectors:
            params["with_connectors"] = "true"
        if tags:
            params["with_tags"] = "true"
        responses = self.post(
            (self.project_id, "skeletons", "compact-detail"), data=params
        )
        for skid_str, response in responses["skeletons"].items():
            yield SkeletonCompactDetail.from_response(int(skid_str), response)

    # todo: decide what to do with these
    # def get_nodes_in_roi(self, roi_xyz, stack_id=None):
    #     """
    #     Get the nodes in the ROI with their coordinates relative to the top-left corner of the ROI.
    #
    #     Parameters
    #     ----------
    #     roi_xyz : np.array
    #         [[xmin, ymin, zmin],[xmax, ymax, zmax]] in stack space
    #     stack_id : if None, coordinates will be returned in project space. If True, use the object's stored stack_id.
    #
    #     Returns
    #     -------
    #
    #     """
    #     if stack_id is True:
    #         stack_id = self.stack_id
    #     transformer = self.get_coord_transformer(stack_id)
    #     # convert a half-closed [xyz, xyz) ROI for slice indexing into closed [xyz, xyz] for geometric intersection
    #     intersection_roi = roi_xyz - np.array([[0, 0, 0], [1, 1, 1]])
    #     roi_xyz_p = transformer.stack_to_project_array(intersection_roi)
    #     data = {
    #         'left': roi_xyz_p[0, 0],
    #         'top': roi_xyz_p[0, 1],
    #         'z1': roi_xyz_p[0, 2],
    #         'right': roi_xyz_p[1, 0],
    #         'bottom': roi_xyz_p[1, 1],
    #         'z2': roi_xyz_p[1, 2]
    #     }
    #     response = self.post((self.project_id, '/node/list'), data)
    #     treenodes = dict()
    #     for treenode_row in response[0]:
    #         tnid, _, x, y, z, _, _, skid, _, _ = treenode_row
    #         if not in_roi(roi_xyz_p, [x, y, z]):
    #             # API returns treenodes which are out of ROI if they have an edge which passes through the ROI
    #             continue
    #
    #         treenodes[tnid] = {
    #             'coords': {
    #                 'x': int(transformer.project_to_stack_coord('x', x)[1] - roi_xyz[0, 0]),
    #                 'y': int(transformer.project_to_stack_coord('y', y)[1] - roi_xyz[0, 1]),
    #                 'z': int(transformer.project_to_stack_coord('z', z)[1] - roi_xyz[0, 2])
    #             },
    #             'skeleton_id': skid,
    #             'treenode_id': tnid
    #         }
    #
    #     return treenodes
    #
    # def _realise_treenodes(self, *skeleton_ids, stack_id=None):
    #     stack_info = self.get_stack_info(stack_id)
    #     z_depth = stack_info["resolution"]["z"]
    #     geometry_data = self.export_widget.get_treenode_and_connector_geometry(*skeleton_ids)
    #
    #     created_treenodes = []
    #
    #     for skid, skel_data in geometry_data['skeletons'].items():
    #         for child_id, child_data in skel_data["treenodes"].items():
    #             parent_id = child_data["parent_id"]
    #             if parent_id in (-1, None):
    #                 continue
    #
    #             parent_data = skel_data["treenodes"][parent_id]
    #
    #             for x, y, z in interpolate_node_locations(parent_data["location"], child_data["location"], z_depth):
    #                 post_data = {
    #                     'x': x,
    #                     'y': y,
    #                     'z': z,
    #                     'confidence': 4,
    #                     'parent_id': int(parent_id),
    #                     'child_id': child_id,
    #                     'state': '{"nocheck": true}'
    #                 }
    #                 response = self.post((self.project_id, "treenode", "insert"), post_data)
    #                 created_treenodes.append(response)
    #                 parent_id = response["treenode_id"]
    #
    #     return created_treenodes
